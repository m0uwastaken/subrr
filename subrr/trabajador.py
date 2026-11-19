"""El trabajador: recorre lo elegido y traduce lo que falte.

Para cada episodio: si no tiene ya subtítulos en el idioma de destino, elige la mejor pista de texto de origen,
la traduce con la cadena de motores y la guarda (aparte, dentro del mkv o entregada a Bazarr).
"""
import datetime, os, re, threading, time, traceback

from . import config as C
from . import motores as M
from . import ocr as O
from . import salida as SA
from . import subs as S
from .servicios import avisar, bazarr, episodios

FINALES = {'hecho', 'ya', 'audio', 'sin_origen', 'solo_imagen', 'quitado'}
TEXTO_R = {'hecho': 'Traducido', 'ya': 'Ya tenía subtítulos', 'audio': 'El audio ya está en el idioma', 'sin_origen': 'Sin subtítulos que traducir',
           'solo_imagen': 'Solo subtítulos de imagen', 'error': 'Error', 'quitado': 'Quitado'}
WANTED = {}          # k → {epid,...} de lo que Bazarr echa de menos (modo Bazarr)


def destino_de(aj):
    return C.DESTINOS.get(aj['destino']) or C.DESTINOS['es']


def elegido(it, e, est=None):
    if it.get('modo') == 'bazarr':
        k = f"{'sonarr' if it['tipo'] == 'serie' else 'radarr'}:{it['id']}"
        if it['tipo'] == 'pelicula':
            return k in WANTED or bool(e['path'] and (est or {}).get(e['path']))
        return e['epid'] in WANTED.get(k, set()) or bool(e['path'] and (est or {}).get(e['path']))
    return it['tipo'] == 'pelicula' or e['temporada'] in it.get('temporadas', [])


def nombre_ep(it, clave):
    return f"{it['titulo']} {clave if clave != 'pelicula' else ''}".strip()


def ruta_origen(it, clave):
    return os.path.join(C.ORIGEN, C.seguro(it['titulo']), f'{clave}.srt')


def pista_id(p):
    return f"dentro:{p['indice']}" if p['donde'] == 'dentro' else 'fuera:' + os.path.basename(p['ruta'])


def mostrar_pistas(video, v):
    """Pistas del vídeo, quitando lo que puso subrr."""
    subs, audio = S.sondear(video)
    nuestro = v.get('srt') if v and SA.es_nuestro_aparte(v.get('srt') or '', v) else None
    subs += [p for p in S.externos(video) if p.get('ruta') != nuestro]
    return subs, audio


def pendiente(it, e, aj, v):
    """¿Hay que hacer algo con este episodio en una pasada normal?"""
    if not e['path'] or not os.path.exists(e['path']):
        return False
    if not v:
        if it.get('modo') == 'bazarr' and aj['bazarr_dias'] and e.get('anadido'):
            try:
                t = datetime.datetime.fromisoformat(e['anadido'].replace('Z', '+00:00')).timestamp()
                if time.time() - t < float(aj['bazarr_dias']) * 86400:
                    return False          # aún le damos tiempo a Bazarr
            except ValueError:
                pass
        return True
    if v.get('r') == 'quitado':
        return False
    if v.get('video') != C.huella(e['path']):          # el vídeo ha cambiado (mejora de calidad, otra versión)
        return True
    if v.get('r') == 'hecho':
        if v.get('srt') and not os.path.exists(v['srt']) and not v.get('dentro'):
            return False                                # alguien lo borró: no insistir
        if aj['grabado'] == 'si' and 'grabado' not in v:
            return True                                 # se activó el texto grabado después
        if v.get('provisional') and aj['mejorar_reserva'] and M.hay_principal(v.get('lang', ''), it['tipo'] + 's' if it['tipo'] == 'serie' else 'peliculas',
                                                                              v.get('car_total', 0)):
            return True
        return False
    if v.get('r') == 'error':
        return v.get('intentos', 0) < 3
    if v.get('r') == 'audio' and not aj['saltar_audio']:
        return True                                     # se desactivó «saltar si el audio ya está en el idioma»
    if v.get('r') == 'solo_imagen' and aj['ocr_imagen'] and O.lector(aj)[0]:
        return True                                     # ahora sí se pueden leer
    if v.get('r') == 'sin_origen' and aj['grabado'] == 'si' and 'grabado' not in v:
        return True
    return v.get('r') not in FINALES


def _cache(it, clave, tipo, video, ident, calcular):
    """Las lecturas OCR tardan: se guardan por vídeo (tamaño+fecha) y por pista/lector."""
    ruta = os.path.join(C.ORIGEN, C.seguro(it['titulo']), f'{clave}.{tipo}.json')
    d = C.leer(ruta, {})
    if d.get('video') == C.huella(video) and d.get('id') == ident:
        return d['datos']
    datos = calcular()
    C.escribir(ruta, {'video': C.huella(video), 'id': ident, 'datos': datos})
    return datos


def procesar(k, it, e, pista_elegida=None, forzar=False, grabado=False):
    aj = C.ajustes(it)
    destino = destino_de(aj)
    video = e['path']
    v_ant = C.estado().get(video) or {}
    C.vivo.update(trabajando=nombre_ep(it, e['clave']), paso='Mirando las pistas', desde=time.time())
    base = {'clave': e['clave'], 'k': k, 'fecha': time.strftime('%Y-%m-%d %H:%M'), 'destino': aj['destino']}
    tipo_media = 'series' if it['tipo'] == 'serie' else 'peliculas'
    grabado = grabado or aj['grabado'] == 'si'

    def fin(r, detalle='', **extra):
        C.poner_estado(video, {**base, 'video': C.huella(video), 'r': r, 'detalle': detalle, **extra})
        return r

    def paso(texto):
        C.vivo['paso'] = texto

    subs, audio = mostrar_pistas(video, v_ant)
    if not forzar:
        hay = S.tiene_destino(subs, destino['code2'], aj['destino'] == 'es-419', aj['variante_vale'])
        if hay:
            return fin('ya', 'Ya tiene ' + S.describir(hay))
        if aj['saltar_audio'] and any(lang == destino['code2'] for lang, _ in audio):
            return fin('audio', 'El audio ya está en ' + destino['nombre'])
    prioridad = [x.strip() for x in aj['prioridad'].split(',') if x.strip()]
    p = next((x for x in subs if pista_id(x) == pista_elegida), None) if pista_elegida else None
    motivo = ''
    if not p:
        p, motivo = S.elegir_origen(subs, prioridad, destino['code2'])
    nota_ocr = ''
    if not p and motivo == 'solo_imagen' and aj['ocr_imagen']:
        lector, porque = O.lector(aj)
        if lector:
            p = S.elegir_imagen(subs, prioridad, destino['code2'])
        else:
            nota_ocr = porque
    if not p and not grabado:
        det = ('Solo tiene subtítulos de imagen (PGS/VobSub)' + (f' y no se pueden leer: {nota_ocr}' if nota_ocr else '; activa el OCR en Ajustes')
               if motivo == 'solo_imagen' else 'No tiene subtítulos de texto en otro idioma')
        C.resultado(it['titulo'], e['clave'], TEXTO_R[motivo], False, det, k)
        return fin(motivo, det, pistas=[S.describir(x) for x in subs])

    def progreso(n, t, nombre):
        paso(f'{nombre}: {n}/{t} frases')
    cues, salida_cues, textos = [], [], []
    usados, provisional, notas = {}, False, []
    extra_estado = {}
    if p:
        if p['codec'] in S.IMAGEN:
            lector = O.lector(aj)
            ident = f"{pista_id(p)}|{lector[0]}|{lector[1]['id'] if lector[1] and lector[0] == 'vision' else aj['ocr_idiomas']}"
            cues = [tuple(x) for x in _cache(it, e['clave'], 'ocr-imagen', video, ident, lambda: O.leer_pista_imagen(video, p, aj, paso))]
            extra_estado['ocr'] = 'subtítulos de imagen leídos con ' + ('Tesseract' if lector[0] == 'tesseract' else lector[1]['nombre'])
        else:
            paso('Sacando el subtítulo en ' + S.NOMBRE.get(p['lang'], p['lang'] or '?'))
            cues = S.parsear(S.extraer(video, p))
        if len(cues) < 5:
            raise RuntimeError(f'El subtítulo de origen ({S.describir(p)}) está casi vacío: {len(cues)} líneas')
        os.makedirs(os.path.dirname(ruta_origen(it, e['clave'])), exist_ok=True)
        S.escribir(cues, ruta_origen(it, e['clave']))
        prep, textos = S.preparar(cues, aj['quitar_sdh'] and p['sdh'])
        traducidos, usados, provisional, notas = M.traducir(textos, p['lang'], destino, tipo_media, aj['motor'], progreso)
        salida_cues = S.montar(prep, traducidos)

    if grabado:
        lector, dato = O.lector(aj)          # dato: el motor con visión, o el motivo si no hay lector
        if not lector:
            notas.append('Texto grabado: ' + dato)
        else:
            lang_def = (p['lang'] if p else '') or next((a for a, _ in audio if a), '')
            ident = f"{lector}|{dato['id'] if lector == 'vision' else aj['ocr_idiomas']}"
            hallado = _cache(it, e['clave'], 'grabado', video, ident, lambda: O.buscar_grabado(video, aj, lang_def, paso))
            hallado = [g for g in O.quitar_repetidos(hallado, cues) if g['lang'] != destino['code2']]
            lista = []
            for lang in sorted({g['lang'] for g in hallado}):
                grupo = [g for g in hallado if g['lang'] == lang]
                # subtítulos y pantallas: como un subtítulo normal (diálogos con guion, frases partidas en dos líneas);
                # rótulos: cada línea por separado y sin mayúsculas, que los traductores las entienden mejor
                falsos = []
                for g in grupo:
                    lineas = [x.strip() for x in g['texto'].split('|') if x.strip()]
                    if g['zona'].startswith('rotulo'):
                        lineas = [x.capitalize() if x.isupper() else x for x in lineas]
                        for x in lineas:
                            falsos.append((g, [x]))
                    else:
                        falsos.append((g, lineas))
                falsos = [(g, ls) for g, ls in falsos if any(S.ETIQ.sub('', x).strip() for x in ls)]   # preparar() quita las vacías
                prep, tx = S.preparar([(int(g['a'] * 1000), int(g['b'] * 1000), ls) for g, ls in falsos], False)
                tr, us2, prov2, n2 = M.traducir(tx, lang, destino, tipo_media, aj['motor'], progreso)
                for x, y in us2.items():
                    usados[x] = usados.get(x, 0) + y
                provisional = provisional or prov2
                notas += n2
                textos += tx
                montados = S.montar(prep, tr)
                por_g = {}
                for (g, _), (_, _, ls) in zip(falsos, montados):
                    por_g.setdefault(id(g), (g, []))[1].extend(ls)
                for g, ls in por_g.values():
                    salida_cues.append((int(g['a'] * 1000), int(max(g['b'], g['a'] + (4 if g['zona'].startswith('rotulo') else 1.2)) * 1000),
                                        [O.POS[g['zona']] + ls[0]] + ls[1:]))
                    lista.append({**g, 'es': ' / '.join(ls)})
            C.escribir(os.path.join(C.ORIGEN, C.seguro(it['titulo']), f"{e['clave']}.grabado-traducido.json"), sorted(lista, key=lambda g: g['a']))
            extra_estado['grabado'] = len(lista)
            salida_cues.sort(key=lambda c: (c[0], c[1]))
    if not salida_cues:
        det = 'No hay subtítulos de texto ni texto grabado que traducir'
        C.resultado(it['titulo'], e['clave'], TEXTO_R['sin_origen'], False, det, k)
        return fin('sin_origen', det, pistas=[S.describir(x) for x in subs], grabado=extra_estado.get('grabado', 0))

    paso('Guardando')
    hecho = SA.guardar(it, e, salida_cues, destino, aj, v_ant)
    motores = {m['id']: m['nombre'] for m in C.cfg()['motores']}
    nombres = [motores.get(i, i) for i in usados]
    fin('hecho', '', motores=nombres, provisional=provisional, origen=S.describir(p) if p else 'solo texto grabado', lang=p['lang'] if p else '',
        pista=pista_id(p) if p else '', lineas=len(salida_cues), car_total=sum(len(t) for t in textos), notas=notas + hecho.pop('notas'),
        **hecho, **extra_estado, pistas=[S.describir(x) for x in subs])
    desde = f"desde el {S.NOMBRE.get(p['lang'], p['lang'])}" if p else 'solo el texto grabado'
    extra_txt = f" + {extra_estado['grabado']} de texto grabado" if extra_estado.get('grabado') else ''
    C.resultado(it['titulo'], e['clave'], f"Traducido {desde}{extra_txt} con {' + '.join(nombres)}" + (' (provisional)' if provisional else ''),
                True, ' · '.join(notas[-2:]), k)
    if any('cupo' in n.lower() for n in notas):
        aviso_cupo(' · '.join(n for n in notas if 'cupo' in n.lower()))
    return 'hecho'


def aviso_cupo(nota):
    mes = time.strftime('%Y-%m')

    def fn(c):
        if c.get('aviso_cupo') == mes:
            return False
        c['aviso_cupo'] = mes
        return True
    if C.cambiar_cfg(fn):
        avisar('subrr: sin cupo', nota + '. Sigo con el siguiente motor de la cadena.')


def seguro_procesar(k, it, e, **kw):
    try:
        return procesar(k, it, e, **kw)
    except Exception as ex:
        traceback.print_exc()
        v = C.estado().get(e['path']) or {}
        C.poner_estado(e['path'], {**v, 'video': C.huella(e['path']), 'fecha': time.strftime('%Y-%m-%d %H:%M'), 'clave': e['clave'],
                                   'k': k, 'r': 'error', 'detalle': str(ex)[:400], 'intentos': v.get('intentos', 0) + 1 if v.get('r') == 'error' else 1,
                                   'previo': v.get('r') if v.get('r') != 'error' else v.get('previo')})
        C.resultado(it['titulo'], e['clave'], 'Error al traducir', False, str(ex)[:300], k)
        return 'error'
    finally:
        C.vivo.update(trabajando='', paso='', desde=0.0)


def hacer_accion(a):
    it = C.cfg()['items'].get(a['item'])
    if not it:
        return
    e = next((x for x in episodios(it) if x['clave'] == a['clave']), None)
    if not e or not e['path']:
        return
    acc = a['accion']
    v = C.estado().get(e['path']) or {}
    if acc == 'quitar':
        hecho = SA.quitar(it, e, v)
        C.poner_estado(e['path'], {**v, 'video': C.huella(e['path']), 'r': 'quitado', 'fecha': time.strftime('%Y-%m-%d %H:%M'),
                                   'detalle': 'Quitado desde la web: ' + (', '.join(hecho) or 'no quedaba nada de subrr')})
        C.resultado(it['titulo'], e['clave'], 'Subtítulo quitado', True, ', '.join(hecho), a['item'])
    elif acc == 'sustituir':
        aj = C.ajustes(it)
        ruta = SA.ruta_aparte(e['path'], destino_de(aj)['code2'])
        if os.path.exists(ruta) and not SA.es_nuestro_aparte(ruta, v):
            copia = ruta + '.antes-subrr'
            if os.path.exists(copia):
                copia = f"{ruta}.antes-subrr-{time.strftime('%Y%m%d%H%M%S')}"
            os.rename(ruta, copia)
            C.resultado(it['titulo'], e['clave'], 'Subtítulo anterior guardado aparte', True, os.path.basename(copia), a['item'])
        seguro_procesar(a['item'], it, e, forzar=True)
    elif acc == 'reintentar':
        C.poner_estado(e['path'], {k: x for k, x in v.items() if k in ('srt', 'srt_huella', 'dentro')} or None)
        seguro_procesar(a['item'], it, e)
    elif acc == 'grabado':
        seguro_procesar(a['item'], it, e, forzar=True, grabado=True)
    elif acc == 'nuevo':                   # aviso de un webhook: archivo recién importado o mejorado
        est = C.estado()
        if elegido(it, e, est) and pendiente(it, e, C.ajustes(it), est.get(e['path'])):
            seguro_procesar(a['item'], it, e)
    elif acc.startswith('rehacer'):
        pista = acc.split('|', 1)[1] if '|' in acc else None
        seguro_procesar(a['item'], it, e, pista_elegida=pista, forzar=True)


def sincronizar_bazarr(aj):
    """Modo Bazarr: crea/actualiza las series y películas con lo que Bazarr echa de menos en el idioma de destino."""
    WANTED.clear()
    if not (aj['bazarr_auto'] and bazarr.ok()):
        return
    code2 = destino_de(aj)['code2']

    def quiere(x):
        return any(m.get('code2') == code2 and not m.get('forced') for m in x.get('missing_subtitles', []))
    nuevos = {}
    for x in bazarr.wanted('episodes'):
        if quiere(x):
            k = f"sonarr:{x['sonarrSeriesId']}"
            WANTED.setdefault(k, set()).add(x['sonarrEpisodeId'])
            nuevos.setdefault(k, {'tipo': 'serie', 'id': x['sonarrSeriesId'], 'titulo': x.get('seriesTitle', '?')})
    for x in bazarr.wanted('movies'):
        if quiere(x) and x.get('radarrId'):
            k = f"radarr:{x['radarrId']}"
            WANTED[k] = {x['radarrId']}
            nuevos.setdefault(k, {'tipo': 'pelicula', 'id': x['radarrId'], 'titulo': x.get('title', '?')})

    def fn(c):
        for k, it in nuevos.items():
            if k not in c['items']:
                c['items'][k] = {**it, 'modo': 'bazarr', 'desde': time.strftime('%Y-%m-%d')}
    C.cambiar_cfg(fn)


def pasada():
    aj = C.ajustes()
    try:
        sincronizar_bazarr(aj)
    except Exception as ex:
        C.log('Bazarr: no pude leer lo que falta:', ex)
    c = C.cfg()
    for k, it in sorted(c['items'].items(), key=lambda x: x[1]['titulo'].lower()):
        if it.get('fase') == 'pausado':
            continue
        try:
            eps = episodios(it)
        except Exception as ex:
            C.log('no puedo leer', it['titulo'], ex)
            continue
        hechos = 0
        for e in eps:
            a = C.tomar_accion()
            while a:
                hacer_accion(a)
                a = C.tomar_accion()
            if not C.cfg()['items'].get(k):          # lo han quitado mientras tanto
                break
            est = C.estado()
            if not elegido(it, e, est):
                continue
            if pendiente(it, e, C.ajustes(it), est.get(e['path']) if e['path'] else None):
                if seguro_procesar(k, it, e) == 'hecho':
                    hechos += 1
        if hechos:
            est = C.estado()
            faltan = [e for e in eps if e['path'] and elegido(it, e, est) and (est.get(e['path']) or {}).get('r') not in FINALES]
            if not faltan:
                avisar('subrr: subtítulos listos', f"{it['titulo']}: {hechos} traducido{'s' if hechos != 1 else ''}")


_ultima_purga = [0.0]


def purgar():
    if time.time() - _ultima_purga[0] < 86400:
        return
    _ultima_purga[0] = time.time()
    aj = C.ajustes()
    carpetas = {v.get('papelera') and os.path.dirname(os.path.dirname(v['papelera'])) for v in C.estado().values()} - {None, ''}
    if aj['papelera']:
        carpetas.add(aj['papelera'])
    SA.purgar_papelera(int(aj['papelera_dias'] or 0), carpetas)


def trabajador():
    while True:
        try:
            a = C.tomar_accion()
            while a:
                try:
                    hacer_accion(a)
                except Exception:
                    traceback.print_exc()
                a = C.tomar_accion()
            pasada()
            purgar()
            C.vivo['ultima_pasada'] = time.strftime('%H:%M')
        except Exception:
            traceback.print_exc()
        C.despertar.wait(max(1, int(C.ajustes()['intervalo_min'] or 10)) * 60)
        C.despertar.clear()


def arrancar():
    threading.Thread(target=trabajador, daemon=True, name='trabajador').start()
