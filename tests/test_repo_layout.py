
from pathlib import Path

def test_core_layout_exists():
    root = Path(__file__).resolve().parents[1]
    for rel in [
        'core/plugin_manager',
        'core/services',
        'core/api',
        'core/models',
        'plugins',
        'runtime/installed_plugins',
        'manifests',
    ]:
        assert (root / rel).exists()
