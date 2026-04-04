
from pathlib import Path
import types
import json

class PluginLifecycle:
    def __init__(self, settings):
        self.settings = settings

    def _load_module(self, script_path: Path):
        module = types.ModuleType(script_path.stem)
        code = compile(script_path.read_text(encoding='utf-8'), str(script_path), 'exec')
        exec(code, module.__dict__)
        return module

    def run_hook(self, plugin_dir: Path, hook: str, manifest: dict):
        script = plugin_dir / f'{hook}.py'
        if not script.exists():
            return {'ok': True, 'message': f'No {hook}.py hook for {manifest["id"]}'}
        module = self._load_module(script)
        func = getattr(module, hook, None)
        if func is None:
            raise AttributeError(f'{hook} not found in {script}')
        return func(self.settings, plugin_dir, manifest)
