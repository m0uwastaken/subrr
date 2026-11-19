"""Motores de traducción y la cadena que decide cuál se usa.

Cada motor configurado (config.json → «motores», en orden de preferencia) tiene:
  tipo      uno de TIPOS
  activo    si se usa
  papel     principal | reserva (lo de reserva se marca provisional y se rehace con un principal cuando se pueda)
  idiomas   idiomas de ORIGEN para los que se usa («en,fr»; vacío = todos)
  limite    caracteres al mes (0 = sin límite; DeepL además consulta su propio cupo)
  media     todo | series | peliculas
  campos    sus datos (claves de API, dirección, modelo…)
"""
import json, os, re, time, urllib.error, urllib.request

from . import config as C

NOMBRES_LLM = {'en': 'English', 'fr': 'French', 'it': 'Italian', 'pt': 'Portuguese', 'de': 'German', 'es': 'Spanish', 'nl': 'Dutch',
               'pl': 'Polish', 'ru': 'Russian', 'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese', 'ar': 'Arabic', 'he': 'Hebrew',
               'tr': 'Turkish', 'sv': 'Swedish', 'da': 'Danish', 'nb': 'Norwegian', 'fi': 'Finnish', 'el': 'Greek', 'cs': 'Czech',
               'hu': 'Hungarian', 'ro': 'Romanian', 'uk': 'Ukrainian', 'ca': 'Catalan'}


class SinCupo(Exception):
    """Se ha acabado el cupo del motor."""


class Falla(Exception):
    """El motor no responde, devuelve un error o una respuesta que no sirve."""


def _post(url, datos, cabeceras, timeout):
    req = urllib.request.Request(url, data=json.dumps(datos).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', **cabeceras})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b'{}')


def _con_reintentos(fn, nombre, reintentar=(429, 500, 502, 503, 504, 529), cupo=(456,), intentos=4):
    espera = 4
    for i in range(intentos):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode(errors='replace')[:240]
            if e.code in cupo or (e.code == 403 and 'quota' in cuerpo.lower()):
                raise SinCupo(f'{nombre}: cupo agotado')
            if e.code in reintentar and i < intentos - 1:
                time.sleep(espera)
                espera *= 2
                continue
            raise Falla(f'{nombre} respondió {e.code}: {cuerpo}')
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if i < intentos - 1:
                time.sleep(espera)
                espera *= 2
                continue
            raise Falla(f'{nombre} no responde: {e}')


# motores con dirección propia: tipo → (variable de entorno, dirección por defecto)
URL_MOTOR = {'openai': ('OPENAI_BASE_URL', 'https://api.openai.com/v1'), 'libre': ('LIBRETRANSLATE_URL', 'http://libretranslate:5000')}


def url_efectiva(m):
    """Dirección que usa el motor (None si el tipo no tiene dirección configurable)."""
    if m.get('tipo') not in URL_MOTOR:
        return None
    var, defecto = URL_MOTOR[m['tipo']]
    return ((m.get('campos') or {}).get('url') or os.environ.get(var) or defecto).strip().rstrip('/')


def campo(m, clave, var=None, defecto=''):
    """Valor de un campo del motor; si está vacío, la variable de entorno.
    La clave de una variable de entorno solo vale para la dirección de esa misma variable: si el usuario pone otra, no se envía."""
    v = (m.get('campos') or {}).get(clave)
    if not v and var and clave == 'key' and m.get('tipo') in URL_MOTOR:
        uvar, udef = URL_MOTOR[m['tipo']]
        if url_efectiva(m) != (os.environ.get(uvar) or udef).strip().rstrip('/'):
            var = None
    return (v or (os.environ.get(var) if var else '') or defecto).strip()


# ================================================================ DeepL
DEEPL_ORIGEN = {'en', 'fr', 'it', 'pt', 'de', 'nl', 'pl', 'ru', 'ja', 'ko', 'zh', 'ar', 'he', 'tr', 'sv', 'da', 'nb', 'fi', 'el', 'cs',
                'hu', 'ro', 'uk', 'es'}


def _deepl_url(m):
    k = campo(m, 'key', 'DEEPL_KEY')
    return campo(m, 'url', None, 'https://api-free.deepl.com' if k.endswith(':fx') else 'https://api.deepl.com').rstrip('/'), k


def deepl_traducir(m, textos, origen, destino, contexto):
    url, k = _deepl_url(m)
    if not destino.get('deepl'):
        raise Falla('DeepL no traduce a ' + destino['nombre'])
    datos = {'text': textos, 'target_lang': destino['deepl'], 'split_sentences': '0', 'preserve_formatting': True,
             'model_type': 'prefer_quality_optimized'}
    if origen in DEEPL_ORIGEN:
        datos['source_lang'] = origen.upper()
    if contexto:
        datos['context'] = contexto            # no se cobra: ayuda con frases partidas entre subtítulos
    f = campo(m, 'formalidad', None, 'default')
    if f != 'default':
        datos['formality'] = 'prefer_' + f
    r = _con_reintentos(lambda: _post(url + '/v2/translate', datos, {'Authorization': 'DeepL-Auth-Key ' + k}, 90), 'DeepL')
    return [t['text'] for t in r.get('translations', [])]


def deepl_uso(m):
    url, k = _deepl_url(m)
    req = urllib.request.Request(url + '/v2/usage', headers={'Authorization': 'DeepL-Auth-Key ' + k})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read())
    return {'usados': d.get('character_count', 0), 'limite': d.get('character_limit', 0)}


# ================================================================ LibreTranslate
def libre_traducir(m, textos, origen, destino, contexto):
    url = campo(m, 'url', 'LIBRETRANSLATE_URL', 'http://libretranslate:5000').rstrip('/')
    datos = {'q': textos, 'source': origen or 'auto', 'target': destino['libre'], 'format': 'text'}
    k = campo(m, 'key', 'LIBRETRANSLATE_KEY')
    if k:
        datos['api_key'] = k
    r = _con_reintentos(lambda: _post(url + '/translate', datos, {}, 900), 'LibreTranslate', intentos=3)
    out = r.get('translatedText')
    return [out] if isinstance(out, str) else out


def libre_estado(m):
    url = campo(m, 'url', 'LIBRETRANSLATE_URL', 'http://libretranslate:5000').rstrip('/')
    with urllib.request.urlopen(url + '/languages', timeout=10) as r:
        return [x['code'] for x in json.loads(r.read())]


# ================================================================ Google Cloud Translation (v2, clave de API)
def google_traducir(m, textos, origen, destino, contexto):
    k = campo(m, 'key', 'GOOGLE_TRANSLATE_KEY')
    datos = {'q': textos, 'target': destino['google'], 'format': 'text'}
    if origen:
        datos['source'] = origen
    r = _con_reintentos(lambda: _post('https://translation.googleapis.com/language/translate/v2?key=' + k, datos, {}, 90),
                        'Google', cupo=())
    import html
    return [html.unescape(t['translatedText']) for t in r['data']['translations']]


# ================================================================ Microsoft Translator (Azure)
def azure_traducir(m, textos, origen, destino, contexto):
    k = campo(m, 'key', 'AZURE_TRANSLATOR_KEY')
    region = campo(m, 'region', 'AZURE_TRANSLATOR_REGION')
    url = 'https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to=' + destino['azure'] + (f'&from={origen}' if origen else '')
    cab = {'Ocp-Apim-Subscription-Key': k}
    if region:
        cab['Ocp-Apim-Subscription-Region'] = region
    r = _con_reintentos(lambda: _post(url, [{'Text': t} for t in textos], cab, 90), 'Microsoft', cupo=(403,))
    return [x['translations'][0]['text'] for x in r]


# ================================================================ LLMs (Claude y compatibles con OpenAI)
def _prompt(m, textos, origen, destino, contexto):
    sistema = (f"You are a professional subtitle translator. Translate the numbered subtitle lines from "
               f"{NOMBRES_LLM.get(origen, 'the original language')} into {destino['llm']}.\n"
               "Rules:\n- Output exactly one line per input line, in the same order, as «N|translation».\n"
               "- Keep it natural and colloquial, like professional subtitles; keep names as they are.\n"
               "- A line can be the continuation of the previous one: translate so they read well together, but keep each in its line.\n"
               "- Keep it short enough to be read on screen. No notes, no explanations, nothing else.")
    extra = campo(m, 'instrucciones')
    if extra:
        sistema += '\nExtra instructions from the user: ' + extra
    usuario = ''
    if contexto:
        usuario += 'Previous lines, for context only (do NOT translate them):\n' + contexto + '\n\n'
    usuario += 'Lines to translate:\n' + '\n'.join(f'{i}|{t}' for i, t in enumerate(textos, 1))
    return sistema, usuario


def _leer_numeradas(texto, n):
    out = {}
    for linea in texto.splitlines():
        mm = re.match(r'^\s*(\d+)\s*[|:.)\]-]\s?(.*)$', linea)
        if mm:
            i = int(mm.group(1))
            if 1 <= i <= n and i not in out:
                out[i] = mm.group(2).strip()
    if len(out) != n:
        raise Falla(f'el modelo devolvió {len(out)} de {n} líneas')
    return [out[i] for i in range(1, n + 1)]


def claude_traducir(m, textos, origen, destino, contexto):
    try:
        import anthropic
    except ImportError:
        raise Falla('falta el paquete «anthropic» (pip install anthropic); la imagen de Docker de subrr ya lo trae')
    k = campo(m, 'key', 'ANTHROPIC_API_KEY')
    modelo = campo(m, 'modelo', None, 'claude-opus-5-5')
    esfuerzo = campo(m, 'esfuerzo', None, 'medium')
    sistema, usuario = _prompt(m, textos, origen, destino, contexto)
    cliente = anthropic.Anthropic(api_key=k, max_retries=3)
    pedir = dict(model=modelo, max_tokens=16000, system=sistema, messages=[{'role': 'user', 'content': usuario}],
                 output_config={'effort': esfuerzo})
    try:
        if modelo in ('claude-opus-5-5', 'claude-sonnet-5-5', 'claude-fable-5-1', 'claude-opus-5'):
            # si el modelo rechaza la petición, la API la reintenta sola con otro modelo
            r = cliente.beta.messages.create(betas=['server-side-fallback-2026-07-01'], fallbacks='default', **pedir)
        else:
            r = cliente.messages.create(**pedir)
    except anthropic.RateLimitError as e:
        raise Falla(f'Claude: límite de peticiones ({e.message})')
    except anthropic.AuthenticationError:
        raise Falla('Claude: clave de API incorrecta')
    except anthropic.APIStatusError as e:
        if e.status_code == 400 and 'credit' in str(e.message).lower():
            raise SinCupo('Claude: sin saldo en la cuenta')
        raise Falla(f'Claude respondió {e.status_code}: {e.message}')
    except anthropic.APIConnectionError as e:
        raise Falla(f'Claude no responde: {e}')
    if r.stop_reason == 'refusal':
        raise Falla('Claude rechazó traducir este fragmento')
    if r.stop_reason == 'max_tokens':
        raise Falla('Claude se quedó sin espacio para la respuesta')
    return _leer_numeradas(''.join(b.text for b in r.content if b.type == 'text'), len(textos))


def openai_traducir(m, textos, origen, destino, contexto):
    base = campo(m, 'url', 'OPENAI_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    k = campo(m, 'key', 'OPENAI_API_KEY')
    modelo = campo(m, 'modelo', 'OPENAI_MODEL')
    if not modelo:
        raise Falla('falta el modelo')
    sistema, usuario = _prompt(m, textos, origen, destino, contexto)
    datos = {'model': modelo, 'messages': [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}]}
    t = campo(m, 'temperatura')
    if t:
        datos['temperature'] = float(t)
    cab = {'Authorization': 'Bearer ' + k} if k else {}
    r = _con_reintentos(lambda: _post(base + '/chat/completions', datos, cab, 600), 'LLM', cupo=(402,))
    try:
        texto = r['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise Falla('respuesta rara del LLM: ' + json.dumps(r)[:200])
    return _leer_numeradas(texto, len(textos))


# ================================================================ registro
# campos: (clave, etiqueta, tipo [texto|secreto|sel|largo], defecto, ayuda, opciones)
TIPOS = {
    'deepl': {'nombre': 'DeepL', 'tanda': 40, 'contexto': 6, 'fn': deepl_traducir,
              'ayuda': 'Muy buena calidad. La API Free da 500.000 caracteres al mes gratis (≈ 20 episodios).',
              'campos': [('key', 'Clave de API', 'secreto', '', 'En deepl.com → Cuenta → Claves API. Las Free acaban en «:fx».', None),
                         ('formalidad', 'Trato', 'sel', 'default', 'Solo en algunos idiomas (en español sí).',
                          (('default', 'Automático'), ('less', 'Tuteo'), ('more', 'Usted')))]},
    'claude': {'nombre': 'Claude (Anthropic)', 'tanda': 60, 'contexto': 8, 'fn': claude_traducir,
               'ayuda': 'La mejor calidad con jerga y contexto. De pago por uso (clave de console.anthropic.com).',
               'campos': [('key', 'Clave de API', 'secreto', '', 'console.anthropic.com → API keys.', None),
                          ('modelo', 'Modelo', 'texto', 'claude-opus-5-5',
                           'Por episodio, aprox.: claude-opus-5-5 0,30 $ · claude-sonnet-5-5 0,15 $ · claude-haiku-5-5 0,01 $.', None),
                          ('esfuerzo', 'Esfuerzo', 'sel', 'medium', 'Más esfuerzo = algo mejor y más caro.',
                           (('low', 'Bajo'), ('medium', 'Medio'), ('high', 'Alto'))),
                          ('instrucciones', 'Instrucciones extra', 'largo', '', 'Opcional. P. ej.: «No traduzcas los nombres de las unidades militares».', None)]},
    'openai': {'nombre': 'LLM compatible con OpenAI', 'tanda': 50, 'contexto': 6, 'fn': openai_traducir,
               'ayuda': 'OpenAI, Gemini, OpenRouter, Mistral, Groq… o un modelo local con Ollama o LM Studio.',
               'campos': [('url', 'Dirección base', 'texto', 'https://api.openai.com/v1',
                           'Ollama: http://ollama:11434/v1 · Gemini: https://generativelanguage.googleapis.com/v1beta/openai · '
                           'OpenRouter: https://openrouter.ai/api/v1', None),
                          ('key', 'Clave de API', 'secreto', '', 'Vacía para Ollama/LM Studio.', None),
                          ('modelo', 'Modelo', 'texto', '', 'P. ej. gpt-4.1-mini, gemini-2.5-flash, qwen2.5:14b…', None),
                          ('temperatura', 'Temperatura', 'texto', '', 'Vacío = la del modelo. 0,2-0,4 va bien para traducir.', None),
                          ('instrucciones', 'Instrucciones extra', 'largo', '', 'Opcional.', None)]},
    'google': {'nombre': 'Google Cloud Translation', 'tanda': 100, 'contexto': 0, 'fn': google_traducir,
               'ayuda': 'API de pago de Google Cloud (500.000 caracteres/mes gratis). Necesita una clave con la API activada.',
               'campos': [('key', 'Clave de API', 'secreto', '', 'Google Cloud → APIs y servicios → Credenciales.', None)]},
    'azure': {'nombre': 'Microsoft Translator', 'tanda': 100, 'contexto': 0, 'fn': azure_traducir,
              'ayuda': 'Azure AI Translator. El nivel F0 da 2 millones de caracteres al mes gratis.',
              'campos': [('key', 'Clave', 'secreto', '', 'Portal de Azure → tu recurso Translator → Claves y punto de conexión.', None),
                         ('region', 'Región', 'texto', '', 'La del recurso, p. ej. westeurope (vacía si es global).', None)]},
    'libre': {'nombre': 'LibreTranslate', 'tanda': 25, 'contexto': 0, 'fn': libre_traducir,
              'ayuda': 'Gratis y local (tu propio contenedor), sin cuentas. Calidad bastante más literal. Ideal de reserva.',
              'campos': [('url', 'Dirección', 'texto', 'http://libretranslate:5000', 'La de tu contenedor de LibreTranslate.', None),
                         ('key', 'Clave', 'secreto', '', 'Solo si tu LibreTranslate pide clave.', None)]},
}


def disponible(m):
    """(ok, motivo) sin hacer peticiones."""
    t = m.get('tipo')
    if t not in TIPOS:
        return False, 'tipo desconocido'
    env = {'deepl': 'DEEPL_KEY', 'claude': 'ANTHROPIC_API_KEY', 'google': 'GOOGLE_TRANSLATE_KEY', 'azure': 'AZURE_TRANSLATOR_KEY'}
    if t in env and not campo(m, 'key', env[t]):
        return False, 'falta la clave'
    if t == 'openai' and not campo(m, 'modelo', 'OPENAI_MODEL'):
        return False, 'falta el modelo'
    if t == 'claude':
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False, 'falta el paquete «anthropic»'
    return True, ''


def cupo(m):
    """Caracteres que le quedan este mes (None = sin límite conocido) y texto para la web."""
    restante, texto = None, ''
    lim = int(m.get('limite') or 0)
    usados = C.uso_mes(m['id'])
    if lim:
        restante = max(0, lim - usados)
        texto = f'{usados:,} de {lim:,} este mes'.replace(',', '.')
    else:
        texto = f'{usados:,} caracteres este mes'.replace(',', '.')
    if m['tipo'] == 'deepl' and disponible(m)[0]:
        try:
            u = deepl_uso(m)
            if u['limite']:
                r2 = max(0, u['limite'] - u['usados'])
                restante = r2 if restante is None else min(restante, r2)
                texto = f"DeepL: {u['usados']:,} de {u['limite']:,} este mes".replace(',', '.')
        except Exception as ex:
            texto += f' · no pude consultar el cupo ({str(ex)[:60]})'
    return restante, texto


def probar(m, destino):
    """Traduce una frase de prueba. Devuelve (ok, texto)."""
    ok, motivo = disponible(m)
    if not ok:
        return False, motivo
    try:
        r = TIPOS[m['tipo']]['fn'](m, ['Hello! How are you doing today?', "I'll be right back, don't go anywhere."], 'en', destino, '')
        return True, ' / '.join(r)
    except (Falla, SinCupo) as e:
        return False, str(e)
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'[:200]


# ================================================================ la cadena
def candidatos(origen, tipo_media, preferido=''):
    """Motores que pueden traducir este origen, en orden: (principales, reservas)."""
    lista = [m for m in C.cfg()['motores'] if m.get('activo')]
    if preferido:
        lista.sort(key=lambda m: m['id'] != preferido)
    prin, res = [], []
    for m in lista:
        if not disponible(m)[0]:
            continue
        idiomas = [x.strip() for x in (m.get('idiomas') or '').split(',') if x.strip()]
        if idiomas and origen not in idiomas:
            continue
        media = m.get('media', 'todo')
        if media != 'todo' and media != tipo_media:
            continue
        (res if m.get('papel') == 'reserva' and m['id'] != preferido else prin).append(m)
    return prin, res


def hay_principal(origen, tipo_media, caracteres):
    for m in candidatos(origen, tipo_media)[0]:
        r, _ = cupo(m)
        if r is None or r >= caracteres:
            return True
    return False


def traducir(textos, origen, destino, tipo_media, preferido='', progreso=lambda n, t, nombre: None):
    """Traduce todas las frases recorriendo la cadena: si un motor falla o se queda sin cupo, sigue el siguiente
    desde donde iba. Devuelve (traducidos, usados {id: frases}, provisional, notas)."""
    prin, res = candidatos(origen, tipo_media, preferido)
    cadena = [(m, False) for m in prin] + [(m, True) for m in res]
    if not cadena:
        raise Falla('No hay ningún motor activo que pueda traducir desde ' + (NOMBRES_LLM.get(origen) or 'este idioma'))
    total = len(textos)
    necesita = sum(len(t) for t in textos)
    out = [None] * total
    usados, notas, provisional = {}, [], False
    i = 0
    for m, es_reserva in cadena:
        if i >= total:
            break
        t = TIPOS[m['tipo']]
        restante, _ = cupo(m)
        if restante is not None and restante < sum(len(x) for x in textos[i:]):
            notas.append(f"{m['nombre']}: cupo insuficiente ({restante:,} caracteres libres)".replace(',', '.'))
            continue
        tam = t['tanda']
        while i < total:
            tanda = textos[i:i + tam]
            while sum(len(x) for x in tanda) > 50000 and len(tanda) > 1:
                tanda = tanda[:len(tanda) // 2]
            contexto = '\n'.join(textos[max(0, i - t['contexto']):i]) if t['contexto'] else ''
            try:
                r = t['fn'](m, tanda, origen, destino, contexto)
                if not isinstance(r, list) or len(r) != len(tanda) or any(x is None for x in r):
                    raise Falla(f'devolvió {len(r) if isinstance(r, list) else "?"} de {len(tanda)} frases')
            except Falla as e:
                if tam > 10 and m['tipo'] in ('claude', 'openai') and 'líneas' in str(e):
                    tam = max(10, tam // 2)          # los LLM a veces se comen líneas: probar con tandas más pequeñas
                    continue
                notas.append(f"{m['nombre']}: {e}")
                break
            except SinCupo as e:
                notas.append(str(e))
                break
            out[i:i + len(tanda)] = r
            C.sumar_uso(m['id'], sum(len(x) for x in tanda))
            usados[m['id']] = usados.get(m['id'], 0) + len(tanda)
            provisional = provisional or es_reserva
            i += len(tanda)
            progreso(i, total, m['nombre'])
    if i < total:
        raise Falla('Ningún motor pudo terminar: ' + ' · '.join(notas[-3:]))
    return out, usados, provisional, notas
