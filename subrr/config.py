"""Configuración de subrr.

Todo se guarda en <DATOS>/config.json y se cambia desde la web. Las variables de entorno solo dan el valor
inicial (útil para docker-compose): si un campo está vacío en config.json se usa la variable de entorno.

Variables de entorno reconocidas (todas opcionales):
  SUBRR_DATA            carpeta de datos (por defecto /config)
  SUBRR_PORT            puerto de la web (por defecto 3007)
  SUBRR_BIND            dirección en la que escucha la web (por defecto 0.0.0.0; en Docker debe ser 0.0.0.0)
  SUBRR_PASSWORD        contraseña de la web (HTTP Basic). Vacía = sin contraseña. /salud y los webhooks quedan fuera
  SUBRR_USER            usuario de la web (opcional: si no se define, vale cualquier usuario con la contraseña correcta)
  SUBRR_WEBHOOK_TOKEN   token de los webhooks de Sonarr/Radarr (si no, se genera uno y se guarda en config.json)
  SUBRR_ALLOWED_ORIGINS hosts extra permitidos como Origin/Referer de los formularios (tras un proxy que cambia el Host)
  SONARR_URL / SONARR_KEY, RADARR_URL / RADARR_KEY, BAZARR_URL / BAZARR_KEY, JELLYFIN_URL / JELLYFIN_KEY
  NTFY_URL / NTFY_TOPIC / NTFY_TOKEN
  DEEPL_KEY, LIBRETRANSLATE_URL, LIBRETRANSLATE_KEY, OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL,
  ANTHROPIC_API_KEY, GOOGLE_TRANSLATE_KEY, AZURE_TRANSLATOR_KEY / AZURE_TRANSLATOR_REGION
  PATH_MAP              mapeo de rutas, «remoto=>local» separados por «;»
"""
import hmac, json, os, re, secrets, threading, time, uuid

DATOS = os.environ.get('SUBRR_DATA', '/config')
PUERTO = int(os.environ.get('SUBRR_PORT', '3007'))
BIND = os.environ.get('SUBRR_BIND', '').strip() or '0.0.0.0'
PASSWORD = os.environ.get('SUBRR_PASSWORD', '')
USUARIO = os.environ.get('SUBRR_USER', '')
ORIGENES_EXTRA = {x.strip().lower() for x in os.environ.get('SUBRR_ALLOWED_ORIGINS', '').split(',') if x.strip()}
CONFIG = os.path.join(DATOS, 'config.json')
ESTADO = os.path.join(DATOS, 'estado.json')
RESULTADOS = os.path.join(DATOS, 'resultados.json')
ACCIONES = os.path.join(DATOS, 'acciones.json')
USO = os.path.join(DATOS, 'uso.json')
ORIGEN = os.path.join(DATOS, 'origen')
CACHE = os.path.join(DATOS, 'cache')
TMP = os.path.join(DATOS, 'tmp')

cerrojo = threading.RLock()
despertar = threading.Event()
vivo = {'trabajando': '', 'paso': '', 'desde': 0.0, 'ultima_pasada': ''}

# ---------------------------------------------------------------- idiomas de destino
# code2: sufijo del .srt y lo que buscan Bazarr/Jellyfin · code3: etiqueta dentro del mkv · el resto: código por motor
DESTINOS = {
    'es': {'nombre': 'Español (España)', 'code2': 'es', 'code3': 'spa', 'deepl': 'ES', 'libre': 'es', 'google': 'es', 'azure': 'es',
           'llm': 'Spanish from Spain (castellano, peninsular vocabulary and "vosotros")'},
    'es-419': {'nombre': 'Español (Latinoamérica)', 'code2': 'es', 'code3': 'spa', 'deepl': 'ES-419', 'libre': 'es', 'google': 'es',
               'azure': 'es', 'llm': 'Latin American Spanish (neutral, "ustedes")'},
    'en': {'nombre': 'English', 'code2': 'en', 'code3': 'eng', 'deepl': 'EN-US', 'libre': 'en', 'google': 'en', 'azure': 'en', 'llm': 'English'},
    'fr': {'nombre': 'Français', 'code2': 'fr', 'code3': 'fre', 'deepl': 'FR', 'libre': 'fr', 'google': 'fr', 'azure': 'fr', 'llm': 'French'},
    'de': {'nombre': 'Deutsch', 'code2': 'de', 'code3': 'ger', 'deepl': 'DE', 'libre': 'de', 'google': 'de', 'azure': 'de', 'llm': 'German'},
    'it': {'nombre': 'Italiano', 'code2': 'it', 'code3': 'ita', 'deepl': 'IT', 'libre': 'it', 'google': 'it', 'azure': 'it', 'llm': 'Italian'},
    'pt-PT': {'nombre': 'Português (Portugal)', 'code2': 'pt', 'code3': 'por', 'deepl': 'PT-PT', 'libre': 'pt', 'google': 'pt-PT',
              'azure': 'pt-pt', 'llm': 'European Portuguese'},
    'pt-BR': {'nombre': 'Português (Brasil)', 'code2': 'pt', 'code3': 'por', 'deepl': 'PT-BR', 'libre': 'pb', 'google': 'pt',
              'azure': 'pt', 'llm': 'Brazilian Portuguese'},
    'ca': {'nombre': 'Català', 'code2': 'ca', 'code3': 'cat', 'deepl': None, 'libre': 'ca', 'google': 'ca', 'azure': 'ca', 'llm': 'Catalan'},
    'nl': {'nombre': 'Nederlands', 'code2': 'nl', 'code3': 'dut', 'deepl': 'NL', 'libre': 'nl', 'google': 'nl', 'azure': 'nl', 'llm': 'Dutch'},
    'pl': {'nombre': 'Polski', 'code2': 'pl', 'code3': 'pol', 'deepl': 'PL', 'libre': 'pl', 'google': 'pl', 'azure': 'pl', 'llm': 'Polish'},
}

# ---------------------------------------------------------------- ajustes generales (y los que puede cambiar cada serie/película)
AJUSTES_DEFECTO = {
    'destino': 'es',                 # clave de DESTINOS
    'prioridad': 'en,fr,it,pt,de',   # idiomas de origen preferidos, en orden
    'quitar_sdh': True,              # quitar [ruidos], ♪ y «NOMBRE:» si el origen es para sordos
    'saltar_audio': True,            # no traducir si ya hay audio en el idioma de destino
    'variante_vale': False,          # (solo español) un subtítulo latino cuenta como castellano y al revés
    'mejorar_reserva': True,         # rehacer lo que hizo un motor de reserva cuando vuelva a haber uno principal
    'salida': 'aparte',              # aparte (.xx.srt) | dentro (pista del mkv) | ambos
    'por_defecto': True,             # al meterlo en el mkv, marcarlo como pista por defecto
    'enlaces_duros': False,          # meterlo en el mkv aunque el vídeo tenga enlaces duros (p. ej. torrents compartiendo)
    'papelera_dias': 7,              # días que se guarda el vídeo original al meter la pista (0 = no se guarda)
    'papelera': '',                  # carpeta de la papelera; vacío = «.subrr-papelera» en la raíz del disco del vídeo
    'nombre_pista': '{idioma} (subrr)',
    'ocr_imagen': True,              # leer con OCR los subtítulos de imagen (PGS/VobSub) si no hay de texto
    'grabado': 'no',                 # buscar también el texto grabado en la imagen: no | si
    'ocr_motor': '',                 # lector: vacío = Tesseract; o el id de un motor con visión (Claude/compatible OpenAI)
    'ocr_idiomas': 'eng+fra+spa+deu+ita+por',   # idiomas de Tesseract
    'motor': '',                     # id de motor que se prueba primero (vacío = según la cadena)
    'intervalo_min': 10,
    'bazarr_auto': False,            # traducir solo lo que Bazarr tenga en «Wanted» para el idioma de destino
    'bazarr_dias': 3,                # días de espera desde que se descargó el vídeo, para dar tiempo a Bazarr
    'bazarr_entrega': 'escanear',    # escanear (subrr guarda y Bazarr lo detecta) | subir (se lo da a Bazarr y él lo guarda)
    'rutas': '',                     # mapeo «ruta en Sonarr/Radarr/Bazarr => ruta en subrr», una por línea
    'rutas_jellyfin': '',            # mapeo «ruta en subrr => ruta en Jellyfin», una por línea
}
POR_ITEM = ('destino', 'prioridad', 'quitar_sdh', 'saltar_audio', 'salida', 'por_defecto', 'motor', 'grabado')

CONEXIONES = {
    'sonarr': {'nombre': 'Sonarr', 'url': ('SONARR_URL', 'http://sonarr:8989'), 'key': ('SONARR_KEY', '')},
    'radarr': {'nombre': 'Radarr', 'url': ('RADARR_URL', 'http://radarr:7878'), 'key': ('RADARR_KEY', '')},
    'bazarr': {'nombre': 'Bazarr', 'url': ('BAZARR_URL', 'http://bazarr:6767'), 'key': ('BAZARR_KEY', '')},
    'jellyfin': {'nombre': 'Jellyfin / Emby', 'url': ('JELLYFIN_URL', ''), 'key': ('JELLYFIN_KEY', '')},
    'ntfy': {'nombre': 'ntfy (avisos al móvil)', 'url': ('NTFY_URL', 'https://ntfy.sh'), 'topic': ('NTFY_TOPIC', ''), 'token': ('NTFY_TOKEN', '')},
}
SECRETOS = {'key', 'token'}


def log(*a):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), *a, flush=True)


# ---------------------------------------------------------------- ficheros
def leer(ruta, defecto):
    try:
        with open(ruta) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return defecto


def escribir(ruta, datos, privado=False):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + '.tmp', 'w') as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    if privado:
        os.chmod(ruta + '.tmp', 0o600)
    os.replace(ruta + '.tmp', ruta)


def seguro(nombre):
    return re.sub(r'[\\/:*?"<>|]', '', nombre).strip()


def cfg():
    c = leer(CONFIG, {})
    c.setdefault('items', {})
    c.setdefault('ajustes', {})
    c.setdefault('conexiones', {})
    if 'motores' not in c:
        with cerrojo:                      # la primera vez se guardan, para que los ids no cambien
            c2 = leer(CONFIG, {})
            if 'motores' not in c2:
                c2['motores'] = motores_iniciales()
                escribir(CONFIG, c2, privado=True)
            c['motores'] = c2['motores']
    return c


def cambiar_cfg(fn):
    """Lee, cambia y guarda la configuración sin pisar lo que haya cambiado otro hilo."""
    with cerrojo:
        c = cfg()
        r = fn(c)
        escribir(CONFIG, c, privado=True)       # lleva claves de API
        return r


def ajustes(item=None):
    """Ajustes efectivos: fábrica ← generales ← los de la serie/película."""
    a = {**AJUSTES_DEFECTO, **cfg()['ajustes']}
    if item:
        a.update({k: v for k, v in (item.get('ajustes') or {}).items() if k in POR_ITEM and v not in (None, '')})
    return a


def _valores(nombre, guardado):
    """Valores efectivos de una conexión a partir de lo guardado (dict): lo guardado o, si está vacío, la variable de entorno.
    La clave/token de una variable de entorno solo vale para la dirección de esa misma variable (o su valor por defecto):
    si el usuario cambia la dirección, esa clave no se envía a la dirección nueva."""
    d = CONEXIONES[nombre]
    var_url, def_url = d['url']
    url_env = (os.environ.get(var_url) or def_url).strip().rstrip('/')
    url = (guardado.get('url') or os.environ.get(var_url) or def_url).strip().rstrip('/')
    out = {'url': url}
    for campo, val in d.items():
        if campo in ('nombre', 'url'):
            continue
        var, defecto = val
        env = os.environ.get(var) if (campo not in SECRETOS or url == url_env) else None
        out[campo] = (guardado.get(campo) or env or defecto).strip()
    return out


def conexion(nombre):
    """Valores de una conexión: lo guardado en la web o, si está vacío, la variable de entorno."""
    return _valores(nombre, cfg()['conexiones'].get(nombre, {}))


# ---------------------------------------------------------------- token de los webhooks
def token_webhook():
    """SUBRR_WEBHOOK_TOKEN o, si no existe, uno generado la primera vez y guardado en config.json."""
    t = os.environ.get('SUBRR_WEBHOOK_TOKEN', '').strip()
    if t:
        return t
    t = cfg().get('webhook_token')
    if t:
        return t

    def fn(c):
        if not c.get('webhook_token'):
            c['webhook_token'] = secrets.token_urlsafe(24)
        return c['webhook_token']
    return cambiar_cfg(fn)


def token_webhook_fijo():
    return bool(os.environ.get('SUBRR_WEBHOOK_TOKEN', '').strip())


def regenerar_token_webhook():
    if token_webhook_fijo():
        return False
    cambiar_cfg(lambda c: c.__setitem__('webhook_token', secrets.token_urlsafe(24)))
    return True


# variables de entorno con claves: sus valores se tapan si alguna vez aparecen en una respuesta de la web
ENV_SECRETOS = ('SONARR_KEY', 'RADARR_KEY', 'BAZARR_KEY', 'JELLYFIN_KEY', 'NTFY_TOKEN', 'DEEPL_KEY', 'LIBRETRANSLATE_KEY', 'OPENAI_API_KEY',
                'ANTHROPIC_API_KEY', 'GOOGLE_TRANSLATE_KEY', 'AZURE_TRANSLATOR_KEY', 'SUBRR_PASSWORD')


def ocultar(texto):
    """Última barrera: tapa en un texto cualquier clave guardada o de entorno (p. ej. si un error de red la repite)."""
    secretos = {os.environ.get(v, '') for v in ENV_SECRETOS}
    c = cfg()
    for g in c['conexiones'].values():
        secretos.update(g.get(k) or '' for k in SECRETOS)
    for m in c['motores']:
        secretos.add((m.get('campos') or {}).get('key') or '')
    for sec in secretos:
        if len(sec) >= 8 and sec in texto:
            texto = texto.replace(sec, '«clave»')
    return texto


def iguales(a, b):
    """Comparación en tiempo constante de dos textos."""
    return hmac.compare_digest((a or '').encode(), (b or '').encode())


def nuevo_id():
    return uuid.uuid4().hex[:8]


def motores_iniciales():
    """Primera vez: los motores que se puedan deducir del entorno."""
    m = []
    if os.environ.get('DEEPL_KEY'):
        m.append({'id': nuevo_id(), 'tipo': 'deepl', 'nombre': 'DeepL', 'activo': True, 'papel': 'principal', 'idiomas': '',
                  'limite': 0, 'campos': {}})
    for var, tipo, nombre in (('ANTHROPIC_API_KEY', 'claude', 'Claude'), ('OPENAI_API_KEY', 'openai', 'OpenAI'),
                              ('GOOGLE_TRANSLATE_KEY', 'google', 'Google Translate'), ('AZURE_TRANSLATOR_KEY', 'azure', 'Microsoft Translator')):
        if os.environ.get(var):
            m.append({'id': nuevo_id(), 'tipo': tipo, 'nombre': nombre, 'activo': True, 'papel': 'principal', 'idiomas': '',
                      'limite': 0, 'campos': {}})
    if os.environ.get('LIBRETRANSLATE_URL'):
        m.append({'id': nuevo_id(), 'tipo': 'libre', 'nombre': 'LibreTranslate', 'activo': True, 'papel': 'reserva', 'idiomas': '',
                  'limite': 0, 'campos': {}})
    return m


# ---------------------------------------------------------------- rutas
def _mapeo(texto):
    pares = []
    for linea in re.split(r'[\n;]', texto or ''):
        if '=>' in linea:
            a, b = (x.strip() for x in linea.split('=>', 1))
            if a and b:
                pares.append((a.rstrip('/'), b.rstrip('/')))
    return sorted(pares, key=lambda x: -len(x[0]))


def ruta_local(p):
    """Ruta que dan Sonarr/Radarr/Bazarr → ruta dentro de subrr."""
    if not p:
        return p
    for a, b in _mapeo(ajustes()['rutas'] or os.environ.get('PATH_MAP', '')):
        if p == a or p.startswith(a + '/'):
            return b + p[len(a):]
    return p


def ruta_remota(p):
    for a, b in _mapeo(ajustes()['rutas'] or os.environ.get('PATH_MAP', '')):
        if p == b or p.startswith(b + '/'):
            return a + p[len(b):]
    return p


def ruta_jellyfin(p):
    for a, b in _mapeo(ajustes()['rutas_jellyfin']):
        if p == a or p.startswith(a + '/'):
            return b + p[len(a):]
    return p


# ---------------------------------------------------------------- estado, resultados, acciones, uso
def estado():
    return leer(ESTADO, {})


def poner_estado(ruta, valor):
    with cerrojo:
        e = estado()
        if valor is None:
            e.pop(ruta, None)
        else:
            e[ruta] = valor
        escribir(ESTADO, e)


def resultado(item, ep, texto, ok, detalle='', k=''):
    with cerrojo:
        r = leer(RESULTADOS, [])
        r.insert(0, {'fecha': time.strftime('%Y-%m-%d %H:%M'), 'item': item, 'ep': ep, 'texto': texto, 'ok': ok,
                     'detalle': detalle, 'k': k})
        escribir(RESULTADOS, r[:800])


def pedir_accion(item_k, clave, accion):
    with cerrojo:
        q = [a for a in leer(ACCIONES, []) if not (a['item'] == item_k and a['clave'] == clave)]
        q.append({'item': item_k, 'clave': clave, 'accion': accion, 'fecha': time.time()})
        escribir(ACCIONES, q)
    despertar.set()


def tomar_accion():
    with cerrojo:
        q = leer(ACCIONES, [])
        if not q:
            return None
        a = q.pop(0)
        escribir(ACCIONES, q)
        return a


def acciones_pendientes():
    return leer(ACCIONES, [])


def uso_mes(motor_id):
    return leer(USO, {}).get(time.strftime('%Y-%m'), {}).get(motor_id, 0)


def sumar_uso(motor_id, n):
    with cerrojo:
        u = leer(USO, {})
        mes = u.setdefault(time.strftime('%Y-%m'), {})
        mes[motor_id] = mes.get(motor_id, 0) + n
        escribir(USO, u)


def huella(ruta):
    """Tamaño y fecha de un archivo, para saber si ha cambiado."""
    try:
        st = os.stat(ruta)
        return f'{st.st_size}|{int(st.st_mtime)}'
    except OSError:
        return None
