
# Repository Map

## Where to handle what

- host bootstrap -> `core/services/bootstrap_host.py`
- reverse proxy -> `core/services/proxy.py`
- health checks -> `core/services/health.py`
- recovery -> `core/services/recovery.py`
- watchdog -> `core/services/watchdog.py`
- backup snapshots -> `core/services/backup.py`
- process execution helpers -> `core/services/process_runner.py`
- persistent state helpers -> `core/services/storage.py`
- plugin packaging -> `core/plugin_manager/builder.py`
- plugin install/uninstall -> `core/plugin_manager/installer.py`
- plugin runtime helpers -> `core/plugin_manager/runtime.py`
- plugin discovery -> `core/plugin_manager/registry.py`
- plugin validation -> `core/plugin_manager/validator.py`
- system APIs -> `core/api/system.py`
- plugin APIs -> `core/api/plugins.py`
- job APIs -> `core/api/jobs.py`
- marketplace APIs -> `core/api/marketplace.py`
