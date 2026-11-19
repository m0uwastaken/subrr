"""Dónde acaba la traducción: archivo aparte, pista dentro del mkv o entregada a Bazarr.

Reglas de seguridad:
- Nunca se modifica un archivo existente: se escribe un .tmp y se renombra.
- Solo se sobrescribe un subtítulo aparte si lo escribió subrr (se guarda su tamaño y fecha).
- Para meter la pista en el mkv se crea un mkv nuevo. Si el vídeo tiene enlaces duros (p. ej. un torrent que se sigue
  compartiendo) no se hace salvo que se active «enlaces_duros», y entonces el torrent conserva su archivo.
- Antes de sustituir el vídeo, el original se guarda en la papelera (enlace duro si se puede) los días configurados.
"""
import json, os, shutil, subprocess, time

from . import config as C
from . import subs as S
from .servicios import bazarr, jellyfin_avisar


def ruta_aparte(video, code2):
    return os.path.splitext(video)[0] + f'.{code2}.srt'


def es_nuestro_aparte(ruta, v):
    return bool(v and v.get('srt') == ruta and v.get('srt_huella') and v['srt_huella'] == C.huella(ruta))


# ---------------------------------------------------------------- papelera
def _raiz_montaje(p):
    p = os.path.abspath(p)
    while not os.path.ismount(p):
        p = os.path.dirname(p)
    return p


def carpeta_papelera(video, aj):
    return aj['papelera'] or os.path.join(_raiz_montaje(video), '.subrr-papelera')


def a_papelera(video, aj):
    """Guarda el vídeo original (enlace duro; si no se puede, copia). Devuelve la ruta o None."""
    if int(aj['papelera_dias'] or 0) <= 0:
        return None
    d = os.path.join(carpeta_papelera(video, aj), time.strftime('%Y%m%d-%H%M%S'))
    os.makedirs(d, exist_ok=True)
    dest = os.path.join(d, os.path.basename(video))
    try:
        os.link(video, dest)
    except OSError:
        shutil.copy2(video, dest)
    with open(dest + '.json', 'w') as fh:
        json.dump({'original': video, 'fecha': time.time()}, fh, ensure_ascii=False)
    return dest


def purgar_papelera(dias, carpetas):
    if dias <= 0:          # 0 = no se guardan originales; lo que hubiera de antes no se toca
        return
    limite = time.time() - dias * 86400
    for raiz in carpetas:
        if not os.path.isdir(raiz):
            continue
        for d in os.listdir(raiz):
            ruta = os.path.join(raiz, d)
            try:
                if os.path.isdir(ruta) and os.path.getmtime(ruta) < limite:
                    shutil.rmtree(ruta)
                    C.log('papelera: borrado', ruta)
            except OSError as e:
                C.log('papelera: no pude borrar', ruta, e)


# ---------------------------------------------------------------- mkv
def _pistas_mkv(video):
    r = subprocess.run(['mkvmerge', '-J', video], capture_output=True, text=True, timeout=120)
    if r.returncode not in (0, 1):
        raise RuntimeError('mkvmerge no puede leer el vídeo: ' + r.stdout[-200:])
    return json.loads(r.stdout).get('tracks', [])


def meter_en_mkv(video, srt, destino, aj):
    """Crea un mkv nuevo con la pista traducida como primera de subtítulos y lo pone en lugar del original.
    Quita la pista anterior de subrr si la hubiera. Devuelve la ruta de la papelera (o None)."""
    pistas = _pistas_mkv(video)
    viejas = [t['id'] for t in pistas if t['type'] == 'subtitles' and 'subrr' in (t['properties'].get('track_name') or '').lower()]
    subs = [t['id'] for t in pistas if t['type'] == 'subtitles' and t['id'] not in viejas]
    resto = [t['id'] for t in pistas if t['type'] != 'subtitles']
    orden = [f'0:{i}' for i in resto] + ['1:0'] + [f'0:{i}' for i in subs]
    nombre = aj['nombre_pista'].replace('{idioma}', destino['nombre'])
    cmd = ['mkvmerge', '-q', '-o', video + '.subrr.tmp']
    if viejas:
        cmd += ['-s', '!' + ','.join(map(str, viejas))]
    if aj['por_defecto']:
        for i in subs:
            cmd += ['--default-track-flag', f'{i}:no']
    cmd += [video, '--language', f"0:{destino['code3']}", '--track-name', f'0:{nombre}', '--sub-charset', '0:UTF-8',
            '--default-track-flag', f"0:{'yes' if aj['por_defecto'] else 'no'}", srt, '--track-order', ','.join(orden)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode not in (0, 1):            # 1 = avisos
        try:
            os.remove(video + '.subrr.tmp')
        except OSError:
            pass
        raise RuntimeError('mkvmerge falló: ' + (r.stdout + r.stderr)[-300:])
    st = os.stat(video)
    papelera = a_papelera(video, aj)
    try:
        os.chmod(video + '.subrr.tmp', st.st_mode & 0o777)
    except OSError:
        pass
    os.replace(video + '.subrr.tmp', video)
    return papelera


# ---------------------------------------------------------------- guardar
def guardar(it, e, cues, destino, aj, v_ant):
    """Guarda la traducción según aj['salida'] y avisa a Bazarr/Jellyfin. Devuelve dict con lo hecho (para el estado)."""
    video = e['path']
    hecho = {'notas': []}
    os.makedirs(C.TMP, exist_ok=True)
    tmp = os.path.join(C.TMP, f"{C.seguro(it['titulo'])}-{e['clave']}.{destino['code2']}.srt")
    S.escribir(cues, tmp)
    salida = aj['salida']
    meter = salida in ('dentro', 'ambos')
    if meter and not video.lower().endswith('.mkv'):
        meter = False
        hecho['notas'].append('No es mkv: se guarda aparte')
        salida = 'aparte'
    if meter and os.stat(video).st_nlink > 1 and not aj['enlaces_duros']:
        meter = False
        hecho['notas'].append('El vídeo tiene enlaces duros (¿torrent compartiendo?): se guarda aparte')
        salida = 'aparte'
    aparte = salida in ('aparte', 'ambos') or not meter
    entregado = False

    if aparte:
        ruta = ruta_aparte(video, destino['code2'])
        if os.path.exists(ruta) and not es_nuestro_aparte(ruta, v_ant):
            raise RuntimeError(f'Ya hay un {os.path.basename(ruta)} que no es de subrr')
        if bazarr.ok() and aj['bazarr_entrega'] == 'subir' and (e.get('epid') or it['tipo'] == 'pelicula'):
            try:
                if os.path.exists(ruta):
                    os.remove(ruta)            # el nuestro de antes: que Bazarr ponga el nuevo
                with open(tmp, 'rb') as fh:
                    bazarr.subir(it, e.get('epid'), destino['code2'], os.path.basename(ruta), fh.read())
                rutas = [C.ruta_local(p) for p in bazarr.subtitulos_de(it, e.get('epid'))]
                cand = [p for p in rutas if os.path.exists(p) and os.path.basename(p).startswith(os.path.splitext(os.path.basename(video))[0])
                        and f".{destino['code2']}." in os.path.basename(p)]
                ruta = max(cand, key=os.path.getmtime) if cand else ruta
                entregado = True
                hecho['notas'].append('Entregado a Bazarr')
            except Exception as ex:
                hecho['notas'].append(f'Bazarr no lo aceptó ({str(ex)[:100]}): lo guardo yo')
        if not entregado:
            shutil.copyfile(tmp, ruta + '.tmp')
            os.replace(ruta + '.tmp', ruta)
            try:
                os.chmod(ruta, 0o664)
            except OSError:
                pass
        hecho['srt'] = ruta
        hecho['srt_huella'] = C.huella(ruta)
    if meter:
        hecho['papelera'] = meter_en_mkv(video, tmp, destino, aj)
        hecho['dentro'] = True
    try:
        os.remove(tmp)
    except OSError:
        pass

    if bazarr.ok() and not entregado:
        try:
            bazarr.escanear(it)
        except Exception as ex:
            hecho['notas'].append(f'Bazarr no respondió al escanear ({str(ex)[:80]})')
    try:
        if jellyfin_avisar(video):
            hecho['notas'].append('Jellyfin avisado')
    except Exception as ex:
        hecho['notas'].append(f'Jellyfin no respondió ({str(ex)[:80]})')
    return hecho


def quitar(it, e, v):
    """Quita lo que puso subrr: el .srt aparte (si sigue siendo el nuestro) y/o la pista del mkv."""
    video = e['path']
    hecho = []
    if v.get('srt') and es_nuestro_aparte(v['srt'], v):
        os.remove(v['srt'])
        hecho.append('archivo aparte')
    if v.get('dentro') and video.lower().endswith('.mkv'):
        pistas = _pistas_mkv(video)
        viejas = [t['id'] for t in pistas if t['type'] == 'subtitles' and 'subrr' in (t['properties'].get('track_name') or '').lower()]
        if viejas:
            r = subprocess.run(['mkvmerge', '-q', '-o', video + '.subrr.tmp', '-s', '!' + ','.join(map(str, viejas)), video],
                               capture_output=True, text=True, timeout=3600)
            if r.returncode not in (0, 1):
                raise RuntimeError('mkvmerge falló: ' + (r.stdout + r.stderr)[-300:])
            a_papelera(video, C.ajustes(it))
            os.replace(video + '.subrr.tmp', video)
            hecho.append('pista del mkv')
    if bazarr.ok():
        try:
            bazarr.escanear(it)
        except Exception:
            pass
    return hecho
