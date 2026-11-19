# Security policy

## Threat model

subrr is a self-hosted tool for a **trusted home network**. It is not hardened to be a public web service.

What it protects, and what it assumes:

- **No user accounts.** Anyone who can open the web UI can change the settings, add translation engines and connections, and read the status of your library. The UI holds API keys (Sonarr, Radarr, Bazarr, translation engines) in `config/config.json`.
- **Do not expose it to the internet** (no port forwarding, no public reverse proxy without authentication). Use your LAN, or a VPN such as Tailscale or WireGuard, or a reverse proxy that adds its own authentication and HTTPS.
- **Set `SUBRR_PASSWORD`.** It enables HTTP Basic authentication on the whole UI (comparison in constant time). Only `/salud` (health check) and the Sonarr/Radarr webhooks are outside it. Basic authentication and the webhook token are sent in clear text over plain HTTP, so on anything but a trusted network put it behind HTTPS.
- **Webhooks** (`/api/webhook/sonarr`, `/api/webhook/radarr`) are protected by a token (`SUBRR_WEBHOOK_TOKEN`, or one generated on first start). A valid token can only ask subrr to translate items you already enabled; it cannot change settings. The token is in the URL, so it may show up in the *arr logs or in a reverse proxy's access logs: treat the URL as a secret and regenerate the token in *Settings → Connections* if it leaks.
- **CSRF**: every POST of the UI must carry an `Origin` (or `Referer`) equal to the `Host`; otherwise it gets `403`. A POST without either header (e.g. `curl`) is accepted only with the key in `X-Api-Key`: the value of `SUBRR_PASSWORD`, or the webhook token when no password is set (so the webhook token, which travels in URLs, cannot change settings once a password exists). Behind a reverse proxy that rewrites `Host`, add your public host to `SUBRR_ALLOWED_ORIGINS`.
- **Secrets are not sent back to the browser**: password fields stay empty, addresses carrying credentials (`user:pass@`, `?key=`) are refused, and saved or environment keys are masked in any response. If a service address is changed and the key field is left empty, the saved key is deleted rather than sent to the new address.
- **Server-side requests**: whoever can use the UI can make subrr send requests to any address it can reach (the service and engine URLs are configurable) and read video files in the mounted media folder. Another reason not to give the UI to untrusted people.
- **Container**: runs as a non-root user. Mount media with only the permissions it needs; subrr must be able to write next to the videos (subtitles) and, if you choose to embed tracks, rewrite the MKV (the original goes to a trash folder first).
- Not covered: DNS rebinding protection (the `Host` header is not validated for GET requests), rate limiting of failed logins, TLS (use a reverse proxy).

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Use GitHub's private reporting: on the repository page go to **Security → Report a vulnerability** (<https://github.com/m0uwastaken/subrr/security/advisories/new>). Describe what you found, how to reproduce it and what you think the impact is.

You can expect an acknowledgement within a few days. It is a hobby project maintained by one person, so there is no formal SLA, but security problems come first. Once a fix is released you are welcome to be credited.

## Supported versions

Only the latest release receives fixes.
