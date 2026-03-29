import json
import os
import subprocess
import tarfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request


def _env_path() -> Path:
    return Path(os.environ.get('HOMELAB_ENV_FILE', '.env')).resolve()


def _parse_env(path: Path) -> dict:
    data = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            data[k.strip()] = v.strip()
    return data


def _paths():
    env_file = _env_path()
    env = _parse_env(env_file)
    repo_root = Path(os.environ.get('REPO_ROOT', env_file.parent)).resolve()
    return {
        'env_file': env_file,
        'apps_dir': Path(env.get('APPS_DIR', '/mnt/nas/homelab/apps')),
        'installers_dir': Path(env.get('INSTALLERS_DIR', '/mnt/nas/homelab/installers')),
        'dist_dir': repo_root / 'dist',
        'tailscale_fqdn': env.get('TAILSCALE_FQDN', 'pi-nas.taild4713b.ts.net'),
        'control_center_public_port': int(env.get('CONTROL_CENTER_PUBLIC_PORT', '8444')),
        'homelabctl_bin': Path(os.environ.get('HOMELABCTL_BIN', repo_root / '.venv' / 'bin' / 'homelabctl')),
    }


def _run_cmd(cmd):
    proc = subprocess.run(list(map(str, cmd)), text=True, capture_output=True)
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def _run_homelabctl(args):
    paths = _paths()
    cmd = [str(paths['homelabctl_bin']), *args, '--env-file', str(paths['env_file'])]
    return _run_cmd(cmd)


def _read_bundle_metadata(bundle_path: Path):
    try:
        with tarfile.open(bundle_path, 'r:*') as tf:
            for member in tf.getmembers():
                if member.name.endswith('metadata.json'):
                    f = tf.extractfile(member)
                    if f:
                        return json.loads(f.read().decode('utf-8'))
    except Exception:
        return None
    return None


def _load_installed():
    paths = _paths()
    out = []
    if not paths['apps_dir'].exists():
        return out
    for p in sorted(paths['apps_dir'].iterdir()):
        meta_path = p / 'metadata.json'
        st_path = p / 'install_state.json'
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except Exception:
            continue
        state = {}
        if st_path.exists():
            try:
                state = json.loads(st_path.read_text(encoding='utf-8'))
            except Exception:
                state = {}
        row = dict(meta)
        row['install_status'] = state.get('status', 'unknown')
        row['last_error'] = state.get('last_error')
        row['log_path'] = state.get('log_path')
        row['is_installed'] = state.get('status') == 'installed'
        out.append(row)
    return out


def _discover_bundles():
    paths = _paths()
    bundles = {}
    for base in [paths['dist_dir'], paths['installers_dir']]:
        if not base.exists():
            continue
        for p in sorted(base.glob('*.tgz')):
            meta = _read_bundle_metadata(p) or {}
            bundles[p.name] = {
                'filename': p.name,
                'id': meta.get('id') or p.name.split('.app.')[0],
                'display_name': meta.get('name') or p.name,
                'version': meta.get('version'),
            }
    return list(bundles.values())


def create_app():
    paths = _paths()
    app = Flask(__name__, template_folder='templates', static_folder='static')

    @app.get('/')
    def index():
        return render_template('index.html', fqdn=paths['tailscale_fqdn'], public_cc_port=paths['control_center_public_port'])

    @app.get('/api/health')
    def health():
        return jsonify({'ok': True, 'backend': 'control-center'})

    @app.get('/api/bundles')
    def bundles():
        installed = _load_installed()
        installed_map = {i['id']: i for i in installed}
        rows = []
        for b in _discover_bundles():
            row = dict(b)
            ii = installed_map.get(b['id'])
            row['installed'] = bool(ii and ii.get('is_installed'))
            row['install_status'] = ii.get('install_status') if ii else None
            row['log_path'] = ii.get('log_path') if ii else None
            rows.append(row)
        return jsonify({'bundles': rows, 'installed': installed})

    @app.post('/api/upload')
    def upload():
        f = request.files['file']
        target = _paths()['installers_dir'] / f.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target)
        return jsonify({'ok': True, 'saved': str(target)})

    @app.post('/api/install')
    def install():
        data = request.get_json(force=True)
        paths = _paths()
        bundle_name = data['bundle_filename']
        bundle_path = paths['installers_dir'] / bundle_name
        if not bundle_path.exists():
            bundle_path = paths['dist_dir'] / bundle_name
        result = _run_homelabctl(['install-bundle', '--bundle', str(bundle_path)])
        return jsonify(result), (200 if result['returncode'] == 0 else 500)

    @app.post('/api/remove')
    def remove():
        data = request.get_json(force=True)
        result = _run_homelabctl(['remove-app', '--app-id', data['app_id']])
        return jsonify(result), (200 if result['returncode'] == 0 else 500)

    @app.get('/api/logs/<app_id>')
    def logs(app_id):
        for item in _load_installed():
            if item['id'] == app_id and item.get('log_path'):
                p = Path(item['log_path'])
                if p.exists():
                    return jsonify({'ok': True, 'content': p.read_text(encoding='utf-8', errors='replace')})
        return jsonify({'ok': False, 'message': 'No log found'}), 404

    return app
