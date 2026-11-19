"""Clientes de Sonarr, Radarr (API v3), Bazarr, Jellyfin/Emby y ntfy. Las direcciones y claves salen de config.conexion()."""
import json, os, time, urllib.error, urllib.parse, urllib.request, uuid

from . import config as C


def _req(metodo, url, cabeceras=None, datos=None, timeout=60, crudo=False, tipo='application/json'):
    cuerpo = None
    if datos is not None:
        cuerpo = datos if isinstance(datos, bytes) else json.dumps(datos).encode()
    req = urllib.request.Request(url, data=cuerpo, method=metodo, headers={'Content-Type': tipo, **(cabeceras or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        t = r.read()
        if crudo:
            return t, r.headers
        return json.loads(t) if t else None


class Arr:
    def __init__(self, nombre):
        self.nombre = nombre

    @property
    def c(self):
        return C.conexion(self.nombre)

    def ok(self):
        c = self.c
        return bool(c['url'] and c['key'])

    def get(self, ruta, **q):
        c = self.c
        url = f"{c['url']}/api/v3/{ruta}" + ('?' + urllib.parse.urlencode(q) if q else '')
        return _req('GET', url, {'X-Api-Key': c['key']})

    def caratula(self, id_, clase):
        c = self.c
        tam = '-500' if clase == 'poster' else '-360'
        datos, cab = _req('GET', f"{c['url']}/api/v3/mediacover/{int(id_)}/{clase}{tam}.jpg", {'X-Api-Key': c['key']}, timeout=15, crudo=True)
        if not cab.get('Content-Type', '').startswith('image'):
            raise ValueError('no es una imagen')
        return datos


sonarr, radarr = Arr('sonarr'), Arr('radarr')


# ---------------------------------------------------------------- Bazarr
class Bazarr:
    @property
    def c(self):
        return C.conexion('bazarr')

    def ok(self):
        c = self.c
        return bool(c['url'] and c['key'])

    def _url(self, ruta, q=None):
        return f"{self.c['url']}/api/{ruta}" + ('?' + urllib.parse.urlencode(q, doseq=True) if q else '')

    def get(self, ruta, **q):
        return _req('GET', self._url(ruta, q), {'X-API-KEY': self.c['key']})

    def estado(self):
        return self.get('system/status')

    def wanted(self, tipo):
        """Todo lo que Bazarr echa de menos. tipo: 'episodes' | 'movies'."""
        out, inicio = [], 0
        while True:
            r = self.get(f'{tipo}/wanted', start=inicio, length=200)
            datos = r.get('data', [])
            out += datos
            inicio += len(datos)
            if not datos or inicio >= r.get('total', 0):
                return out

    def escanear(self, item):
        """Que Bazarr vuelva a mirar el disco de esta serie/película (y vea el subtítulo nuevo)."""
        if item['tipo'] == 'serie':
            q = {'seriesid': item['id'], 'action': 'scan-disk'}
            ruta = 'series'
        else:
            q = {'radarrid': item['id'], 'action': 'scan-disk'}
            ruta = 'movies'
        _req('PATCH', self._url(ruta, q), {'X-API-KEY': self.c['key']})

    def subir(self, item, epid, code2, nombre, contenido):
        """Entrega el subtítulo a Bazarr: él lo guarda con su nombre de archivo y lo apunta en su historial."""
        frontera = uuid.uuid4().hex
        cuerpo = (f'--{frontera}\r\nContent-Disposition: form-data; name="file"; filename="{nombre}"\r\n'
                  f'Content-Type: application/x-subrip\r\n\r\n').encode() + contenido + f'\r\n--{frontera}--\r\n'.encode()
        if item['tipo'] == 'serie':
            q = {'seriesid': item['id'], 'episodeid': epid, 'language': code2, 'forced': 'false', 'hi': 'false'}
            ruta = 'episodes/subtitles'
        else:
            q = {'radarrid': item['id'], 'language': code2, 'forced': 'false', 'hi': 'false'}
            ruta = 'movies/subtitles'
        _req('POST', self._url(ruta, q), {'X-API-KEY': self.c['key']}, cuerpo, timeout=120,
             tipo=f'multipart/form-data; boundary={frontera}')

    def subtitulos_de(self, item, epid):
        """Rutas (vistas por Bazarr) de los subtítulos externos que conoce de un episodio/película."""
        if item['tipo'] == 'serie':
            d = self.get('episodes', **{'episodeid[]': epid}).get('data', [])
        else:
            d = self.get('movies', **{'radarrid[]': item['id']}).get('data', [])
        return [s.get('path') for x in d for s in x.get('subtitles', []) if s.get('path')]


bazarr = Bazarr()


# ---------------------------------------------------------------- Jellyfin / Emby
def _jf(key):
    # Jellyfin nuevo solo acepta «Authorization: MediaBrowser Token=…»; Emby usa X-Emby-Token
    return {'Authorization': f'MediaBrowser Token="{key}"', 'X-Emby-Token': key}


def jellyfin_avisar(ruta_local):
    """Pide a Jellyfin/Emby que vuelva a leer ese archivo (para que vea el subtítulo nuevo sin esperar al escaneo)."""
    c = C.conexion('jellyfin')
    if not (c['url'] and c['key']):
        return False
    _req('POST', f"{c['url']}/Library/Media/Updated", _jf(c['key']),
         {'Updates': [{'Path': C.ruta_jellyfin(ruta_local), 'UpdateType': 'Modified'}]}, timeout=20)
    return True


# ---------------------------------------------------------------- ntfy
def avisar(titulo, mensaje, prioridad=3):
    c = C.conexion('ntfy')
    C.log('AVISO', titulo, '|', mensaje)
    if not (c['url'] and c['topic']):
        return
    cab = {'Authorization': 'Bearer ' + c['token']} if c['token'] else {}
    try:
        _req('POST', c['url'], cab, {'topic': c['topic'], 'title': titulo, 'message': mensaje, 'tags': ['speech_balloon'],
                                      'priority': prioridad}, timeout=20)
    except Exception as e:
        C.log('ntfy falló:', e)


# ---------------------------------------------------------------- episodios y carátulas
def episodios(item):
    """Episodios (o la película) con la ruta del vídeo ya traducida a la de subrr."""
    if item['tipo'] == 'serie':
        eps = sonarr.get('episode', seriesId=item['id'])
        fs = {f['id']: f for f in sonarr.get('episodefile', seriesId=item['id'])}
        out = []
        for e in eps:
            f = fs.get(e.get('episodeFileId') or -1) or {}
            out.append({'clave': f"S{e['seasonNumber']:02d}E{e['episodeNumber']:02d}", 'temporada': e['seasonNumber'],
                        'epid': e['id'], 'titulo': e.get('title', ''), 'path': C.ruta_local(f.get('path')),
                        'anadido': f.get('dateAdded')})
        return sorted(out, key=lambda x: x['clave'])
    m = radarr.get(f"movie/{item['id']}")
    f = m.get('movieFile') or {}
    return [{'clave': 'pelicula', 'temporada': None, 'epid': None, 'titulo': m['title'], 'path': C.ruta_local(f.get('path')),
             'anadido': f.get('dateAdded')}]


_cache_eps = {}


def episodios_cache(item, segundos=20):
    k = f"{item['tipo']}:{item['id']}"
    t, v = _cache_eps.get(k, (0, None))
    if time.time() - t > segundos or v is None:
        v = episodios(item)
        _cache_eps[k] = (time.time(), v)
    return v


def caratula(tipo, id_, clase='poster'):
    """Carátula desde Sonarr/Radarr, guardada 7 días en la caché."""
    os.makedirs(C.CACHE, exist_ok=True)
    ruta = os.path.join(C.CACHE, f'{tipo}-{int(id_)}-{clase}.jpg')
    if os.path.exists(ruta) and time.time() - os.path.getmtime(ruta) < 7 * 86400:
        with open(ruta, 'rb') as fh:
            return fh.read()
    try:
        datos = (sonarr if tipo == 'sonarr' else radarr).caratula(id_, clase)
    except Exception:
        if os.path.exists(ruta):
            with open(ruta, 'rb') as fh:
                return fh.read()
        return None
    with open(ruta + '.tmp', 'wb') as fh:
        fh.write(datos)
    os.replace(ruta + '.tmp', ruta)
    return datos


def probar(nombre):
    """Comprueba una conexión. Devuelve (ok, texto)."""
    try:
        if nombre in ('sonarr', 'radarr'):
            a = sonarr if nombre == 'sonarr' else radarr
            if not a.ok():
                return False, 'Falta la dirección o la clave'
            v = a.get('system/status')
            return True, f"{v.get('appName', nombre)} {v.get('version', '')}"
        if nombre == 'bazarr':
            if not bazarr.ok():
                return False, 'Falta la dirección o la clave'
            v = bazarr.estado().get('data', {})
            return True, f"Bazarr {v.get('bazarr_version', '')}"
        if nombre == 'jellyfin':
            c = C.conexion('jellyfin')
            if not (c['url'] and c['key']):
                return False, 'Sin configurar (opcional)'
            v = _req('GET', f"{c['url']}/System/Info", _jf(c['key']), timeout=15)
            return True, f"{v.get('ProductName', 'Jellyfin')} {v.get('Version', '')}"
        if nombre == 'ntfy':
            c = C.conexion('ntfy')
            return (bool(c['topic']), f"Tema «{c['topic']}»" if c['topic'] else 'Sin tema: no se envían avisos')
    except urllib.error.HTTPError as e:
        return False, f'Responde {e.code}' + (' (¿clave incorrecta?)' if e.code in (401, 403) else '')
    except Exception as e:
        return False, str(e)[:160]
    return False, '?'
