"""OCR: subtítulos de imagen (PGS/VobSub/DVB) y texto grabado en el vídeo.

Lectores:
  - Tesseract (local, gratis): necesita el programa «tesseract» y los idiomas instalados.
  - Un motor con visión de la cadena (Claude o compatible con OpenAI con un modelo que acepte imágenes):
    más fiable, y además distingue un subtítulo de un cartel o una pantalla de móvil.

Texto grabado: se busca en
  abajo     subtítulos grabados (amarillos o blancos, centrados)   → se ponen arriba ({\an8})
  rotulo_i  rótulos abajo a la izquierda (hora, lugar)             → arriba a la izquierda ({\an7})
  rotulo_d  rótulos abajo a la derecha                              → arriba a la derecha ({\an9})
  pantalla  pantallas de texto sobre fondo oscuro (epílogos)        → abajo
"""
import base64, json, os, re, shutil, subprocess

from . import config as C
from . import motores as M

try:
    import numpy as np
except ImportError:          # sin numpy no hay OCR (la imagen de Docker lo trae)
    np = None

POS = {'abajo': '{\\an8}', 'rotulo_i': '{\\an7}', 'rotulo_d': '{\\an9}', 'pantalla': ''}
# (fila_ini, fila_fin, col_ini, col_fin) en fracción del fotograma
ZONAS = {'abajo': (0.78, 0.985, 0.08, 0.92), 'rotulo_i': (0.66, 0.96, 0.03, 0.45), 'rotulo_d': (0.66, 0.96, 0.55, 0.97)}
TESS = {'en': 'eng', 'fr': 'fra', 'es': 'spa', 'de': 'deu', 'it': 'ita', 'pt': 'por', 'nl': 'nld', 'pl': 'pol', 'ru': 'rus',
        'ca': 'cat', 'sv': 'swe', 'da': 'dan', 'nb': 'nor', 'fi': 'fin', 'cs': 'ces', 'ro': 'ron', 'hu': 'hun', 'tr': 'tur'}


# ================================================================ disponibilidad
def tesseract_ok():
    return bool(shutil.which('tesseract'))


def tesseract_idiomas():
    try:
        r = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True, timeout=20)
        return [x.strip() for x in r.stdout.splitlines()[1:] if x.strip()]
    except Exception:
        return []


def lector(aj):
    """('tesseract', None) | ('vision', motor) | (None, motivo)."""
    if np is None:
        return None, 'falta el paquete «numpy»'
    mid = aj.get('ocr_motor') or ''
    if mid:
        m = next((x for x in C.cfg()['motores'] if x['id'] == mid), None)
        if not m:
            return None, 'el motor elegido para leer ya no existe'
        if m['tipo'] not in ('claude', 'openai'):
            return None, f"{m['nombre']} no puede leer imágenes"
        ok, motivo = M.disponible(m)
        return ('vision', m) if ok else (None, f"{m['nombre']}: {motivo}")
    if tesseract_ok():
        return 'tesseract', None
    return None, 'no hay lector: instala Tesseract o elige un motor con visión en Ajustes'


# ================================================================ utilidades de vídeo
def _probe(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=index,codec_type,width,height:format=duration',
                        '-of', 'json', video], capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout or '{}')


def _tam_video(info):
    v = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video' and s.get('width')), None)
    return (v['width'], v['height']) if v else (1920, 1080)


def _fotogramas(cmd, w, h, c):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = w * h * c
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield np.frombuffer(b, np.uint8).reshape(h, w, c) if c > 1 else np.frombuffer(b, np.uint8).reshape(h, w)
    finally:
        p.stdout.close()
        p.wait()


def _recorte(cmd, w, h, texto):
    """Un fotograma recortado: (png en color, pgm binarizado). texto(rgb) → máscara de los píxeles de texto."""
    r = subprocess.run(cmd + ['-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, timeout=120)
    if r.returncode or len(r.stdout) < w * h * 3:
        return None
    rgb = np.frombuffer(r.stdout[:w * h * 3], np.uint8).reshape(h, w, 3)
    png = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-i', '-',
                          '-f', 'image2', '-c:v', 'png', '-'], input=rgb.tobytes(), capture_output=True, timeout=60).stdout
    return png, _pgm(texto(rgb.astype(np.int16)))


def _es_texto_claro(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (rgb.min(axis=2) > 190) | ((r > 165) & (g > 165) & (b < 120) & (r - b > 70))


def _caja_px(m, escala, W, H, margen=14):
    """Caja (x, y, w, h) en píxeles reales de la máscara reducida m, con margen; ancho y alto pares."""
    ys, xs = np.nonzero(m)
    x0, x1 = max(0, int(xs.min() * escala) - margen), min(W, int((xs.max() + 1) * escala) + margen)
    y0, y1 = max(0, int(ys.min() * escala) - margen), min(H, int((ys.max() + 1) * escala) + margen)
    return x0, y0, (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2


def _caja(a, k):
    """Media en una ventana de (2k)x(2k) (filtro de caja con sumas acumuladas)."""
    h, w = a.shape
    c = np.cumsum(np.cumsum(np.pad(a, ((k, k), (k, k)), mode='edge'), 0), 1)
    return (c[2 * k:, 2 * k:] - c[:-2 * k, 2 * k:] - c[2 * k:, :-2 * k] + c[:-2 * k, :-2 * k])[:h, :w] / (2 * k) ** 2


class _Tramos:
    """Agrupa fotogramas seguidos con el mismo texto (máscara parecida). hueco: fotogramas vacíos tolerados."""

    def __init__(self, fps, minimo=2, hueco=1):
        self.fps, self.minimo, self.hueco = fps, minimo, hueco
        self.abierto, self.hechos = None, []

    def _cerrar_abierto(self):
        a = self.abierto
        if a and a['fin'] - a['ini'] + 1 >= self.minimo:
            self.hechos.append(a)
        self.abierto = None

    def poner(self, i, m):
        a = self.abierto
        if m is None:
            if a and i - a['fin'] > self.hueco:
                self._cerrar_abierto()
            return
        if a and i - a['fin'] <= 1 + self.hueco and (m ^ a['m']).sum() < 0.5 * max(m.sum(), a['m'].sum()):
            a['fin'] = i
            if m.sum() > a['m'].sum():
                a['m'] = m
            return
        self._cerrar_abierto()
        self.abierto = {'ini': i, 'fin': i, 'm': m}

    def cerrar(self):
        self._cerrar_abierto()
        return [(t['ini'] / self.fps, (t['fin'] + 1) / self.fps, t['m']) for t in self.hechos]


# ================================================================ leer imágenes
def _pgm(binaria):
    """Imagen binaria (True = texto) → PGM con texto negro sobre blanco y un margen, que es lo que mejor lee Tesseract."""
    m = np.pad(binaria, 12)
    img = np.where(m, 0, 255).astype(np.uint8)
    return f'P5\n{img.shape[1]} {img.shape[0]}\n255\n'.encode() + img.tobytes()


def _tesseract(imagen, idiomas):
    """Lee una imagen (PGM/PNG). Se queda con las líneas en las que Tesseract confía."""
    r = subprocess.run(['tesseract', 'stdin', 'stdout', '-l', idiomas, '--psm', '6', 'tsv'], input=imagen, capture_output=True, timeout=120)
    lineas = {}
    for fila in r.stdout.decode(errors='replace').splitlines()[1:]:
        c = fila.split('\t')
        if len(c) < 12 or not c[11].strip():
            continue
        try:
            conf = float(c[10])
        except ValueError:
            continue
        lineas.setdefault((c[2], c[3], c[4]), []).append((conf, c[11].strip().replace('|', 'I')))
    out = []
    for clave in sorted(lineas, key=lambda x: tuple(int(y) for y in x)):
        palabras = [(cf, w) for cf, w in lineas[clave] if cf >= 35]
        if not palabras or sum(cf for cf, _ in palabras) / len(palabras) < 62:
            continue
        t = ' '.join(w for _, w in palabras)
        if sum(ch.isalpha() for ch in t) >= max(2, 0.6 * len(t.replace(' ', ''))):
            out.append(t)
    return ' | '.join(out)


PROMPT_VISION = (
    "Each image is a crop of a video frame. Transcribe the subtitle or caption text that is overlaid on each image "
    "(burned-in subtitles, captions with time/place, title cards), exactly as written, joining lines with ' | '. "
    "Ignore text that is part of the filmed scene itself (signs, phone screens, labels, logos) unless it is an overlaid subtitle. "
    "Reply with exactly one line per image, in order, as «N|lang|text» where lang is the ISO 639-1 code of the text; "
    "use «N|-|-» when there is no overlaid subtitle or caption. Nothing else.")


def _vision(m, pngs):
    """Lee varias imágenes con un motor con visión. Devuelve [(lang, texto)] ('' si no hay texto)."""
    n = len(pngs)
    if m['tipo'] == 'claude':
        import anthropic
        cliente = anthropic.Anthropic(api_key=M.campo(m, 'key', 'ANTHROPIC_API_KEY'), max_retries=3)
        contenido = []
        for i, p in enumerate(pngs, 1):
            contenido += [{'type': 'text', 'text': f'Image {i}:'},
                          {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(p).decode()}}]
        contenido.append({'type': 'text', 'text': PROMPT_VISION})
        try:
            r = cliente.messages.create(model=M.campo(m, 'modelo', None, 'claude-opus-5-5'), max_tokens=8000,
                                        output_config={'effort': 'low'}, messages=[{'role': 'user', 'content': contenido}])
        except anthropic.APIStatusError as e:
            raise M.Falla(f'Claude respondió {e.status_code}: {e.message}')
        except anthropic.APIConnectionError as e:
            raise M.Falla(f'Claude no responde: {e}')
        if r.stop_reason == 'refusal':
            raise M.Falla('Claude rechazó leer estas imágenes')
        texto = ''.join(b.text for b in r.content if b.type == 'text')
    else:
        base = M.campo(m, 'url', 'OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
        k = M.campo(m, 'key', 'OPENAI_API_KEY')
        contenido = []
        for i, p in enumerate(pngs, 1):
            contenido += [{'type': 'text', 'text': f'Image {i}:'},
                          {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(p).decode()}}]
        contenido.append({'type': 'text', 'text': PROMPT_VISION})
        datos = {'model': M.campo(m, 'modelo', 'OPENAI_MODEL'), 'messages': [{'role': 'user', 'content': contenido}]}
        r = M._con_reintentos(lambda: M._post(base + '/chat/completions', datos, {'Authorization': 'Bearer ' + k} if k else {}, 600),
                              'LLM', cupo=(402,))
        try:
            texto = r['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise M.Falla('respuesta rara del LLM: ' + json.dumps(r)[:200])
    out = {}
    for linea in texto.splitlines():
        mm = re.match(r'^\s*(\d+)\s*\|\s*([a-zA-Z-]+)\s*\|\s*(.*)$', linea)
        if mm and 1 <= int(mm.group(1)) <= n:
            lang, t = mm.group(2).lower(), mm.group(3).strip()
            out[int(mm.group(1))] = ('', '') if lang == '-' or t in ('-', '') else (lang.split('-')[0], t)
    if len(out) < n:
        raise M.Falla(f'el modelo leyó {len(out)} de {n} imágenes')
    return [out[i] for i in range(1, n + 1)]


def leer(imagenes, aj, lang_defecto, progreso=lambda n, t: None):
    """imagenes: [(png en color, pgm binarizado)]. Devuelve [(lang, texto)] con el lector configurado."""
    pngs = [x[0] for x in imagenes]
    tipo, m = lector(aj)
    if not tipo:
        raise M.Falla(m)
    out = []
    if tipo == 'vision':
        for i in range(0, len(pngs), 12):
            out += _vision(m, pngs[i:i + 12])
            progreso(min(len(pngs), i + 12), len(pngs))
        return out
    idi = aj.get('ocr_idiomas') or 'eng+fra+spa+deu+ita+por'
    if lang_defecto in TESS:     # el idioma que esperamos, el primero
        idi = '+'.join([TESS[lang_defecto]] + [x for x in idi.split('+') if x != TESS[lang_defecto]])
    instalados = set(tesseract_idiomas())
    idi = '+'.join(x for x in idi.split('+') if x in instalados) or 'eng'
    for i, (_, pgm) in enumerate(imagenes):
        out.append((lang_defecto, _tesseract(pgm, idi)))
        progreso(i + 1, len(imagenes))
    return out


# ================================================================ subtítulos de imagen
def leer_pista_imagen(video, pista, aj, progreso=lambda paso: None):
    """Pasa a texto una pista de subtítulos de imagen. Devuelve [(ini_ms, fin_ms, [líneas])]."""
    info = _probe(video)
    s = next((x for x in info.get('streams', []) if x.get('index') == pista['indice']), {})
    W, H = (s.get('width') or 0, s.get('height') or 0)
    if not (W and H):
        W, H = _tam_video(info)
    dur = float(info.get('format', {}).get('duration') or 0) or 3 * 3600
    w, h = max(2, W // 4 // 2 * 2), max(2, H // 4 // 2 * 2)
    FPS = 10
    base = ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=black:s={W}x{H}:r={FPS}:d={dur:.1f}', '-canvas_size', f'{W}x{H}']
    cmd = base + ['-i', video, '-filter_complex', f"[0:v][1:{pista['indice']}]overlay=eof_action=pass,scale={w}:{h},format=gray",
                  '-f', 'rawvideo', '-pix_fmt', 'gray', '-']
    tr = _Tramos(FPS, minimo=2, hueco=0)
    for i, f in enumerate(_fotogramas(cmd, w, h, 1)):
        if i % (FPS * 60) == 0:
            progreso(f'Buscando subtítulos de imagen: minuto {i // (FPS * 60)}')
        m = f > 90
        tr.poner(i, m if m.sum() > 12 else None)
    tramos = tr.cerrar()
    imagenes = []
    for n, (a, b, m) in enumerate(tramos):
        if n % 20 == 0:
            progreso(f'Recortando subtítulos {n}/{len(tramos)}')
        x, y, cw, ch = _caja_px(m, W / w, W, H)
        ini = max(0.0, a - 1.0)
        imagenes.append(_recorte(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=black:s={W}x{H}:r={FPS}:d=4', '-canvas_size', f'{W}x{H}',
                                  '-ss', f'{ini:.2f}', '-i', video, '-filter_complex',
                                  f"[0:v][1:{pista['indice']}]overlay=eof_action=pass,crop={cw}:{ch}:{x}:{y}",
                                  '-ss', f'{(a - ini) + min(0.3, (b - a) / 2):.2f}'], cw, ch, lambda rgb: rgb.max(axis=2) > 110))
    vale = [(t, im) for t, im in zip(tramos, imagenes) if im]
    textos = leer([im for _, im in vale], aj, pista['lang'], progreso=lambda n, t: progreso(f'Leyendo subtítulos de imagen {n}/{t}'))
    cues = []
    for ((a, b, _), _), (lang, t) in zip(vale, textos):
        if not t:
            continue
        lineas = [x.strip() for x in t.split('|') if x.strip()]
        if cues and cues[-1][2] == lineas and a * 1000 - cues[-1][1] < 300:
            cues[-1] = (cues[-1][0], int(b * 1000), lineas)
        else:
            cues.append((int(a * 1000), int(b * 1000), lineas))
    return cues


# ================================================================ texto grabado en el vídeo
def buscar_grabado(video, aj, lang_defecto, progreso=lambda paso: None):
    """Busca y lee el texto grabado en la imagen. Devuelve [{'a','b','zona','lang','texto'}] (segundos)."""
    info = _probe(video)
    W, H = _tam_video(info)
    w = 480
    h = max(2, int(round(w * H / W / 2)) * 2)
    FPS = 4
    cmd = ['ffmpeg', '-v', 'error', '-hwaccel', 'auto', '-i', video, '-map', '0:v:0', '-vf', f'fps={FPS},scale={w}:{h}',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    zonas = {z: (int(f0 * h), int(f1 * h), int(c0 * w), int(c1 * w)) for z, (f0, f1, c0, c1) in ZONAS.items()}
    tramos = {z: _Tramos(FPS) for z in list(ZONAS) + ['pantalla']}
    for i, f in enumerate(_fotogramas(cmd, w, h, 3)):
        if i % (FPS * 60) == 0:
            progreso(f'Buscando texto grabado: minuto {i // (FPS * 60)}')
        f = f.astype(np.int16)
        r, g, b = f[..., 0], f[..., 1], f[..., 2]
        blanco = f.min(axis=2) > 205
        amarillo = (r > 170) & (g > 170) & (b < 115) & (r - b > 80)
        texto = blanco | amarillo
        for z, (y0, y1, x0, x1) in zonas.items():
            m = texto[y0:y1, x0:x1] if z == 'abajo' else blanco[y0:y1, x0:x1]
            n = int(m.sum())
            area = m.size
            ok = 15 <= n <= 0.12 * area
            if ok:
                cx = (m.sum(axis=0) * np.arange(m.shape[1])).sum() / n
                if z == 'abajo':
                    ok = abs(cx - m.shape[1] / 2) < 0.15 * m.shape[1]
                elif z == 'rotulo_i':
                    ok = cx < 0.6 * m.shape[1] and n >= 30
                else:
                    ok = cx > 0.4 * m.shape[1] and n >= 30
            tramos[z].poner(i, m if ok else None)
        gris = f.mean(axis=2)
        if (gris < 40).mean() > 0.55:
            oscuro = _caja((gris < 40).astype(float), 6) > 0.6
            m = (gris > 170) & oscuro
            m[int(0.76 * h):, :] = False          # la franja de los subtítulos ya la mira «abajo»
            tramos['pantalla'].poner(i, m if m.sum() >= 25 else None)
        else:
            tramos['pantalla'].poner(i, None)
    candidatos = []
    for z, t in tramos.items():
        y_off, x_off = (zonas[z][0], zonas[z][2]) if z in zonas else (0, 0)
        for a, b, m in t.cerrar():
            completa = np.zeros((h, w), bool)
            completa[y_off:y_off + m.shape[0], x_off:x_off + m.shape[1]] = m
            candidatos.append((a, b, z, completa))
    candidatos.sort(key=lambda c: c[0])
    progreso(f'Recortando {len(candidatos)} posibles textos')
    imagenes = []
    for a, b, z, m in candidatos:
        x, y, cw, ch = _caja_px(m, W / w, W, H, margen=24)
        texto = _es_texto_claro if z != 'pantalla' else (lambda rgb: rgb.mean(axis=2) > 170)
        imagenes.append(_recorte(['ffmpeg', '-v', 'error', '-ss', f'{(a + b) / 2:.2f}', '-i', video, '-map', '0:v:0',
                                  '-vf', f'crop={cw}:{ch}:{x}:{y}'], cw, ch, texto))
    vale = [(c, im) for c, im in zip(candidatos, imagenes) if im]
    textos = leer([im for _, im in vale], aj, lang_defecto, progreso=lambda n, t: progreso(f'Leyendo texto grabado {n}/{t}'))
    out = []
    subt = [(a, b) for (a, b, z, _), _ in vale if z == 'abajo']
    for ((a, b, z, _), _), (lang, t) in zip(vale, textos):
        if not t:
            continue
        if z == 'pantalla' and any(min(b, y) - max(a, x) > 0.5 * (b - a) for x, y in subt):
            continue                              # era un subtítulo sobre fondo oscuro
        prev = next((x for x in reversed(out) if x['zona'] == z), None)
        if prev and prev['texto'] == t and a - prev['b'] < 0.8:
            prev['b'] = b
            continue
        out.append({'a': a, 'b': b, 'zona': z, 'lang': lang or lang_defecto, 'texto': t})
    return out


def quitar_repetidos(grabado, cues_origen):
    """Fuera los subtítulos grabados que ya están en la pista de texto (se solapan con una línea de origen)."""
    out = []
    for g in grabado:
        if g['zona'] == 'abajo':
            a, b = g['a'] * 1000, g['b'] * 1000
            solape = sum(max(0, min(b, y) - max(a, x)) for x, y, _ in cues_origen)
            if solape > 0.5 * (b - a):
                continue
        out.append(g)
    return out
