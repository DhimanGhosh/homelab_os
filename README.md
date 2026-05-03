# Music Player Plugin — Homelab OS

A self-hosted, browser-based music player for Homelab OS on Raspberry Pi. Streams your local music library from NAS storage, with playlist management, rich metadata, artist artwork, and a fully animated Now Playing experience.

---

## Version History

### v9.0.1 — Patch (current)
**Files changed:**
- `music-player/plugin.json`
- `music-player/docker/docker-compose.yml`
- `music-player/docker/app/config.py`
- `music-player/docker/static/css/styles.css`
- `homelab_os/core/plugin_manager/installer.py`

**Fixes:**
- **Scroll flicker in Now Playing (PC) — correctly fixed.** Root cause: the `v8.4.33` CSS block had `transition: min-height .06s linear` on `.now-playing-main`. Since JS updates `min-height` every animation frame (~16 ms), the 60 ms CSS transition lag caused total scroll-height to trail behind `scrollTop`, making the browser reset scroll position on every frame — producing visible flicker on short queues. Fix: a `v9.0.1` CSS block placed *after* `v8.4.33` strips `min-height` from the transition and sets `min-height: calc(210px + 100dvh)` on the queue sheet (desktop only), guaranteeing enough scroll room even with 1–3 songs. The `210px` value is derived from the collapse math: `collapseDistance (520) + 100dvh − compactHeight (310) = 210px + 100dvh`.
- **Version display now shows `v9.0.1`.** All three version sources updated: `plugin.json`, `docker-compose.yml` (`APP_VERSION` env var), and `config.py` (fallback default). The UI reads version from `/api/library` → `data.app.version`.
- **Playlist data loss on plugin update — fixed in installer.** `PluginInstaller._cleanup_existing_install()` previously called the full uninstall path on every reinstall, which ran `shutil.rmtree()` on the NAS data directory (`/mnt/nas/homelab/runtime/music-player/data/`), destroying all playlists. Now the update path only stops containers and removes the plugin *code* directory — the data directory is never touched on update. Only an explicit user-initiated uninstall removes data.

---

### v9.0.0 — Major
**Files changed:**
- `music-player/docker/static/js/script.js`
- `music-player/plugin.json`

**New features & fixes:**
- **URL routing / browser back button support.** Hash-based routing (`#home`, `#artists`, `#artists/ArtistName`, `#nowplaying`). `navigate()` calls `history.pushState()`. Now Playing open/close pushes and pops `#nowplaying`. Android back gesture and browser back button work correctly via a `popstate` handler that restores the previous view and context.
- **Shuffle queue reorder.** Pressing Shuffle immediately rearranges the current playback queue (current song stays at position 0, rest are randomised). Pressing Shuffle off restores the *exact original order* — current song's position is tracked and restored correctly.
- **Mobile footer swipe-up to open Now Playing.** Swipe up on the mini-player footer to reveal the Now Playing overlay with a thumb-driven animation. Progress is driven by `deltaY / window.innerHeight`; overlay `transform` and `opacity` update on each `touchmove`. Commits on release if `deltaY > 80px` or velocity `> 0.4 px/ms`.
- **Mobile drag-to-reorder no longer flickers.** Switched from per-item passive `touchmove` listeners to a single document-level `{ passive: false }` `touchmove` with `preventDefault()`, preventing page scroll during drag. Added `pointerEvents: none` trick so `elementFromPoint` locates the correct drop target beneath the dragged element.

---

## Architecture

### Persistent Storage

All user data is stored on the NAS, outside the container, so it survives plugin updates and Docker rebuilds:

```
/mnt/nas/homelab/runtime/music-player/data/
  ├── playlists.json          # All user playlists
  ├── artist_images.json      # Artist image index
  ├── artist_images/          # Downloaded artist images
  └── art_cache/              # Album art cache
```

Music files are read-only from:
```
/mnt/nas/media/music/
```

Both paths are bind-mounted into the container via `docker-compose.yml`. The `config.py` bootstrap creates all data directories and initialises `playlists.json` on first start.

**This is the canonical Homelab OS plugin persistence pattern.** Future plugins (e.g. Expense Tracker) should follow the same convention: store all runtime state under `/mnt/nas/homelab/runtime/<plugin-id>/data/`, bind-mount it in `docker-compose.yml`, and never rely on container-local storage or `localStorage`.

### Installer Update Contract

`PluginInstaller` (`homelab_os/core/plugin_manager/installer.py`) enforces:

| Scenario | Containers | Code directory | NAS data directory |
|---|---|---|---|
| **Update** (plugin in registry) | Stopped | Deleted & replaced | **Preserved** |
| **Orphan cleanup** (not in registry) | Stopped | Deleted | Deleted |
| **Explicit uninstall** | Stopped + `-v` | Deleted | Deleted |

### Network

| Setting | Value |
|---|---|
| Internal port | `8140` |
| Public port (Caddy proxy) | `8459` |
| Bind | `127.0.0.1:8140` |
| Access URL | `https://<tailscale-hostname>:8459` or via reverse proxy route |

### API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Single-page app shell |
| `GET` | `/api/library` | Full library scan + app metadata |
| `GET` | `/api/playlists` | All playlists |
| `POST` | `/api/playlists` | Create / rename / delete playlist |
| `POST` | `/api/playlists/add-tracks` | Add tracks to a playlist |
| `GET` | `/api/metadata/<relpath>` | Track metadata (lyrics, album art, tags) |
| `GET` | `/api/artist-image/<artist>` | Artist image (fetched + cached) |
| `GET` | `/api/stream/<relpath>` | Audio stream |

---

## Supported Formats

`.mp3` `.flac` `.wav` `.m4a` `.aac` `.ogg` `.opus` `.webm` `.oga`

---

## Plugin Structure

```
music-player/
├── plugin.json                  # Plugin manifest (id, version, ports, entrypoint)
└── docker/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── app.py                   # Flask entry point
    └── app/
        ├── config.py            # Env-driven config + directory bootstrap
        ├── routes.py            # All API routes
        ├── library.py           # Music library scanner
        ├── media.py             # Audio streaming
        ├── playlists.py         # Playlist CRUD
        └── utils.py
    └── static/
        ├── css/styles.css       # Full UI stylesheet
        └── js/script.js         # Single-page app logic
    └── templates/
        └── index.html           # SPA shell
```

---

## Deployment

Install or update via the Homelab OS control center, or with the CLI:

```bash
homelabctl plugin install music-player
```

On update, all playlists and cached artwork are preserved automatically.
