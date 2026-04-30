from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from app.config import (
    APP_DATA_DIR, DOWNLOAD_ROOT, CONVERTED_ROOT, UPLOAD_ROOT, ALLOWED_SAVE_ROOTS,
)


def safe_name(text: str) -> str:
    text = re.sub(r'[^A-Za-z0-9._ -]+', '_', str(text)).strip().strip('.')
    text = re.sub(r'\s+', '_', text)
    return text[:180] or 'download'


def list_saved_files() -> list[dict]:
    items = []
    for root in [DOWNLOAD_ROOT, CONVERTED_ROOT, UPLOAD_ROOT]:
        if not root.exists():
            continue
        for path in sorted(
            [p for p in root.rglob('*') if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            rel = path.relative_to(APP_DATA_DIR).as_posix()
            ext = path.suffix.lower()
            if ext in ('.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'):
                kind = 'audio'
            elif ext in ('.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v'):
                kind = 'video'
            else:
                kind = 'file'
            items.append({
                'name':           path.name,
                'kind':           kind,
                'relative_path':  rel,
                'full_path':      str(path),
                'size_bytes':     path.stat().st_size,
                'modified_at':    path.stat().st_mtime,
                'browser_open_url': '/open/'       + '/'.join(quote(p) for p in rel.split('/')),
                'download_url':     '/downloaded/' + '/'.join(quote(p) for p in rel.split('/')),
            })
    return items


def clear_saved_files() -> dict:
    removed_files = 0
    removed_dirs  = 0
    for root in [DOWNLOAD_ROOT, CONVERTED_ROOT, UPLOAD_ROOT]:
        if not root.exists():
            continue
        for path in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink(missing_ok=True)
                    removed_files += 1
                elif path.is_dir():
                    path.rmdir()
                    removed_dirs += 1
            except (FileNotFoundError, OSError):
                continue
        root.mkdir(parents=True, exist_ok=True)
    return {'removed_files': removed_files, 'removed_dirs': removed_dirs}


def resolve_saved_file(relative_path: str) -> Path:
    rel  = relative_path.strip().lstrip('/')
    path = (APP_DATA_DIR / rel).resolve()
    base = APP_DATA_DIR.resolve()
    if base not in path.parents and path != base:
        raise ValueError('relative_path must point to a file inside app data')
    if not path.exists() or not path.is_file():
        raise FileNotFoundError('selected source file does not exist')
    return path


def ensure_allowed_destination(dest_dir: str) -> Path:
    if not dest_dir:
        raise ValueError('destination_path is required')
    dest = Path(dest_dir).expanduser()
    if not dest.is_absolute():
        raise ValueError('destination_path must be an absolute path')
    resolved = dest.resolve()
    allowed  = []
    for root in ALLOWED_SAVE_ROOTS:
        root_resolved = root.resolve()
        allowed.append(str(root_resolved))
        if resolved == root_resolved or root_resolved in resolved.parents:
            resolved.mkdir(parents=True, exist_ok=True)
            return resolved
    raise ValueError('destination_path must stay inside one of: ' + ', '.join(allowed))


def build_target_name(source: Path, new_name: str) -> str:
    name = (new_name or '').strip()
    if not name:
        return source.name
    cleaned = safe_name(name)
    if '.' not in cleaned and source.suffix:
        cleaned += source.suffix
    return cleaned


def reserve_target(dest_dir: Path, target_name: str) -> Path:
    target = dest_dir / target_name
    if not target.exists():
        return target
    stem   = target.stem
    suffix = target.suffix
    idx = 1
    while True:
        candidate = dest_dir / f'{stem}_{idx}{suffix}'
        if not candidate.exists():
            return candidate
        idx += 1
