# Homelab OS

Plugin-based Raspberry Pi homelab control platform.

## Status

This repo includes:

- bootstrap flow
- Python packaging
- CLI foundation
- config loading
- FastAPI core app foundation
- runtime directory initialization

---

## Quick start

```bash
cd ~/homelab_os
python3 bootstrap.py
source .venv/bin/activate
sudo systemctl restart homelab-os-core.service
homelabctl build-all-plugins --env-file .env
```

---

## What each command does

### Full project bootstrap

```bash
python3 bootstrap.py
```

This:
- installs or refreshes the project in `.venv`
- runs host bootstrap logic internally

---

### Host bootstrap only

```bash
homelabctl bootstrap-host --env-file .env
```

Use this only when:
- you want to rerun host/bootstrap logic
- you do NOT want to reinstall the project into the virtual environment

---

### Reload the Control Center (core changes only)

```bash
cd ~/homelab_os
python3 bootstrap.py
source .venv/bin/activate
sudo systemctl restart homelab-os-core.service
```

---

## Build plugin archives

```bash
cd ~/homelab_os
source .venv/bin/activate
homelabctl build-all-plugins --env-file .env
```

This creates versioned plugin archives such as:

- build/music-player.v7.1.2.tgz
- build/song-downloader.v1.0.1.tgz

---

## Install and start a plugin

```bash
homelabctl install-plugin build/<plugin-name>.v<version>.tgz --env-file .env
homelabctl start-plugin <plugin-id> --env-file .env
```

Example:

```bash
homelabctl install-plugin build/music-player.v7.1.2.tgz --env-file .env
homelabctl start-plugin music-player --env-file .env
```

---

## When plugin code changes

For plugin container/UI/backend changes:

```bash
cd ~/homelab_os
python3 bootstrap.py
source .venv/bin/activate

homelabctl build-all-plugins --env-file .env
sudo systemctl restart homelab-os-core.service

homelabctl uninstall-plugin <plugin-id> --env-file .env
homelabctl install-plugin build/<plugin>.v<version>.tgz --env-file .env
homelabctl start-plugin <plugin-id> --env-file .env
```

---

## Rule of thumb

- Core changes (Control Center, backend, routing):
  ```bash
  python3 bootstrap.py
  source .venv/bin/activate
  sudo systemctl restart homelab-os-core.service
  ```

- Plugin changes:
  ```bash
  homelabctl build-all-plugins --env-file .env
  homelabctl install-plugin build/<plugin>.v<version>.tgz --env-file .env
  homelabctl start-plugin <plugin-id> --env-file .env
  ```

---

## Notes

- Plugin archives are versioned. Multiple versions can coexist.
- Control Center will show update buttons when newer versions are available.
- Some plugins (like Song Downloader) may use internal APIs (e.g., Media Downloader) with fallback mechanisms.
