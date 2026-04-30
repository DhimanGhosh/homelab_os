from __future__ import annotations

import os
from pathlib import Path

APP_NAME    = os.environ.get('APP_NAME',    'Media Downloader')
APP_VERSION = os.environ.get('APP_VERSION', '1.0.9')

APP_DATA_DIR  = Path(os.environ.get('APP_DATA_DIR',  '/data'))
DOWNLOAD_ROOT = Path(os.environ.get('DOWNLOAD_ROOT', str(APP_DATA_DIR / 'downloads')))
CACHE_DIR     = Path(os.environ.get('YTDLP_CACHE_DIR', str(APP_DATA_DIR / 'cache' / 'yt-dlp')))
PORT          = int(os.environ.get('PORT', '8160'))

ALLOWED_SAVE_ROOTS = [
    Path(p) for p in os.environ.get('ALLOWED_SAVE_ROOTS', '/mnt/nas:/data').split(':') if p
]
DEFAULT_EXTERNAL_SAVE_DIR = os.environ.get('DEFAULT_EXTERNAL_SAVE_DIR', '/mnt/nas/media/music')
HOST_DOWNLOAD_ROOT        = os.environ.get(
    'HOST_DOWNLOAD_ROOT',
    '/mnt/nas/homelab/runtime/link-downloader/data/downloads',
)

UPLOAD_ROOT    = APP_DATA_DIR / 'uploads'
CONVERTED_ROOT = APP_DATA_DIR / 'converted'

# Ensure runtime directories exist on startup
for _p in [DOWNLOAD_ROOT, UPLOAD_ROOT, CONVERTED_ROOT, CACHE_DIR]:
    _p.mkdir(parents=True, exist_ok=True)
