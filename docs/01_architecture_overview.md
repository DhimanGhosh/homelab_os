
# Architecture Overview

Homelab OS is organized around a small core and installable plugins.

## Core

`core/` contains:
- app bootstrap
- CLI
- plugin manager
- services
- APIs
- models
- shared shell assets

## Plugins

`plugins/` contains one folder per plugin. Each plugin should expose:
- `plugin.json`
- `backend/`
- `frontend/`
- `docker/`
- `assets/`
- `migrations/`
- lifecycle hooks: `install.py`, `uninstall.py`, `upgrade.py`

## Runtime

`runtime/` contains operational state that is not source code:
- `installed_plugins/`
- `marketplace_cache/`
- `jobs/`
- `logs/`
- `backups/`
