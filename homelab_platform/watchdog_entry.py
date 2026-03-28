import os
from homelab_platform.config import Settings
from homelab_platform.services.watchdog import watchdog_loop
if __name__ == '__main__':
    watchdog_loop(Settings.from_env_file(os.environ.get('HOMELAB_ENV_FILE', '.env')))
