
import json
from pathlib import Path
from core.models.plugin import PluginManifest

REQUIRED_KEYS = ['id', 'name', 'version', 'entrypoint', 'backend', 'ui', 'network', 'capabilities', 'healthcheck', 'lifecycle']

def load_manifest(plugin_dir: Path) -> dict:
    path = plugin_dir / 'plugin.json'
    if not path.exists():
        raise FileNotFoundError(f'plugin.json missing in {plugin_dir}')
    return json.loads(path.read_text(encoding='utf-8'))

def validate_manifest(plugin_dir: Path) -> PluginManifest:
    raw = load_manifest(plugin_dir)
    missing = [k for k in REQUIRED_KEYS if k not in raw]
    if missing:
        raise ValueError(f'Missing manifest keys for {plugin_dir.name}: {missing}')
    return PluginManifest(**raw)
