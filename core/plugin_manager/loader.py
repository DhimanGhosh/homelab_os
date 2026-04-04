
from pathlib import Path
from core.plugin_manager.validator import validate_manifest

class PluginLoader:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir

    def load(self, plugin_id: str) -> dict:
        plugin_dir = self.plugins_dir / plugin_id
        return validate_manifest(plugin_dir).__dict__
