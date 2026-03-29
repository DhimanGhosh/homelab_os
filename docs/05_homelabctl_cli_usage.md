# homelabctl CLI Usage Guide

This guide explains every `homelabctl` command in the current framework, what it does, when to use it, which files it touches, and example usage.

## What `homelabctl` is

`homelabctl` is the Typer-based command line entrypoint defined in:

```text
homelab_platform/cli.py
```

It is installed from `pyproject.toml` as a console script. After bootstrap and editable install, you run it like:

```bash
source .venv/bin/activate
homelabctl --help
```

## Global pattern

Most commands either:

- read settings from `.env`
- operate on `bundle_specs/`
- operate on `dist/`
- operate on live install state under `/mnt/nas/homelab/...`

The common env-file pattern is:

```bash
homelabctl <command> --env-file .env
```

If you omit `--env-file`, the CLI defaults to `.env` in the current working directory.

---

## Command list

### 1. `bootstrap-host`

#### Purpose
Prepares the machine for the framework.

It calls:

- `BootstrapService.install_host_dependencies()`
- `BootstrapService.write_caddy_base()`
- `BootstrapService.install_service()`

Defined in:

```text
homelab_platform/cli.py
homelab_platform/services/bootstrap.py
```

#### What it does
- runs `apt-get update`
- installs packages such as Docker, Caddy, curl, git, Python venv tools
- creates runtime folders
- writes base Caddy config
- installs the systemd service for the Python Control Center
- enables and starts the service

#### Example
```bash
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env
```

#### When to use it
- first machine setup
- after moving the framework to a new Raspberry Pi
- after major service/config recovery

#### Important
This command modifies system state. It is not just a local Python action.

---

### 2. `run-control-center`

#### Purpose
Starts the Flask Control Center app directly in the foreground using Waitress.

Defined in:

```text
homelab_platform/cli.py
bundle_specs/control-center.app.v1.7.0/payload/app/control_center_app/web.py
```

#### What it does
- exports `HOMELAB_ENV_FILE`
- loads `control_center_app` from the Control Center bundle payload
- loads settings from that env file
- starts Waitress on `control_center_bind:control_center_port`

#### Example
```bash
source .venv/bin/activate
homelabctl run-control-center --env-file .env
```

#### What you should expect
- terminal stays busy while the server runs
- if port 8444 is already in use, it exits cleanly with a message

#### Use this when
- testing locally
- developing the UI or backend
- running CC manually outside systemd

#### Do not use this when
- the systemd service is already running on port 8444
- you already have a working production CC instance

---

### 3. `install-bundle`

#### Purpose
Installs one bundle file by CLI.

Defined in:

```text
homelab_platform/cli.py
homelab_platform/services/bundle_installer.py
```

#### Accepted bundle types
The current installer extracts:
- `.tgz`
- `.tar.gz`
- `.zip`

But your preferred workflow is `.tgz`.

#### Example
```bash
source .venv/bin/activate
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env
```

#### What it does internally
1. creates a temp extraction directory
2. extracts the bundle
3. reads `metadata.json`
4. checks whether `bundle.py` exists
5. if `bundle.py` exists, imports it dynamically and calls `install(settings, extracted, meta)`
6. otherwise, if `install.sh` exists, runs the legacy shell installer
7. returns a status message

#### Use this when
- testing a bundle before uploading via UI
- automating installs
- debugging bundle behavior directly

---

### 4. `remove-app`

#### Purpose
Uninstalls an installed app by app id.

Defined in:

```text
homelab_platform/cli.py
homelab_platform/services/bundle_installer.py
```

#### Example
```bash
source .venv/bin/activate
homelabctl remove-app --app-id dictionary --env-file .env
```

#### What it does internally
- finds the installed app folder under `settings.apps_dir / app_id`
- reads stored metadata
- if stored bundle contains `bundle.py`, calls `uninstall(settings, extracted, meta)`
- else if stored bundle contains `uninstall.sh`, runs legacy shell uninstall
- removes app state

#### Use this when
- removing a test app
- validating uninstall behavior
- resetting an app before reinstalling

---

### 5. `build-bundle`

#### Purpose
Builds one `.tgz` bundle from one source directory.

Defined in:

```text
homelab_platform/cli.py
homelab_platform/services/bundle_builder.py
```

#### Example
```bash
source .venv/bin/activate
homelabctl build-bundle \
  --source-dir bundle_specs/dictionary.app.v1.4.5 \
  --output-path dist/dictionary.app.v1.4.5.tgz
```

#### What it does internally
- validates/uses the folder you pass
- creates the output folder if missing
- packs the full source dir into a gzipped tar archive

#### Typical use
You edit files inside `bundle_specs/<bundle-name>/`, then rebuild the `.tgz` from there.

---

### 6. `build-all-bundles`

#### Purpose
Builds all bundle source directories found inside `bundle_specs/`.

Defined in:

```text
homelab_platform/cli.py
```

#### Example
```bash
source .venv/bin/activate
homelabctl build-all-bundles --env-file .env
```

#### What it scans
It loops through:

```text
bundle_specs/*
```

And only builds a folder if it contains:

```text
metadata.json
```

#### Output pattern
Each bundle is written into:

```text
dist/<source-folder-name>.tgz
```

#### Use this when
- making multiple app updates
- preparing a release pack
- regenerating all OTA packages after source edits

---

## Example workflows

### Workflow A: Edit one app and rebuild one OTA bundle
```bash
cd pi_homelab_platformthon_ota_framework_v2_real_bundles
source .venv/bin/activate
nano bundle_specs/dictionary.app.v1.4.5/Dockerfile
homelabctl build-bundle \
  --source-dir bundle_specs/dictionary.app.v1.4.5 \
  --output-path dist/dictionary.app.v1.4.5.tgz
```

Then either:
- upload `dist/dictionary.app.v1.4.5.tgz` to the Control Center
- or install from CLI

```bash
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env
```

### Workflow B: Rebuild all OTA packages
```bash
cd pi_homelab_platformthon_ota_framework_v2_real_bundles
source .venv/bin/activate
homelabctl build-all-bundles --env-file .env
```

### Workflow C: Run local CC for development
```bash
cd pi_homelab_platformthon_ota_framework_v2_real_bundles
source .venv/bin/activate
homelabctl run-control-center --env-file .env
```

### Workflow D: First host setup on a fresh Pi
```bash
cd pi_homelab_platformthon_ota_framework_v2_real_bundles
python3 bootstrap.py
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env
```

---

## Which command should you prefer?

### Use the UI upload when
- you want the same drag-and-drop OTA feel as before
- you are testing the actual end-user install path
- you want to update running apps from CC

### Use the CLI install when
- you want faster debug cycles
- you want better visibility of Python tracebacks
- you are developing bundle logic

### Use `build-bundle` when
- you edited one app

### Use `build-all-bundles` when
- you changed shared code or several apps at once

---

## Troubleshooting map

### `Port 8444 is already in use.`
Meaning:
- the Control Center service is already running

What to do:
- do not start another copy
- use the current UI instead

### `metadata.json` missing
Meaning:
- the bundle source folder is incomplete

What to do:
- add/fix `metadata.json`
- rebuild the bundle

### bundle installs but app does not open
Meaning:
- bundle installer completed, but runtime health/config still failed

What to check:
- `docker ps -a`
- app logs
- `/etc/caddy/apps/<app-id>.caddy`
- live install state under `/mnt/nas/homelab/apps/<app-id>/`

### `install-bundle` works in CLI but not in UI
Meaning:
- UI upload/save/install path may differ from direct CLI path

What to check:
- file is present under `settings.installers_dir`
- Control Center logs
- JSON response from `/api/install`

---

## Short command cheat sheet

```bash
# first setup
python3 bootstrap.py
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env

# run CC manually
homelabctl run-control-center --env-file .env

# build one bundle
homelabctl build-bundle --source-dir bundle_specs/dictionary.app.v1.4.5 --output-path dist/dictionary.app.v1.4.5.tgz

# build all bundles
homelabctl build-all-bundles --env-file .env

# install one bundle by CLI
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env

# remove one app
homelabctl remove-app --app-id dictionary --env-file .env
```
