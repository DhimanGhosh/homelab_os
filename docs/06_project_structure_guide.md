# Full Project Structure Guide

This document explains the main folders and files in `raspi_homelab_python_framework`, what each one is for, and when you should edit it.

## Top-level layout

```text
raspi_homelab_python_framework/
├── .env.example
├── README.md
├── bootstrap.py
├── pyproject.toml
├── bundle_specs/
├── dist/
├── docs/
├── homelab_platform/
└── reference_uploads/
```

---

## Top-level files

### `.env.example`
Template environment file.

Use it as the base for your real `.env`.

Controls values such as:
- hostname
- LAN IP
- Tailscale IP
- FQDN
- mount paths
- control center port
- Caddy dirs
- timezone
- Pi-hole password

### `README.md`
High-level entry document for the whole project.

Read this first when onboarding someone new.

### `bootstrap.py`
Python helper script that:
- creates `.venv`
- installs the project editable
- copies `.env.example` to `.env` if missing

Use this before running `homelabctl` on a fresh clone.

### `pyproject.toml`
Python package configuration.

Important because it:
- defines project metadata
- declares dependencies
- installs `homelabctl`

---

## `homelab_platform/`
This is the framework code.

```text
homelab_platform/
├── __init__.py
├── cli.py
├── config.py
├── web.py
├── services/
├── static/
└── templates/
```

### `homelab_platform/cli.py`
Defines all `homelabctl` commands.

Edit this when you want to:
- add a new CLI command
- change CLI options
- change how commands connect to services

### `homelab_platform/config.py`
Loads `.env` values into a `Settings` object.

Edit this when you want to:
- add a new config variable
- change default values
- expose more paths/ports to bundles

### `bundle_specs/control-center.app.v1.7.0/payload/app/control_center_app/web.py`
Flask Control Center backend.

Handles:
- rendering the main UI
- scanning uploaded bundles
- uploading bundle files
- installing bundles from UI
- uninstalling apps from UI
- building app card state

Edit this when you want to:
- change dashboard behavior
- add new API routes
- change version detection
- change open URL logic

### `homelab_platform/static/`
CSS, JS, images, client-side assets for Control Center.

### `homelab_platform/templates/`
Jinja templates for Flask pages.

Usually the main dashboard template lives here.

---

## `homelab_platform/services/`
Service layer for the framework.

### `bootstrap.py`
Machine/bootstrap logic.

Does:
- apt installs
- creates host folders
- writes base Caddyfile
- installs systemd service

### `bundle_builder.py`
Builds `.tgz` bundle archives from source folders.

### `bundle_installer.py`
Core bundle install/uninstall dispatcher.

This is the main bridge between:
- CLI or UI request
- bundle extraction
- bundle metadata loading
- Python bundle execution

### `bundle_runtime.py`
Shared helper functions used by bundle installers.

Contains helpers such as:
- `generic_docker_install(...)`
- `generic_docker_uninstall(...)`
- `write_caddy_snippet(...)`
- `ensure_tailscale_cert(...)`
- `record_install_state(...)`
- `wait_health(...)`

Edit this when you want to change common install behavior for many apps.

### `subprocesses.py`
Command execution helpers.

Used for:
- `run(...)`
- file writes with sudo
- port checks

If system command behavior needs hardening, this is one of the first places to inspect.

---

## `bundle_specs/`
This is the most important folder for app maintenance.

Every installable bundle has a source folder here.

Example:

```text
bundle_specs/
├── control_center_bundle_v1_6_4/
├── control_center_bundle_v1_6_6/
├── dictionary.app.v1.4.5/
├── pihole.app.v1.2.4/
├── navidrome.app.v1.3.3/
├── jellyfin.app.v1.3.0/
└── ...
```

For each bundle folder, you usually find some combination of:

```text
metadata.json
bundle.py
runtime/
Dockerfile
docker-compose.yml
app/
static/
requirements.txt
install.py
uninstall.py
```

### What each bundle folder is for
A bundle folder is the source-of-truth for that OTA package.

You edit here, then rebuild into `dist/`.

### Typical file meanings inside one bundle

#### `metadata.json`
Defines app identity and install/runtime metadata.

Common values include:
- `id`
- `name`
- `version`
- `port`
- `open_path`
- `local_upstream`
- `health_url`

#### `bundle.py`
Python entrypoint for bundle install/uninstall.

Usually defines:

```python
def install(settings, extracted, meta):
    ...

def uninstall(settings, extracted, meta):
    ...
```

#### `runtime/`
Files copied into the live runtime folder, commonly:
- `docker-compose.yml`
- Docker build context
- app runtime files

#### `app/`
Application source code, if the app is custom Python/Flask/FastAPI.

#### `static/`
Static assets used by that app.

#### `Dockerfile`
Container build instructions.

#### `requirements.txt`
Python dependencies for the app container.

---

## `dist/`
Built output bundles.

This is what you upload into Control Center or install by CLI.

Example:

```text
dist/dictionary.app.v1.4.5.tgz
dist/pihole.app.v1.2.4.tgz
dist/control_center_bundle_v1_6_6.tgz
```

Rule of thumb:
- edit in `bundle_specs/`
- build into `dist/`
- install from `dist/`

---

## `docs/`
Project documentation folder.

In your current repo it already contains:
- `01_structure.md`
- `02_edit_build_install.md`
- `03_control_center_upgrade.md`

This new documentation pack extends that.

---

## `reference_uploads/`
Reference inputs you originally provided.

These are not the live framework code. They are source references for migration and comparison.

Current examples include:
- original Control Center bundle
- original `APPS.zip`
- HTTPS recovery bundle

Use this folder when you want to compare old behavior against the new Python implementation.

---

## Live runtime folders after installation

The framework also writes to machine paths during real installs.

### `/mnt/nas/homelab/installers`
Uploaded bundle files stored by Control Center.

### `/mnt/nas/homelab/apps/<app-id>`
Per-app installed state.

Common files:
- `metadata.json`
- `install_state.json`
- `bundle/` copied installer source

### `/mnt/nas/homelab/runtime/<app-id>`
Live runtime folder, often used for Docker compose.

### `/etc/caddy/apps`
Per-app Caddy snippets.

### `/etc/caddy/certs/tailscale`
Tailscale certificate files used by Caddy.

---

## Where should you edit what?

### Change CC UI
Edit:
- `bundle_specs/control-center.app.v1.7.0/payload/app/control_center_app/web.py`
- `homelab_platform/templates/`
- `homelab_platform/static/`

### Change one app’s install logic
Edit:
- `bundle_specs/<app>/bundle.py`
- and possibly `runtime/`, `Dockerfile`, `docker-compose.yml`

### Change common Docker install behavior for many apps
Edit:
- `homelab_platform/services/bundle_runtime.py`

### Change CLI behavior
Edit:
- `homelab_platform/cli.py`

### Change config variables or defaults
Edit:
- `homelab_platform/config.py`
- `.env.example`

### Change system bootstrap logic
Edit:
- `homelab_platform/services/bootstrap.py`

---

## Short mental model

```text
bundle_specs/    = source code for OTA bundles
build-bundle     = pack source into .tgz
dist/            = generated installable bundles
web.py           = UI upload/install entrypoint
bundle_installer = chooses Python bundle and runs it
bundle.py        = per-app install/uninstall logic
runtime/         = live Docker/app files copied for running
```
