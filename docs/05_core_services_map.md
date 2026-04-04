
# Core Services Map

## services/
- `bootstrap_host.py` -> prepare the Raspberry Pi host
- `proxy.py` -> write base and per-plugin Caddy configs
- `health.py` -> platform and app-level health checks
- `recovery.py` -> invoke the self-healing flow
- `watchdog.py` -> periodic health polling and recovery trigger
- `jobs.py` -> lightweight job persistence helpers
- `events.py` -> append-only event bus
- `logging.py` -> generic append-log helper
- `backup.py` -> snapshot archive creation
- `storage.py` -> installed-plugin state read/write helpers
- `process_runner.py` -> subprocess execution wrapper
