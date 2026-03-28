import json, time
from pathlib import Path
from homelab_platform.services.health import health_snapshot
from homelab_platform.services.recovery import recover_stack
LOG_PATH = Path('/var/log/raspi-homelab-watchdog.log')

def log(msg: str):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('a', encoding='utf-8') as f: f.write(msg + '\n')

def watchdog_loop(settings):
    interval = max(5, settings.watchdog_interval_seconds)
    while True:
        snap = health_snapshot(settings)
        log(json.dumps(snap))
        if not all(snap.values()):
            log('[WATCHDOG] issue detected -> triggering recovery')
            try: recover_stack(settings)
            except Exception as e: log(f'[WATCHDOG] recovery failed: {e}')
        time.sleep(interval)
