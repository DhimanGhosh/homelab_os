from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

from app.config import APP_DATA_DIR, DOWNLOAD_ROOT, CONVERTED_ROOT, CACHE_DIR
from app.files import safe_name, reserve_target, resolve_saved_file, ensure_allowed_destination, build_target_name
from app.jobs import JOBS, now, update_job


# ── Tool helpers ───────────────────────────────────────────────────────────────

def which(cmd: str):
    return shutil.which(cmd)


def tool_status() -> dict:
    yt = which('yt-dlp')
    ff = which('ffmpeg')
    errors = []
    if not yt:
        errors.append('yt-dlp missing')
    if not ff:
        errors.append('ffmpeg missing')
    return {
        'yt_dlp_ready': yt is not None,
        'ffmpeg_ready': ff is not None,
        'installing':   False,
        'message':      'yt-dlp + ffmpeg ready' if (yt and ff) else (' · '.join(errors) or 'Ready'),
        'errors':       errors,
    }


def device_hint(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    if 'iphone' in ua or 'ipad' in ua or 'ios' in ua:
        return 'On iPhone/iPad, "Download to this device" usually saves into Safari downloads or the Files app.'
    if 'android' in ua:
        return 'On Android, "Download to this device" usually saves into Downloads unless your browser asks where to save.'
    return 'On desktop browsers, "Download to this device" usually saves into Downloads unless your browser is set to ask every time.'


# ── File utilities ─────────────────────────────────────────────────────────────

def is_direct_file_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    direct_exts = (
        '.mp4', '.mp3', '.m4a', '.mkv', '.webm', '.mov', '.avi',
        '.wav', '.flac', '.aac', '.jpg', '.jpeg', '.png',
        '.pdf', '.zip', '.rar', '.7z',
    )
    return path.endswith(direct_exts)


def pick_latest_file(folder: Path, started_at: float) -> Path | None:
    candidates = [p for p in folder.rglob('*') if p.is_file() and p.stat().st_mtime >= started_at - 2]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def finalize_job_file(job_id: str, output: Path, message: str = 'Completed') -> None:
    rel = output.relative_to(APP_DATA_DIR).as_posix()
    update_job(
        job_id,
        status='completed', progress=100, message=message,
        output_path=str(output), output_name=output.name, output_relative=rel,
        log_line=f'Saved to {output}',
    )


# ── Download workers ───────────────────────────────────────────────────────────

def serve_file_bytes(url: str, target_dir: Path, job_id: str) -> Path:
    parsed   = urlparse(url)
    filename = safe_name(Path(unquote(parsed.path)).name or f'{job_id}.bin')
    target_dir.mkdir(parents=True, exist_ok=True)
    target = reserve_target(target_dir, filename)
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req) as resp, open(target, 'wb') as out:
        total      = int(resp.headers.get('Content-Length', '0') or '0')
        downloaded = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            pct = round((downloaded / total) * 100, 2) if total else 0
            update_job(
                job_id,
                status='downloading', progress=min(pct, 99.0),
                message=f'Downloading direct file… {pct:.2f}%' if total else 'Downloading direct file…',
            )
    return target


def run_ytdlp(job_id: str, url: str, mode: str, audio_format: str) -> None:
    import yt_dlp
    target_dir = DOWNLOAD_ROOT / ('audio' if mode == 'audio' else 'video')
    target_dir.mkdir(parents=True, exist_ok=True)
    started_at     = now()
    error_messages = []
    update_job(job_id, status='starting', progress=1, message='Starting yt-dlp…')

    try:
        def hook(d):
            s = d.get('status')
            if s == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                done  = d.get('downloaded_bytes') or 0
                pct   = (done / total * 100) if total else 0
                msg   = d.get('_percent_str', '').strip() or f'Downloading… {pct:.1f}%'
                update_job(job_id, status='downloading', progress=min(pct, 99.0), message=msg)
            elif s == 'finished':
                update_job(job_id, status='processing', progress=99.0, message='Post-processing…',
                           log_line=f'Finished download: {d.get("filename")}')

        ydl_opts = {
            'paths':            {'home': str(target_dir)},
            'outtmpl':          {'default': '%(title).150B [%(id)s].%(ext)s'},
            'restrictfilenames': True,
            'noplaylist':       True,
            'cachedir':         str(CACHE_DIR),
            'progress_hooks':   [hook],
            'quiet':            True,
            'no_warnings':      True,
            'windowsfilenames': False,
            'consoletitle':     False,
        }
        if mode == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key':             'FFmpegExtractAudio',
                    'preferredcodec':  audio_format or 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({'format': 'bv*+ba/b', 'merge_output_format': 'mp4'})

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        error_messages.append(str(exc))

    output = pick_latest_file(target_dir, started_at)
    if output and output.exists():
        finalize_job_file(job_id, output, 'Download completed')
        return
    msg = error_messages[-1] if error_messages else 'Download failed with no output file'
    update_job(job_id, status='failed', progress=0, message=msg, log_line=msg)


def start_download_worker(job_id: str) -> None:
    payload      = JOBS[job_id]['payload']
    url          = payload['url'].strip()
    mode         = payload.get('mode', 'video')
    audio_format = payload.get('audio_format', 'mp3')
    try:
        if is_direct_file_url(url):
            target = serve_file_bytes(url, DOWNLOAD_ROOT / 'files', job_id)
            if mode == 'audio' and target.suffix.lower() != '.mp3':
                update_job(job_id, status='processing', progress=99,
                           message='Download complete, converting to MP3…',
                           output_path=str(target), output_name=target.name)
                run_convert_to_mp3(job_id, target.relative_to(APP_DATA_DIR).as_posix())
            else:
                finalize_job_file(job_id, target, 'Direct file downloaded')
            return
        run_ytdlp(job_id, url, mode, audio_format)
    except Exception as exc:
        update_job(job_id, status='failed', progress=0, message=str(exc), log_line=str(exc))


# ── Conversion + save workers ──────────────────────────────────────────────────

def run_convert_to_mp3(job_id: str, source_rel: str, new_name: str | None = None) -> None:
    try:
        source = resolve_saved_file(source_rel)
    except Exception as exc:
        update_job(job_id, status='failed', message=str(exc), progress=0)
        return
    ffmpeg = which('ffmpeg')
    if not ffmpeg:
        update_job(job_id, status='failed', message='FFmpeg is not available inside the container.', progress=0)
        return
    CONVERTED_ROOT.mkdir(parents=True, exist_ok=True)
    base_name = safe_name(new_name or source.stem)
    target    = reserve_target(CONVERTED_ROOT, f'{base_name}.mp3')
    cmd       = [ffmpeg, '-y', '-i', str(source), '-vn', '-codec:a', 'libmp3lame', '-q:a', '2', str(target)]
    update_job(job_id, status='converting', progress=1, message='Converting to MP3…')
    proc  = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
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
    finalize_job_file(job_id, target, 'Conversion completed')


def start_upload_convert_worker(job_id: str, upload_rel: str, new_name: str | None) -> None:
    run_convert_to_mp3(job_id, upload_rel, new_name=new_name)


def run_save_as(job_id: str, source_rel: str, destination_path: str, new_name: str, operation: str) -> None:
    try:
        import shutil as _sh
        source      = resolve_saved_file(source_rel)
        dest_dir    = ensure_allowed_destination(destination_path)
        target_name = build_target_name(source, new_name)
        target      = reserve_target(dest_dir, target_name)
        update_job(job_id, status='processing', progress=25,
                   message='Preparing file save…', log_line=f'Source: {source}')
        if operation == 'move':
            _sh.move(str(source), str(target))
            action = 'Moved'
        else:
            _sh.copy2(str(source), str(target))
            action = 'Copied'
        update_job(
            job_id, status='completed', progress=100,
            message=f'{action} to {target}',
            output_path=str(target), output_name=target.name, output_relative=None,
            log_line=f'{action} file to {target}',
        )
    except Exception as exc:
        update_job(job_id, status='failed', progress=0, message=str(exc), log_line=str(exc))
