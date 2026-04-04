
import os
import sys
from pathlib import Path
from core.config import Settings

def main(env_file: str = '.env'):
    settings = Settings.from_env_file(env_file)
    plugin_root = settings.plugins_dir / 'control_center'
    backend_app_root = plugin_root / 'backend' / 'app'
    if not backend_app_root.exists():
        raise FileNotFoundError(f'Control Center backend not found: {backend_app_root}')
    os.environ['HOMELAB_ENV_FILE'] = env_file
    sys.path.insert(0, str(backend_app_root))
    from control_center_app import main as cc_main
    cc_main()
