from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

APP_NAME = os.environ.get('APP_NAME', 'Song Downloader')
APP_VERSION = os.environ.get('APP_VERSION', '1.0.1')
PORT = int(os.environ.get('PORT', '8145'))
APP_DATA_DIR = Path(os.environ.get('APP_DATA_DIR', '/data'))
DOWNLOAD_ROOT = Path(os.environ.get('DOWNLOAD_ROOT', str(APP_DATA_DIR / 'downloads')))
DEFAULT_DESTINATION_DIR = os.environ.get('DEFAULT_DESTINATION_DIR', '/mnt/nas/media/music')
MEDIA_DOWNLOADER_BASE_URL = os.environ.get('MEDIA_DOWNLOADER_BASE_URL', '').rstrip('/')
ALLOWED_DEST_ROOTS = [Path(p) for p in os.environ.get('ALLOWED_DEST_ROOTS', '/mnt/nas:/data').split(':') if p]
STATIC_DIR = Path(__file__).resolve().parent / 'static'
HOST = '0.0.0.0'
YOUTUBE_HOST_HINTS = ('youtube.com', 'youtu.be', 'music.youtube.com')

for path in [APP_DATA_DIR, DOWNLOAD_ROOT]:
    path.mkdir(parents=True, exist_ok=True)

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()


def now_iso() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def safe_name(text: str) -> str:
    text = re.sub(r'[^A-Za-z0-9._,()\- ]+', '_', str(text)).strip().strip('.')
    text = re.sub(r'\s+', ' ', text)
    return text[:180] or 'song'


def normalize_artists(artists_raw: str) -> str:
    parts = [p.strip() for p in re.split(r'\s*,\s*', artists_raw or '') if p.strip()]
    return ', '.join(parts)


def final_song_name(song_name: str, artists: str, rename_to: str | None, youtube_url: str | None = None) -> str:
    custom = (rename_to or '').strip()
    if custom:
        return safe_name(custom)
    song_name = (song_name or '').strip()
    artists = normalize_artists(artists)
    if song_name and artists:
        return safe_name(f'{song_name} - {artists}')
    if song_name:
        return safe_name(song_name)
    if youtube_url:
        return safe_name('downloaded-audio')
    return safe_name('song')


def query_text(song_name: str, artists: str, album_name: str) -> str:
    pieces = [song_name.strip(), normalize_artists(artists), (album_name or '').strip(), 'official audio', '-video']
    return ' '.join([p for p in pieces if p])


def within_allowed_root(dest: Path) -> bool:
    resolved = dest.resolve()
    for root in ALLOWED_DEST_ROOTS:
        root_resolved = root.resolve()
        if resolved == root_resolved or root_resolved in resolved.parents:
            return True
    return False


def ensure_destination(dest_path: str) -> Path:
    target = Path(dest_path).expanduser()
    if not target.is_absolute():
        raise ValueError('destination_path must be absolute')
    resolved = target.resolve()
    if not within_allowed_root(resolved):
        allowed = ', '.join(str(p.resolve()) for p in ALLOWED_DEST_ROOTS)
        raise ValueError(f'destination_path must stay inside one of: {allowed}')
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def reserve_target(dest_dir: Path, stem: str, suffix: str = '.mp3') -> Path:
    target = dest_dir / f'{stem}{suffix}'
    if not target.exists():
        return target
    idx = 1
    while True:
        candidate = dest_dir / f'{stem}_{idx}{suffix}'
        if not candidate.exists():
            return candidate
        idx += 1


def media_downloader_available() -> bool:
    if not MEDIA_DOWNLOADER_BASE_URL:
        return False
    try:
        with urlopen(MEDIA_DOWNLOADER_BASE_URL + '/api/health', timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def api_get(path: str):
    with urlopen(MEDIA_DOWNLOADER_BASE_URL + path, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


def api_post(path: str, payload: dict):
    body = json.dumps(payload).encode('utf-8')
    req = Request(MEDIA_DOWNLOADER_BASE_URL + path, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def poll_media_job(job_id: str, timeout: int = 1800) -> dict:
    started = time.time()
    while time.time() - started < timeout:
        payload = api_get('/api/status')
        jobs = payload.get('jobs', [])
        match = next((j for j in jobs if j.get('id') == job_id), None)
        if match and match.get('status') in {'completed', 'failed'}:
            return match
        time.sleep(2)
    raise TimeoutError('Timed out waiting for Media Downloader job')


def update_job(job_id: str, **fields):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job['updated_at'] = now_iso()


def new_job(payload: dict) -> str:
    job_id = str(uuid.uuid4())
    display_name = payload.get('song_name') or payload.get('rename_to') or payload.get('youtube_url') or 'audio download'
    with LOCK:
        JOBS[job_id] = {
            'id': job_id,
            'status': 'queued',
            'progress': 0,
            'message': 'Queued',
            'payload': payload,
            'display_name': display_name,
            'created_at': now_iso(),
            'updated_at': now_iso(),
            'final_path': None,
            'download_backend': None,
        }
    return job_id


def clear_jobs() -> int:
    with LOCK:
        before = len(JOBS)
        removable = [job_id for job_id, job in JOBS.items() if job.get('status') in {'completed', 'failed'}]
        for job_id in removable:
            JOBS.pop(job_id, None)
    return len(removable) if before else 0


def resolve_source(youtube_url: str, query: str) -> tuple[str, str]:
    url = (youtube_url or '').strip()
    if not url:
        return 'search', 'ytsearch1:' + query
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'}:
        raise ValueError('youtube_url must begin with http:// or https://')
    if not any(host in (parsed.netloc or '') for host in YOUTUBE_HOST_HINTS):
        raise ValueError('youtube_url must be a YouTube or YouTube Music link')
    return 'youtube_url', url


def run_direct_download(job_id: str, source_value: str, destination_dir: Path, final_stem: str, source_kind: str):
    update_job(job_id, status='starting', progress=5, message='Downloading with direct yt-dlp fallback…', download_backend='direct-yt-dlp')
    try:
        import yt_dlp
    except Exception as exc:
        update_job(job_id, status='failed', progress=100, message=f'yt-dlp is unavailable in the container: {exc}')
        return

    temp_dir = DOWNLOAD_ROOT / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(temp_dir / '%(title).150B [%(id)s].%(ext)s')

    def hook(d):
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            done = d.get('downloaded_bytes') or 0
            pct = int((done / total) * 70) if total else 20
            update_job(job_id, status='downloading', progress=max(10, min(pct, 75)), message=d.get('_percent_str', 'Downloading audio…').strip() or 'Downloading audio…')
        elif d.get('status') == 'finished':
            update_job(job_id, status='processing', progress=80, message='Extracting MP3…')

    opts = {
        'outtmpl': output_template,
        'restrictfilenames': False,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [hook],
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
    }
    if source_kind == 'search':
        opts['default_search'] = 'ytsearch'

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(source_value, download=True)
    except Exception as exc:
        update_job(job_id, status='failed', progress=100, message=str(exc))
        return

    candidates = sorted([p for p in temp_dir.rglob('*') if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        update_job(job_id, status='failed', progress=100, message='No downloaded file was produced')
        return
    source = candidates[0]
    suffix = source.suffix if source.suffix else '.mp3'
    target = reserve_target(destination_dir, final_stem, suffix)
    shutil.move(str(source), str(target))
    shutil.rmtree(temp_dir, ignore_errors=True)
    update_job(job_id, status='completed', progress=100, message='Song downloaded and transferred', final_path=str(target))


def run_media_api_download(job_id: str, source_value: str, destination_dir: Path, final_stem: str, source_kind: str):
    update_job(job_id, status='starting', progress=5, message='Requesting Media Downloader API…', download_backend='media-downloader-api')
    try:
        payload = {'url': source_value, 'mode': 'audio', 'audio_format': 'mp3'}
        if source_kind == 'search':
            payload['url'] = source_value
        result = api_post('/api/download', payload)
        md_job_id = result['job_id']
    except (HTTPError, URLError, KeyError, TimeoutError) as exc:
        update_job(job_id, status='failed', progress=100, message=f'Media Downloader API request failed: {exc}')
        return

    while True:
        try:
            state = poll_media_job(md_job_id)
            break
        except TimeoutError as exc:
            update_job(job_id, status='failed', progress=100, message=str(exc))
            return
        except Exception as exc:
            update_job(job_id, status='failed', progress=100, message=f'Polling Media Downloader failed: {exc}')
            return

    if state.get('status') == 'failed':
        update_job(job_id, status='failed', progress=100, message=state.get('message') or 'Media Downloader failed')
        return

    relative_path = state.get('output_relative')
    if not relative_path:
        update_job(job_id, status='failed', progress=100, message='Media Downloader did not return an output_relative path')
        return

    update_job(job_id, status='processing', progress=85, message='Auto-transferring song into music library…')
    try:
        save_result = api_post('/api/save-as', {
            'relative_path': relative_path,
            'destination_path': str(destination_dir),
            'new_name': final_stem + '.mp3',
            'operation': 'move',
        })
        save_job_id = save_result['job_id']
        saved_state = poll_media_job(save_job_id)
    except Exception as exc:
        update_job(job_id, status='failed', progress=100, message=f'Auto-transfer through Media Downloader failed: {exc}')
        return

    if saved_state.get('status') == 'failed':
        update_job(job_id, status='failed', progress=100, message=saved_state.get('message') or 'Auto-transfer failed')
        return

    update_job(job_id, status='completed', progress=100, message='Song downloaded and transferred', final_path=saved_state.get('output_path'))


def worker(job_id: str):
    payload = JOBS[job_id]['payload']
    song_name = payload.get('song_name', '')
    artists = payload.get('artists', '')
    album_name = payload.get('album_name', '')
    rename_to = payload.get('rename_to') or ''
    youtube_url = payload.get('youtube_url') or ''
    destination_path = payload.get('destination_path') or DEFAULT_DESTINATION_DIR

    try:
        destination_dir = ensure_destination(destination_path)
        final_stem = final_song_name(song_name, artists, rename_to, youtube_url)
        query = query_text(song_name, artists, album_name)
        source_kind, source_value = resolve_source(youtube_url, query)
    except Exception as exc:
        update_job(job_id, status='failed', progress=100, message=str(exc))
        return

    if media_downloader_available():
        run_media_api_download(job_id, source_value, destination_dir, final_stem, source_kind)
        return
    run_direct_download(job_id, source_value, destination_dir, final_stem, source_kind)


def json_response(handler: BaseHTTPRequestHandler, payload: dict | list, code: int = HTTPStatus.OK, head_only: bool = False):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    if not head_only:
        handler.wfile.write(body)


def build_status_payload() -> dict:
    with LOCK:
        jobs = sorted(JOBS.values(), key=lambda item: item['created_at'], reverse=True)
    return {
        'status': 'ok',
        'version': APP_VERSION,
        'jobs': jobs,
        'default_destination': DEFAULT_DESTINATION_DIR,
        'media_downloader_base_url': MEDIA_DOWNLOADER_BASE_URL,
        'media_downloader_available': media_downloader_available(),
        'note': 'This app may use the Media Downloader API to fetch audio when that API is reachable. It falls back to direct yt-dlp when needed.'
    }


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET,HEAD,POST,OPTIONS')
        self.end_headers()

    def _read_json(self):
        length = int(self.headers.get('Content-Length', '0') or '0')
        raw = self.rfile.read(length) if length else b'{}'
        return json.loads(raw.decode('utf-8')) if raw else {}

    def _serve_index(self, head_only: bool = False):
        body = (STATIC_DIR / 'index.html').read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_HEAD(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            return self._serve_index(head_only=True)
        if parsed.path == '/api/health':
            return json_response(self, {'status': 'ok', 'service': APP_NAME, 'version': APP_VERSION}, head_only=True)
        if parsed.path == '/api/status':
            return json_response(self, build_status_payload(), head_only=True)
        return json_response(self, {'error': 'not found'}, HTTPStatus.NOT_FOUND, head_only=True)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            return self._serve_index()
        if parsed.path == '/api/health':
            return json_response(self, {'status': 'ok', 'service': APP_NAME, 'version': APP_VERSION})
        if parsed.path == '/api/status':
            return json_response(self, build_status_payload())
        return json_response(self, {'error': 'not found'}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/clear-jobs':
            cleared = clear_jobs()
            return json_response(self, {'ok': True, 'cleared': cleared})
        if parsed.path != '/api/download-song':
            return json_response(self, {'error': 'not found'}, HTTPStatus.NOT_FOUND)

        payload = self._read_json()
        song_name = (payload.get('song_name') or '').strip()
        artists = normalize_artists(payload.get('artists') or '')
        album_name = (payload.get('album_name') or '').strip()
        rename_to = (payload.get('rename_to') or '').strip()
        destination_path = (payload.get('destination_path') or DEFAULT_DESTINATION_DIR).strip()
        youtube_url = (payload.get('youtube_url') or '').strip()

        if not youtube_url and not song_name:
            return json_response(self, {'error': 'song_name is required when youtube_url is not provided'}, HTTPStatus.BAD_REQUEST)
        if not youtube_url and not artists:
            return json_response(self, {'error': 'artists is required when youtube_url is not provided'}, HTTPStatus.BAD_REQUEST)
        if youtube_url and not (rename_to or (song_name and artists) or song_name):
            return json_response(self, {'error': 'Provide rename_to or song_name when using a youtube_url so the final filename can be generated'}, HTTPStatus.BAD_REQUEST)

        job_id = new_job({
            'song_name': song_name,
            'artists': artists,
            'album_name': album_name,
            'rename_to': rename_to,
            'destination_path': destination_path,
            'youtube_url': youtube_url,
        })
        threading.Thread(target=worker, args=(job_id,), daemon=True).start()
        return json_response(self, {'ok': True, 'job_id': job_id})


if __name__ == '__main__':
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'{APP_NAME} listening on {PORT}', flush=True)
    server.serve_forever()
