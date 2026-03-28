from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
FQDN = os.getenv('TAILSCALE_FQDN', 'pi-nas.taild4713b.ts.net')
NAS_PATH = Path(os.getenv('NAS_PATH', '/mnt/nas'))
APP_BASE = Path(os.getenv('APP_BASE', '/mnt/nas/homelab/apps'))

app = FastAPI(title='Pi Status Board', version='1.3.0')
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')

SERVICES = [
    {'id': 'control-center', 'name': 'Control Center', 'url': f'https://{FQDN}:8444', 'health': 'http://127.0.0.1:9000/api/health'},
    {'id': 'navidrome', 'name': 'Navidrome', 'url': f'https://{FQDN}:8445', 'health': 'http://127.0.0.1:4533/'},
    {'id': 'jellyfin', 'name': 'Jellyfin', 'url': f'https://{FQDN}:8446', 'health': 'http://127.0.0.1:8096/health'},
    {'id': 'pihole', 'name': 'Pi-hole', 'url': f'https://{FQDN}:8447/admin/', 'health': 'http://127.0.0.1/admin/'},
    {'id': 'nextcloud', 'name': 'Nextcloud', 'url': f'https://{FQDN}:8448/', 'health': 'http://127.0.0.1:8081/status.php'},
    {'id': 'files', 'name': 'Files', 'url': f'https://{FQDN}:8449/', 'health': 'http://127.0.0.1:8088/'},
    {'id': 'home-assistant', 'name': 'Home Assistant', 'url': f'https://{FQDN}:8450/', 'health': 'http://127.0.0.1:8123/manifest.json'},
    {'id': 'status', 'name': 'Status Board', 'url': f'https://{FQDN}:8451/', 'health': 'http://127.0.0.1:8131/api/health'},
    {'id': 'voice-ai', 'name': 'Voice AI', 'url': f'https://{FQDN}:8452/', 'health': 'http://127.0.0.1:8124/config/client'},
    {'id': 'homarr', 'name': 'Homarr', 'url': f'https://{FQDN}:8453/', 'health': 'http://127.0.0.1:7575/'},
    {'id': 'personal-library', 'name': 'Personal Library', 'url': f'https://{FQDN}:8454/', 'health': 'http://127.0.0.1:8132/api/health'},
    {'id': 'dictionary', 'name': 'Dictionary', 'url': f'https://{FQDN}:8455/', 'health': 'http://127.0.0.1:8133/api/health'},
    {'id': 'api-gateway', 'name': 'API Gateway', 'url': f'https://{FQDN}:8456/docs', 'health': 'http://127.0.0.1:8134/api/health'},
]


def check_url(url: str) -> dict:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'pi-statusboard/1.3'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return {'ok': True, 'status': resp.status}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)[:200]}


def disk_info(path: Path) -> dict:
    try:
        u = shutil.disk_usage(path)
        used = u.total - u.free
        return {'path': str(path), 'total_gb': round(u.total/1024**3, 2), 'used_gb': round(used/1024**3, 2), 'free_gb': round(u.free/1024**3, 2), 'used_pct': round((used/u.total)*100, 2) if u.total else 0}
    except Exception:
        return {'path': str(path), 'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'used_pct': 0}


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=8).strip()
    except Exception:
        return ''


def tailscale_devices() -> list[dict]:
    raw = run(['tailscale', 'status', '--json'])
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    peers = []
    for peer in (data.get('Peer') or {}).values():
        peers.append({
            'name': peer.get('HostName') or peer.get('DNSName', '').rstrip('.') or peer.get('TailscaleIPs', [''])[0],
            'online': bool(peer.get('Online')),
            'os': peer.get('OS', ''),
            'ip': (peer.get('TailscaleIPs') or [''])[0],
        })
    peers.sort(key=lambda x: (not x['online'], x['name']))
    return peers


def app_versions() -> dict:
    out = {}
    if not APP_BASE.exists():
        return out
    for d in APP_BASE.iterdir():
        state = d / 'install_state.json'
        if state.exists():
            try:
                payload = json.loads(state.read_text())
                out[d.name] = {'version': payload.get('installed_version') or payload.get('version') or '-', 'port': payload.get('port') or '-'}
            except Exception:
                pass
    return out


@app.get('/')
def index() -> HTMLResponse:
    return HTMLResponse((STATIC / 'index.html').read_text(encoding='utf-8'))


@app.get('/api/health')
def health():
    return {'ok': True, 'service': 'Pi Status Board', 'version': '1.3.0'}


@app.get('/api/system')
def system() -> JSONResponse:
    versions = app_versions()
    services = []
    ok_count = 0
    for item in SERVICES:
        res = check_url(item['health'])
        if res.get('ok'):
            ok_count += 1
        meta = versions.get(item['id'], {})
        services.append({**item, **res, 'version': meta.get('version', '-'), 'port': meta.get('port', '-')})
    return JSONResponse({
        'hostname': socket.gethostname(),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'summary': {'ok': ok_count, 'total': len(services)},
        'uptime': run(['uptime', '-p']) or run(['uptime']),
        'tailscale_ip': run(['tailscale', 'ip', '-4']),
        'nas_storage': disk_info(NAS_PATH),
        'root_storage': disk_info(Path('/')),
        'tailscale_devices': tailscale_devices(),
        'services': services,
    })
