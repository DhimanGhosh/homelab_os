from __future__ import annotations

import mimetypes
import threading
from pathlib import Path

from flask import Blueprint, abort, jsonify, render_template, request, send_file

from app.config import (
    APP_NAME, APP_VERSION, APP_DATA_DIR,
    DOWNLOAD_ROOT, UPLOAD_ROOT,
    DEFAULT_EXTERNAL_SAVE_DIR, ALLOWED_SAVE_ROOTS, HOST_DOWNLOAD_ROOT,
)
from app.files import (
    list_saved_files, clear_saved_files,
    safe_name, resolve_saved_file, ensure_allowed_destination, reserve_target,
)
from app.jobs import JOBS, JOBS_LOCK, new_job, clear_finished_jobs
from app.workers import (
    tool_status, device_hint,
    run_convert_to_mp3, run_save_as,
    start_download_worker, start_upload_convert_worker,
)

routes_bp = Blueprint('routes', __name__)


# ── UI ─────────────────────────────────────────────────────────────────────────

@routes_bp.route('/')
def index():
    return render_template('index.html')


# ── Health / Status ────────────────────────────────────────────────────────────

@routes_bp.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'service': APP_NAME, 'version': APP_VERSION})


@routes_bp.route('/api/status')
def status():
    with JOBS_LOCK:
        jobs = sorted(JOBS.values(), key=lambda j: j['created_at'], reverse=True)
    return jsonify({
        'tools':                    tool_status(),
        'jobs':                     jobs,
        'saved_files':              list_saved_files(),
        'server_save_root':         str(DOWNLOAD_ROOT),
        'server_save_root_host':    HOST_DOWNLOAD_ROOT,
        'device_hint':              device_hint(request.headers.get('User-Agent', '')),
        'default_external_save_dir': DEFAULT_EXTERNAL_SAVE_DIR,
        'allowed_save_roots':       [str(p) for p in ALLOWED_SAVE_ROOTS],
        'common_destinations': [
            DEFAULT_EXTERNAL_SAVE_DIR,
            '/mnt/nas/media/music',
            '/mnt/nas/media/videos',
            '/mnt/nas/downloads',
            str(DOWNLOAD_ROOT),
        ],
    })


# ── File serving ───────────────────────────────────────────────────────────────

@routes_bp.route('/downloaded/<path:rel>')
def downloaded(rel: str):
    full = (APP_DATA_DIR / rel).resolve()
    base = APP_DATA_DIR.resolve()
    if base not in full.parents or not full.is_file():
        abort(404)
    download_name = request.args.get('filename') or full.name
    return send_file(full, as_attachment=True, download_name=safe_name(download_name))


@routes_bp.route('/open/<path:rel>')
def open_file(rel: str):
    full = (APP_DATA_DIR / rel).resolve()
    base = APP_DATA_DIR.resolve()
    if base not in full.parents or not full.is_file():
        abort(404)
    mime = mimetypes.guess_type(full.name)[0] or 'application/octet-stream'
    return send_file(full, mimetype=mime, as_attachment=False, download_name=full.name)


# ── Download ───────────────────────────────────────────────────────────────────

@routes_bp.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json(force=True) or {}
    url  = (data.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    mode   = (data.get('mode') or 'video').strip()
    job_id = new_job('download', {'url': url, 'mode': mode, 'audio_format': data.get('audio_format', 'mp3')})
    threading.Thread(target=start_download_worker, args=(job_id,), daemon=True).start()
    return jsonify({'ok': True, 'job_id': job_id})


# ── Convert ────────────────────────────────────────────────────────────────────

@routes_bp.route('/api/convert', methods=['POST'])
def api_convert():
    data = request.get_json(force=True) or {}
    rel  = (data.get('relative_path') or '').strip()
    if not rel:
        return jsonify({'error': 'relative_path is required'}), 400
    new_name = (data.get('new_name') or '').strip() or None
    job_id   = new_job('convert', {'relative_path': rel, 'new_name': new_name})
    threading.Thread(target=run_convert_to_mp3, args=(job_id, rel, new_name), daemon=True).start()
    return jsonify({'ok': True, 'job_id': job_id})


# ── Save elsewhere ─────────────────────────────────────────────────────────────

@routes_bp.route('/api/save-as', methods=['POST'])
def api_save_as():
    data             = request.get_json(force=True) or {}
    rel              = (data.get('relative_path')  or '').strip()
    destination_path = (data.get('destination_path') or '').strip()
    new_name         = (data.get('new_name')        or '').strip()
    operation        = (data.get('operation')       or 'copy').strip().lower()
    if not rel:
        return jsonify({'error': 'relative_path is required'}), 400
    if operation not in ('copy', 'move'):
        return jsonify({'error': 'operation must be copy or move'}), 400
    try:
        ensure_allowed_destination(destination_path)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400
    job_id = new_job('save-as', {
        'relative_path':  rel,
        'destination_path': destination_path,
        'new_name':       new_name,
        'operation':      operation,
    })
    threading.Thread(target=run_save_as, args=(job_id, rel, destination_path, new_name, operation), daemon=True).start()
    return jsonify({'ok': True, 'job_id': job_id})


# ── Upload + convert ───────────────────────────────────────────────────────────

@routes_bp.route('/api/upload-convert', methods=['POST'])
def api_upload_convert():
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'error': 'Choose a file first'}), 400
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    upload_name   = safe_name(Path(f.filename).name)
    upload_target = reserve_target(UPLOAD_ROOT, upload_name)
    f.save(str(upload_target))
    convert_to = (request.form.get('convert_to') or 'mp3').strip()
    if convert_to != 'mp3':
        return jsonify({'error': 'Only MP3 conversion is supported right now'}), 400
    new_name = (request.form.get('new_name') or '').strip() or None
    rel      = upload_target.relative_to(APP_DATA_DIR).as_posix()
    job_id   = new_job('upload-convert', {'relative_path': rel, 'new_name': new_name})
    threading.Thread(target=start_upload_convert_worker, args=(job_id, rel, new_name), daemon=True).start()
    return jsonify({'ok': True, 'job_id': job_id, 'uploaded_relative_path': rel})


# ── Clear ──────────────────────────────────────────────────────────────────────

@routes_bp.route('/api/clear-jobs', methods=['POST'])
def api_clear_jobs():
    removed = clear_finished_jobs()
    return jsonify({'ok': True, 'removed': removed})


@routes_bp.route('/api/clear-clutter', methods=['POST'])
def api_clear_clutter():
    removed_jobs  = clear_finished_jobs()
    removed_files = clear_saved_files()
    return jsonify({'ok': True, 'removed_jobs': removed_jobs, **removed_files})
