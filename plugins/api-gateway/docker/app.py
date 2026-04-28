from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ── Config ─────────────────────────────────────────────────────────────────────
APP_NAME    = os.getenv("APP_NAME",    "API Gateway")
APP_VERSION = os.getenv("APP_VERSION", "1.4.0")
PORT        = int(os.getenv("PORT",    "8134"))

MUSIC_PLAYER_API = os.getenv("MUSIC_PLAYER_API", "http://127.0.0.1:8140")
FILES_API        = os.getenv("FILES_API",         "http://127.0.0.1:8088")
PIHOLE_API       = os.getenv("PIHOLE_API",        "http://127.0.0.1:8080")

ROOT          = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR    = ROOT / "static"

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "Unified API Gateway for all Homelab services. "
        "Proxies Music Player, Files, and Pi-hole APIs through a single entry point."
    ),
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Pydantic models ────────────────────────────────────────────────────────────
class PlaylistPayload(BaseModel):
    name: str
    tracks: list[str] = []

class PlaylistAddTracksPayload(BaseModel):
    name: str
    track_ids: list[str]
    force: bool = False

class MetadataUpdatePayload(BaseModel):
    title: Optional[str] = ""
    artist: Optional[str] = ""
    album: Optional[str] = ""
    year: Optional[str] = ""
    art_link: Optional[str] = ""
    art_upload_data: Optional[str] = ""

class ArtistImagePayload(BaseModel):
    image_link: Optional[str] = ""
    upload_data: Optional[str] = ""


# ── Helpers ────────────────────────────────────────────────────────────────────
def _upstream(url: str, method: str = "GET", timeout: int = 20, **kwargs) -> Any:
    """Proxy a request to an upstream service and return parsed JSON."""
    try:
        r = requests.request(method, url, timeout=timeout, **kwargs)
        r.raise_for_status()
    except requests.RequestException as exc:
        body = getattr(getattr(exc, "response", None), "text", "")[:400]
        raise HTTPException(
            status_code=502,
            detail={"message": "Upstream request failed", "url": url, "error": str(exc), "body": body},
        )
    try:
        return r.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail={"message": "Upstream returned non-JSON", "url": url, "body": r.text[:400]},
        )

def _upstream_raw(url: str, timeout: int = 60) -> requests.Response:
    """Proxy a request and return the raw response (for streaming)."""
    try:
        return requests.get(url, timeout=timeout, stream=True)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=str(exc))

def _service_status(name: str, url: str) -> dict:
    try:
        r = requests.get(url, timeout=5)
        return {"service": name, "ok": r.ok, "status_code": r.status_code}
    except Exception as exc:
        return {"service": name, "ok": False, "error": str(exc)}


# ══════════════════════════════════════════════════════════════════════════════
# Gateway routes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request):
    """Serve the API Gateway dashboard."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": APP_NAME, "app_version": APP_VERSION},
    )


@app.get("/api/health", tags=["gateway"])
def health():
    """Gateway health check."""
    return {"ok": True, "service": APP_NAME, "version": APP_VERSION}


@app.get("/api/debug/upstreams", tags=["gateway"])
def debug_upstreams():
    """Check connectivity to all upstream services."""
    return {
        "music_player": _service_status("music-player", f"{MUSIC_PLAYER_API}/api/library"),
        "files":        _service_status("files",        f"{FILES_API}/"),
        "pihole":       _service_status("pihole",       f"{PIHOLE_API}/admin/"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Music Player  (/api/music/*)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/music/library", tags=["music-player"])
def music_library():
    """
    Full music library — tracks, albums, artists, folders, playlists.
    Proxies GET /api/library on the Music Player service.
    """
    return _upstream(f"{MUSIC_PLAYER_API}/api/library", timeout=30)


@app.get("/api/music/stream/{relpath:path}", tags=["music-player"])
def music_stream(relpath: str):
    """
    Stream an audio file by its relative path (e.g. Artist/album/track.mp3).
    Proxies GET /api/stream/<relpath> on the Music Player service.
    """
    upstream_resp = _upstream_raw(f"{MUSIC_PLAYER_API}/api/stream/{relpath}")
    return StreamingResponse(
        upstream_resp.iter_content(chunk_size=65536),
        status_code=upstream_resp.status_code,
        media_type=upstream_resp.headers.get("content-type", "audio/mpeg"),
        headers={
            "Accept-Ranges": upstream_resp.headers.get("Accept-Ranges", "bytes"),
            "Content-Length": upstream_resp.headers.get("Content-Length", ""),
        },
    )


@app.get("/api/music/art-cache/{filename}", tags=["music-player"])
def music_art_cache(filename: str):
    """
    Fetch a cached album art image by filename.
    Proxies GET /api/art-cache/<filename> on the Music Player service.
    """
    upstream_resp = _upstream_raw(f"{MUSIC_PLAYER_API}/api/art-cache/{filename}")
    return StreamingResponse(
        upstream_resp.iter_content(chunk_size=65536),
        status_code=upstream_resp.status_code,
        media_type=upstream_resp.headers.get("content-type", "image/jpeg"),
    )


@app.get("/api/music/artist-images/{filename}", tags=["music-player"])
def music_artist_images(filename: str):
    """
    Fetch a stored artist image by filename.
    Proxies GET /api/artist-images/<filename> on the Music Player service.
    """
    upstream_resp = _upstream_raw(f"{MUSIC_PLAYER_API}/api/artist-images/{filename}")
    return StreamingResponse(
        upstream_resp.iter_content(chunk_size=65536),
        status_code=upstream_resp.status_code,
        media_type=upstream_resp.headers.get("content-type", "image/jpeg"),
    )


@app.get("/api/music/metadata/{relpath:path}", tags=["music-player"])
def music_get_metadata(relpath: str):
    """
    Get metadata for a specific track.
    Proxies GET /api/metadata/<relpath> on the Music Player service.
    """
    return _upstream(f"{MUSIC_PLAYER_API}/api/metadata/{relpath}")


@app.post("/api/music/metadata/{relpath:path}", tags=["music-player"])
def music_update_metadata(relpath: str, payload: MetadataUpdatePayload):
    """
    Update metadata (title, artist, album, year, art) for a specific track.
    Proxies POST /api/metadata/<relpath> on the Music Player service.
    """
    return _upstream(
        f"{MUSIC_PLAYER_API}/api/metadata/{relpath}",
        method="POST",
        json=payload.model_dump(exclude_none=True),
        timeout=40,
    )


@app.post("/api/music/playlists", tags=["music-player"])
def music_create_playlist(payload: PlaylistPayload):
    """
    Create a new playlist or add tracks to an existing one.
    Proxies POST /api/playlists on the Music Player service.
    """
    return _upstream(
        f"{MUSIC_PLAYER_API}/api/playlists",
        method="POST",
        json=payload.model_dump(),
        timeout=20,
    )


@app.post("/api/music/playlists/add-tracks", tags=["music-player"])
def music_playlist_add_tracks(payload: PlaylistAddTracksPayload):
    """
    Add specific tracks to an existing playlist.
    Proxies POST /api/playlists/add-tracks on the Music Player service.
    """
    return _upstream(
        f"{MUSIC_PLAYER_API}/api/playlists/add-tracks",
        method="POST",
        json=payload.model_dump(),
        timeout=20,
    )


@app.post("/api/music/artist-image/{artist}", tags=["music-player"])
def music_set_artist_image(artist: str, payload: ArtistImagePayload):
    """
    Set or update the image for an artist (via URL or base64 upload).
    Proxies POST /api/artist-image/<artist> on the Music Player service.
    """
    return _upstream(
        f"{MUSIC_PLAYER_API}/api/artist-image/{artist}",
        method="POST",
        json=payload.model_dump(exclude_none=True),
        timeout=30,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Files  (/api/files/*)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/files/health", tags=["files"])
def files_health():
    """
    Check whether the Files (FileBrowser) service is reachable.
    """
    return _service_status("files", f"{FILES_API}/")


@app.get("/api/files/info", tags=["files"])
def files_info():
    """
    Return connection info for the Files service so clients can redirect.
    """
    return {
        "service": "files",
        "base_url": FILES_API,
        "browse_path": "/files/Incoming/",
        "note": "FileBrowser does not expose a REST API; use the web UI directly.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Pi-hole  (/api/pihole/*)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/pihole/health", tags=["pihole"])
def pihole_health():
    """
    Check whether the Pi-hole admin interface is reachable.
    """
    return _service_status("pihole", f"{PIHOLE_API}/admin/")


@app.get("/api/pihole/summary", tags=["pihole"])
def pihole_summary():
    """
    Fetch Pi-hole statistics summary via the Pi-hole API.
    Proxies GET /admin/api.php?summary on the Pi-hole service.
    """
    return _upstream(f"{PIHOLE_API}/admin/api.php", params={"summary": ""}, timeout=10)


@app.get("/api/pihole/status", tags=["pihole"])
def pihole_status():
    """
    Get Pi-hole enabled/disabled status.
    Proxies GET /admin/api.php?status on the Pi-hole service.
    """
    return _upstream(f"{PIHOLE_API}/admin/api.php", params={"status": ""}, timeout=10)


@app.get("/api/pihole/top-items", tags=["pihole"])
def pihole_top_items(count: int = Query(default=10, ge=1, le=100)):
    """
    Get top queried/blocked domains from Pi-hole.
    Proxies GET /admin/api.php?topItems=<count> on the Pi-hole service.
    """
    return _upstream(f"{PIHOLE_API}/admin/api.php", params={"topItems": count}, timeout=10)


@app.get("/api/pihole/query-types", tags=["pihole"])
def pihole_query_types():
    """
    Get DNS query type breakdown from Pi-hole.
    Proxies GET /admin/api.php?getQueryTypes on the Pi-hole service.
    """
    return _upstream(f"{PIHOLE_API}/admin/api.php", params={"getQueryTypes": ""}, timeout=10)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
