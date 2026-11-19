"""Subtítulos: qué pistas tiene un vídeo, cuál usar de origen, leer/escribir SRT y preparar el texto para traducir."""
import json, os, re, subprocess

TEXTO = {'subrip', 'srt', 'ass', 'ssa', 'mov_text', 'webvtt', 'text'}
IMAGEN = {'hdmv_pgs_subtitle', 'dvd_subtitle', 'dvb_subtitle', 'xsub', 'pgssub'}
EXT_SUB = ('.srt', '.ass', '.ssa', '.vtt')

# ISO 639-2 (lo que ponen los mkv) / 639-1 (lo que llevan los .srt externos) → código corto
CORTO = {'eng': 'en', 'en': 'en', 'fre': 'fr', 'fra': 'fr', 'fr': 'fr', 'ita': 'it', 'it': 'it', 'por': 'pt', 'pt': 'pt',
         'pob': 'pt', 'ger': 'de', 'deu': 'de', 'de': 'de', 'spa': 'es', 'es': 'es', 'esp': 'es', 'dut': 'nl', 'nld': 'nl',
         'nl': 'nl', 'pol': 'pl', 'pl': 'pl', 'rus': 'ru', 'ru': 'ru', 'jpn': 'ja', 'ja': 'ja', 'kor': 'ko', 'ko': 'ko',
         'chi': 'zh', 'zho': 'zh', 'zh': 'zh', 'ara': 'ar', 'ar': 'ar', 'heb': 'he', 'he': 'he', 'tur': 'tr', 'tr': 'tr',
         'swe': 'sv', 'sv': 'sv', 'dan': 'da', 'da': 'da', 'nor': 'nb', 'nob': 'nb', 'no': 'nb', 'nb': 'nb', 'fin': 'fi',
         'fi': 'fi', 'gre': 'el', 'ell': 'el', 'el': 'el', 'cze': 'cs', 'ces': 'cs', 'cs': 'cs', 'hun': 'hu', 'hu': 'hu',
         'rum': 'ro', 'ron': 'ro', 'ro': 'ro', 'ukr': 'uk', 'uk': 'uk', 'cat': 'ca', 'ca': 'ca', 'pb': 'pt'}
NOMBRE = {'en': 'inglés', 'fr': 'francés', 'it': 'italiano', 'pt': 'portugués', 'de': 'alemán', 'es': 'castellano',
          'nl': 'neerlandés', 'pl': 'polaco', 'ru': 'ruso', 'ja': 'japonés', 'ko': 'coreano', 'zh': 'chino', 'ar': 'árabe',
          'he': 'hebreo', 'tr': 'turco', 'sv': 'sueco', 'da': 'danés', 'nb': 'noruego', 'fi': 'finés', 'el': 'griego',
          'cs': 'checo', 'hu': 'húngaro', 'ro': 'rumano', 'uk': 'ucraniano', 'ca': 'catalán', '': 'idioma sin marcar'}
LATINO = re.compile(r'lat|419|m[eé]xic|am[eé]rica', re.I)
SDH = re.compile(r'\b(sdh|cc|hi|hoh)\b|sordos|malentendants|hearing', re.I)
FORZADO = re.compile(r'forc|forz|signs|carteles|songs', re.I)


def corto(lang):
    return CORTO.get((lang or '').lower().split('-')[0], '')


# ------------------------------------------------------------------------------------------------ pistas
def sondear(ruta):
    """Pistas de un vídeo con ffprobe: (subtítulos, idiomas de audio)."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'stream=index,codec_type,codec_name:stream_tags=language,title:stream_disposition=forced,hearing_impaired',
                        '-of', 'json', ruta], capture_output=True, text=True, timeout=120)
    datos = json.loads(r.stdout or '{}').get('streams', [])
    subs, audio = [], []
    for s in datos:
        tags, disp = s.get('tags', {}), s.get('disposition', {})
        lang, titulo = corto(tags.get('language')), tags.get('title') or ''
        if s.get('codec_type') == 'audio':
            audio.append((lang, titulo))
        elif s.get('codec_type') == 'subtitle':
            subs.append({'donde': 'dentro', 'indice': s['index'], 'codec': s.get('codec_name') or '', 'lang': lang,
                         'titulo': titulo, 'forzado': bool(disp.get('forced')) or bool(FORZADO.search(titulo)),
                         'sdh': bool(disp.get('hearing_impaired')) or bool(SDH.search(titulo)),
                         'latino': bool(LATINO.search(titulo)), 'subrr': 'subrr' in titulo.lower()})
    return subs, audio


def externos(ruta):
    """Subtítulos sueltos junto al vídeo: «<nombre>.<idioma>[.forced|.sdh…].srt»."""
    base = os.path.splitext(os.path.basename(ruta))[0]
    carpeta = os.path.dirname(ruta)
    out = []
    try:
        nombres = os.listdir(carpeta)
    except OSError:
        return out
    for f in nombres:
        if not f.startswith(base + '.') or not f.lower().endswith(EXT_SUB) or f.endswith('.tmp'):
            continue
        partes = f[len(base) + 1:].rsplit('.', 1)[0].lower().split('.')
        lang = next((corto(p) for p in partes if corto(p)), '')
        resto = ' '.join(partes)
        out.append({'donde': 'fuera', 'ruta': os.path.join(carpeta, f), 'codec': f.rsplit('.', 1)[1].lower(), 'lang': lang,
                    'titulo': f, 'forzado': bool(re.search(r'forced|forzad', resto)), 'sdh': bool(re.search(r'\b(sdh|hi|cc)\b', resto)),
                    'latino': bool(LATINO.search(resto))})
    return out


def describir(p):
    donde = 'incrustado' if p['donde'] == 'dentro' else 'archivo aparte'
    extra = ' · SDH' if p.get('sdh') else ''
    return f"{NOMBRE.get(p['lang'], p['lang'])} ({donde}{extra})"


def tiene_destino(subs, code2, latino=False, variante_vale=False):
    """¿Ya hay subtítulos completos (no forzados) en el idioma de destino?
    En español distingue España/Latinoamérica por el título de la pista, salvo que variante_vale."""
    for p in subs:
        if p['lang'] == code2 and not p['forzado'] and not p.get('subrr'):
            if code2 != 'es' or variante_vale or p['latino'] == latino:
                return p
    return None


def elegir_origen(subs, prioridad, code2):
    """La mejor pista de texto para traducir. prioridad: ['en','fr',...]; las demás van detrás.
    Devuelve (pista, motivo_si_no_hay)."""
    texto = [p for p in subs if p['codec'] in TEXTO and p['lang'] != code2 and not p['forzado'] and not p.get('subrr')]
    if not texto:
        if any(p['codec'] in IMAGEN and not p['forzado'] for p in subs):
            return None, 'solo_imagen'
        return None, 'sin_origen'

    def nota(p):
        pos = prioridad.index(p['lang']) if p['lang'] in prioridad else len(prioridad) + (0 if p['lang'] else 1)
        return (pos, p['sdh'], p['donde'] != 'dentro')
    return sorted(texto, key=nota)[0], ''


def elegir_imagen(subs, prioridad, code2):
    """La mejor pista de subtítulos de imagen (PGS/VobSub) para pasar a texto con OCR, o None."""
    img = [p for p in subs if p['codec'] in IMAGEN and p['donde'] == 'dentro' and p['lang'] != code2 and not p['forzado']]
    if not img:
        return None

    def nota(p):
        pos = prioridad.index(p['lang']) if p['lang'] in prioridad else len(prioridad) + (0 if p['lang'] else 1)
        return (pos, p['sdh'])
    return sorted(img, key=nota)[0]


# ------------------------------------------------------------------------------------------------ SRT
TIEMPO = re.compile(r'(\d+):(\d\d):(\d\d)[,.](\d{1,3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{1,3})')


def _ms(h, m, s, f):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(f.ljust(3, '0'))


def _ts(ms):
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def leer_texto(ruta):
    with open(ruta, 'rb') as fh:
        b = fh.read()
    for cod in ('utf-8-sig', 'utf-16', 'cp1252'):
        try:
            t = b.decode(cod)
            if cod == 'utf-16' and not b.startswith((b'\xff\xfe', b'\xfe\xff')):
                continue
            return t
        except UnicodeDecodeError:
            continue
    return b.decode('latin-1')


def parsear(texto):
    """[(inicio_ms, fin_ms, [líneas])]"""
    out = []
    for bloque in re.split(r'\n\s*\n', texto.replace('\r', '').strip()):
        lineas = bloque.split('\n')
        for i, l in enumerate(lineas[:3]):
            m = TIEMPO.search(l)
            if m:
                a, b = _ms(*m.groups()[:4]), _ms(*m.groups()[4:])
                tx = [x.strip() for x in lineas[i + 1:] if x.strip()]
                if tx:
                    out.append((a, b, tx))
                break
    return out


def escribir(cues, ruta):
    """Escribe en .tmp y renombra (nunca deja un archivo a medias)."""
    with open(ruta + '.tmp', 'w', encoding='utf-8') as fh:
        for n, (a, b, tx) in enumerate(cues, 1):
            fh.write(f'{n}\n{_ts(a)} --> {_ts(b)}\n' + '\n'.join(tx) + '\n\n')
    os.replace(ruta + '.tmp', ruta)


def extraer(video, pista):
    """Texto SRT de la pista elegida (incrustada → ffmpeg; aparte → se convierte si no es .srt)."""
    if pista['donde'] == 'fuera' and pista['codec'] == 'srt':
        return leer_texto(pista['ruta'])
    entrada = video if pista['donde'] == 'dentro' else pista['ruta']
    mapa = f"0:{pista['indice']}" if pista['donde'] == 'dentro' else '0:s:0'
    r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', entrada, '-map', mapa, '-f', 'srt', '-'],
                       capture_output=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError('ffmpeg no pudo sacar el subtítulo: ' + r.stderr.decode(errors='replace')[-300:])
    return r.stdout.decode('utf-8', errors='replace')


# ------------------------------------------------------------------------------------------------ preparar y montar
ETIQ = re.compile(r'</?(?:i|b|u|font)[^>]*>|\{\\[^}]*\}', re.I)
ANOT = re.compile(r'\[[^\]]*\]|\([A-ZÁÉÍÓÚÑ0-9 ,.\'-]{3,}\)')
HABLANTE = re.compile(r'^(-\s*)?[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 .\'-]{1,25}:\s*')
MUSICA = re.compile(r'^[♪♫#\s]+$')


def limpiar_sdh(lineas):
    out = []
    for l in lineas:
        l = ANOT.sub('', l)
        l = HABLANTE.sub(lambda m: m.group(1) or '', l)
        l = re.sub(r'\s{2,}', ' ', l).strip()
        if l and not MUSICA.match(l) and l not in ('-', '- '):
            out.append(l)
    return out


def preparar(cues, quitar_sdh):
    """Cada subtítulo → piezas para traducir. Diálogos («- A / - B») van por separado; el resto, en una frase.
    Devuelve (lista_de_cues_preparados, textos). Cada cue: (a, b, cursiva, [(guion, indice_texto)])."""
    prep, textos = [], []
    for a, b, tx in cues:
        cursiva = all(re.match(r'^\s*<i>', l, re.I) for l in tx) or (tx and re.match(r'^\s*<i>', tx[0], re.I) and re.search(r'</i>\s*$', tx[-1], re.I))
        lineas = [ETIQ.sub('', l).strip() for l in tx]
        if quitar_sdh:
            lineas = limpiar_sdh(lineas)
        lineas = [l for l in lineas if l]
        if not lineas:
            continue
        if len(lineas) > 1 and sum(1 for l in lineas if l.startswith('-')) >= 2:
            trozos, actual = [], None
            for l in lineas:
                if l.startswith('-') or actual is None:
                    actual = [l.lstrip('-–— ').strip()]
                    trozos.append(actual)
                else:
                    actual.append(l)
            piezas = []
            for t in trozos:
                piezas.append(('- ', len(textos)))
                textos.append(' '.join(t))
        else:
            piezas = [('', len(textos))]
            textos.append(' '.join(lineas))
        prep.append((a, b, bool(cursiva), piezas))
    return prep, textos


def partir(texto, ancho=42):
    """Una frase larga en dos líneas, cortando por el espacio más cercano al centro."""
    if len(texto) <= ancho:
        return [texto]
    mitad = len(texto) // 2
    huecos = [i for i, ch in enumerate(texto) if ch == ' ']
    if not huecos:
        return [texto]
    i = min(huecos, key=lambda x: abs(x - mitad))
    return [texto[:i].strip(), texto[i + 1:].strip()]


def montar(prep, traducidos):
    out = []
    for a, b, cursiva, piezas in prep:
        if len(piezas) == 1 and not piezas[0][0]:
            lineas = partir(traducidos[piezas[0][1]].strip())
        else:
            lineas = [g + traducidos[i].strip() for g, i in piezas]
        if cursiva:
            lineas = ['<i>' + l + '</i>' for l in lineas]
        out.append((a, b, lineas))
    return out
