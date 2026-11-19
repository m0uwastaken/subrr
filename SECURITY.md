# Política de seguridad

## Modelo de amenazas

subrr es una herramienta para alojar tú mismo, pensada para una **red doméstica de confianza**. No está endurecida para ser un servicio web público.

Qué protege y qué da por supuesto:

- **No hay cuentas de usuario.** Cualquiera que pueda abrir la web puede cambiar los ajustes, añadir motores de traducción y conexiones, y ver el estado de tu biblioteca. La web guarda las claves de API (Sonarr, Radarr, Bazarr, motores de traducción) en `config/config.json`.
- **No lo expongas a internet** (ni redirección de puertos ni proxy inverso público sin autenticación). Usa tu red local, una VPN como Tailscale o WireGuard, o un proxy inverso que añada su propia autenticación y HTTPS.
- **Define `SUBRR_PASSWORD`.** Activa la autenticación HTTP Basic en toda la web (con comparación en tiempo constante). Solo quedan fuera `/salud` (comprobación de estado) y los webhooks de Sonarr/Radarr. La autenticación Basic y el token del webhook viajan en claro por HTTP sin cifrar, así que fuera de una red de confianza ponlo detrás de HTTPS.
- **Los webhooks** (`/api/webhook/sonarr`, `/api/webhook/radarr`) se protegen con un token (`SUBRR_WEBHOOK_TOKEN`, o uno generado en el primer arranque). Un token válido solo puede pedirle a subrr que traduzca elementos que ya tengas activados; no puede cambiar ajustes. El token va en la URL, así que puede aparecer en los registros de las apps *arr o en los de un proxy inverso: trata la URL como un secreto y regenera el token en *Ajustes → Conexiones* si se filtra.
- **CSRF**: todo POST de la web debe llevar un `Origin` (o `Referer`) igual al `Host`; si no, recibe un `403`. Un POST sin ninguna de las dos cabeceras (por ejemplo con `curl`) solo se acepta con la clave en `X-Api-Key`: el valor de `SUBRR_PASSWORD` o, si no hay contraseña, el token del webhook (así el token del webhook, que viaja en URLs, no puede cambiar ajustes cuando existe una contraseña). Detrás de un proxy inverso que reescriba el `Host`, añade tu nombre público a `SUBRR_ALLOWED_ORIGINS`.
- **Los secretos no vuelven al navegador**: los campos de contraseña salen vacíos, se rechazan las direcciones con credenciales (`usuario:clave@`, `?clave=`) y las claves guardadas o de entorno se enmascaran en cualquier respuesta. Si cambias la dirección de un servicio y dejas la clave vacía, se borra la clave guardada en vez de enviarse a la dirección nueva.
- **Peticiones desde el servidor**: quien pueda usar la web puede hacer que subrr envíe peticiones a cualquier dirección que alcance (las direcciones de servicios y motores son configurables) y leer vídeos de la carpeta de medios montada. Otra razón para no dar la web a gente de poca confianza.
- **Contenedor**: corre con un usuario sin privilegios. Monta los medios solo con los permisos necesarios: subrr tiene que poder escribir junto a los vídeos (subtítulos) y, si eliges incrustar pistas, reescribir el MKV (el original va antes a una papelera).
- Lo que no cubre: protección contra *DNS rebinding* (no se valida la cabecera `Host` en los GET), límite de intentos de acceso fallidos y TLS (usa un proxy inverso).

## Cómo avisar de una vulnerabilidad

Por favor, **no abras una incidencia pública** para un problema de seguridad.

Usa el aviso privado de GitHub: en la página del repositorio ve a **Security → Report a vulnerability** (<https://github.com/m0uwastaken/subrr/security/advisories/new>). Describe qué has encontrado, cómo reproducirlo y qué impacto crees que tiene.

Puedes esperar una respuesta en unos días. Es un proyecto personal que mantiene una sola persona, así que no hay plazos formales, pero los problemas de seguridad van primero. Cuando salga el arreglo, si quieres, te mencionaré como descubridor.

## Versiones con soporte

Solo la última versión recibe arreglos.
