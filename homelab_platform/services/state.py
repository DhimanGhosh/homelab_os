import shutil, json
from pathlib import Path

def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')

def record_install_state(apps_dir: Path, app_id: str, meta: dict, extracted: Path, runtime_dir: Path | None = None):
    dst = apps_dir / app_id
    dst.mkdir(parents=True, exist_ok=True)
    write_json(dst / 'metadata.json', meta)
    write_json(dst / 'install_state.json', {'app_id': app_id, 'version': meta.get('version'), 'runtime_dir': str(runtime_dir) if runtime_dir else None})
    bundle_copy = dst / 'bundle'
    if bundle_copy.exists(): shutil.rmtree(bundle_copy)
    shutil.copytree(extracted, bundle_copy)

def load_installed_apps(apps_dir: Path) -> list[dict]:
    out=[]
    if not apps_dir.exists(): return out
    for p in sorted(apps_dir.iterdir()):
        meta = read_json(p / 'metadata.json', default=None)
        if meta: out.append(meta)
    return out
