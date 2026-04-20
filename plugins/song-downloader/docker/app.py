from __future__ import annotations

import json
from html import unescape
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests
from flask import Flask, jsonify, request, send_from_directory

APP_NAME = os.getenv("APP_NAME", "Song Downloader")
APP_VERSION = "1.1.2"
PORT = int(os.getenv("PORT", "8145"))
MUSIC_ROOT = Path(os.getenv("MUSIC_ROOT", "/mnt/nas/media/music")).resolve()
APP_DATA_DIR = Path(os.getenv("APP_DATA_DIR", "/mnt/nas/homelab/runtime/song-downloader/data")).resolve()
DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", "/mnt/nas/homelab/runtime/song-downloader/downloads")).resolve()
JOBS_FILE = APP_DATA_DIR / "jobs.json"

APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
JOBS_LOCK = threading.Lock()
JOB_CANCEL_EVENTS: dict[str, threading.Event] = {}
RUNNING_PROCS: dict[str, set[subprocess.Popen]] = {}
RUNNING_PROCS_LOCK = threading.Lock()

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def recover_stale_jobs() -> None:
    with JOBS_LOCK:
        jobs = load_jobs()
        changed = False
        for job in jobs:
            if job.get("status") in {"running", "queued"}:
                job["status"] = "aborted"
                job["error"] = "Recovered after app restart"
                job.setdefault("logs", []).append("Recovered after app restart; stale running job marked aborted")
                job["updated_at"] = datetime.now().isoformat(timespec="seconds")
                changed = True
        if changed:
            save_jobs(jobs)


# -------------------------------
# Jobs helpers
# -------------------------------
def load_jobs() -> list[dict]:
    if JOBS_FILE.exists():
        try:
            return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_jobs(jobs: list[dict]) -> None:
    JOBS_FILE.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")


def update_job(job_id: str, **updates) -> dict | None:
    with JOBS_LOCK:
        jobs = load_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job.update(updates)
                job["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_jobs(jobs)
                return job
    return None


def create_job(payload: dict) -> dict:
    job = {
        "id": str(uuid.uuid4()),
        "status": "queued",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "payload": payload,
        "logs": [],
        "output_file": "",
        "final_file": "",
        "error": "",
        "progress": 0,
    }
    with JOBS_LOCK:
        jobs = load_jobs()
        jobs.insert(0, job)
        save_jobs(jobs)
    return job


def append_log(job_id: str, line: str) -> None:
    with JOBS_LOCK:
        jobs = load_jobs()
        for job in jobs:
            if job["id"] == job_id:
                job.setdefault("logs", []).append(line)
                job["updated_at"] = datetime.now().isoformat(timespec="seconds")
                save_jobs(jobs)
                return


def get_cancel_event(job_id: str) -> threading.Event:
    with JOBS_LOCK:
        event = JOB_CANCEL_EVENTS.get(job_id)
        if event is None:
            event = threading.Event()
            JOB_CANCEL_EVENTS[job_id] = event
        return event


def is_abort_requested(job_id: str) -> bool:
    return get_cancel_event(job_id).is_set()


def register_process(job_id: str, proc: subprocess.Popen) -> None:
    with RUNNING_PROCS_LOCK:
        RUNNING_PROCS.setdefault(job_id, set()).add(proc)


def unregister_process(job_id: str, proc: subprocess.Popen) -> None:
    with RUNNING_PROCS_LOCK:
        procs = RUNNING_PROCS.get(job_id)
        if not procs:
            return
        procs.discard(proc)
        if not procs:
            RUNNING_PROCS.pop(job_id, None)


def abort_job_runtime(job_id: str) -> bool:
    event = get_cancel_event(job_id)
    event.set()
    aborted_any = False
    with RUNNING_PROCS_LOCK:
        procs = list(RUNNING_PROCS.get(job_id, set()))
    for proc in procs:
        try:
            if proc.poll() is None:
                proc.terminate()
                aborted_any = True
        except Exception:
            pass
    job = update_job(job_id, abort_requested=True)
    return bool(job) or aborted_any


def mark_job_aborted(job_id: str, message: str = 'Job aborted by user') -> None:
    update_job(job_id, status='aborted', error=message)
    append_log(job_id, message)


def ensure_not_aborted(job_id: str) -> None:
    if is_abort_requested(job_id):
        raise RuntimeError('Job aborted by user')


# -------------------------------
# Naming helpers
# -------------------------------
def slugify_filename(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "downloaded-track"


def build_target_filename(song_name: str, artist_names: str, album_name: str) -> str:
    song_name = slugify_filename(song_name or "Unknown Song")
    artist_names = slugify_filename(artist_names or "Unknown Artist")
    album_name = slugify_filename(album_name or "Unknown")
    if album_name and album_name.lower() != "unknown":
        return f"{song_name} - {album_name} - {artist_names}.mp3"
    return f"{song_name} - {artist_names}.mp3"


def safe_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    idx = 1
    while True:
        option = path.with_name(f"{stem} ({idx}){suffix}")
        if not option.exists():
            return option
        idx += 1


# -------------------------------
# Source helpers
# -------------------------------
def yt_search_query(song_name: str, artist_names: str, album_name: str) -> str:
    query = " ".join(x for x in [song_name, artist_names, album_name, "official audio"] if x)
    return f"ytsearch1:{query.strip()}"


def resolve_source(payload: dict) -> str:
    youtube_url = (payload.get("youtube_url") or "").strip()
    if youtube_url:
        return youtube_url
    return yt_search_query(
        payload.get("song_name", "").strip(),
        payload.get("artist_names", "").strip(),
        payload.get("album_name", "").strip(),
    )


def find_downloaded_file(download_dir: Path, marker: str) -> Path | None:
    matches = sorted(download_dir.glob(f"{marker}*"))
    for match in matches:
        if match.is_file() and match.suffix.lower() == ".mp3":
            return match
    return None


def set_progress(job_id: str, value: int) -> None:
    value = max(0, min(100, int(value)))
    update_job(job_id, progress=value)


def infer_album_from_rename(rename_to: str, song_name: str, artist_names: str, album_name: str) -> str:
    rename_to = (rename_to or "").strip()
    if album_name and album_name.strip() and album_name.strip().lower() != "unknown":
        return album_name.strip()
    if not rename_to:
        return "Unknown"
    base = rename_to[:-4] if rename_to.lower().endswith('.mp3') else rename_to
    parts = [part.strip() for part in base.split(' - ') if part.strip()]
    if len(parts) >= 3:
        return parts[1]
    return "Unknown"


def _extract_progress_percent(line: str) -> int | None:
    match = re.search(r'\[download\]\s+(\d+(?:\.\d+)?)%', line)
    if not match:
        return None
    return int(float(match.group(1)))


# -------------------------------
# Metadata enrichment
# -------------------------------
def safe_music_relative(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(MUSIC_ROOT))
    except ValueError:
        raise ValueError("Selected file must be inside /mnt/nas/media/music")


def parse_existing_lyrics(vtt_path: Path) -> str:
    try:
        text = vtt_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "WEBVTT":
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}\.\d+\s+-->\s+\d{2}:\d{2}:\d{2}\.\d+", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines).strip()


def normalize_compare_text(value: str) -> str:
    value = (value or '').replace('，', ',').replace('–', '-').replace('—', '-')
    value = re.sub(r'\s+', ' ', value).strip().lower()
    return value


def split_artist_names(value: str) -> list[str]:
    value = (value or '').replace('，', ',').replace('&', ',')
    parts = re.split(r'\s*,\s*|\s*/\s*|\s+feat\.?\s+|\s+ft\.?\s+', value, flags=re.I)
    return [normalize_compare_text(part) for part in parts if normalize_compare_text(part)]


def read_audio_metadata(file_path: Path) -> dict:
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_entries', 'format_tags=title,artist,album,lyrics',
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {'title': '', 'artist': '', 'album': '', 'lyrics': ''}
    try:
        data = json.loads(result.stdout or '{}')
    except Exception:
        return {'title': '', 'artist': '', 'album': '', 'lyrics': ''}
    tags = ((data.get('format') or {}).get('tags') or {})
    def _get(*keys):
        for key in keys:
            if tags.get(key):
                return str(tags.get(key)).strip()
        return ''
    return {
        'title': _get('title', 'TITLE'),
        'artist': _get('artist', 'ARTIST'),
        'album': _get('album', 'ALBUM'),
        'lyrics': _get('lyrics', 'LYRICS', 'unsyncedlyrics', 'UNSYNCEDLYRICS'),
    }


def metadata_matches_filename(file_path: Path, payload: dict) -> bool:
    existing = read_audio_metadata(file_path)
    requested_title = normalize_compare_text(payload.get('song_name', ''))
    requested_album = normalize_compare_text(payload.get('album_name', ''))
    requested_artists = set(split_artist_names(payload.get('artist_names', '')))
    existing_title = normalize_compare_text(existing.get('title', ''))
    existing_album = normalize_compare_text(existing.get('album', ''))
    existing_artists = set(split_artist_names(existing.get('artist', '')))

    title_ok = bool(requested_title) and requested_title == existing_title
    artists_ok = bool(requested_artists) and requested_artists == existing_artists
    if not title_ok or not artists_ok:
        return False
    if requested_album and requested_album != 'unknown':
        return requested_album == existing_album
    return True


def google_search_html(query: str, search_type: str = '') -> str:
    params = {'q': query, 'hl': 'en'}
    if search_type == 'images':
        params['tbm'] = 'isch'
    url = 'https://www.google.com/search?' + '&'.join(f"{k}={quote_plus(v)}" for k, v in params.items())
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def find_image_url_in_html(html: str) -> str:
    patterns = [
        r'https://encrypted-tbn0\.gstatic\.com/images\?[^"\']+',
        r'https://lh3\.googleusercontent\.com/[^"\']+',
        r'https://[^"\']+\.(?:jpg|jpeg|png|webp)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            if 'gstatic' in match or 'googleusercontent' in match or re.search(r'\.(jpg|jpeg|png|webp)(?:$|[?&])', match, re.I):
                return unescape(match)
    return ''


def fetch_google_image_file(query: str, temp_dir: Path, logger) -> str:
    try:
        html = google_search_html(query, search_type='images')
        image_url = find_image_url_in_html(html)
        if not image_url:
            logger('Google Images album art not found')
            return ''
        suffix = Path(urlparse(image_url).path).suffix or '.jpg'
        dest = temp_dir / f'google_cover{suffix}'
        response = requests.get(image_url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()
        dest.write_bytes(response.content)
        logger('Fetched album art from Google Images search')
        return str(dest)
    except Exception as exc:
        logger(f'Google Images album art skipped: {exc}')
        return ''


def extract_google_lyrics(html: str) -> str:
    text = unescape(html)
    text = re.sub(r'<script.*?</script>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<style.*?</style>', ' ', text, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', '\n', text)
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    candidates = []
    for i, line in enumerate(lines):
        low = line.lower()
        if 'lyrics' in low and i + 1 < len(lines):
            block = []
            for nxt in lines[i+1:i+25]:
                if len(nxt.split()) <= 1 and not re.search(r'[a-zA-Z]', nxt):
                    continue
                if 'searches related to' in nxt.lower() or 'people also ask' in nxt.lower():
                    break
                block.append(nxt)
            if block:
                candidates.append('\n'.join(block[:16]))
    if candidates:
        return max(candidates, key=len)
    return ''


def fetch_google_lyrics(query: str, logger) -> str:
    try:
        html = google_search_html(query + ' lyrics')
        lyrics = extract_google_lyrics(html)
        if lyrics:
            logger('Fetched lyrics from Google search')
            return lyrics
        logger('Google lyrics search returned no extractable lyrics')
        return ''
    except Exception as exc:
        logger(f'Google lyrics search skipped: {exc}')
        return ''


def parse_filename_metadata(file_name: str) -> dict:
    base = Path(file_name).stem.replace('，', ',').replace('–', '-').replace('—', '-').strip()
    parts = [part.strip() for part in base.split(' - ') if part.strip()]
    if len(parts) >= 3:
        return {'song_name': parts[0], 'album_name': ' - '.join(parts[1:-1]), 'artist_names': parts[-1]}
    if len(parts) == 2:
        return {'song_name': parts[0], 'album_name': '', 'artist_names': parts[1]}
    return {'song_name': base, 'album_name': '', 'artist_names': ''}


def build_download_payload_from_batch_item(song_key: str, item: dict) -> dict:
    file_name = (item.get("file_name") or song_key or "").strip()
    parsed = parse_filename_metadata(file_name)
    return {
        "song_name": (parsed.get("song_name") or song_key or "").strip(),
        "artist_names": (parsed.get("artist_names") or "").strip(),
        "album_name": (parsed.get("album_name") or "").strip(),
        "youtube_url": (item.get("ytb_link") or "").strip(),
        "rename_to": file_name,
        "auto_move": True,
        "album_art_url": (item.get("album_art") or "").strip(),
    }


def fetch_remote_image_file(image_url: str, temp_dir: Path, logger, prefix: str = 'cover') -> str:
    if not image_url:
        return ''
    try:
        suffix = Path(urlparse(image_url).path).suffix or '.jpg'
        dest = temp_dir / f'{prefix}{suffix}'
        response = requests.get(image_url, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        dest.write_bytes(response.content)
        logger(f'Fetched album art from provided URL')
        return str(dest)
    except Exception as exc:
        logger(f'Provided album art fetch skipped: {exc}')
        return ''


def fetch_source_info(source: str, temp_dir: Path, logger) -> dict:
    info_cmd = ["yt-dlp", "--no-playlist", "-J", source]
    result = subprocess.run(info_cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout or "{}")

    thumbnail_file = None
    thumbnail_url = info.get("thumbnail")
    if thumbnail_url:
        try:
            suffix = Path(urlparse(thumbnail_url).path).suffix or ".jpg"
            thumbnail_file = temp_dir / f"cover{suffix}"
            response = requests.get(thumbnail_url, timeout=30)
            response.raise_for_status()
            thumbnail_file.write_bytes(response.content)
            logger(f"Fetched album art from source metadata")
        except Exception as exc:
            logger(f"Album art fetch skipped: {exc}")
            thumbnail_file = None

    lyrics_text = ""
    subs_base = temp_dir / "subs"
    subs_cmd = [
        "yt-dlp",
        "--no-playlist",
        "--skip-download",
        "--write-auto-sub",
        "--write-sub",
        "--sub-langs",
        "en.*,en",
        "--sub-format",
        "vtt/best",
        "-o",
        str(subs_base),
        source,
    ]
    subs_proc = subprocess.run(subs_cmd, capture_output=True, text=True)
    if subs_proc.returncode == 0:
        for candidate in sorted(temp_dir.glob("subs*.vtt")):
            lyrics_text = parse_existing_lyrics(candidate)
            if lyrics_text:
                logger("Fetched lyrics from subtitles/auto-captions")
                break
    else:
        logger("Lyrics fetch skipped: subtitles not available")

    return {
        "title": (info.get("track") or info.get("title") or "").strip(),
        "artist": (info.get("artist") or info.get("uploader") or "").strip(),
        "album": (info.get("album") or "").strip(),
        "thumbnail_url": (info.get("thumbnail") or "").strip(),
        "thumbnail_file": str(thumbnail_file) if thumbnail_file and thumbnail_file.exists() else "",
        "lyrics": lyrics_text,
    }


def enrich_file_metadata(file_path: Path, payload: dict, source: str, logger) -> bool:
    requested_title = (payload.get("song_name") or "").strip()
    requested_artist = (payload.get("artist_names") or "").strip()
    requested_album = (payload.get("album_name") or "").strip()

    if metadata_matches_filename(file_path, payload):
        logger('Metadata already matches filename-derived values; skipping retag')
        return False

    with tempfile.TemporaryDirectory(prefix="songdown_meta_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        metadata = {
            "title": requested_title,
            "artist": requested_artist,
            "album": requested_album if requested_album and requested_album.lower() != "unknown" else "",
            "lyrics": "",
            "thumbnail_file": "",
        }

        try:
            source_info = fetch_source_info(source, temp_dir, logger)
        except Exception as exc:
            logger(f"Metadata lookup skipped: {exc}")
            source_info = {}

        if not metadata["title"]:
            metadata["title"] = (source_info.get("title") or "").strip()
        if not metadata["artist"]:
            metadata["artist"] = (source_info.get("artist") or "").strip()
        if not metadata["album"]:
            metadata["album"] = (source_info.get("album") or "").strip()

        requested_album_art_url = (payload.get("album_art_url") or "").strip()
        if requested_album_art_url:
            metadata["thumbnail_file"] = fetch_remote_image_file(requested_album_art_url, temp_dir, logger, prefix='provided_cover')

        if not metadata["thumbnail_file"] and metadata["album"]:
            google_image_query = ' '.join(x for x in [metadata["title"], metadata["album"], metadata["artist"], 'album cover'] if x)
            metadata["thumbnail_file"] = fetch_google_image_file(google_image_query, temp_dir, logger)

        if not metadata["thumbnail_file"]:
            metadata["thumbnail_file"] = (source_info.get("thumbnail_file") or "").strip()
            if metadata["thumbnail_file"]:
                logger('Using YouTube thumbnail as album art')

        metadata["lyrics"] = (source_info.get("lyrics") or "").strip()
        if not metadata["lyrics"]:
            google_lyrics_query = ' '.join(x for x in [metadata["title"], metadata["artist"], metadata["album"]] if x)
            metadata["lyrics"] = fetch_google_lyrics(google_lyrics_query, logger)

        output_file = file_path.with_name(f"{file_path.stem}.retag{file_path.suffix}")
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(file_path)]
        if metadata["thumbnail_file"]:
            ffmpeg_cmd.extend(["-i", metadata["thumbnail_file"]])

        ffmpeg_cmd.extend(["-map", "0:a"])
        if metadata["thumbnail_file"]:
            ffmpeg_cmd.extend(["-map", "1", "-c:v", "mjpeg"])

        ffmpeg_cmd.extend([
            "-c:a", "copy",
            "-id3v2_version", "3",
            "-metadata", f"title={metadata['title']}",
            "-metadata", f"artist={metadata['artist']}",
            "-metadata", f"album={metadata['album']}",
        ])
        if metadata["lyrics"]:
            ffmpeg_cmd.extend(["-metadata", f"lyrics={metadata['lyrics']}"])
        if metadata["thumbnail_file"]:
            ffmpeg_cmd.extend([
                "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)",
            ])
        ffmpeg_cmd.append(str(output_file))

        proc = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ffmpeg metadata update failed")

        output_file.replace(file_path)
        logger(
            "Metadata applied: "
            f"title={metadata['title'] or '—'}, "
            f"artist={metadata['artist'] or '—'}, "
            f"album={metadata['album'] or '—'}, "
            f"lyrics={'yes' if metadata['lyrics'] else 'no'}, "
            f"album_art={'yes' if metadata['thumbnail_file'] else 'no'}"
        )
        return True


# -------------------------------
# Download / retag workers
# -------------------------------
def run_download_job(job_id: str) -> None:
    job = update_job(job_id, status="running", progress=1)
    if not job:
        return

    payload = job["payload"]
    song_name = payload.get("song_name", "").strip()
    artist_names = payload.get("artist_names", "").strip()
    rename_to = payload.get("rename_to", "").strip()
    album_name = infer_album_from_rename(
        rename_to=rename_to,
        song_name=song_name,
        artist_names=artist_names,
        album_name=payload.get("album_name", "").strip() or "Unknown",
    )
    auto_move = bool(payload.get("auto_move", True))

    try:
        append_log(job_id, "Preparing download job")
        source = resolve_source(payload)
        marker = f"job_{job_id.replace('-', '')}"
        output_template = str(DOWNLOADS_DIR / f"{marker}.%(ext)s")

        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--embed-metadata",
            "--no-playlist",
            "--newline",
            "-o", output_template,
            source,
        ]

        append_log(job_id, "Running yt-dlp")
        ensure_not_aborted(job_id)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        register_process(job_id, proc)
        last_progress = 1
        if proc.stdout is not None:
            for raw_line in proc.stdout:
                if is_abort_requested(job_id):
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                line = raw_line.rstrip()
                if line:
                    append_log(job_id, line)
                    progress = _extract_progress_percent(line)
                    if progress is not None:
                        last_progress = max(last_progress, progress)
                        set_progress(job_id, last_progress)
        return_code = proc.wait()
        unregister_process(job_id, proc)
        if is_abort_requested(job_id):
            raise RuntimeError('Job aborted by user')
        if return_code != 0:
            raise RuntimeError(f"yt-dlp failed with exit code {return_code}")

        ensure_not_aborted(job_id)
        set_progress(job_id, max(last_progress, 95))
        downloaded = find_downloaded_file(DOWNLOADS_DIR, marker)
        if not downloaded:
            raise RuntimeError("Downloaded file not found after yt-dlp run")

        target_name = rename_to or build_target_filename(song_name, artist_names, album_name)
        if not target_name.lower().endswith(".mp3"):
            target_name += ".mp3"
        final_path = safe_destination((MUSIC_ROOT if auto_move else DOWNLOADS_DIR) / target_name)

        shutil.move(str(downloaded), str(final_path))
        append_log(job_id, f"Saved file: {final_path}")
        append_log(job_id, "Applying metadata enrichment")
        enrich_file_metadata(
            final_path,
            payload={
                **payload,
                "song_name": song_name,
                "artist_names": artist_names,
                "album_name": album_name,
            },
            source=source,
            logger=lambda line: append_log(job_id, line),
        )

        update_job(
            job_id,
            status="completed",
            output_file=str(downloaded),
            final_file=str(final_path),
            progress=100,
            payload={
                **payload,
                "song_name": song_name,
                "artist_names": artist_names,
                "album_name": album_name,
            },
        )

    except Exception as exc:
        if 'aborted by user' in str(exc).lower():
            mark_job_aborted(job_id)
            return
        update_job(job_id, status="failed", error=str(exc), progress=100)
        append_log(job_id, f"ERROR: {exc}")


def run_retag_job(job_id: str) -> None:
    job = update_job(job_id, status="running", progress=5)
    if not job:
        return

    payload = job["payload"]
    try:
        relative_path = payload.get("selected_file", "")
        if not relative_path:
            raise ValueError("No song selected for retagging")
        target = (MUSIC_ROOT / relative_path).resolve()
        safe_music_relative(target)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError("Selected song file was not found")

        append_log(job_id, f"Retagging file: {target}")
        ensure_not_aborted(job_id)
        source = resolve_source(payload)
        changed = enrich_file_metadata(target, payload, source, lambda line: append_log(job_id, line))
        ensure_not_aborted(job_id)
        if not changed:
            append_log(job_id, "Retag skipped because metadata already matches filename")
        update_job(job_id, status="completed", final_file=str(target), progress=100)
    except Exception as exc:
        if 'aborted by user' in str(exc).lower():
            mark_job_aborted(job_id)
            return
        update_job(job_id, status="failed", error=str(exc), progress=100)
        append_log(job_id, f"ERROR: {exc}")




def run_retag_all_job(job_id: str) -> None:
    job = update_job(job_id, status='running', progress=1)
    if not job:
        return
    try:
        songs = [path for path in sorted(MUSIC_ROOT.rglob('*')) if path.is_file() and path.suffix.lower() == '.mp3']
        total = len(songs)
        if not total:
            raise FileNotFoundError('No songs found in music library')

        max_workers = max(4, min(16, (os.cpu_count() or 4) * 2))
        append_log(job_id, f'Retag-all started with {total} songs using {max_workers} workers')
        completed = 0
        failed = 0
        cancelled = get_cancel_event(job_id)

        def worker(target: Path) -> tuple[str, bool, str]:
            if cancelled.is_set():
                return target.name, False, 'aborted before start'
            meta = parse_filename_metadata(target.name)
            payload = {**meta, 'selected_file': safe_music_relative(target), 'youtube_url': ''}
            source = resolve_source(payload)
            local_logs: list[str] = [f'Retagging {target.name}']
            try:
                changed = enrich_file_metadata(target, payload, source, lambda line: local_logs.append(line))
                if not changed:
                    local_logs.append(f'Skipped {target.name}: metadata already matches filename')
                return target.name, True, '\n'.join(local_logs)
            except Exception as exc:
                local_logs.append(f'Skipped {target.name}: {exc}')
                return target.name, False, '\n'.join(local_logs)

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='retagall') as executor:
            futures = {executor.submit(worker, song): song for song in songs}
            for future in as_completed(futures):
                name = futures[future].name
                if cancelled.is_set():
                    for fut in futures:
                        fut.cancel()
                    break
                try:
                    _name, ok, logs_text = future.result()
                    for line in logs_text.splitlines():
                        append_log(job_id, line)
                    if ok:
                        completed += 1
                    else:
                        failed += 1
                except Exception as exc:
                    append_log(job_id, f'Skipped {name}: {exc}')
                    failed += 1
                done = completed + failed
                update_job(job_id, progress=int(done * 100 / total))

        if cancelled.is_set():
            mark_job_aborted(job_id, f'Job aborted by user after processing {completed + failed} / {total} songs')
            return

        append_log(job_id, f'Retag-all completed: success={completed}, failed={failed}, total={total}')
        update_job(job_id, status='completed', progress=100)
    except Exception as exc:
        if 'aborted by user' in str(exc).lower():
            mark_job_aborted(job_id)
            return
        update_job(job_id, status='failed', error=str(exc), progress=100)
        append_log(job_id, f'ERROR: {exc}')



def run_download_batch_jobs(batch_job_id: str, items: list[tuple[str, dict]]) -> None:
    batch_job = update_job(batch_job_id, status='running', progress=1)
    if not batch_job:
        return
    total = len(items)
    if total == 0:
        update_job(batch_job_id, status='failed', error='No batch items found', progress=100)
        return
    append_log(batch_job_id, f'Queued {total} songs from JSON batch')
    created = 0
    for index, (song_key, item) in enumerate(items, start=1):
        ensure_not_aborted(batch_job_id)
        try:
            payload = build_download_payload_from_batch_item(song_key, item)
            if not payload['youtube_url']:
                append_log(batch_job_id, f'Skipped {song_key}: missing ytb_link')
                continue
            if not payload['song_name'] or not payload['artist_names']:
                append_log(batch_job_id, f'Skipped {song_key}: file_name must follow <song> - <artist> or <song> - <album> - <artist>')
                continue
            job = create_job({**payload, 'job_type': 'download'})
            threading.Thread(target=run_download_job, args=(job['id'],), daemon=True).start()
            created += 1
            append_log(batch_job_id, f'Queued: {payload["rename_to"] or payload["song_name"]}')
        except Exception as exc:
            append_log(batch_job_id, f'Skipped {song_key}: {exc}')
        update_job(batch_job_id, progress=int(index * 100 / total))

    if is_abort_requested(batch_job_id):
        mark_job_aborted(batch_job_id, f'Batch queue aborted after {created} / {total} items')
        return

    final_status = 'completed' if created else 'failed'
    final_error = '' if created else 'No valid songs could be queued from JSON batch'
    update_job(batch_job_id, status=final_status, progress=100, error=final_error)
    append_log(batch_job_id, f'Batch queue complete: queued={created}, total={total}')


recover_stale_jobs()

# -------------------------------
# Routes
# -------------------------------
@app.route("/")
def index():
    return send_from_directory(app.template_folder, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)


@app.route("/api/health")
def health():
    response = jsonify({
        "status": "ok",
        "name": APP_NAME,
        "version": APP_VERSION,
        "music_root": str(MUSIC_ROOT),
        "downloads_dir": str(DOWNLOADS_DIR),
    })
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    return jsonify({"jobs": load_jobs()})


@app.route("/api/jobs/clear", methods=["POST"])
def clear_jobs():
    with JOBS_LOCK:
        jobs = load_jobs()
        remaining = [job for job in jobs if job.get("status") not in {"completed", "failed", "aborted"}]
        save_jobs(remaining)
    return jsonify({"ok": True})


@app.route("/api/jobs/<job_id>/abort", methods=["POST"])
def abort_job(job_id: str):
    ok = abort_job_runtime(job_id)
    return jsonify({"ok": ok})


@app.route("/api/library-songs", methods=["GET"])
def library_songs():
    songs = []
    for path in sorted(MUSIC_ROOT.rglob('*')):
        if path.is_file() and path.suffix.lower() == '.mp3':
            try:
                rel = safe_music_relative(path)
                songs.append({"path": rel, "name": path.name, "label": f"{path.name} — {rel}"})
            except Exception:
                continue
    return jsonify({"songs": songs})


@app.route("/api/download", methods=["POST"])
def download():
    payload = request.get_json(force=True)
    job = create_job(payload)
    threading.Thread(target=run_download_job, args=(job["id"],), daemon=True).start()
    return jsonify({"ok": True, "job_id": job["id"]})




@app.route("/api/download-batch", methods=["POST"])
def download_batch():
    payload = request.get_json(force=True) or {}
    json_text = (payload.get("json_text") or "").strip()
    if not json_text:
        return jsonify({"ok": False, "error": "JSON payload is required"}), 400
    try:
        parsed = json.loads(json_text)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Invalid JSON: {exc}"}), 400
    if not isinstance(parsed, dict):
        return jsonify({"ok": False, "error": "JSON payload must be an object"}), 400
    items = list(parsed.items())
    job = create_job({"job_type": "download-batch", "song_name": f"{len(items)} songs from JSON"})
    threading.Thread(target=run_download_batch_jobs, args=(job["id"], items), daemon=True).start()
    return jsonify({"ok": True, "job_id": job["id"]})

@app.route("/api/retag", methods=["POST"])
def retag():
    payload = request.get_json(force=True)
    job = create_job({**payload, "job_type": "retag"})
    threading.Thread(target=run_retag_job, args=(job["id"],), daemon=True).start()
    return jsonify({"ok": True, "job_id": job["id"]})


@app.route("/api/retag-all", methods=["POST"])
def retag_all():
    job = create_job({"job_type": "retag-all", "song_name": "All songs from filenames"})
    threading.Thread(target=run_retag_all_job, args=(job["id"],), daemon=True).start()
    return jsonify({"ok": True, "job_id": job["id"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)