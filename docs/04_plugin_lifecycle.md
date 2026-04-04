
# Plugin Lifecycle

Each plugin may expose three hooks:
- `install.py`
- `uninstall.py`
- `upgrade.py`

The CLI builds a plugin archive from a plugin folder, then the installer extracts it, reads `plugin.json`, and executes the relevant lifecycle hook.
