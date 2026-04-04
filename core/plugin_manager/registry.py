
import json
from pathlib import Path
from core.plugin_manager.validator import validate_manifest

class PluginRegistry:
    def __init__(self, plugins_dir: Path, installed_dir: Path):
        self.plugins_dir = plugins_dir
        self.installed_dir = installed_dir

    def discover(self) -> list[dict]:
        items = []
        if not self.plugins_dir.exists():
            return items
        for plugin_dir in sorted(p for p in self.plugins_dir.iterdir() if p.is_dir()):
            try:
                manifest = validate_manifest(plugin_dir)
                items.append(manifest.__dict__)
            except Exception:
                continue
        return items

    def installed_plugins(self) -> list[dict]:
        items = []
        if not self.installed_dir.exists():
            return items
        for p in sorted(self.installed_dir.iterdir()):
            manifest = p / 'plugin.json'
            if manifest.exists():
                items.append(json.loads(manifest.read_text(encoding='utf-8')))
        return items
