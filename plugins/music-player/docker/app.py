from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, send_from_directory, request
from mutagen import File as MutagenFile

ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
APP_NAME = os.getenv("APP_NAME", "Music Player")
APP_VERSION = os.getenv("APP_VERSION", "8.1.1")
MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/mnt/nas/media/music")).resolve()
APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/mnt/nas/homelab/runtime/music-player/data")).resolve()
PLAYLISTS_FILE = APP_DATA_DIR / "playlists.json"
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".webm", ".oga"}
ARTIST_SPLIT_RE = re.compile(r"\s*(?:,|，|/|&| feat\.? | ft\.? | featuring )\s*", re.I)
IGNORE_ARTISTS = {"chorus", "others", "other", "music"}

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
if not PLAYLISTS_FILE.exists():
    PLAYLISTS_FILE.write_text("{}", encoding="utf-8")

app = Flask(__name__, template_folder=str(TEMPLATES_DIR), static_folder=str(STATIC_DIR), static_url_path="/static")


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("，", ",")).strip()


def split_artists(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        raw = ", ".join(str(x) for x in value if x)
    else:
        raw = str(value or "")
    artists: list[str] = []
    for chunk in ARTIST_SPLIT_RE.split(raw):
        item = normalize_spaces(chunk)
        if item and item.lower() not in IGNORE_ARTISTS and item not in artists:
            artists.append(item)
    return artists


def parse_filename(name: str) -> tuple[str, str, list[str]]:
    base = normalize_spaces(re.sub(r"[_\.]+", " ", Path(name).stem))
    parts = [normalize_spaces(p) for p in base.split(" - ") if normalize_spaces(p)]
    if len(parts) >= 3:
        title = " - ".join(parts[:-2])
        album = parts[-2]
        artists = split_artists(parts[-1])
        return title or base, album or "Unknown", artists
    if len(parts) == 2:
        return parts[0], "Unknown", split_artists(parts[1])
    return base, "Unknown", []


def read_playlists() -> dict[str, list[str]]:
    try:
        payload = json.loads(PLAYLISTS_FILE.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {str(k): [str(x) for x in (v or [])] for k, v in payload.items()}
    except Exception:
        pass
    return {}


def write_playlists(data: dict[str, list[str]]) -> None:
    PLAYLISTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def first_value(tags: Any, keys: list[str]) -> str:
    for key in keys:
        if not tags or key not in tags:
            continue
        value = tags.get(key)
        if isinstance(value, list):
            return str(value[0]) if value else ""
        text = getattr(value, "text", None)
        if isinstance(text, list) and text:
            return str(text[0])
        if text:
            return str(text)
        if value:
            return str(value)
    return ""


def track_metadata(path: Path) -> dict[str, Any]:
    file_title, file_album, file_artists = parse_filename(path.name)
    title, album, artists, year, duration = file_title, file_album or "Unknown", file_artists[:], "", 0
    try:
        audio = MutagenFile(path)
        if audio is not None:
            duration = int(getattr(getattr(audio, "info", None), "length", 0) or 0)
            tags = getattr(audio, "tags", None)
            tag_title = normalize_spaces(first_value(tags, ["TIT2", "title", "TITLE"]))
            tag_album = normalize_spaces(first_value(tags, ["TALB", "album", "ALBUM"]))
            tag_artist = normalize_spaces(first_value(tags, ["TPE1", "artist", "ARTIST"]))
            tag_year = normalize_spaces(first_value(tags, ["TDRC", "date", "DATE", "year", "YEAR"]))
            if tag_title:
                title = tag_title
            if tag_album:
                album = tag_album
            if tag_artist:
                artists = split_artists(tag_artist) or artists
            if tag_year:
                year = re.sub(r"[^0-9]", "", tag_year)[:4]
    except Exception:
        pass
    if not artists:
        artists = ["Unknown Artist"]
    return {"title": title, "album": album or "Unknown", "artists": artists, "artist": ", ".join(artists), "year": year, "duration": duration}


def scan_tracks() -> list[dict[str, Any]]:
    tracks = []
    if not MUSIC_ROOT.exists():
        return tracks
    for path in sorted(MUSIC_ROOT.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            rel = path.relative_to(MUSIC_ROOT).as_posix()
            meta = track_metadata(path)
            tracks.append({
                "id": rel,
                "path": rel,
                "title": meta["title"],
                "album": meta["album"],
                "artist": meta["artist"],
                "artists": meta["artists"],
                "year": meta["year"],
                "duration": meta["duration"],
                "folder": "" if str(Path(rel).parent) == "." else str(Path(rel).parent),
                "filename": path.name,
                "stream_url": "/api/stream/" + rel,
            })
    return tracks


def library_payload() -> dict[str, Any]:
    tracks = scan_tracks()
    track_map = {track["id"]: track for track in tracks}
    artist_map: dict[str, list[str]] = {}
    album_map: dict[str, list[str]] = {}
    folder_map: dict[str, list[str]] = {}
    for track in tracks:
        for artist in track.get("artists") or [track.get("artist") or "Unknown Artist"]:
            artist_map.setdefault(artist.strip(), []).append(track["id"])
        album_map.setdefault(track.get("album") or "Unknown", []).append(track["id"])
        folder_map.setdefault(track.get("folder") or "Root", []).append(track["id"])
    playlists_raw = read_playlists()
    playlists = [{"name": k, "tracks": [tid for tid in v if tid in track_map], "count": len([tid for tid in v if tid in track_map])} for k, v in sorted(playlists_raw.items())]
    artists = [{"name": k, "tracks": v, "count": len(v)} for k, v in sorted(artist_map.items(), key=lambda x: x[0].lower())]
    albums = [{"name": k, "tracks": v, "count": len(v)} for k, v in sorted(album_map.items(), key=lambda x: x[0].lower())]
    folders = [{"name": k, "tracks": v, "count": len(v)} for k, v in sorted(folder_map.items(), key=lambda x: x[0].lower())]
    return {"app": {"name": APP_NAME, "version": APP_VERSION}, "tracks": tracks, "artists": artists, "albums": albums, "folders": folders, "playlists": playlists}


@app.route("/")
def index():
    return render_template("index.html", app_name=APP_NAME, app_version=APP_VERSION)


@app.route("/api/library")
def api_library():
    return jsonify(library_payload())


@app.route("/api/playlists", methods=["POST"])
def api_playlists():
    data = request.get_json(force=True, silent=True) or {}
    name = normalize_spaces(data.get("name", ""))
    tracks = [str(x) for x in data.get("tracks", [])]
    if not name:
        return jsonify({"ok": False, "error": "playlist name required"}), 400
    payload = read_playlists()
    payload[name] = tracks
    write_playlists(payload)
    return jsonify({"ok": True})


@app.route("/api/stream/<path:relpath>")
def api_stream(relpath: str):
    return send_from_directory(MUSIC_ROOT, relpath)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8140)
