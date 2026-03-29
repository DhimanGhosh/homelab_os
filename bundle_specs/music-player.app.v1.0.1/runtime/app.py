from __future__ import annotations

import json
import mimetypes
import os
import re
from hashlib import sha1
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from mutagen import File as MutagenFile
except Exception:
    MutagenFile = None

APP_VERSION = "1.0.1"
ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/mnt/nas/media/music")).resolve()
APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/mnt/nas/homelab/runtime/music-player/data")).resolve()
PLAYLISTS_FILE = APP_DATA_DIR / "playlists.json"
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".webm", ".oga"}

app = FastAPI(title="Music Player", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


def safe_rel_path(path: Path) -> str:
    return path.relative_to(MUSIC_ROOT).as_posix()


def title_from_name(name: str) -> str:
    text = Path(name).stem
    text = re.sub(r"[_\.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or name


def file_id(path: Path) -> str:
    return sha1(safe_rel_path(path).encode("utf-8")).hexdigest()[:16]


def read_playlists() -> dict[str, list[str]]:
    if PLAYLISTS_FILE.exists():
        try:
            data = json.loads(PLAYLISTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(k): [str(x) for x in (v or [])] for k, v in data.items()}
        except Exception:
            pass
    return {}


def write_playlists(payload: dict[str, list[str]]) -> None:
    PLAYLISTS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_tags(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "title": title_from_name(path.name),
        "artist": "Unknown Artist",
        "album": "Unknown Album",
        "duration": None,
    }
    if MutagenFile is None:
        return result
    try:
        audio = MutagenFile(str(path), easy=True)
        if not audio:
            return result
        result["title"] = (audio.get("title") or [result["title"]])[0]
        result["artist"] = (audio.get("artist") or [result["artist"]])[0]
        result["album"] = (audio.get("album") or [result["album"]])[0]
        if getattr(audio, "info", None) and getattr(audio.info, "length", None):
            result["duration"] = round(float(audio.info.length), 2)
    except Exception:
        return result
    return result


def track_from_file(path: Path) -> dict[str, Any]:
    tags = extract_tags(path)
    rel = safe_rel_path(path)
    folder = Path(rel).parent.as_posix()
    if folder == ".":
        folder = ""
    mime = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    return {
        "id": file_id(path),
        "path": rel,
        "title": tags["title"],
        "artist": tags["artist"],
        "album": tags["album"],
        "duration": tags["duration"],
        "folder": folder,
        "filename": path.name,
        "ext": path.suffix.lower().lstrip("."),
        "size": path.stat().st_size,
        "mime": mime,
        "stream_url": f"/api/stream/{quote(rel, safe='')}"
    }


def scan_tracks() -> list[dict[str, Any]]:
    if not MUSIC_ROOT.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(MUSIC_ROOT.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            items.append(track_from_file(path))
    return items


def build_tree(paths: list[str]) -> list[dict[str, Any]]:
    tree: dict[str, Any] = {}
    for rel in paths:
        parts = [p for p in Path(rel).parent.as_posix().split("/") if p and p != "."]
        node = tree
        for part in parts:
            node = node.setdefault(part, {})
    def convert(node: dict[str, Any], prefix: str = "") -> list[dict[str, Any]]:
        out = []
        for name in sorted(node):
            current = f"{prefix}/{name}" if prefix else name
            out.append({"name": name, "path": current, "children": convert(node[name], current)})
        return out
    return convert(tree)


def resolve_music_path(rel_path: str) -> Path:
    target = (MUSIC_ROOT / rel_path).resolve()
    if MUSIC_ROOT not in target.parents and target != MUSIC_ROOT:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Track not found")
    return target


class PlaylistPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tracks: list[str] = Field(default_factory=list)


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "Music Player",
        "version": APP_VERSION,
        "music_root": str(MUSIC_ROOT),
        "music_root_exists": MUSIC_ROOT.exists(),
    }


@app.get("/api/library")
def library() -> JSONResponse:
    tracks = scan_tracks()
    playlists = read_playlists()
    folders = build_tree([t["path"] for t in tracks])
    return JSONResponse({
        "tracks": tracks,
        "folders": folders,
        "playlists": [{"name": name, "tracks": items} for name, items in sorted(playlists.items())],
        "stats": {
            "track_count": len(tracks),
            "folder_count": len({t["folder"] for t in tracks if t["folder"]}),
        },
    })


@app.get("/api/playlists")
def get_playlists() -> JSONResponse:
    playlists = read_playlists()
    return JSONResponse({"playlists": [{"name": name, "tracks": items} for name, items in sorted(playlists.items())]})


@app.post("/api/playlists")
def upsert_playlist(payload: PlaylistPayload) -> JSONResponse:
    playlists = read_playlists()
    playlists[payload.name.strip()] = list(dict.fromkeys(payload.tracks))
    write_playlists(playlists)
    return JSONResponse({"ok": True, "message": "Playlist saved"})


@app.delete("/api/playlists/{name}")
def delete_playlist(name: str) -> JSONResponse:
    playlists = read_playlists()
    removed = playlists.pop(name, None)
    write_playlists(playlists)
    return JSONResponse({"ok": True, "removed": removed is not None})


@app.get("/api/stream/{track_path:path}")
def stream_track(track_path: str):
    path = resolve_music_path(track_path)
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", filename=path.name)
