"""Webhooks de Sonarr y Radarr (Ajustes → Connect → Webhook en la app *arr).

Cuando *arr importa (o mejora) un archivo, avisa aquí y subrr traduce ese episodio/película al momento en vez de esperar
a la siguiente pasada. Solo se encola lo que ya esté activado en subrr (serie con esa temporada elegida, o película añadida).
El trabajo lo hace el trabajador de siempre a través de la cola de acciones (config.pedir_accion): este módulo solo encola.

Eventos de Sonarr y Radarr que cuentan: «Download» (importación y actualización) y «ImportComplete» (Sonarr v4).
«Test» responde 200 sin hacer nada y cualquier otro evento (Grab, Rename, EpisodeFileDelete, MovieFileDelete, Health…) se ignora con 200.
"""
import os

from . import config as C
from . import trabajador as T

EVENTOS_IMPORTAR = {'download', 'importcomplete'}


def _entero(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _rutas(p):
    """Rutas de archivo que trae el aviso, tal como las ve *arr."""
    fs = []
    for k in ('episodeFile', 'movieFile'):
        if isinstance(p.get(k), dict):
            fs.append(p[k])
    for k in ('episodeFiles', 'movieFiles'):
        if isinstance(p.get(k), list):
            fs += [f for f in p[k] if isinstance(f, dict)]
    return [f['path'] for f in fs if f.get('path')]


def _claves(origen, p):
    """(k del item en subrr, [(clave de episodio, temporada o None)]) o None si el aviso no trae lo necesario."""
    if origen == 'sonarr':
        id_ = _entero((p.get('series') or {}).get('id'))
        eps = []
        for e in p.get('episodes') or []:
            t, n = _entero(e.get('seasonNumber')), _entero(e.get('episodeNumber'))
            if t is not None and n is not None:
                eps.append((f'S{t:02d}E{n:02d}', t))
        return (f'sonarr:{id_}', eps) if id_ is not None and eps else None
    id_ = _entero((p.get('movie') or {}).get('id'))
    return (f'radarr:{id_}', [('pelicula', None)]) if id_ is not None else None


def manejar(origen, p):
    """Procesa un aviso ya autenticado. origen: 'sonarr' | 'radarr'. Devuelve (código HTTP, dict para el JSON)."""
    if not isinstance(p, dict):
        return 400, {'ok': False, 'error': 'el cuerpo no es un objeto JSON'}
    evento = str(p.get('eventType') or '')
    if evento.lower() == 'test':
        C.log(f'webhook de {origen}: prueba recibida')
        return 200, {'ok': True, 'evento': 'Test'}
    if evento.lower() not in EVENTOS_IMPORTAR:
        return 200, {'ok': True, 'ignorado': evento or 'sin evento'}
    cl = _claves(origen, p)
    if not cl:
        return 200, {'ok': True, 'ignorado': 'el aviso no trae serie/película o episodios'}
    k, eps = cl
    aj = C.ajustes()
    it = C.cfg()['items'].get(k)
    if aj['bazarr_auto'] and not aj['bazarr_dias']:
        C.despertar.set()              # modo Bazarr sin espera: que mire ya lo que falta
    if not it:
        return 200, {'ok': True, 'ignorado': 'no está activado en subrr'}
    if it.get('fase') == 'pausado':
        return 200, {'ok': True, 'ignorado': 'en pausa'}
    if it.get('modo') == 'bazarr':
        return 200, {'ok': True, 'ignorado': 'lo gestiona el modo Bazarr (espera los días configurados)'}
    pendientes = {(a['item'], a['clave']) for a in C.acciones_pendientes()}
    encolados, saltados = [], []
    for clave, temporada in eps:
        if not T.elegido(it, {'temporada': temporada, 'epid': None, 'path': None}):
            saltados.append(clave)
        elif (k, clave) not in pendientes:      # no pisar lo que el usuario haya pedido a mano
            C.pedir_accion(k, clave, 'nuevo')
            encolados.append(clave)
    avisos = []
    for ruta in _rutas(p):
        local = C.ruta_local(ruta)
        if not os.path.exists(local):
            avisos.append(f'subrr no ve el archivo en «{local}»: revisa el mapeo de rutas (Ajustes → General → Rutas)')
    if avisos:
        C.log('webhook de', origen, '·', it['titulo'], '·', avisos[0])
    return 200, {'ok': True, 'encolados': encolados, 'no_elegidos': saltados, **({'avisos': avisos} if avisos else {})}
