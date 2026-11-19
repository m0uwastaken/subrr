# Registro de cambios

Aquí se anotan los cambios importantes del proyecto. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [0.1.0] - 2026-11-19

Primera versión pública.

### Añadido
- Traducción de los subtítulos que ya trae un vídeo, para las series y películas elegidas desde Sonarr/Radarr, con seis motores en cadena: DeepL, Claude (Anthropic), LLM compatibles con OpenAI, Google Cloud Translation, Microsoft Translator y LibreTranslate. Idiomas de origen, tipo de contenido, límite mensual y papel de *reserva* por motor.
- Modo automático de Bazarr (traducir lo que Bazarr tiene en *Wanted*, pasados N días) y entrega a Bazarr (reescaneo o subida).
- Salida como `.srt` aparte o como pista dentro del MKV, con papelera para el original y protección de enlaces duros.
- OCR de subtítulos de imagen (PGS/VobSub) y de texto grabado en la imagen, con Tesseract o un motor con visión.
- Ficha de cada episodio, registro de actividad, avisos con ntfy y aviso a Jellyfin/Emby para que relea el archivo.
- **Webhook de Sonarr/Radarr** (`POST /api/webhook/sonarr`, `/api/webhook/radarr`): las importaciones y mejoras nuevas se ponen en cola al instante si el elemento está activado en subrr. Autenticación por token (`SUBRR_WEBHOOK_TOKEN`, o generado y mostrado en *Ajustes → Conexiones*; se acepta como `?token=`, `X-Api-Key` o contraseña Basic). `Test` responde `200`; los demás eventos se ignoran.
- Contraseña opcional de la web (`SUBRR_PASSWORD`, `SUBRR_USER`), dirección de escucha configurable (`SUBRR_BIND`) y `SUBRR_ALLOWED_ORIGINS` para proxies inversos.
- Docker: usuario sin privilegios, comprobación de estado en el puerto configurado, rangos de dependencias fijados y compose de ejemplo con la red compartida de los *arr y la convención `/data` de TRaSH.
- `SECURITY.md` y un README en castellano con guía de integración con la suite *arr.

### Seguridad
- Protección contra CSRF: los POST de la web deben venir del mismo `Origin`/`Referer` que el `Host` (si no, `403`).
- Una clave guardada nunca se reutiliza con una dirección nueva: cambiar la dirección de una conexión o motor con el campo de clave vacío borra la clave guardada; las claves de variables de entorno solo se aplican a la dirección de su propia variable.
- Las respuestas nunca contienen claves guardadas; se rechazan las direcciones con credenciales incrustadas.
- Cabeceras de endurecimiento en todas las respuestas (`X-Frame-Options`, `Content-Security-Policy: frame-ancestors`, `nosniff`, `Referrer-Policy`) y límite de tamaño en los cuerpos de las peticiones.
