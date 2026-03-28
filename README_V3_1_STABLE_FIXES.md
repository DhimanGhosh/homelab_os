# raspi_homelab_python_framework v3.1 stable fixes

This pack fixes two major issues found during bundle installation:

1. **Dictionary install failure**
   - The container could fail with:
     - `exec: "python": executable file not found in $PATH`
   - Fixed by switching the Dictionary bundle to a `start.sh` launcher that uses `python3` explicitly and creates required data directories before startup.

2. **Poor install visibility / stale installed state**
   - Failed installs could leave confusing status in the Control Center.
   - There was no persistent detailed operation log for each install.
   - Fixed by adding:
     - per-app install log files under `/mnt/nas/homelab/logs/installs/`
     - install states: `installing`, `installed`, `failed`
     - stored failure message + log path
     - Control Center UI buttons to view the latest log for each app
     - cleaner CLI failure output with log path instead of a giant traceback

## Files changed
- `homelab_platform/config.py`
- `homelab_platform/services/state.py`
- `homelab_platform/services/subprocesses.py`
- `homelab_platform/services/bundle_installer.py`
- `homelab_platform/services/bundle_runtime.py`
- `homelab_platform/cli.py`
- `homelab_platform/web.py`
- `homelab_platform/templates/index.html`
- `homelab_platform/static/js/app.js`
- `homelab_platform/static/css/style.css`
- `bundle_specs/dictionary.app.v1.4.5/runtime/Dockerfile`
- `bundle_specs/dictionary.app.v1.4.5/runtime/start.sh`
- `bundle_specs/dictionary.app.v1.4.2/runtime/Dockerfile`
- `bundle_specs/dictionary.app.v1.4.2/runtime/start.sh`
- rebuilt `dist/*.tgz`

## Recommended replacement steps on Raspberry Pi

```bash
cd ~
mv raspi_homelab_python_framework raspi_homelab_python_framework_old_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
unzip raspi_homelab_python_framework_v3_1_stable_logs_fixed.zip -d ~
cd ~/raspi_homelab_python_framework_v3_1_stable_logs_fixed
python3 bootstrap.py
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env
homelabctl build-all-bundles --env-file .env
```

## Recommended clean reinstall for Dictionary

```bash
sudo rm -rf /mnt/nas/homelab/runtime/dictionary
sudo rm -rf /mnt/nas/homelab/apps/dictionary
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env
```

## Where detailed logs are stored

After each install attempt:

```bash
/mnt/nas/homelab/logs/installs/
```

Examples:

```bash
/mnt/nas/homelab/logs/installs/dictionary_20260329_123456.log
/mnt/nas/homelab/logs/installs/personal-library_20260329_124500.log
```

## How to inspect latest Dictionary log

```bash
ls -1t /mnt/nas/homelab/logs/installs/dictionary_*.log | head -n 1
cat "$(ls -1t /mnt/nas/homelab/logs/installs/dictionary_*.log | head -n 1)"
```

## What the Control Center will now show
- install status badge
- last failure message if an app failed
- **View Log** button for each app with saved logs
- latest operation output block

