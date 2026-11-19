# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-19

First public release.

### Added
- Translation of the subtitles a video already carries, for the series and movies chosen from Sonarr/Radarr, with six engines in a chain: DeepL, Claude (Anthropic), OpenAI-compatible LLMs, Google Cloud Translation, Microsoft Translator and LibreTranslate. Per-engine source languages, media type, monthly limit and *fallback* role.
- Bazarr automatic mode (translate what Bazarr has in *Wanted*, after N days) and delivery to Bazarr (rescan or upload).
- Output as a separate `.srt` or as a track inside the MKV, with a trash folder for the original and hard-link protection.
- OCR for image subtitles (PGS/VobSub) and for text burned into the picture, with Tesseract or a vision-capable engine.
- Per-episode view, activity log, ntfy notifications and Jellyfin/Emby refresh.
- **Sonarr/Radarr webhook** (`POST /api/webhook/sonarr`, `/api/webhook/radarr`): new imports and upgrades are queued immediately if the item is enabled in subrr. Token authentication (`SUBRR_WEBHOOK_TOKEN`, or generated and shown in *Settings → Connections*; accepted as `?token=`, `X-Api-Key` or Basic password). `Test` answers `200`; other events are ignored.
- Optional password for the web UI (`SUBRR_PASSWORD`, `SUBRR_USER`), configurable bind address (`SUBRR_BIND`) and `SUBRR_ALLOWED_ORIGINS` for reverse proxies.
- Docker: non-root user, health check on the configured port, pinned dependency ranges, example compose with the shared *arr network and the TRaSH `/data` convention.
- `SECURITY.md`, English and Spanish READMEs with an *arr integration guide.

### Security
- CSRF protection: POST requests of the UI must come from the same `Origin`/`Referer` as the `Host` (otherwise `403`).
- Saved keys are never reused against a new address: changing a connection or engine URL with an empty key field deletes the stored key; keys from environment variables only apply to the address of their own variable.
- Responses never contain saved keys; addresses with embedded credentials are refused.
- Hardening headers on every response (`X-Frame-Options`, `Content-Security-Policy: frame-ancestors`, `nosniff`, `Referrer-Policy`) and size limits on request bodies.
