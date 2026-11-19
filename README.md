# subrr

**Translate the subtitles your media already has into your language** — for the series and movies in Sonarr/Radarr, or automatically for whatever Bazarr can't find.

subrr looks at each video, picks the best text subtitle it carries (embedded or a separate file, English first by default), translates it and saves it next to the video as `movie.es.srt` — or as a new track inside the MKV, set as default. Jellyfin, Emby, Plex and Bazarr pick it up like any other subtitle.

> The web interface is in Spanish for now. Contributions for other languages are welcome.

## Features

- **Six translation engines, chained** — DeepL, Claude (Anthropic), any OpenAI-compatible LLM (OpenAI, Gemini, OpenRouter, Mistral, Groq, a local Ollama or LM Studio…), Google Cloud Translation, Microsoft Translator and LibreTranslate (free, self-hosted).
  - Put them in order; the first one that fits is used. If it fails or runs out of quota halfway, the next one continues from where it stopped.
  - Per engine: only for some source languages (e.g. an LLM only for Japanese/Korean), only for series or only for movies, a monthly character limit, and *fallback* role (its output is marked as provisional and redone with a primary engine when one is available again — e.g. when your DeepL quota resets).
  - Each series/movie can have its own preferred engine.
- **Bazarr integration**
  - *Automatic mode*: translate only what Bazarr has in *Wanted* for your language, after waiting N days so Bazarr gets a chance to find a real one.
  - After saving, subrr asks Bazarr to rescan, or hands the file to Bazarr so it stores it and records it in its history. Either way Bazarr stops searching for it.
- **Safe by design** — never modifies an existing file: it writes a temp file and renames. It only overwrites subtitles it created itself. Before putting a track inside an MKV, the original goes to a trash folder for N days (a hard link, so it takes no extra space). It won't remux videos with hard links (e.g. torrents still seeding) unless you allow it.
- **OCR**
  - *Image subtitles* (Blu-ray PGS, DVD VobSub): if a video has no text subtitles, subrr renders the bitmap track, reads it and translates it.
  - *Text burned into the picture* (optional, per series, or with a button on each episode): burned-in subtitles (yellow or white),
    time/place captions in the lower corners and text cards on dark backgrounds (epilogues). Typical of dubbed releases, where the parts in
    another language are subtitled in the picture. What is already in the text track is skipped; the rest is translated and added at the
    top of the screen so it doesn't cover the burned text. Takes a few minutes per episode.
  - Reader: **Tesseract** (free, local; included in the Docker image) or any engine with **vision** (Claude, or an OpenAI-compatible model
    that accepts images), which reads better and tells subtitles apart from signs or phone screens.
- Smart source selection: language priority, skips forced tracks, uses image-based (PGS/VobSub) tracks only when there is no text one, cleans SDH annotations (`[door closes]`, `♪`, `JOHN:`), keeps italics and two-speaker dialogue lines.
- Target language configurable (Spanish from Spain or Latin America, English, French, German, Italian, Portuguese, Catalan, Dutch, Polish…).
- Per-episode view: which tracks it has, what was used, side-by-side sample (original / translation), redo with another source track, remove.
- **Sonarr / Radarr webhook**: new imports and upgrades are translated as soon as they land, no waiting for the next scan.
- Notifications through [ntfy](https://ntfy.sh). Tells Jellyfin/Emby to refresh the file.
- No database; only `numpy` (OCR) and `anthropic` (Claude engine) as Python dependencies. Settings in a JSON file.

## Quick start (Docker)

```bash
git clone https://github.com/m0uwastaken/subrr.git
cd subrr
cp docker-compose.example.yml docker-compose.yml   # edit paths and keys
docker compose up -d --build
```

> **Do not expose subrr to the internet.** It has no user accounts and holds your API keys. Keep it on your LAN or VPN and set `SUBRR_PASSWORD` (see [Security](#security)).

Open `http://<server>:3007` and go to **Ajustes**:

1. **Conexiones**: Sonarr and/or Radarr (URL + API key). Bazarr and Jellyfin are optional. Each has a *Probar* (test) button.
2. **Motores**: add at least one engine and press *Probar*. A good free combination: **DeepL API Free** (500,000 characters/month ≈ 20 episodes) as primary and **LibreTranslate** as fallback.
3. **General**: target language, where to save (separate `.srt`, inside the MKV, or both), Bazarr automatic mode, path mappings.

Then pick series (seasons) or movies in **Añadir**, enable the Bazarr automatic mode, and/or [add the webhook](#sonarr--radarr-webhook) so new downloads are translated right away.

### Paths

subrr must see the video files. The easiest way is to mount your media at the same path Sonarr/Radarr use. If not, add path mappings in *Ajustes → General → Rutas*, one per line:

```
/tv => /data/media/tv
/movies => /data/media/movies
```

### Environment variables

All optional — they are just initial values; whatever you set in the web UI wins.

| Variable | Meaning |
|---|---|
| `SUBRR_DATA` | Data folder (default `/config`) |
| `SUBRR_PORT` | Web port (default `3007`) |
| `SUBRR_BIND` | Address the web server listens on (default `0.0.0.0`, which Docker needs; use `127.0.0.1` outside Docker if you only want local access) |
| `SUBRR_PASSWORD` | Optional password for the web UI (HTTP Basic). `/salud` and the webhooks stay outside it. Recommended |
| `SUBRR_USER` | Optional user name for that login; if unset, any user name is accepted with the right password |
| `SUBRR_WEBHOOK_TOKEN` | Token for the Sonarr/Radarr webhooks. If unset, one is generated on first start, saved in `config.json` and shown (and regenerable) in *Ajustes → Conexiones* |
| `SUBRR_ALLOWED_ORIGINS` | Extra hosts accepted as `Origin`/`Referer` of the web forms, comma-separated (only needed behind a reverse proxy that rewrites the `Host` header) |
| `SONARR_URL`, `SONARR_KEY`, `RADARR_URL`, `RADARR_KEY` | Sonarr / Radarr |
| `BAZARR_URL`, `BAZARR_KEY` | Bazarr (optional) |
| `JELLYFIN_URL`, `JELLYFIN_KEY` | Jellyfin/Emby, to refresh files (optional) |
| `NTFY_URL`, `NTFY_TOPIC`, `NTFY_TOKEN` | Notifications (optional) |
| `DEEPL_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `GOOGLE_TRANSLATE_KEY`, `AZURE_TRANSLATOR_KEY`, `AZURE_TRANSLATOR_REGION`, `LIBRETRANSLATE_URL`, `LIBRETRANSLATE_KEY` | Engines: on first start, one engine is created for each key found |
| `PATH_MAP` | Path mappings, `remote=>local` separated by `;` |

`config/config.json` contains your API keys and the webhook token (it is written with `0600` permissions). Don't share it.

An API key coming from an environment variable is only used with the address from its own variable (or the default one): if you type a different address in the web UI and leave the key empty, the key is not sent there.

## Integration with the *arr stack

subrr talks to the **v3 API** that Sonarr v3/v4 and Radarr v3 to v5 expose, and to Bazarr's API. It never writes to their databases.

### Connections

In *Ajustes → Conexiones* (or with the `*_URL` / `*_KEY` variables):

| Service | URL (same Docker network) | Key |
|---|---|---|
| Sonarr | `http://sonarr:8989` | Settings → General → API Key |
| Radarr | `http://radarr:7878` | Settings → General → API Key |
| Bazarr (optional) | `http://bazarr:6767` | Settings → General → API Key |
| Jellyfin / Emby (optional) | `http://jellyfin:8096` | Dashboard → API Keys |

subrr and the other containers must share a Docker network to use those names (see the commented `networks:` lines in `docker-compose.example.yml`), or use `http://<host-ip>:<port>`. Each connection has a *Probar* button.

### Sonarr / Radarr webhook

By default subrr checks everything it manages every 10 minutes. With the webhook, Sonarr/Radarr tell subrr the moment they import or upgrade a file, and it is queued immediately.

1. In subrr, open *Ajustes → Conexiones* and copy the webhook URL (the token is generated the first time; you can also set it with `SUBRR_WEBHOOK_TOKEN`).
2. In **Sonarr**: *Settings → Connect → + → Webhook*. In **Radarr**: the same.
3. Fill in:
   - **Name**: `subrr`
   - **Notification Triggers**: tick **only** *On Import* and *On Upgrade*; leave everything else off (including *On Import Complete* in Sonarr v4: it would only repeat the same event).
   - **URL**: `http://subrr:3007/api/webhook/sonarr?token=YOUR_TOKEN` (Radarr: `/api/webhook/radarr?...`). Change `subrr` if your container has another name.
   - **Method**: `POST`. Leave *Username* and *Password* empty (if you prefer, the password may be the token; a custom header `X-Api-Key: YOUR_TOKEN` also works where the app lets you add headers).
4. Press **Test**: subrr answers `200` and does nothing. **Save**.

What it does: on *Import*/*Upgrade* it queues the translation of that episode or movie, but **only if you already enabled it in subrr** (the series/season or the movie was added in *Añadir*). Anything not enabled, paused, or handled by Bazarr automatic mode (which has its own waiting days) is ignored with a `200`. All other events (Grab, Rename, file deleted, health…) are ignored as well.

The endpoint is protected by its token (compared in constant time) and is exempt from `SUBRR_PASSWORD`. Without a valid token it answers `401`.

### Path mapping

subrr must open the video files, so it has to see them at some path. The simplest setup mounts your media at the **same path** as Sonarr/Radarr (the [TRaSH Guides](https://trash-guides.info/) layout uses `/data`, e.g. `/data/media/tv`), and then no mapping is needed.

If the paths differ, map them in *Ajustes → General → Rutas*, one per line, as `path-seen-by-the-arr => path-inside-subrr`. It is the same idea as Sonarr/Radarr's *Remote Path Mapping* (remote path → local path), where "remote" is what Sonarr/Radarr/Bazarr report and "local" is where subrr sees the file:

```
# Sonarr sees /tv, subrr sees /data/media/tv
/tv => /data/media/tv
/movies => /data/media/movies
```

Equivalent with an environment variable: `PATH_MAP=/tv=>/data/media/tv;/movies=>/data/media/movies`. The paths inside webhooks are mapped the same way; if subrr can't see a file it says so in its log and in the webhook response.

For Jellyfin/Emby there is a second, separate mapping (*Rutas de Jellyfin*: `path-inside-subrr => path-seen-by-Jellyfin`) used only to tell it which file changed.

### Bazarr

- Connect it in *Conexiones*. In Bazarr, add your target language to a language profile so missing subtitles show up in *Wanted*.
- **Automatic mode** (*Ajustes → General → Bazarr*): subrr translates what Bazarr still lacks in your language, after the days you choose so Bazarr can find a real one first.
- **Delivery**: *subrr saves it and Bazarr detects it* (subrr asks Bazarr to rescan the disk) or *hand it to Bazarr* (uploaded through Bazarr's API; Bazarr stores it and records it in its history). Either way Bazarr stops searching for that language.

### Jellyfin, Emby and Plex

- **Jellyfin / Emby**: add URL and API key in *Conexiones*: after saving a subtitle, subrr asks the server to re-read that file, so it shows up without waiting for a library scan.
- **Plex**: there is no direct integration. Plex reads `movie.es.srt` next to the video on its next library scan (or when you trigger *Scan Library Files*). A track added *inside* the MKV is picked up the same way.
- If Jellyfin jumps to another track when you use separate `.srt` files, choose *Guardar como → Pista dentro del mkv*.

### Supported versions

Sonarr v3 and v4, Radarr v3 to v5 (API v3), Bazarr 1.x. Webhook payloads from both major versions are accepted.

## Security

subrr is built for a trusted home network, not for the internet.

- The web UI has no user accounts. Set **`SUBRR_PASSWORD`** to require a password (HTTP Basic; compared in constant time). `/salud` (health check) and the webhooks are the only things outside it, and the webhooks need their token.
- **POST requests** from the UI must come from the same site: `Origin` (or `Referer`) has to match the `Host` of the request, otherwise `403` (protection against CSRF). A request with neither header (e.g. `curl`) is only accepted if it carries the key in an `X-Api-Key` header: the value of `SUBRR_PASSWORD`, or the webhook token if no password is set. Behind a reverse proxy that changes the `Host`, list your public host name in `SUBRR_ALLOWED_ORIGINS`.
- API keys are never sent back to the browser (password fields stay empty), and addresses with `user:password@` or `?key=` in them are refused: use the key fields. If you change a service's address and leave its key empty, the saved key is deleted instead of being sent to the new address.
- The container runs as a non-root user (uid 1000 by default; use `user:` in the compose file to match your media owner).
- Keep it off the internet. If you need remote access use a VPN (Tailscale, WireGuard) or a reverse proxy with its own authentication and HTTPS, and keep `SUBRR_PASSWORD` too. The password and the webhook token travel in clear text over plain HTTP.

Read [SECURITY.md](SECURITY.md) for the threat model and how to report a vulnerability privately.

## Engines: cost and quality (rough guide)

| Engine | Cost | Quality on dialogue |
|---|---|---|
| DeepL API Free | free up to 500k chars/month | very good |
| Claude (`claude-opus-5-5` / `claude-sonnet-5-5` / `claude-haiku-5-5`) | ≈ $0.30 / $0.15 / $0.01 per episode | best with slang and context |
| OpenAI-compatible LLM | depends on the model; free with Ollama | good to very good |
| Google Cloud Translation | 500k chars/month free, then paid | good |
| Microsoft Translator | 2M chars/month free (F0) | good |
| LibreTranslate (self-hosted) | free | literal; good as fallback |

A 45-minute episode is about 25,000 characters.

## Running without Docker

Python 3.10+, `ffmpeg`/`ffprobe`, `mkvmerge` (MKVToolNix) and, for OCR, `tesseract` in the PATH:

```bash
pip install -r requirements.txt    # numpy: OCR · anthropic: Claude engine
SUBRR_DATA=./config SUBRR_BIND=127.0.0.1 python -m subrr
```

## Known limitations

- Burned-in text detection looks for light (white/yellow) text in the usual places; unusual styles or positions can be missed, and very
  short lines sometimes too. Check the list shown in each episode.
- Machine translation of a subtitle that is itself a translation loses nuance. Prefer English or the original language as source.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT © 2026 m0uwastaken
