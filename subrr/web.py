"""Interfaz web. Sin dependencias: HTML del servidor y un poco de JS."""
import base64, html, json, os, time, traceback, unicodedata
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, urlsplit, urlunsplit, quote

from . import config as C
from . import motores as M
from . import subs as S
from . import trabajador as T
from . import salida as SA
from . import ocr as O
from . import webhook as W
from .estilo import CSS, JS, LOGO, FAVICON, ic
from .servicios import sonarr, radarr, bazarr, episodios_cache, caratula, probar as probar_conexion

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
esc = html.escape


def url_visible(u):
    """Una dirección sin usuario:clave ni parámetros, para mostrarla (las claves no se enseñan nunca)."""
    try:
        p = urlsplit(u or '')
        if not (p.username or p.password or p.query):
            return u or ''
        return urlunsplit((p.scheme, (p.hostname or '') + (f':{p.port}' if p.port else ''), p.path, '', ''))
    except ValueError:
        return ''


def url_valida(u):
    """Las claves van en su campo, no dentro de la dirección (así nunca se muestran ni se mandan por error a otro sitio)."""
    u = (u or '').strip().rstrip('/')
    try:
        p = urlsplit(u)
        if p.username or p.password or p.query or p.fragment:
            raise ValueError('La dirección no puede llevar usuario:clave ni parámetros (?clave=…): pon la clave en su campo.')
    except ValueError as ex:
        raise ValueError(str(ex) if 'clave' in str(ex) else 'Dirección no válida.')
    return u
VERSION = '0.1.0'


def pagina(titulo, cuerpo, activa=''):
    nav = ''.join(f'<a href="{u}" class="{"on" if u == activa else ""}">{ic(i, 19)}<span>{t}</span></a>'
                  for u, i, t in (('/', 'biblio', 'Biblioteca'), ('/anadir', 'mas', 'Añadir'),
                                  ('/actividad', 'act', 'Actividad'), ('/ajustes', 'ajustes', 'Ajustes')))
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0b0b0d">
<title>{esc(titulo)} · subrr</title><link rel="icon" href="/favicon.svg"><style>{CSS}</style></head><body>
<header class="top"><div><a class="marca" href="/">{LOGO}subrr</a><nav class="nav">{nav}</nav>
<div class="vivo"><i class="punto" id="vivo-p"></i><span id="vivo-t">…</span></div></div></header>
<main>{cuerpo}</main><nav class="pestanas-m">{nav}</nav><script>{JS}</script></body></html>"""


def boton(ruta, campos, texto, clase='btn peq', icono=None, confirmar=None):
    ocultos = ''.join(f'<input type="hidden" name="{esc(k)}" value="{esc(str(v))}">' for k, v in campos.items())
    conf = f' data-confirmar="{esc(confirmar)}"' if confirmar else ''
    return (f'<form class="in" method="post" action="{ruta}"{conf}>{ocultos}'
            f'<button class="{clase}">{ic(icono, 16) if icono else ""}{texto}</button></form>')


def img(tipo, id_, clase='poster'):
    return f'/img/{tipo}/{int(id_)}/{clase}'


def tipo_arr(it):
    return 'sonarr' if it['tipo'] == 'serie' else 'radarr'


def vacio(titulo, texto, extra=''):
    return f'<div class="panel vacio">{ic("bocadillo", 30)}<h2 style="margin-top:12px">{titulo}</h2><p>{texto}</p>{extra}</div>'


# ------------------------------------------------------------------------------------------------ estado por episodio
ESTADOS = (('ok', 'Traducido'), ('medio', 'Provisional (motor de reserva)'), ('ya', 'Ya tenía subtítulos'),
           ('cola', 'Pendiente'), ('fallo', 'Sin origen o error'), ('vacio', 'Sin archivo / quitado'))


def estado_ep(e, est):
    """('ok'|'medio'|'ya'|'cola'|'fallo'|'vacio', texto, entrada_estado)"""
    if not e['path']:
        return 'vacio', 'Sin archivo', None
    v = est.get(e['path'])
    if v and v.get('r') == 'quitado':
        return 'vacio', 'Quitado', v
    if not v or v.get('video') != C.huella(e['path']):
        return 'cola', 'Pendiente', v
    r = v.get('r')
    if r == 'hecho':
        if v.get('srt') and not v.get('dentro') and not os.path.exists(v['srt']):
            return 'fallo', 'El subtítulo ya no está', v
        motores = ' + '.join(v.get('motores') or [])
        if v.get('provisional'):
            return 'medio', 'Provisional · ' + motores, v
        return 'ok', 'Traducido · ' + motores, v
    if r in ('ya', 'audio'):
        return 'ya', T.TEXTO_R[r], v
    if r in ('sin_origen', 'solo_imagen', 'error'):
        return 'fallo', T.TEXTO_R[r], v
    return 'cola', 'Pendiente', v


def leyenda():
    return '<div class="leyenda">' + ''.join(f'<span><i class="e-{k}"></i>{t}</span>' for k, t in ESTADOS) + '</div>'


def ahora_html():
    t = C.vivo.get('trabajando') or ''
    return (f'<div class="panel ahora" id="ahora" {"hidden" if not t else ""}>{ic("bocadillo", 22)}<div><div class="eti">Ahora</div>'
            f'<div class="q">{esc(t)}</div><div class="p">{esc(C.vivo.get("paso") or "")}</div></div></div>')


def resumen(it, est):
    eps = [e for e in episodios_cache(it) if T.elegido(it, e, est)]
    return eps, [(e, estado_ep(e, est)[0]) for e in eps]


def mapa_html(it, pares):
    if it['tipo'] != 'serie':
        return ''
    porT = {}
    for e, s in pares:
        porT.setdefault(e['temporada'], []).append((e, s))
    return '<div class="mapa">' + ''.join(
        f'<div class="t"><span>T{t}</span><div class="celdas">' +
        ''.join(f'<i class="e-{s}" title="{e["clave"]} · {dict(ESTADOS)[s]}"></i>' for e, s in xs) + '</div></div>'
        for t, xs in sorted(porT.items())) + '</div>'


def meta_item(it):
    temps = ('T' + ', T'.join(map(str, it.get('temporadas', [])))) if it['tipo'] == 'serie' and it.get('temporadas') and it.get('modo') != 'bazarr' else ''
    return ' · '.join(x for x in ('Serie' if it['tipo'] == 'serie' else 'Película', str(it.get('anio') or ''), temps,
                                  'lo que pide Bazarr' if it.get('modo') == 'bazarr' else '') if x)


def aviso_config():
    """Qué falta para que subrr pueda trabajar."""
    falta = []
    if not (sonarr.ok() or radarr.ok()):
        falta.append('<a href="/ajustes/conexiones"><b>conectar Sonarr o Radarr</b></a>')
    if not any(m.get('activo') and M.disponible(m)[0] for m in C.cfg()['motores']):
        falta.append('<a href="/ajustes/motores"><b>añadir un motor de traducción</b></a>')
    if not falta:
        return ''
    return f'<div class="panel nota">{ic("aviso", 18)}<div>Para empezar falta ' + ' y '.join(falta) + '.</div></div>'


# ------------------------------------------------------------------------------------------------ vistas
def vista_biblioteca():
    c = C.cfg()
    est = C.estado()
    cab = ('<div class="cab"><div><h1>Biblioteca</h1><p class="sub">Series y películas a las que subrr pone subtítulos traducidos.</p></div>'
           '<a class="btn pri" href="/anadir">' + ic('mas', 16) + 'Añadir</a></div>')
    cab += aviso_config()
    if not c['items']:
        txt = ('Elige series, temporadas o películas y subrr traducirá los subtítulos que ya traen (inglés, francés…). '
               'O activa en Ajustes el modo Bazarr para que traduzca solo lo que Bazarr no encuentra.')
        return pagina('Biblioteca', cab + ahora_html() + vacio('Nada todavía', txt, '<a class="btn pri" href="/anadir">Elegir qué traducir</a>'), '/')
    filas, total = [], {'trad': 0, 'ya': 0, 'fallo': 0}
    for k, it in sorted(c['items'].items(), key=lambda x: x[1]['titulo'].lower()):
        try:
            eps, pares = resumen(it, est)
            error = ''
        except Exception as ex:
            eps, pares, error = [], [], str(ex)
        if it.get('modo') == 'bazarr' and not eps and not error:
            continue
        n = len(eps) or 1
        cu = {s: sum(1 for _, x in pares if x == s) for s, _ in ESTADOS}
        trad = cu['ok'] + cu['medio']
        total['trad'] += trad
        total['ya'] += cu['ya']
        total['fallo'] += cu['fallo']
        cifras = [('Traducidos', trad, 'var(--ok)'), ('Ya tenían', cu['ya'], 'var(--info)'), ('Pendientes', cu['cola'], 'var(--warn)')]
        cif = ''.join(f'<div class="cifra"><div class="n"><span>{t}</span><b>{v}/{len(eps)}</b></div>'
                      f'<div class="barra"><i style="width:{100 * v / n:.0f}%;background:{col}"></i></div></div>' for t, v, col in cifras)
        avisos = ''
        if error:
            avisos = f'<div class="aviso err">{ic("aviso", 16)}{esc(error[:160])}</div>'
        elif cu['fallo']:
            avisos = f'<div class="aviso">{ic("aviso", 16)}{cu["fallo"]} sin traducir: entra para ver por qué</div>'
        fase = 'pausado' if it.get('fase') == 'pausado' else 'activo' if cu['cola'] else 'aldia'
        badge = {'pausado': 'En pausa', 'activo': 'Traduciendo', 'aldia': 'Al día'}[fase]
        filas.append(f'<a class="fila" href="/item?k={quote(k)}"><div class="poster" style="background-image:url({img(tipo_arr(it), it["id"])})"></div>'
                     f'<div style="min-width:0"><div class="titulo">{esc(it["titulo"])}</div><div class="meta">{esc(meta_item(it))}</div>'
                     f'<div class="cifras">{cif}</div>{mapa_html(it, pares)}{avisos}</div>'
                     f'<div class="der"><span class="badge b-{fase}">{badge}</span></div></a>')
    datos = (f'<div class="datos"><div><b>{len(filas)}</b><span>series y películas</span></div>'
             f'<div><b>{total["trad"]}</b><span>traducidos</span></div><div><b>{total["ya"]}</b><span>ya tenían subtítulos</span></div>'
             f'<div><b>{total["fallo"]}</b><span>sin traducir</span></div></div>')
    lista = '<div class="panel lista">' + ''.join(filas) + '</div>' if filas else vacio('Nada pendiente', 'Bazarr no echa nada de menos ahora mismo.')
    return pagina('Biblioteca', cab + ahora_html() + datos + '<div class="seccion"><span class="eti">Elegidas</span></div>' + lista + leyenda(), '/')


def dialogo_serie(s, ya, did):
    temps = [x for x in s['seasons'] if x['seasonNumber'] > 0] + [x for x in s['seasons'] if x['seasonNumber'] == 0]
    marcadas = ya.get('temporadas', []) if ya and ya.get('modo') != 'bazarr' else None
    cajas = ''.join(
        f'<label><input type="checkbox" name="t" value="{x["seasonNumber"]}" {"checked" if (marcadas is not None and x["seasonNumber"] in marcadas) or (marcadas is None and x["seasonNumber"] > 0) else ""}>'
        f'{"Especiales" if x["seasonNumber"] == 0 else "T" + str(x["seasonNumber"])}<small>{x.get("statistics", {}).get("episodeFileCount", 0)}/{x.get("statistics", {}).get("totalEpisodeCount", 0)}</small></label>'
        for x in temps)
    return (f'<dialog id="{did}"><form method="post" action="/anadir"><div class="dc"><div class="eti">Serie · {s.get("year", "")}</div>'
            f'<h2 style="font-size:20px;margin-top:4px">{esc(s["title"])}</h2><p class="sub">Elige las temporadas que quieres traducir. '
            f'Los episodios que ya tengan subtítulos en tu idioma se dejan como están.</p><input type="hidden" name="k" value="sonarr:{s["id"]}"><div class="temps">{cajas}</div></div>'
            f'<div class="pie"><button type="button" class="btn" data-cerrar>Cancelar</button><button class="btn pri">{"Guardar" if ya else "Empezar"}</button></div></form></dialog>')


def vista_anadir():
    c = C.cfg()
    series, pelis, errores = [], [], []
    for a, dest in ((sonarr, series), (radarr, pelis)):
        if a.ok():
            try:
                dest += sorted(a.get('series' if a is sonarr else 'movie'), key=lambda s: s.get('sortTitle') or s['title'])
            except Exception as ex:
                errores.append(f'{a.nombre.capitalize()}: {ex}')
    if not series and not pelis:
        txt = esc(' · '.join(errores)) if errores else 'Conecta Sonarr y/o Radarr para elegir qué traducir.'
        return pagina('Añadir', vacio('No hay nada que elegir', txt, '<a class="btn pri" href="/ajustes/conexiones">Conexiones</a>'), '/anadir')

    def norm(t):
        return ''.join(ch for ch in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(ch) != 'Mn')
    tarjetas, dialogos = [], []
    for s in series:
        k = f"sonarr:{s['id']}"
        ya = c['items'].get(k)
        st = s.get('statistics', {})
        did = f"d-s{s['id']}"
        tarjetas.append(f'<button class="tarjeta" data-abrir="{did}" data-tipo="serie" data-n="{esc(norm(s["title"] + " " + str(s.get("year", ""))))}">'
                        f'<div class="poster" style="background-image:url({img("sonarr", s["id"])})">{"<span class=marca-d>en subrr</span>" if ya else ""}</div>'
                        f'<b>{esc(s["title"])}</b><span>{s.get("year", "")} · {st.get("episodeFileCount", 0)}/{st.get("totalEpisodeCount", 0)} ep.</span></button>')
        dialogos.append(dialogo_serie(s, ya, did))
    for m in pelis:
        k = f"radarr:{m['id']}"
        ya = c['items'].get(k)
        did = f"d-p{m['id']}"
        tarjetas.append(f'<button class="tarjeta" data-abrir="{did}" data-tipo="pelicula" data-n="{esc(norm(m["title"] + " " + str(m.get("year", ""))))}">'
                        f'<div class="poster" style="background-image:url({img("radarr", m["id"])})">{"<span class=marca-d>en subrr</span>" if ya else ""}</div>'
                        f'<b>{esc(m["title"])}</b><span>{m.get("year", "")} · {"descargada" if m.get("hasFile") else "sin descargar"}</span></button>')
        cuerpo_d = ('<p class="sub">Ya está en subrr.</p>' if ya else
                    '<p class="sub">subrr traducirá los subtítulos que traiga, si no los tiene ya en tu idioma.</p>')
        boton_d = (f'<a class="btn pri" href="/item?k={quote(k)}">Abrir</a>' if ya else '<button class="btn pri">Empezar</button>')
        dialogos.append(f'<dialog id="{did}"><form method="post" action="/anadir"><div class="dc"><div class="eti">Película · {m.get("year", "")}</div>'
                        f'<h2 style="font-size:20px;margin-top:4px">{esc(m["title"])}</h2>{cuerpo_d}<input type="hidden" name="k" value="{k}"></div>'
                        f'<div class="pie"><button type="button" class="btn" data-cerrar>Cancelar</button>{boton_d}</div></form></dialog>')
    pest = '<button data-tab="" class="on">Todo</button>' + ('<button data-tab="serie">Series</button>' if series else '') + \
           ('<button data-tab="pelicula">Películas</button>' if pelis else '')
    nota = ''
    if bazarr.ok() and not C.ajustes()['bazarr_auto']:
        nota = (f'<div class="panel nota">{ic("enchufe", 18)}<div>¿Prefieres que subrr traduzca solo lo que <b>Bazarr no encuentra</b>, sin elegir nada? '
                'Actívalo en <a href="/ajustes#bazarr"><b>Ajustes → Bazarr</b></a>.</div></div>')
    cuerpo = ('<div class="cab"><div><h1>Añadir</h1><p class="sub">Series y películas de Sonarr y Radarr.</p></div></div>' + nota +
              f'<div class="herram"><div class="busca">{ic("buscar", 17)}<input type="search" id="busca" placeholder="Buscar título" autocomplete="off"></div>'
              f'<div class="pestanas">{pest}</div></div>'
              f'<div class="rejilla">{"".join(tarjetas)}</div>{"".join(dialogos)}')
    if errores:
        cuerpo = f'<div class="aviso err">{ic("aviso", 16)}{esc(" · ".join(errores))}</div>' + cuerpo
    return pagina('Añadir', cuerpo, '/anadir')


# ---- campos de ajustes (generales y por serie)
OPC_SALIDA = (('aparte', 'Archivo aparte (.xx.srt)'), ('dentro', 'Pista dentro del mkv'), ('ambos', 'Las dos cosas'))
CAMPOS = (
    ('Traducción', '', (
        ('destino', 'Idioma de destino', '', 'sel', tuple((k, v['nombre']) for k, v in C.DESTINOS.items())),
        ('prioridad', 'Idiomas de origen preferidos', 'Códigos separados por comas, el primero es el preferido. El inglés suele dar las mejores traducciones.', 'txt', None),
        ('quitar_sdh', 'Quitar anotaciones para sordos', 'Si el origen es SDH: quita [ruidos], ♪ y «NOMBRE:».', 'sw', None),
        ('saltar_audio', 'Saltar si el audio ya está en el idioma', 'No traduce vídeos que ya tienen una pista de audio en el idioma de destino.', 'sw', None),
        ('variante_vale', 'Cualquier variante cuenta (español)', 'Si está activo, un subtítulo latino cuenta como castellano y al revés.', 'sw', None),
        ('mejorar_reserva', 'Rehacer lo provisional', 'Lo que hizo un motor de reserva se rehace con uno principal cuando vuelva a estar disponible.', 'sw', None),
    )),
    ('Dónde se guarda', '', (
        ('salida', 'Guardar como', 'Jellyfin a veces salta a otra pista con los subtítulos aparte; dentro del mkv no pasa. '
                                   'Meterlo en el mkv crea un vídeo nuevo (el original va a la papelera).', 'sel', OPC_SALIDA),
        ('por_defecto', 'Marcar como pista por defecto', 'Al meterlo en el mkv: va la primera y por defecto; las demás se desmarcan.', 'sw', None),
        ('enlaces_duros', 'Meterlo aunque haya enlaces duros', 'Si el vídeo es también el de un torrent que se comparte, meter la pista lo separa (ocupa el doble). '
                                                               'Desactivado: en esos casos se guarda aparte.', 'sw', None),
        ('papelera_dias', 'Días en la papelera', 'Cuánto se guarda el vídeo original al meter la pista. 0 = no se guarda.', 'num', None),
        ('papelera', 'Carpeta de la papelera', 'Vacío: «.subrr-papelera» en la raíz del disco del vídeo (así puede usar enlaces duros y no ocupa más).', 'txt', None),
        ('nombre_pista', 'Nombre de la pista', '«{idioma}» se cambia por el idioma. Deja «subrr» en el nombre: así sabe cuál es la suya.', 'txt', None),
    )),
    ('Subtítulos de imagen y texto grabado', 'ocr', (
        ('ocr_imagen', 'Leer subtítulos de imagen', 'Si un vídeo solo trae subtítulos de imagen (PGS de Blu-ray, VobSub de DVD), los pasa a texto con OCR y los traduce.', 'sw', None),
        ('grabado', 'Buscar texto grabado en la imagen', 'Subtítulos, rótulos y pantallas de texto metidos en el propio vídeo (típico en versiones dobladas: '
                    'las partes en otro idioma). Tarda unos minutos por episodio. También hay un botón en cada episodio.', 'sel', (('no', 'No'), ('si', 'Sí'))),
        ('ocr_motor', 'Lector', 'Tesseract es gratis y local. Un motor con visión (Claude o un LLM compatible con OpenAI que acepte imágenes) lee mejor '
                                'y distingue un subtítulo de un cartel; cuesta unos céntimos por episodio.', 'sel', None),
        ('ocr_idiomas', 'Idiomas de Tesseract', 'Separados por «+» (eng, fra, spa, deu, ita, por…). Solo se usan los que estén instalados.', 'txt', None),
    )),
    ('Bazarr', 'bazarr', (
        ('bazarr_auto', 'Traducir lo que Bazarr no encuentra', 'subrr mira la lista «Wanted» de Bazarr y traduce lo que falte en tu idioma, sin elegir nada a mano.', 'sw', None),
        ('bazarr_dias', 'Esperar antes de traducir', 'Días desde que se descargó el vídeo, para dar tiempo a Bazarr a encontrar uno de verdad.', 'num', None),
        ('bazarr_entrega', 'Entrega', 'Con «Dárselo a Bazarr» él guarda el archivo y lo apunta en su historial. Con cualquiera de las dos deja de buscarlo.', 'sel',
         (('escanear', 'Lo guarda subrr y Bazarr lo detecta'), ('subir', 'Dárselo a Bazarr'))),
    )),
    ('Rutas', 'rutas', (
        ('rutas', 'Rutas de Sonarr/Radarr/Bazarr', 'Si ven los vídeos en otra carpeta que subrr. Una por línea: «/tv => /media/tv». Vacío si coinciden.', 'largo', None),
        ('rutas_jellyfin', 'Rutas de Jellyfin', 'Para avisar a Jellyfin del archivo cambiado. Una por línea: «/media/tv => /data/tv».', 'largo', None),
    )),
    ('Funcionamiento', '', (
        ('intervalo_min', 'Revisar cada', 'Minutos entre pasadas (también revisa al momento al añadir algo).', 'num', None),
    )),
)


def control(clave, tipo, ops, valor, heredado=None):
    """Un control de formulario. heredado != None → ajuste de una serie (se puede dejar «como en Ajustes»)."""
    if tipo == 'sel' or (tipo == 'sw' and heredado is not None):
        if tipo == 'sw':
            ops = (('1', 'Sí'), ('0', 'No'))
            valor = '' if valor in (None, '') else ('1' if valor else '0')
        op = ''
        if heredado is not None:
            h = dict(ops).get(heredado if tipo != 'sw' else ('1' if heredado else '0'), heredado)
            op = f'<option value="">Como en Ajustes ({esc(str(h))})</option>'
        op += ''.join(f'<option value="{esc(str(v))}" {"selected" if str(valor) == str(v) else ""}>{esc(str(t))}</option>' for v, t in ops)
        return f'<select name="{clave}">{op}</select>'
    if tipo == 'sw':
        return f'<label class="interruptor"><input type="checkbox" name="{clave}" value="1" {"checked" if valor else ""}><i></i></label>'
    if tipo == 'num':
        return f'<input type="number" min="0" name="{clave}" value="{esc(str(valor))}">'
    if tipo == 'largo':
        return f'<textarea name="{clave}" spellcheck="false">{esc(str(valor or ""))}</textarea>'
    ph = f' placeholder="{esc(str(heredado))}"' if heredado is not None else ''
    return f'<input type="text" name="{clave}" value="{esc(str(valor or ""))}"{ph}>'


def opciones_lector():
    return tuple([('', 'Tesseract (local)')] + [(m['id'], m['nombre'] + ' (visión)') for m in C.cfg()['motores'] if m['tipo'] in ('claude', 'openai')])


def opciones_motor():
    return tuple([('', 'Según la cadena')] + [(m['id'], m['nombre']) for m in C.cfg()['motores']])


def vista_item(k):
    c = C.cfg()
    it = c['items'].get(k)
    if not it:
        return pagina('No existe', vacio('Ya no está en subrr', '', '<a class="btn" href="/">Volver</a>'))
    est = C.estado()
    try:
        eps, pares = resumen(it, est)
    except Exception as ex:
        return pagina(it['titulo'], vacio('No puedo leer los episodios', f'<span class="mono">{esc(str(ex))}</span>'))
    cu = {s: sum(1 for _, x in pares if x == s) for s, _ in ESTADOS}
    pausado = it.get('fase') == 'pausado'
    ta = tipo_arr(it)
    acciones = [boton('/item', {'k': k, 'a': 'reanudar' if pausado else 'pausar'}, 'Reanudar' if pausado else 'Pausar', 'btn peq',
                      'play' if pausado else 'pausa')]
    dlg = ''
    if it['tipo'] == 'serie':
        try:
            dlg = dialogo_serie(sonarr.get(f"series/{it['id']}"), it, 'd-temps')
            acciones.append('<button class="btn peq" data-abrir="d-temps">' + ('Elegir temporadas' if it.get('modo') == 'bazarr' else 'Temporadas') + '</button>')
        except Exception:
            pass
    n_audio = sum(1 for e, s in pares if s == 'ya' and (est.get(e['path']) or {}).get('r') == 'audio')
    if cu['fallo'] or n_audio:
        n_rei = cu['fallo'] + n_audio
        acciones.append(boton('/item', {'k': k, 'a': 'reintentar_fallos'},
                              f'Reintentar {n_rei} sin traducir' + (f' ({n_audio} saltados por audio)' if n_audio else ''), 'btn peq', 'repetir'))
    acciones.append(boton('/item', {'k': k, 'a': 'quitar'}, 'Quitar de subrr', 'btn peq peligro', 'x',
                          'Deja de vigilarla. Los subtítulos ya traducidos se quedan.'))
    heroe = (f'<a class="volver" href="/">{ic("atras", 16)}Biblioteca</a><div class="heroe"><div class="fondo" style="background-image:url({img(ta, it["id"], "fanart")})"></div>'
             f'<div class="cont"><div class="poster" style="background-image:url({img(ta, it["id"])})"></div><div>'
             f'<div class="eti">{esc(meta_item(it))}</div><h1 style="margin-top:4px">{esc(it["titulo"])}</h1>'
             f'<p class="sub">{cu["ok"] + cu["medio"]} traducidos · {cu["ya"]} ya tenían subtítulos · {cu["cola"]} pendientes · {cu["fallo"]} sin traducir</p>'
             f'{mapa_html(it, pares)}<div class="btns" style="margin-top:16px">{"".join(acciones)}</div></div></div></div>')
    # ajustes propios
    glob = C.ajustes()
    propios = it.get('ajustes') or {}
    filas_aj = ''
    defs = {cl: (et, ay, tp, op) for _, _, cs in CAMPOS for cl, et, ay, tp, op in cs}
    defs['motor'] = ('Motor preferido', 'Se prueba primero; si falla sigue la cadena.', 'sel', opciones_motor())
    for cl in C.POR_ITEM:
        et, ay, tp, op = defs[cl]
        her = glob[cl]
        if cl == 'motor':
            her = dict(op).get(glob[cl], 'Según la cadena')
        filas_aj += (f'<div class="campo{" cambiado" if propios.get(cl) not in (None, "") else ""}"><div><label>{et}</label><div class="ay">{ay}</div></div>'
                     f'<div>{control(cl, tp, op, propios.get(cl, ""), her)}</div></div>')
    n_prop = sum(1 for v in propios.values() if v not in (None, ''))
    ajustes_html = (f'<details class="panel" style="margin-top:22px"><summary class="grupo" style="cursor:pointer;list-style:none"><h3>Ajustes de '
                    f'{"esta serie" if it["tipo"] == "serie" else "esta película"}</h3><p style="margin:3px 0 0;color:var(--tx3);font-size:13px">'
                    f'{f"{n_prop} cambiado(s) respecto a Ajustes" if n_prop else "Como en Ajustes"} · se aplican a lo que se traduzca a partir de ahora</p></summary>'
                    f'<form method="post" action="/item" class="grupo"><input type="hidden" name="k" value="{esc(k)}"><input type="hidden" name="a" value="ajustes">'
                    f'{filas_aj}<div class="btns" style="margin-top:14px"><button class="btn pri">Guardar</button></div></form></details>')
    filas = []
    for e, s in pares:
        _, texto, v = estado_ep(e, est)
        num = e['clave'].replace('S', 'T').replace('E', '·E') if e['clave'] != 'pelicula' else 'Peli'
        det = ''
        if v and v.get('origen') and s in ('ok', 'medio'):
            det = 'desde el ' + v['origen'].split(' (')[0]
        elif v and v.get('detalle') and s in ('fallo', 'ya', 'vacio'):
            det = v['detalle']
        filas.append(f'<details class="ep" data-k="{esc(k)}" data-c="{e["clave"]}"><summary><span class="num">{num}</span>'
                     f'<span class="ept">{esc(e["titulo"] or "")}<small>{esc(det[:120])}</small></span>'
                     f'<span class="estado"><i class="e-{s}"></i>{esc(texto)}</span></summary><div class="desp"><div class="cargando">Cargando…</div></div></details>')
    lista = '<div class="panel">' + ''.join(filas) + '</div>' if filas else vacio('Nada elegido', 'Elige temporadas para empezar.')
    cuerpo = heroe + ahora_html() + ajustes_html + '<div class="seccion"><span class="eti">Episodios</span></div>' + lista + leyenda() + dlg
    return pagina(it['titulo'], cuerpo)


def fragmento_ep(k, clave):
    """Detalle de un episodio (se carga al abrirlo): pistas, origen usado, muestra y acciones."""
    it = C.cfg()['items'].get(k)
    if not it:
        return '<p>Ya no está en subrr.</p>'
    e = next((x for x in episodios_cache(it) if x['clave'] == clave), None)
    if not e or not e['path'] or not os.path.exists(e['path']):
        return '<p>No encuentro el vídeo' + (f' (<span class="mono">{esc(e["path"])}</span>; ¿falta un mapeo de rutas?)' if e and e['path'] else '') + '.</p>'
    aj = C.ajustes(it)
    destino = T.destino_de(aj)
    est = C.estado()
    s, texto, v = estado_ep(e, est)
    v = v or {}
    try:
        subs, audio = T.mostrar_pistas(e['path'], v)
    except Exception:
        subs, audio = [], []
    nuestro_srt = v.get('srt') if SA.es_nuestro_aparte(v.get('srt') or '', v) else None
    kv = [('Archivo', esc(os.path.basename(e['path']))),
          ('Audio', esc(', '.join(S.NOMBRE.get(a, a) for a, _ in audio) or '—')),
          ('Subtítulos', esc(', '.join(S.describir(p) + ('' if p['codec'] in S.TEXTO else ' · imagen') + (' · forzados' if p['forzado'] else '')
                                       + (' · de subrr' if p.get('subrr') else '') for p in subs) or 'ninguno'))]
    if v.get('origen'):
        kv.append(('Traducido desde', esc(v['origen'])))
    if v.get('motores'):
        kv.append(('Motores', esc(' + '.join(v['motores'])) + (' · provisional, se rehará con un motor principal' if v.get('provisional') else '')))
    guardado = []
    if nuestro_srt:
        guardado.append('aparte: ' + os.path.basename(nuestro_srt))
    if v.get('dentro'):
        guardado.append('pista dentro del mkv')
    if guardado:
        kv.append(('Guardado', esc(' · '.join(guardado))))
    for n in v.get('notas') or []:
        kv.append(('Nota', esc(n)))
    if v.get('detalle'):
        kv.append(('Detalle', esc(v['detalle'])))
    if v.get('fecha'):
        kv.append(('Fecha', esc(v['fecha'])))
    out = '<div class="kv">' + ''.join(f'<b>{a}</b><span>{b}</span>' for a, b in kv) + '</div>'
    # muestra: original y traducción lado a lado
    trad_txt = None
    if s in ('ok', 'medio') and os.path.exists(T.ruta_origen(it, clave)):
        try:
            if nuestro_srt:
                trad_txt = S.leer_texto(nuestro_srt)
            elif v.get('dentro'):
                p_sub = next((p for p in subs if p.get('subrr')), None)
                trad_txt = S.extraer(e['path'], p_sub) if p_sub else None
        except Exception:
            trad_txt = None
    if trad_txt:
        orig = S.parsear(S.leer_texto(T.ruta_origen(it, clave)))
        trad = S.parsear(trad_txt)
        por_t = {a: tx for a, _, tx in orig}
        n = len(trad)
        elegidos = [trad[i] for i in sorted({min(n - 1, int(n * f)) for f in (0.08, 0.09, 0.10, 0.11, 0.45, 0.46, 0.47, 0.80, 0.81)})] if n else []
        filas = ''.join(f'<div class="t mono">{S._ts(a)[:8]}</div><div>{esc(" ".join(S.ETIQ.sub("", x) for x in por_t.get(a, [])))}</div>'
                        f'<div class="es">{esc(" ".join(S.ETIQ.sub("", x) for x in tx))}</div>' for a, _, tx in elegidos)
        out += f'<div class="eti">Muestra</div><div class="muestra"><div>Tiempo</div><div>Original</div><div>{esc(destino["nombre"])}</div>{filas}</div>'
    if v.get('ocr'):
        out = out.replace('</div>', f'<b>OCR</b><span>{esc(v["ocr"])}</span></div>', 1)
    lista_g = C.leer(os.path.join(C.ORIGEN, C.seguro(it['titulo']), f'{clave}.grabado-traducido.json'), [])
    if lista_g and 'grabado' in v:
        zona = {'abajo': 'subtítulo', 'rotulo_i': 'rótulo', 'rotulo_d': 'rótulo', 'pantalla': 'pantalla'}
        filas_g = ''.join(f'<div class="t mono">{S._ts(int(g["a"] * 1000))[:8]}</div><div>{esc(g["texto"].replace(" | ", " / "))}'
                          f' <span class="meta">· {zona.get(g["zona"], "")}</span></div><div class="es">{esc(g["es"])}</div>' for g in lista_g[:60])
        out += (f'<div class="eti">Texto grabado en la imagen ({len(lista_g)})</div><div class="muestra"><div>Tiempo</div><div>Grabado</div>'
                f'<div>{esc(destino["nombre"])}</div>{filas_g}</div>')
    # acciones
    texto_subs = [p for p in subs if p['codec'] in S.TEXTO and p['lang'] != destino['code2'] and not p['forzado'] and not p.get('subrr')]
    opciones = ''.join(f'<option value="{esc(T.pista_id(p))}">{esc(S.describir(p))}</option>' for p in texto_subs)
    btns = []
    ruta_ap = SA.ruta_aparte(e['path'], destino['code2'])
    ajeno = os.path.exists(ruta_ap) and ruta_ap != nuestro_srt
    if texto_subs and not ajeno:
        btns.append(f'<form class="in" method="post" action="/episodio"><input type="hidden" name="k" value="{esc(k)}"><input type="hidden" name="c" value="{clave}">'
                    f'<input type="hidden" name="a" value="rehacer"><span class="btns"><select name="pista" style="width:auto;height:30px;font-size:12.5px">'
                    f'<option value="">Origen automático</option>{opciones}</select><button class="btn peq">{ic("repetir", 16)}'
                    f'{"Rehacer" if s in ("ok", "medio") else "Traducir"}</button></span></form>')
    if ajeno:
        btns.append(boton('/episodio', {'k': k, 'c': clave, 'a': 'sustituir'}, f'Sustituir el {os.path.basename(ruta_ap)[-7:]} que hay', 'btn peq', 'repetir',
                          'Guarda el subtítulo actual con «.antes-subrr» al final (los reproductores no lo ven) y traduce uno nuevo.'))
    if s == 'fallo' or v.get('r') in ('quitado', 'error', 'audio'):
        btns.append(boton('/episodio', {'k': k, 'c': clave, 'a': 'reintentar'}, 'Reintentar', 'btn peq', 'repetir'))
    if not ajeno:
        btns.append(boton('/episodio', {'k': k, 'c': clave, 'a': 'grabado'}, 'Buscar texto grabado', 'btn peq', 'buscar',
                          'Recorre el vídeo buscando subtítulos, rótulos y pantallas de texto grabados en la imagen, los traduce y los añade. '
                          'Tarda unos minutos.'))
    if nuestro_srt or v.get('dentro'):
        btns.append(boton('/episodio', {'k': k, 'c': clave, 'a': 'quitar'}, 'Quitar subtítulo', 'btn peq peligro', 'papelera',
                          'Quita lo que puso subrr (archivo aparte y/o pista del mkv) y no lo vuelve a hacer salvo que pulses Reintentar.'))
    return out + '<div class="btns">' + ''.join(btns) + '</div>'


def vista_actividad(filtro='todo'):
    r = C.leer(C.RESULTADOS, [])
    if filtro == 'ok':
        r = [x for x in r if x['ok']]
    elif filtro == 'ko':
        r = [x for x in r if not x['ok']]
    filtros = ''.join(f'<a href="/actividad?f={f}" class="{"on" if f == filtro else ""}">{t}</a>'
                      for f, t in (('todo', 'Todo'), ('ok', 'Traducidos'), ('ko', 'Problemas')))
    cab = f'<div class="cab"><div><h1>Actividad</h1><p class="sub">Lo último que ha hecho subrr.</p></div><div class="filtros">{filtros}</div></div>'
    if not r:
        return pagina('Actividad', cab + vacio('Sin actividad todavía', ''), '/actividad')
    dias = {}
    for x in r[:300]:
        dias.setdefault(x['fecha'][:10], []).append(x)
    hoy = time.strftime('%Y-%m-%d')
    out = cab
    for d, xs in dias.items():
        y, m, dd = d.split('-')
        out += f'<div class="dia eti">{"Hoy" if d == hoy else f"{int(dd)} de {MESES[int(m) - 1]}"}</div><div class="panel lista">'
        for x in xs:
            enlace = f' href="/item?k={quote(x["k"])}"' if x.get('k') else ''
            out += (f'<a class="act"{enlace}><div class="ico {"ok" if x["ok"] else "ko"}">{ic("ok" if x["ok"] else "aviso", 16)}</div>'
                    f'<div><div class="q"><b>{esc(x["item"])}</b> {esc(x["ep"] if x["ep"] != "pelicula" else "")} · {esc(x["texto"])}</div>'
                    f'<div class="d">{esc(x.get("detalle") or "")}</div></div><div class="h">{x["fecha"][11:]}</div></a>')
        out += '</div>'
    return pagina('Actividad', out, '/actividad')


# ---- ajustes
def subnav(activa):
    return '<div class="subnav">' + ''.join(f'<a href="{u}" class="{"on" if u == activa else ""}">{t}</a>' for u, t in
                                            (('/ajustes', 'General'), ('/ajustes/motores', 'Motores'), ('/ajustes/conexiones', 'Conexiones'))) + '</div>'


def vista_ajustes():
    aj = C.ajustes()
    grupos = ''
    for titulo, ancla, campos in CAMPOS:
        filas = ''.join(f'<div class="campo"><div><label>{et}</label><div class="ay">{ay}</div></div>'
                        f'<div>{control(cl, tp, opciones_lector() if cl == "ocr_motor" else op, aj[cl])}</div></div>'
                        for cl, et, ay, tp, op in campos)
        extra = ''
        if ancla == 'ocr':
            lec, dato = O.lector(aj)
            if lec == 'tesseract':
                extra = f'<div class="aviso ok">{ic("ok", 16)}Tesseract instalado · idiomas: {esc(", ".join(O.tesseract_idiomas()) or "?")}</div>'
            elif lec == 'vision':
                extra = f'<div class="aviso ok">{ic("ok", 16)}Leerá con {esc(dato["nombre"])}</div>'
            else:
                extra = f'<div class="aviso">{ic("aviso", 16)}{esc(dato)}</div>'
        if ancla == 'bazarr' and not bazarr.ok():
            extra = '<div class="aviso">' + ic('aviso', 16) + 'Bazarr no está conectado: configúralo en <a href="/ajustes/conexiones"><b>Conexiones</b></a>.</div>'
        grupos += f'<div class="grupo" id="{ancla}"><h3>{titulo}</h3>{extra}{filas}</div>'
    cuerpo = ('<div class="cab"><div><h1>Ajustes</h1><p class="sub">Para todas las series y películas (cada una puede cambiar algunos en su ficha).</p></div></div>'
              + subnav('/ajustes') + f'<form method="post" action="/ajustes" class="panel">{grupos}'
              '<div class="grupo"><button class="btn pri">Guardar</button></div></form>'
              f'<p class="meta" style="margin-top:18px">subrr {VERSION} · datos en <span class="mono">{esc(C.DATOS)}</span></p>')
    return pagina('Ajustes', cuerpo, '/ajustes')


def _papel(m):
    if not m.get('activo'):
        return '<span class="pildora off">desactivado</span>'
    if m.get('papel') == 'reserva':
        return '<span class="pildora res">reserva</span>'
    return '<span class="pildora pri">principal</span>'


def vista_motores():
    ms = C.cfg()['motores']
    filas = ''
    for i, m in enumerate(ms):
        t = M.TIPOS.get(m['tipo'], {'nombre': m['tipo']})
        ok, motivo = M.disponible(m)
        _, cupo_txt = M.cupo(m) if ok else (None, '')
        reglas = []
        if m.get('idiomas'):
            reglas.append('solo desde ' + m['idiomas'])
        if m.get('media', 'todo') != 'todo':
            reglas.append('solo ' + m['media'])
        if m.get('limite'):
            reglas.append(f"límite {int(m['limite']):,} car./mes".replace(',', '.'))
        detalle = ' · '.join([t['nombre']] + reglas + ([cupo_txt] if cupo_txt else []) + ([f'<span style="color:var(--err)">{esc(motivo)}</span>'] if not ok else []))
        filas += (f'<div class="motor"><div class="orden">'
                  f'<form method="post" action="/motor/mover"><input type="hidden" name="id" value="{m["id"]}"><input type="hidden" name="d" value="-1">'
                  f'<button {"disabled" if i == 0 else ""} title="Subir">{ic("arriba", 14)}</button></form>'
                  f'<form method="post" action="/motor/mover"><input type="hidden" name="id" value="{m["id"]}"><input type="hidden" name="d" value="1">'
                  f'<button {"disabled" if i == len(ms) - 1 else ""} title="Bajar">{ic("abajo", 14)}</button></form></div>'
                  f'<div><div class="n">{i + 1}. {esc(m["nombre"])}{_papel(m)}</div><div class="m">{detalle}</div>'
                  f'<div class="m" id="p-{m["id"]}"></div></div>'
                  f'<div class="btns"><button class="btn peq" data-probar="/api/probar/motor?id={m["id"]}" data-out="p-{m["id"]}">{ic("prueba", 16)}Probar</button>'
                  f'<a class="btn peq" href="/ajustes/motor?id={m["id"]}">{ic("editar", 16)}Editar</a></div></div>')
    if not filas:
        filas = vacio('Sin motores', 'Añade al menos uno. Una combinación que va bien: DeepL (gratis hasta 500.000 caracteres/mes) de principal y LibreTranslate local de reserva.')
    nuevos = ''.join(f'<a class="btn" href="/ajustes/motor?tipo={t}">{ic("mas", 16)}{esc(d["nombre"])}</a>' for t, d in M.TIPOS.items())
    cuerpo = ('<div class="cab"><div><h1>Ajustes</h1><p class="sub">Motores de traducción.</p></div></div>' + subnav('/ajustes/motores') +
              f'<div class="panel nota">{ic("motor", 18)}<div><b>Cómo se elige el motor:</b> se prueba el primero de la lista que valga para ese idioma de origen y '
              'tenga cupo; si falla o se queda sin cupo a mitad, sigue el siguiente desde donde iba. Los de <b>reserva</b> solo se usan si no queda ningún principal, '
              'y lo que hacen se marca como provisional para rehacerlo después. Cada serie puede elegir un motor preferido en su ficha.</div></div>'
              f'<div class="panel">{filas}</div><div class="seccion"><span class="eti">Añadir motor</span></div><div class="btns">{nuevos}</div>')
    return pagina('Motores', cuerpo, '/ajustes')


def vista_motor(mid='', tipo='', aviso=''):
    m = next((x for x in C.cfg()['motores'] if x['id'] == mid), None)
    if not m:
        if tipo not in M.TIPOS:
            return pagina('Motor', vacio('Ese motor no existe', '', '<a class="btn" href="/ajustes/motores">Volver</a>'))
        m = {'id': '', 'tipo': tipo, 'nombre': M.TIPOS[tipo]['nombre'], 'activo': True, 'papel': 'reserva' if tipo == 'libre' else 'principal',
             'idiomas': '', 'limite': 0, 'media': 'todo', 'campos': {}}
    t = M.TIPOS[m['tipo']]
    filas = ''
    for cl, et, tp, defecto, ay, ops in t['campos']:
        val = (m.get('campos') or {}).get(cl, '')
        if tp == 'secreto':
            guardada = bool(M.campo(m, cl, {'deepl': 'DEEPL_KEY', 'claude': 'ANTHROPIC_API_KEY', 'openai': 'OPENAI_API_KEY',
                                           'google': 'GOOGLE_TRANSLATE_KEY', 'azure': 'AZURE_TRANSLATOR_KEY',
                                           'libre': 'LIBRETRANSLATE_KEY'}.get(m['tipo'])))
            ctl = (f'<input type="password" name="c_{cl}" autocomplete="new-password" placeholder="{"guardada · vacío = no cambiarla, «-» = borrarla" if guardada else ""}">')
        elif tp == 'sel':
            ctl = f'<select name="c_{cl}">' + ''.join(f'<option value="{v}" {"selected" if (val or defecto) == v else ""}>{esc(x)}</option>' for v, x in ops) + '</select>'
        elif tp == 'largo':
            ctl = f'<textarea name="c_{cl}">{esc(val)}</textarea>'
        else:
            if cl == 'url':
                val = url_visible(val)
            ctl = f'<input type="text" name="c_{cl}" value="{esc(val)}" placeholder="{esc(defecto)}">'
        filas += f'<div class="campo"><div><label>{et}</label><div class="ay">{esc(ay)}</div></div><div>{ctl}</div></div>'
    reglas = (
        f'<div class="campo"><div><label>Nombre</label></div><div><input type="text" name="nombre" value="{esc(m["nombre"])}"></div></div>'
        f'<div class="campo"><div><label>Activo</label></div><div><label class="interruptor"><input type="checkbox" name="activo" value="1" {"checked" if m.get("activo") else ""}><i></i></label></div></div>'
        f'<div class="campo"><div><label>Papel</label><div class="ay">Reserva: solo si no queda ningún principal; lo que hace se marca como provisional.</div></div>'
        f'<div>{control("papel", "sel", (("principal", "Principal"), ("reserva", "Reserva")), m.get("papel", "principal"))}</div></div>'
        f'<div class="campo"><div><label>Solo desde estos idiomas</label><div class="ay">Idiomas de origen, separados por comas (p. ej. «ja,ko» para un LLM que va bien con anime). Vacío = todos.</div></div>'
        f'<div><input type="text" name="idiomas" value="{esc(m.get("idiomas", ""))}"></div></div>'
        f'<div class="campo"><div><label>Solo para</label></div><div>{control("media", "sel", (("todo", "Series y películas"), ("series", "Solo series"), ("peliculas", "Solo películas")), m.get("media", "todo"))}</div></div>'
        f'<div class="campo"><div><label>Límite al mes</label><div class="ay">Caracteres de origen al mes; al llegar, pasa al siguiente. 0 = sin límite. Un episodio son unos 25.000.</div></div>'
        f'<div><input type="number" min="0" name="limite" value="{int(m.get("limite") or 0)}"></div></div>')
    borrar = ''
    if m['id']:
        borrar = boton('/motor/borrar', {'id': m['id']}, 'Borrar motor', 'btn peligro', 'papelera', '¿Borrar este motor?')
    nota = (f'<div class="aviso">{ic("aviso", 16)}Has cambiado la dirección: por seguridad, la clave guardada se ha borrado. '
            'Vuelve a escribirla si hace falta.</div>' if aviso == 'clave' else '')
    cuerpo = (f'<a class="volver" href="/ajustes/motores">{ic("atras", 16)}Motores</a><div class="cab"><div><h1>{esc(m["nombre"])}</h1>'
              f'<p class="sub">{esc(t["ayuda"])}</p></div></div>{nota}'
              f'<form method="post" action="/motor" class="panel"><input type="hidden" name="id" value="{m["id"]}"><input type="hidden" name="tipo" value="{m["tipo"]}">'
              f'<div class="grupo"><h3>Conexión</h3>{filas}</div><div class="grupo"><h3>Cuándo se usa</h3>{reglas}</div>'
              f'<div class="grupo btns"><button class="btn pri">Guardar</button>'
              + (f'<button class="btn" data-probar="/api/probar/motor?id={m["id"]}" data-out="prueba">{ic("prueba", 16)}Probar</button><span id="prueba"></span>' if m['id'] else
                 '<span class="meta">Guárdalo para poder probarlo.</span>')
              + f'</div></form><div style="margin-top:16px">{borrar}</div>')
    return pagina(m['nombre'], cuerpo, '/ajustes')


def vista_conexiones(aviso=''):
    filas = ''
    guardado = C.cfg()['conexiones']
    for n, d in C.CONEXIONES.items():
        efectivo = C.conexion(n)
        campos = ''
        for cl, (var, defecto) in [(x, y) for x, y in d.items() if x != 'nombre']:
            if cl in C.SECRETOS:
                hay = bool(efectivo.get(cl))
                origen = '' if (guardado.get(n) or {}).get(cl) else (f' (de {var})' if hay else '')
                campos += (f'<input type="password" name="{n}_{cl}" autocomplete="new-password" '
                           f'placeholder="{("clave guardada" + origen + " · vacío = no cambiar, «-» = borrar") if hay else ("clave" if cl == "key" else "token (opcional)")}">')
            else:
                val = (guardado.get(n) or {}).get(cl, '')
                ph = efectivo.get(cl) or defecto or var
                if cl == 'url':
                    val, ph = url_visible(val), url_visible(ph)
                campos += f'<input type="text" name="{n}_{cl}" value="{esc(val)}" placeholder="{esc(ph)}">'
        filas += (f'<div class="conex"><div><b>{d["nombre"]}</b><div class="estado-c" id="c-{n}"></div></div>{campos}'
                  f'<button class="btn peq" data-probar="/api/probar/conexion?n={n}" data-out="c-{n}">Probar</button></div>')
    nota = ''
    if aviso:
        nombres = [C.CONEXIONES[x]['nombre'] for x in aviso.split(',') if x in C.CONEXIONES]
        if nombres:
            nota = (f'<div class="aviso">{ic("aviso", 16)}Has cambiado la dirección de {esc(", ".join(nombres))}: por seguridad, la clave guardada '
                    'se ha borrado y no se reutiliza con la dirección nueva. Vuelve a escribirla.</div>')
    # webhook de Sonarr/Radarr
    token = C.token_webhook()
    base = f'http://subrr:{C.PUERTO}/api/webhook'
    fijo = C.token_webhook_fijo()
    urls = ''.join(f'<div class="campo"><div><label>{t}</label></div><div><input type="text" readonly onfocus="this.select()" '
                   f'value="{esc(base)}/{n}?token={esc(token)}"></div></div>' for n, t in (('sonarr', 'URL para Sonarr'), ('radarr', 'URL para Radarr')))
    regenerar = ('<p class="meta">El token viene de la variable <span class="mono">SUBRR_WEBHOOK_TOKEN</span>.</p>' if fijo else
                 boton('/webhook/token', {}, 'Generar un token nuevo', 'btn peq peligro', 'repetir',
                       'Los webhooks que ya tengas en Sonarr/Radarr dejarán de funcionar hasta que cambies su URL.'))
    webhook = (f'<div class="panel"><div class="grupo"><h3>Webhook de Sonarr y Radarr</h3>'
               '<p>Para traducir al momento lo que importen (en vez de esperar a la siguiente pasada): en Sonarr/Radarr, Ajustes → Connect → Webhook, '
               'pega la URL, método POST, y marca solo «On Import» y «On Upgrade». Cambia «subrr» por el nombre del contenedor si es otro. '
               'Quien tenga esta URL puede pedir traducciones: no la compartas.</p>'
               f'{urls}{regenerar}</div></div>')
    cuerpo = ('<div class="cab"><div><h1>Ajustes</h1><p class="sub">Conexiones con otros servicios.</p></div></div>' + subnav('/ajustes/conexiones') + nota +
              f'<form method="post" action="/conexiones" class="panel"><div class="grupo"><p>Lo que dejes vacío se toma de las variables de entorno '
              f'(SONARR_URL, SONARR_KEY…). Las claves nunca se muestran. Si cambias una dirección y no escribes la clave, la guardada se borra '
              f'(no se envía a la dirección nueva).</p>{filas}</div>'
              '<div class="grupo"><button class="btn pri">Guardar</button></div></form>' + webhook)
    return pagina('Conexiones', cuerpo, '/ajustes')


# ------------------------------------------------------------------------------------------------ formularios
def _uno(campos, n, d=''):
    return (campos.get(n) or [d])[0]


def anadir_web(campos):
    k = _uno(campos, 'k')
    tipo, id_ = k.split(':')
    temps = sorted({int(x) for x in campos.get('t', [])})
    if tipo == 'sonarr':
        s = sonarr.get(f'series/{int(id_)}')
        nuevo = {'tipo': 'serie', 'id': int(id_), 'titulo': s['title'], 'anio': s.get('year'), 'temporadas': temps, 'modo': 'temporadas'}
    else:
        m = radarr.get(f'movie/{int(id_)}')
        nuevo = {'tipo': 'pelicula', 'id': int(id_), 'titulo': m['title'], 'anio': m.get('year'), 'modo': 'temporadas'}

    def fn(c):
        if tipo == 'sonarr' and not temps:
            c['items'].pop(k, None)
            return
        viejo = c['items'].get(k, {})
        c['items'][k] = {**viejo, **nuevo, 'desde': viejo.get('desde') or time.strftime('%Y-%m-%d')}
    C.cambiar_cfg(fn)
    C.despertar.set()
    return f'/item?k={quote(k)}' if (tipo != 'sonarr' or temps) else '/'


def item_web(campos):
    k, a = _uno(campos, 'k'), _uno(campos, 'a')
    if a in ('pausar', 'reanudar'):
        def fn(c):
            if k in c['items']:
                c['items'][k]['fase'] = 'pausado' if a == 'pausar' else 'activo'
        C.cambiar_cfg(fn)
        C.despertar.set()
    elif a == 'quitar':
        C.cambiar_cfg(lambda c: c['items'].pop(k, None))
        return '/'
    elif a == 'reintentar_fallos':
        it = C.cfg()['items'].get(k)
        est = C.estado()
        for e in episodios_cache(it, 0):
            if T.elegido(it, e, est) and (estado_ep(e, est)[0] == 'fallo' or (est.get(e['path']) or {}).get('r') == 'audio'):
                C.pedir_accion(k, e['clave'], 'reintentar')
    elif a == 'ajustes':
        nuevos = {}
        for cl in C.POR_ITEM:
            v = _uno(campos, cl).strip()
            if v == '':
                continue
            if cl in ('quitar_sdh', 'saltar_audio', 'por_defecto'):
                nuevos[cl] = v == '1'
            elif cl == 'prioridad':
                nuevos[cl] = ','.join(x.strip().lower() for x in v.split(',') if S.corto(x.strip())) or None
            else:
                nuevos[cl] = v

        def fn(c):
            if k in c['items']:
                c['items'][k]['ajustes'] = {x: y for x, y in nuevos.items() if y not in (None, '')}
        C.cambiar_cfg(fn)
        C.despertar.set()
    return f'/item?k={quote(k)}'


def episodio_web(campos):
    k, clave, a = _uno(campos, 'k'), _uno(campos, 'c'), _uno(campos, 'a')
    if a == 'rehacer':
        pista = _uno(campos, 'pista')
        C.pedir_accion(k, clave, 'rehacer' + ('|' + pista if pista else ''))
    elif a in ('reintentar', 'quitar', 'sustituir', 'grabado'):
        C.pedir_accion(k, clave, a)
    return f'/item?k={quote(k)}'


def ajustes_web(campos):
    nuevos = {}
    for _, _, cs in CAMPOS:
        for cl, _, _, tp, ops in cs:
            v = _uno(campos, cl)
            if tp == 'sw':
                nuevos[cl] = v == '1'
            elif tp == 'sel':
                if v in dict(opciones_lector() if cl == 'ocr_motor' else ops):
                    nuevos[cl] = v
            elif tp == 'num':
                try:
                    nuevos[cl] = max(0, int(float(v)))
                except ValueError:
                    pass
            elif cl == 'prioridad':
                nuevos[cl] = ','.join(x.strip().lower() for x in v.split(',') if S.corto(x.strip())) or C.AJUSTES_DEFECTO[cl]
            else:
                nuevos[cl] = v.strip()
    if not nuevos.get('nombre_pista') or 'subrr' not in nuevos['nombre_pista'].lower():
        nuevos['nombre_pista'] = (nuevos.get('nombre_pista') or '{idioma}') + ' (subrr)'
    C.cambiar_cfg(lambda c: c['ajustes'].update(nuevos))
    C.despertar.set()
    return '/ajustes'


def motor_web(campos):
    mid, tipo = _uno(campos, 'id'), _uno(campos, 'tipo')
    if tipo not in M.TIPOS:
        return '/ajustes/motores'

    def fn(c):
        m = next((x for x in c['motores'] if x['id'] == mid), None)
        antes = M.url_efectiva(m) if m else None
        if not m:
            m = {'id': C.nuevo_id(), 'tipo': tipo, 'campos': {}}
            c['motores'].append(m)
        m['nombre'] = _uno(campos, 'nombre').strip() or M.TIPOS[tipo]['nombre']
        m['activo'] = _uno(campos, 'activo') == '1'
        m['papel'] = 'reserva' if _uno(campos, 'papel') == 'reserva' else 'principal'
        m['idiomas'] = ','.join(S.corto(x.strip()) for x in _uno(campos, 'idiomas').split(',') if S.corto(x.strip()))
        m['media'] = _uno(campos, 'media') if _uno(campos, 'media') in ('todo', 'series', 'peliculas') else 'todo'
        try:
            m['limite'] = max(0, int(float(_uno(campos, 'limite') or 0)))
        except ValueError:
            m['limite'] = 0
        for cl, _, tp, _, _, _ in M.TIPOS[tipo]['campos']:
            if tp != 'secreto':
                v = _uno(campos, 'c_' + cl).strip()
                m['campos'][cl] = url_valida(v) if cl == 'url' else v
        cambio = antes is not None and M.url_efectiva(m) != antes
        borrada = False
        for cl, _, tp, _, _, _ in M.TIPOS[tipo]['campos']:
            if tp == 'secreto':
                v = _uno(campos, 'c_' + cl).strip()
                if v == '-':
                    m['campos'].pop(cl, None)
                elif v:
                    m['campos'][cl] = v
                elif cambio and m['campos'].pop(cl, None):      # dirección nueva y clave vacía: no se reutiliza la guardada
                    borrada = True
        return m['id'], borrada
    nid, borrada = C.cambiar_cfg(fn)
    C.despertar.set()
    return f'/ajustes/motor?id={nid}' + ('&aviso=clave' if borrada else '')


def motor_mover(campos):
    mid, d = _uno(campos, 'id'), int(_uno(campos, 'd', '0'))

    def fn(c):
        ms = c['motores']
        i = next((n for n, x in enumerate(ms) if x['id'] == mid), None)
        if i is not None and 0 <= i + d < len(ms):
            ms[i], ms[i + d] = ms[i + d], ms[i]
    C.cambiar_cfg(fn)
    return '/ajustes/motores'


def motor_borrar(campos):
    mid = _uno(campos, 'id')
    C.cambiar_cfg(lambda c: c.__setitem__('motores', [x for x in c['motores'] if x['id'] != mid]))
    return '/ajustes/motores'


def conexiones_web(campos):
    def fn(c):
        borradas = []
        for n, d in C.CONEXIONES.items():
            g = c['conexiones'].setdefault(n, {})
            antes = C._valores(n, g)['url']
            for cl in d:
                if cl != 'nombre' and cl not in C.SECRETOS:
                    v = _uno(campos, f'{n}_{cl}').strip()
                    g[cl] = url_valida(v) if cl == 'url' else v
            cambio = C._valores(n, g)['url'] != antes
            for cl in d:
                if cl in C.SECRETOS:
                    v = _uno(campos, f'{n}_{cl}').strip()
                    if v == '-':
                        g.pop(cl, None)
                    elif v:
                        g[cl] = v
                    elif cambio and g.pop(cl, None):          # dirección nueva y clave vacía: no se reutiliza la guardada
                        borradas.append(n)
        return borradas
    borradas = C.cambiar_cfg(fn)
    C.despertar.set()
    return '/ajustes/conexiones' + ('?aviso=' + ','.join(sorted(set(borradas))) if borradas else '')


def webhook_token_web(campos):
    C.regenerar_token_webhook()
    return '/ajustes/conexiones'


# ------------------------------------------------------------------------------------------------ servidor
MAX_FORM = 2 * 1024 * 1024          # tamaño máximo del cuerpo de un formulario de la web
MAX_WEBHOOK = 8 * 1024 * 1024       # y de un aviso de Sonarr/Radarr (series enormes traen muchos episodios)
WEBHOOKS = {'/api/webhook/sonarr': 'sonarr', '/api/webhook/radarr': 'radarr'}


class Web(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cabeceras_seguras(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
        self.send_header('Referrer-Policy', 'same-origin')

    def _enviar(self, cuerpo, tipo='text/html; charset=utf-8', codigo=200, cache=None, extra=None):
        if isinstance(cuerpo, str):
            cuerpo = C.ocultar(cuerpo)           # nunca sale una clave guardada, ni siquiera dentro de un mensaje de error
        b = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode()
        self.send_response(codigo)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', cache or 'no-store')
        self._cabeceras_seguras()
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _json(self, d, codigo=200):
        self._enviar(json.dumps(d, ensure_ascii=False), 'application/json', codigo)

    # ---- seguridad
    def _credenciales(self):
        """(usuario, contraseña) de la cabecera HTTP Basic, o ('', '')."""
        h = self.headers.get('Authorization') or ''
        if h[:6].lower() == 'basic ':
            try:
                u, _, pw = base64.b64decode(h[6:].strip()).decode('utf-8').partition(':')
                return u, pw
            except Exception:
                pass
        return '', ''

    def _con_permiso(self):
        """Contraseña de la web (SUBRR_PASSWORD, opcional). Responde 401 y devuelve False si falta o no vale."""
        if not C.PASSWORD:
            return True
        u, pw = self._credenciales()
        ok_pw = C.iguales(pw, C.PASSWORD)
        ok_u = C.iguales(u, C.USUARIO) if C.USUARIO else True
        if ok_pw and ok_u:
            return True
        self._enviar('Hace falta usuario y contraseña', 'text/plain; charset=utf-8', 401, extra={'WWW-Authenticate': 'Basic realm="subrr", charset="UTF-8"'})
        return False

    def _origen_valido(self):
        """Anti-CSRF de los POST de la web: Origin (o Referer) tiene que ser este mismo servidor. Sin ninguno de los dos solo vale
        con la clave de API de la web en la cabecera X-Api-Key: la contraseña si hay SUBRR_PASSWORD (así el token del webhook, que viaja
        en URLs, no da control de los ajustes) y, si no hay contraseña, el token del webhook."""
        permitidos = {(self.headers.get('Host') or '').lower()} | C.ORIGENES_EXTRA
        for cab in ('Origin', 'Referer'):
            v = self.headers.get(cab)
            if v:
                return urlparse(v).netloc.lower() in permitidos - {''}
        clave = self.headers.get('X-Api-Key') or ''
        return bool(clave) and C.iguales(clave, C.PASSWORD or C.token_webhook())

    def _token_valido(self, q):
        """Token de un webhook: ?token=…, cabecera X-Api-Key o la contraseña de HTTP Basic (Sonarr/Radarr pueden mandar usuario y contraseña)."""
        token = C.token_webhook()
        ok = False
        for cand in (_uno(q, 'token'), self.headers.get('X-Api-Key') or '', self._credenciales()[1]):
            ok = (bool(cand) and C.iguales(cand, token)) or ok       # sin cortocircuito: tarda lo mismo acierte o no
        return ok

    def _leer_cuerpo(self, maximo):
        try:
            largo = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            largo = -1
        if largo < 0 or largo > maximo:
            self._enviar('Cuerpo demasiado grande o no válido', 'text/plain; charset=utf-8', 413)
            return None
        return self.rfile.read(largo)

    def do_GET(self):
        u = urlparse(self.path)
        ruta, q = u.path, parse_qs(u.query)
        try:
            if ruta == '/salud':
                return self._enviar('ok', 'text/plain')
            if not self._con_permiso():
                return
            if ruta == '/favicon.svg':
                return self._enviar(FAVICON, 'image/svg+xml', cache='max-age=86400')
            if ruta == '/api/vivo':
                return self._json({**C.vivo, 'cola': len(C.acciones_pendientes())})
            if ruta == '/api/estado':
                est = C.estado()
                return self._json({'trabajando': C.vivo['trabajando'], 'traducidos': sum(1 for v in est.values() if v.get('r') == 'hecho'),
                                   'pendientes_accion': len(C.acciones_pendientes())})
            if ruta == '/api/ep':
                return self._enviar(fragmento_ep(_uno(q, 'k'), _uno(q, 'c')))
            if ruta.startswith('/img/'):
                partes = ruta.split('/')
                if len(partes) != 5 or partes[2] not in ('sonarr', 'radarr') or partes[4] not in ('poster', 'fanart') or not partes[3].isdigit():
                    return self._enviar('no', 'text/plain', 404)
                datos = caratula(partes[2], int(partes[3]), partes[4])
                return self._enviar(datos, 'image/jpeg', cache='max-age=86400') if datos else self._enviar('', 'text/plain', 404)
            if ruta == '/item':
                return self._enviar(vista_item(_uno(q, 'k')))
            if ruta == '/actividad':
                return self._enviar(vista_actividad(_uno(q, 'f', 'todo')))
            if ruta == '/ajustes/motor':
                return self._enviar(vista_motor(_uno(q, 'id'), _uno(q, 'tipo'), _uno(q, 'aviso')))
            if ruta == '/ajustes/conexiones':
                return self._enviar(vista_conexiones(_uno(q, 'aviso')))
            vista = {'/': vista_biblioteca, '/anadir': vista_anadir, '/ajustes': vista_ajustes, '/ajustes/motores': vista_motores}.get(ruta)
            if not vista:
                return self._enviar(pagina('No existe', vacio('Esta página no existe', '', '<a class="btn" href="/">Volver</a>')), codigo=404)
            self._enviar(vista())
        except Exception as ex:
            traceback.print_exc()
            self._enviar(pagina('Error', vacio('Algo ha fallado', f'<span class="mono">{esc(str(ex))}</span>')), codigo=500)

    def _webhook(self, origen, q):
        """Aviso de Sonarr/Radarr: se autentica con su token, no con la contraseña de la web."""
        if not self._token_valido(q):
            return self._json({'ok': False, 'error': 'token no válido'}, 401)
        cuerpo = self._leer_cuerpo(MAX_WEBHOOK)
        if cuerpo is None:
            return
        try:
            datos = json.loads(cuerpo or b'{}')
        except ValueError:
            return self._json({'ok': False, 'error': 'JSON no válido'}, 400)
        try:
            codigo, r = W.manejar(origen, datos)
        except Exception as ex:
            traceback.print_exc()
            return self._json({'ok': False, 'error': str(ex)[:200]}, 500)
        self._json(r, codigo)

    def do_POST(self):
        u = urlparse(self.path)
        ruta, q = u.path, parse_qs(u.query)
        if ruta in WEBHOOKS:
            return self._webhook(WEBHOOKS[ruta], q)
        if not self._con_permiso():
            return
        if not self._origen_valido():
            return self._enviar('Petición rechazada: no viene de esta web (Origin/Referer no coinciden con el servidor)', 'text/plain; charset=utf-8', 403)
        cuerpo = self._leer_cuerpo(MAX_FORM)
        if cuerpo is None:
            return
        campos = parse_qs(cuerpo.decode('utf-8', 'replace'), keep_blank_values=True)
        try:
            if ruta == '/api/probar/motor':
                m = next((x for x in C.cfg()['motores'] if x['id'] == _uno(q, 'id')), None)
                if not m:
                    return self._json({'ok': False, 'texto': 'no existe'})
                ok, texto = M.probar(m, T.destino_de(C.ajustes()))
                return self._json({'ok': ok, 'texto': texto})
            if ruta == '/api/probar/conexion':
                n = _uno(q, 'n')
                if n not in C.CONEXIONES:
                    return self._json({'ok': False, 'texto': 'no existe'})
                ok, texto = probar_conexion(n)
                return self._json({'ok': ok, 'texto': texto})
        except Exception as ex:
            traceback.print_exc()
            return self._json({'ok': False, 'texto': str(ex)[:200]})
        fn = {'/anadir': anadir_web, '/item': item_web, '/episodio': episodio_web, '/ajustes': ajustes_web, '/motor': motor_web,
              '/motor/mover': motor_mover, '/motor/borrar': motor_borrar, '/conexiones': conexiones_web,
              '/webhook/token': webhook_token_web}.get(ruta)
        if not fn:
            return self._enviar('no', 'text/plain', 404)
        try:
            destino = fn(campos)
        except Exception as ex:
            traceback.print_exc()
            return self._enviar(pagina('Error', vacio('Algo ha fallado', f'<span class="mono">{esc(str(ex))}</span>')), codigo=500)
        self.send_response(303)
        self.send_header('Location', destino)
        self._cabeceras_seguras()
        self.end_headers()


def servir():
    ThreadingHTTPServer((C.BIND, C.PUERTO), Web).serve_forever()
