# subrr

**Traduce a tu idioma los subtítulos que ya traen tus series y películas**: las que elijas de Sonarr/Radarr o, automáticamente, lo que Bazarr no encuentre.

subrr mira cada vídeo, elige la mejor pista de subtítulos de texto que lleve (dentro del vídeo o en un archivo aparte; por defecto, primero el inglés), la traduce y la guarda junto al vídeo como `pelicula.es.srt`, o como una pista nueva dentro del MKV marcada por defecto. Jellyfin, Emby, Plex y Bazarr la ven como cualquier otro subtítulo.

## Qué hace

- **Seis motores de traducción en cadena**: DeepL, Claude (Anthropic), cualquier LLM compatible con OpenAI (OpenAI, Gemini, OpenRouter, Mistral, Groq, Ollama o LM Studio en local…), Google Cloud Translation, Microsoft Translator y LibreTranslate (gratis, en tu servidor).
  - Se ordenan y se usa el primero que valga. Si falla o se queda sin cupo a mitad, el siguiente sigue desde donde iba.
  - Para cada motor puedes elegir: solo para ciertos idiomas de origen, solo series o solo películas, un límite de caracteres al mes y el papel de **reserva**. Lo que hace un motor de reserva se marca como provisional y se rehace con uno principal cuando vuelva a estar disponible, por ejemplo cuando se renueve el cupo de DeepL.
  - Cada serie o película puede tener su motor preferido.
- **Integración con Bazarr**:
  - **Modo automático**: traduce solo lo que Bazarr tiene en «Wanted» para tu idioma, después de esperar N días para darle tiempo a encontrar uno de verdad.
  - **Al guardar**: subrr le pide a Bazarr que vuelva a escanear el disco, o le entrega el archivo para que él lo guarde y lo apunte en su historial. En los dos casos Bazarr deja de buscarlo.
- **Seguro**: nunca modifica un archivo existente (escribe un temporal y lo renombra). Solo sobrescribe subtítulos hechos por él. Antes de meter una pista en un MKV, el original va a una papelera durante N días (con un enlace duro, así que no ocupa más). Si el vídeo tiene enlaces duros, como un torrent que se sigue compartiendo, no lo toca salvo que lo permitas.
- **Elige bien el origen**: respeta tu orden de idiomas preferidos, salta las pistas forzadas, usa las de imagen (PGS/VobSub) solo si no hay de texto, quita las anotaciones para sordos y conserva la cursiva y los diálogos a dos voces.
- **Idioma de destino configurable**.
- **Ficha de cada episodio**: pistas que tiene, cuál se usó, una muestra con el original y la traducción lado a lado, y botones para rehacer con otra pista o quitar el subtítulo.
- **OCR**:
  - **Subtítulos de imagen** (PGS de Blu-ray, VobSub de DVD): si un vídeo no trae subtítulos de texto, los lee y los traduce.
  - **Texto grabado en la imagen** (opcional, por serie o con un botón en cada episodio): subtítulos amarillos o blancos, rótulos de hora
    y lugar y pantallas de texto (epílogos), típicos de las versiones dobladas. Lo que ya está en la pista de texto se salta; el resto se
    traduce y se pone arriba para no tapar lo grabado.
  - **Lector**: Tesseract (gratis, local, incluido en la imagen de Docker) o un motor con visión (Claude o un modelo compatible con OpenAI
    que acepte imágenes), que lee mejor y distingue un subtítulo de un cartel.
- **Webhook de Sonarr/Radarr**: lo que se importa o se mejora se traduce nada más llegar, sin esperar a la siguiente pasada.
- Avisos con ntfy, y avisa a Jellyfin/Emby para que relea el archivo.

## Instalación (Docker)

```bash
git clone https://github.com/m0uwastaken/subrr.git
cd subrr
cp docker-compose.example.yml docker-compose.yml   # cambia rutas y claves
docker compose up -d --build
```

> **No expongas subrr a internet.** No tiene cuentas de usuario y guarda tus claves de API. Déjalo en tu red local o tu VPN y pon `SUBRR_PASSWORD` (mira [Seguridad](#seguridad)).

Abre `http://<servidor>:3007` → **Ajustes**:

1. **Conexiones**: Sonarr y/o Radarr (dirección y clave de API). Bazarr y Jellyfin son opcionales. Cada una tiene un botón «Probar».
2. **Motores**: añade al menos uno y pulsa «Probar». Una combinación gratuita que va bien: **DeepL API Free** (500.000 caracteres al mes, unos 20 episodios) de principal y **LibreTranslate** de reserva.
3. **General**: idioma de destino, dónde guardar (archivo aparte, dentro del MKV o las dos cosas), modo automático de Bazarr y mapeo de rutas.

subrr tiene que ver los vídeos en la misma ruta que Sonarr/Radarr. Si no es así, añade el mapeo en **Ajustes → General → Rutas** («/tv => /data/media/tv», uno por línea).

`config/config.json` guarda tus claves de API y el token del webhook (con permisos 0600). No lo compartas.

Variables de entorno de seguridad (todas opcionales): `SUBRR_PASSWORD` (contraseña de la web), `SUBRR_USER` (usuario; si no se define vale cualquiera con la contraseña correcta), `SUBRR_WEBHOOK_TOKEN` (token del webhook), `SUBRR_BIND` (dirección en la que escucha, por defecto `0.0.0.0`, necesaria en Docker) y `SUBRR_ALLOWED_ORIGINS` (hosts extra válidos como Origin/Referer tras un proxy inverso que cambie el `Host`). La lista completa de variables, los costes de cada motor y el uso sin Docker están en el [README en inglés](README.md).

## Integración con la suite *arr

subrr usa la **API v3** que ofrecen Sonarr v3/v4 y Radarr v3 a v5, y la API de Bazarr. Nunca escribe en sus bases de datos.

### Conexiones

En *Ajustes → Conexiones* (o con las variables `*_URL` / `*_KEY`):

| Servicio | Dirección (misma red de Docker) | Clave |
|---|---|---|
| Sonarr | `http://sonarr:8989` | Settings → General → API Key |
| Radarr | `http://radarr:7878` | Settings → General → API Key |
| Bazarr (opcional) | `http://bazarr:6767` | Settings → General → API Key |
| Jellyfin / Emby (opcional) | `http://jellyfin:8096` | Panel → Claves de API |

Para usar esos nombres, subrr y los demás contenedores tienen que compartir una red de Docker (mira las líneas `networks:` comentadas de `docker-compose.example.yml`); si no, usa `http://<ip-del-servidor>:<puerto>`. Cada conexión tiene un botón «Probar».

### Webhook de Sonarr y Radarr

Sin webhook, subrr revisa lo que gestiona cada 10 minutos. Con él, Sonarr/Radarr le avisan en el momento de importar o mejorar un archivo y se pone en cola al instante.

1. En subrr, abre *Ajustes → Conexiones* y copia la URL del webhook (el token se genera la primera vez; también puedes fijarlo con `SUBRR_WEBHOOK_TOKEN`).
2. En **Sonarr**: *Settings → Connect → + → Webhook*. En **Radarr**, igual.
3. Rellena:
   - **Name**: `subrr`
   - **Notification Triggers**: marca **solo** *On Import* y *On Upgrade*; deja todo lo demás sin marcar (también *On Import Complete* de Sonarr v4: repetiría el mismo aviso).
   - **URL**: `http://subrr:3007/api/webhook/sonarr?token=TU_TOKEN` (Radarr: `/api/webhook/radarr?...`). Cambia `subrr` si tu contenedor se llama de otra forma.
   - **Method**: `POST`. Deja *Username* y *Password* vacíos (si prefieres, la contraseña puede ser el token; la cabecera `X-Api-Key: TU_TOKEN` también vale donde la app deje añadir cabeceras).
4. Pulsa **Test**: subrr responde `200` y no hace nada. **Save**.

Qué hace: al importar o mejorar, pone en cola la traducción de ese episodio o película, pero **solo si ya lo tienes activado en subrr** (la serie o temporada, o la película, añadida en *Añadir*). Lo que no esté activado, esté en pausa o lo lleve el modo automático de Bazarr (que tiene sus propios días de espera) se ignora con un `200`. El resto de eventos (Grab, Rename, archivo borrado, salud…) también se ignoran.

El endpoint se protege con su token (se compara en tiempo constante) y queda fuera de `SUBRR_PASSWORD`. Sin un token válido responde `401`.

### Mapeo de rutas

subrr tiene que abrir los vídeos, así que debe verlos en alguna ruta. Lo más sencillo es montar tus medios en la **misma ruta** que Sonarr/Radarr (la convención de las [guías TRaSH](https://trash-guides.info/) es `/data`, p. ej. `/data/media/tv`); entonces no hace falta mapeo.

Si las rutas son distintas, mapéalas en *Ajustes → General → Rutas*, una por línea, como `ruta-que-ve-el-arr => ruta-dentro-de-subrr`. Es la misma idea que el *Remote Path Mapping* de Sonarr/Radarr (ruta remota → ruta local): «remota» es la que dicen Sonarr/Radarr/Bazarr y «local» donde subrr ve el archivo:

```
# Sonarr ve /tv, subrr ve /data/media/tv
/tv => /data/media/tv
/movies => /data/media/movies
```

Con una variable de entorno: `PATH_MAP=/tv=>/data/media/tv;/movies=>/data/media/movies`. Las rutas que llegan por webhook se traducen igual; si subrr no ve un archivo, lo dice en su registro y en la respuesta del webhook.

Para Jellyfin/Emby hay un segundo mapeo aparte (*Rutas de Jellyfin*: `ruta-dentro-de-subrr => ruta-que-ve-Jellyfin`), solo para decirle qué archivo ha cambiado.

### Bazarr

- Conéctalo en *Conexiones*. En Bazarr, añade tu idioma de destino a un perfil de idiomas para que lo que falte aparezca en *Wanted*.
- **Modo automático** (*Ajustes → General → Bazarr*): subrr traduce lo que a Bazarr aún le falta en tu idioma, pasados los días que elijas para que Bazarr pueda encontrar uno de verdad.
- **Entrega**: *lo guarda subrr y Bazarr lo detecta* (subrr le pide que reescanee el disco) o *dárselo a Bazarr* (se sube por su API; Bazarr lo guarda y lo apunta en su historial). En los dos casos Bazarr deja de buscarlo.

### Jellyfin, Emby y Plex

- **Jellyfin / Emby**: pon la dirección y la clave de API en *Conexiones*: al guardar un subtítulo, subrr le pide al servidor que relea el archivo y aparece sin esperar al escaneo.
- **Plex**: no hay integración directa. Plex lee `pelicula.es.srt` junto al vídeo en su siguiente escaneo (o al pulsar *Scan Library Files*). Una pista metida *dentro* del MKV se detecta igual.
- Si Jellyfin salta a otra pista con subtítulos en archivo aparte, elige *Guardar como → Pista dentro del mkv*.

### Versiones compatibles

Sonarr v3 y v4, Radarr v3 a v5 (API v3), Bazarr 1.x. Se aceptan los avisos del webhook de las dos versiones mayores.

## Seguridad

subrr está pensado para una red doméstica de confianza, no para internet.

- La web no tiene cuentas de usuario. Define **`SUBRR_PASSWORD`** para pedir contraseña (HTTP Basic, comparada en tiempo constante). Solo `/salud` (comprobación de estado) y los webhooks quedan fuera, y los webhooks exigen su token.
- Los **POST** de la web tienen que venir del mismo sitio: `Origin` (o `Referer`) debe coincidir con el `Host` de la petición; si no, `403` (protección contra CSRF). Una petición sin ninguna de las dos cabeceras (p. ej. `curl`) solo vale si lleva la clave en la cabecera `X-Api-Key`: el valor de `SUBRR_PASSWORD` o, si no hay contraseña, el token del webhook. Detrás de un proxy inverso que cambie el `Host`, pon tu nombre público en `SUBRR_ALLOWED_ORIGINS`.
- Las claves de API nunca se devuelven al navegador (los campos de contraseña salen vacíos) y se rechazan las direcciones con `usuario:clave@` o `?clave=` dentro: usa los campos de clave. Si cambias la dirección de un servicio y dejas su clave vacía, la guardada se borra en vez de enviarse a la dirección nueva.
- El contenedor corre con un usuario sin privilegios (uid 1000 por defecto; usa `user:` en el compose para que coincida con el dueño de tus vídeos).
- No lo publiques en internet. Para acceder desde fuera usa una VPN (Tailscale, WireGuard) o un proxy inverso con su propia autenticación y HTTPS, y deja también `SUBRR_PASSWORD`. Con HTTP sin cifrar, la contraseña y el token viajan en claro.

El modelo de amenazas y cómo avisar de una vulnerabilidad en privado están en [SECURITY.md](SECURITY.md).

## Limitaciones

- El texto grabado se busca claro (blanco o amarillo) y en los sitios habituales: estilos o posiciones raras, o líneas muy cortas,
  se pueden escapar. Revisa la lista que sale en cada episodio.

## Cambios

Mira [CHANGELOG.md](CHANGELOG.md).

## Licencia

MIT © 2026 m0uwastaken
