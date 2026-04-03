from __future__ import annotations

import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

APP_DATA_DIR = Path(os.environ.get('APP_DATA_DIR', '/data'))
DOWNLOAD_ROOT = Path(os.environ.get('DOWNLOAD_ROOT', str(APP_DATA_DIR / 'downloads')))
CACHE_DIR = Path(os.environ.get('YTDLP_CACHE_DIR', str(APP_DATA_DIR / 'cache' / 'yt-dlp')))
PORT = int(os.environ.get('PORT', '8160'))
HOST = '0.0.0.0'

DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
(APP_DATA_DIR / 'uploads').mkdir(parents=True, exist_ok=True)
(APP_DATA_DIR / 'converted').mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR = Path(__file__).resolve().parent / 'static'

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def which(cmd: str):
    return shutil.which(cmd)


def tool_status() -> dict:
    yt = which('yt-dlp')
    ff = which('ffmpeg')
    errors = []
    if not yt:
        errors.append('yt-dlp binary not found in container PATH')
    if not ff:
        errors.append('ffmpeg binary not found in container PATH')
    return {
        'yt_dlp_ready': yt is not None,
        'ffmpeg_ready': ff is not None,
        'installing': False,
        'message': 'yt-dlp + ffmpeg ready' if yt and ff else ('Tools missing' if errors else 'Ready'),
        'errors': errors,
    }


def device_hint(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    if 'iphone' in ua or 'ipad' in ua or 'ios' in ua:
        return 'On iPhone/iPad, browser-saved files typically appear in the Files app or the Safari download location.'
    if 'android' in ua:
        return 'On Android, browser-saved files usually go to Downloads unless your browser asks you to choose another location.'
    return 'On desktop browsers, files usually go to Downloads unless your browser is set to ask for a save location.'


def now():
    return time.time()


def new_job(kind: str, payload: dict):
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {
            'id': job_id,
            'kind': kind,
            'status': 'queued',
            'progress': 0.0,
            'message': 'Queued',
            'created_at': now(),
            'updated_at': now(),
            'payload': payload,
            'output_path': None,
            'output_name': None,
            'log': [],
        }
    return job_id


def update_job(job_id: str, **fields):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        log_line = fields.pop('log_line', None)
        job.update(fields)
        job['updated_at'] = now()
        if log_line:
            job.setdefault('log', []).append(log_line)
            if len(job['log']) > 120:
                job['log'] = job['log'][-120:]


def safe_name(text: str) -> str:
    text = re.sub(r'[^A-Za-z0-9._ -]+', '_', text).strip().strip('.')
    return text[:180] or 'download'


def list_saved_files():
    items = []
    for root in [DOWNLOAD_ROOT, APP_DATA_DIR / 'converted']:
        if not root.exists():
            continue
        for path in sorted([p for p in root.rglob('*') if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True):
            rel = path.relative_to(APP_DATA_DIR).as_posix()
            ext = path.suffix.lower()
            if root.name == 'converted' or ext in ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'):
                kind = 'audio' if root.name != 'converted' else 'converted'
            elif ext in ('.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v'):
                kind = 'video'
            else:
                kind = 'file'
            items.append({
                'name': path.name,
                'kind': kind,
                'relative_path': rel,
                'full_path': str(path),
                'size_bytes': path.stat().st_size,
                'modified_at': path.stat().st_mtime,
            })
    return items


def is_direct_file_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    direct_exts = ('.mp4', '.mp3', '.m4a', '.mkv', '.webm', '.mov', '.avi', '.wav', '.flac', '.aac', '.jpg', '.jpeg', '.png', '.pdf', '.zip', '.rar', '.7z')
    return path.endswith(direct_exts)


def pick_latest_file(folder: Path, started_at: float) -> Path | None:
    candidates = [p for p in folder.rglob('*') if p.is_file() and p.stat().st_mtime >= started_at - 2]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def serve_file_bytes(url: str, target_dir: Path, job_id: str):
    parsed = urlparse(url)
    filename = safe_name(Path(unquote(parsed.path)).name or f'{job_id}.bin')
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req) as resp, open(target, 'wb') as out:
        total = int(resp.headers.get('Content-Length', '0') or '0')
        downloaded = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            pct = round((downloaded / total) * 100, 2) if total else 0
            update_job(job_id, status='downloading', progress=min(pct, 99.0), message=f'Downloading direct file… {pct:.2f}%' if total else 'Downloading direct file…')
    return target


def run_ytdlp(job_id: str, url: str, mode: str, audio_format: str):
    target_dir = DOWNLOAD_ROOT / ('audio' if mode == 'audio' else 'video')
    target_dir.mkdir(parents=True, exist_ok=True)
    started_at = now()
    update_job(job_id, status='starting', progress=1, message='Starting yt-dlp…')
    error_messages = []
    try:
        import yt_dlp

        def hook(d):
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                done = d.get('downloaded_bytes') or 0
                pct = (done / total * 100) if total else 0
                msg = d.get('_percent_str', '').strip() or f'Downloading… {pct:.1f}%'
                update_job(job_id, status='downloading', progress=min(pct, 99.0), message=msg)
            elif status == 'finished':
                filename = d.get('filename')
                update_job(job_id, status='processing', progress=99.0, message='Post-processing…', log_line=f'Finished download: {filename}')

        ydl_opts = {
            'paths': {'home': str(target_dir)},
            'outtmpl': {'default': '%(title).150B [%(id)s].%(ext)s'},
            'restrictfilenames': True,
            'noplaylist': True,
            'cachedir': str(CACHE_DIR),
            'progress_hooks': [hook],
            'quiet': True,
            'no_warnings': True,
            'windowsfilenames': False,
            'consoletitle': False,
            'nopart': False,
        }
        if mode == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': audio_format or 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({
                'format': 'bv*+ba/b',
                'merge_output_format': 'mp4',
            })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        error_messages.append(str(exc))

    output = pick_latest_file(target_dir, started_at)
    if output and output.exists():
        update_job(job_id, status='completed', progress=100, message='Download completed', output_path=str(output), output_name=output.name, log_line=f'Saved to {output}')
        return

    if error_messages:
        update_job(job_id, status='failed', progress=0, message=error_messages[-1], log_line=error_messages[-1])
        return

    # Fallback to binary if module path failed but binary exists
    yt_bin = which('yt-dlp')
    if not yt_bin:
        update_job(job_id, status='failed', progress=0, message='yt-dlp is not available inside the container.')
        return
    cmd = [yt_bin, '--newline', '--restrict-filenames', '--no-progress-delta', '--cache-dir', str(CACHE_DIR), '-P', str(target_dir)]
    if mode == 'audio':
        cmd += ['-x', '--audio-format', audio_format or 'mp3']
    else:
        cmd += ['-f', 'bv*+ba/b']
    cmd += [url]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    percent_re = re.compile(r'(\d+(?:\.\d+)?)%')
    lines = []
    for raw_line in proc.stdout or []:
        line = raw_line.strip()
        if not line:
            continue
        lines.append(line)
        pct_match = percent_re.search(line)
        pct = float(pct_match.group(1)) if pct_match else None
        update_job(job_id, status='downloading', progress=min(pct or 0, 99.0), message=line, log_line=line)
    code = proc.wait()
    output = pick_latest_file(target_dir, started_at)
    if code == 0 and output and output.exists():
        update_job(job_id, status='completed', progress=100, message='Download completed', output_path=str(output), output_name=output.name)
    else:
        message = lines[-1] if lines else f'Download failed with exit code {code}'
        update_job(job_id, status='failed', progress=0, message=message, log_line=message)


def run_convert_to_mp3(job_id: str, source_rel: str):
    source = APP_DATA_DIR / source_rel
    if not source.exists() or not source.is_file():
        update_job(job_id, status='failed', message='Selected source file does not exist.', progress=0)
        return
    ffmpeg = which('ffmpeg')
    if not ffmpeg:
        update_job(job_id, status='failed', message='FFmpeg is not available inside the container.', progress=0)
        return
    target_dir = APP_DATA_DIR / 'converted'
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f'{source.stem}.mp3'
    cmd = [ffmpeg, '-y', '-i', str(source), '-vn', '-codec:a', 'libmp3lame', '-q:a', '2', str(target)]
    update_job(job_id, status='converting', progress=1, message='Converting to MP3…')
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines = []
    for raw_line in proc.stdout or []:
        line = raw_line.strip()
        if line:
            lines.append(line)
            update_job(job_id, status='converting', message='Converting to MP3…', log_line=line)
    code = proc.wait()
    if code != 0 or not target.exists():
        message = lines[-1] if lines else 'FFmpeg conversion failed.'
        update_job(job_id, status='failed', message=message, progress=0, log_line=message)
        return
    update_job(job_id, status='completed', progress=100, message='Conversion completed', output_path=str(target), output_name=target.name)


def start_download_worker(job_id: str):
    payload = JOBS[job_id]['payload']
    url = payload['url'].strip()
    mode = payload.get('mode', 'video')
    audio_format = payload.get('audio_format', 'mp3')
    try:
        if is_direct_file_url(url):
            target = serve_file_bytes(url, DOWNLOAD_ROOT / 'files', job_id)
            if mode == 'audio' and target.suffix.lower() not in ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'):
                update_job(job_id, status='processing', progress=99, message='Download complete, converting to MP3…', output_path=str(target), output_name=target.name)
                run_convert_to_mp3(job_id, target.relative_to(APP_DATA_DIR).as_posix())
            else:
                update_job(job_id, status='completed', progress=100, message='Direct file downloaded', output_path=str(target), output_name=target.name)
            return
        run_ytdlp(job_id, url, mode, audio_format)
    except Exception as exc:
        update_job(job_id, status='failed', progress=0, message=str(exc), log_line=str(exc))


def json_response(handler: BaseHTTPRequestHandler, payload: dict | list, code: int = HTTPStatus.OK):
    body = json.dumps(payload).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def _read_json(self):
        length = int(self.headers.get('Content-Length', '0') or '0')
        raw = self.rfile.read(length) if length else b'{}'
        return json.loads(raw.decode('utf-8')) if raw else {}

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            body = (STATIC_DIR / 'index.html').read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == '/api/health':
            json_response(self, {'status': 'ok'})
            return
        if parsed.path == '/api/status':
            with JOBS_LOCK:
                jobs = sorted(JOBS.values(), key=lambda j: j['created_at'], reverse=True)
            json_response(self, {
                'tools': tool_status(),
                'jobs': jobs,
                'saved_files': list_saved_files(),
                'server_save_root': str(DOWNLOAD_ROOT),
                'device_hint': device_hint(self.headers.get('User-Agent', '')),
                'host_platform': platform.platform(),
            })
            return
        if parsed.path.startswith('/downloaded/'):
            rel = unquote(parsed.path[len('/downloaded/'):])
            full = APP_DATA_DIR / rel
            if not full.exists() or not full.is_file() or APP_DATA_DIR not in full.resolve().parents and full.resolve() != APP_DATA_DIR.resolve():
                json_response(self, {'error': 'not found'}, HTTPStatus.NOT_FOUND)
                return
            mime = mimetypes.guess_type(full.name)[0] or 'application/octet-stream'
            body = full.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Disposition', f'attachment; filename="{full.name}"')
            self.end_headers()
            self.wfile.write(body)
            return
        json_response(self, {'error': 'not found'}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/download':
            data = self._read_json()
            url = (data.get('url') or '').strip()
            mode = (data.get('mode') or 'video').strip()
            if not url:
                json_response(self, {'error': 'URL is required'}, HTTPStatus.BAD_REQUEST)
                return
            job_id = new_job('download', {'url': url, 'mode': mode, 'audio_format': data.get('audio_format', 'mp3')})
            threading.Thread(target=start_download_worker, args=(job_id,), daemon=True).start()
            json_response(self, {'ok': True, 'job_id': job_id})
            return
        if parsed.path == '/api/convert':
            data = self._read_json()
            rel = (data.get('relative_path') or '').strip()
            if not rel:
                json_response(self, {'error': 'relative_path is required'}, HTTPStatus.BAD_REQUEST)
                return
            job_id = new_job('convert', {'relative_path': rel})
            threading.Thread(target=run_convert_to_mp3, args=(job_id, rel), daemon=True).start()
            json_response(self, {'ok': True, 'job_id': job_id})
            return
        json_response(self, {'error': 'not found'}, HTTPStatus.NOT_FOUND)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == '__main__':
    main()
