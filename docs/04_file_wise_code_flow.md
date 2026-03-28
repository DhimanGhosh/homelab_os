# File-wise Code Flow and Bundle Execution Guide

This document explains how the framework runs, file by file, and answers the key question:

> Inside `bundle_specs/<app>/bundle.py` I see:
>
> ```python
> def install(settings, extracted, meta):
>     return generic_docker_install(settings, extracted, meta)
> ```
>
> Who calls this? What values are passed? Where do those values come from?

That is exactly what this document explains.

---

## Big picture flow

There are two main entry paths:

### Path A: UI upload/install
1. User uploads a `.tgz` in the Control Center
2. Flask saves it into `settings.installers_dir`
3. User clicks install in UI
4. Flask calls `BundleInstaller(settings).install(...)`
5. `BundleInstaller` extracts the bundle and loads `metadata.json`
6. `BundleInstaller` dynamically imports `bundle.py`
7. `BundleInstaller` calls `install(settings, extracted, meta)`
8. `bundle.py` either does custom logic or calls `generic_docker_install(...)`
9. Common runtime helpers create runtime dirs, run Docker compose, write Caddy config, record install state

### Path B: CLI install
1. User runs `homelabctl install-bundle --bundle ... --env-file .env`
2. CLI loads `Settings`
3. CLI calls `BundleInstaller(settings).install(bundle_path)`
4. Then the same install path as above continues

So UI and CLI converge at the same installer service.

---

## Step-by-step file flow

## 1. `homelab_py/cli.py`
This is the CLI entrypoint.

Example command:

```bash
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env
```

Relevant code path:

```python
settings = Settings.from_env_file(env_file)
BundleInstaller(settings).install(Path(bundle))
```

### What values are created here?
- `env_file` comes from the CLI option
- `settings` comes from `Settings.from_env_file(...)`
- `bundle` comes from the CLI option path

So by the time `BundleInstaller.install(...)` is called, it already has:
- all environment settings
- the bundle file location

---

## 2. `homelab_py/web.py`
This is the Flask Control Center.

### Upload route

```python
@app.post('/api/upload')
```

This route:
- receives uploaded files from browser
- saves them into `settings.installers_dir`

### Install route

```python
@app.post('/api/install')
```

This route does:

```python
result = BundleInstaller(settings).install(settings.installers_dir / data['bundle_filename'])
```

### Where does `settings` come from here?
At module import time:

```python
ENV_FILE = os.environ.get('HOMELAB_ENV_FILE', '.env')
settings = Settings.from_env_file(ENV_FILE)
```

So the web app loads settings once from the env file pointed to by `HOMELAB_ENV_FILE`.

---

## 3. `homelab_py/config.py`
This is where `Settings` values come from.

### Flow

```python
Settings.from_env_file('.env')
```

calls:

```python
load_env(path)
```

which:
- reads key-value lines from `.env`
- merges environment variables
- returns a dictionary

Then `Settings.from_env_file(...)` converts those values into a structured `Settings` dataclass.

### Examples of values created here
- `settings.hostname`
- `settings.tailscale_fqdn`
- `settings.apps_dir`
- `settings.runtime_dir`
- `settings.caddy_snippets_dir`
- `settings.control_center_port`

These are then passed into bundle installers.

---

## 4. `homelab_py/services/bundle_installer.py`
This is the main dispatcher.

### Method: `install(bundle_path)`
This is the core install flow.

#### Step 1: normalize path
```python
bundle_path = Path(bundle_path)
```

#### Step 2: extract bundle
```python
extracted = self.extract_bundle(bundle_path)
```

### What is `extracted`?
It is a temporary folder path where the bundle was unpacked.

For example:

```text
/tmp/homelab_bundle_xxxxx/dictionary.app.v1.4.5/
```

#### Step 3: load metadata
```python
meta = self.load_metadata(extracted)
```

### What is `meta`?
A Python dict loaded from:

```text
<bundle root>/metadata.json
```

Typical contents:

```json
{
  "id": "dictionary",
  "name": "Dictionary",
  "version": "1.4.5",
  "port": 8455,
  "open_path": "/",
  "local_upstream": "http://127.0.0.1:18055",
  "health_url": "http://127.0.0.1:18055/"
}
```

#### Step 4: choose install mode
If `bundle.py` exists:

```python
return self._run_python_bundle(extracted, meta, 'install')
```

This is the line that leads to your `bundle.py install(...)` function.

---

## 5. `BundleInstaller._run_python_bundle(...)`
This is the answer to your main question.

### What it does

```python
spec = importlib.util.spec_from_file_location('bundle_module', extracted / 'bundle.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
fn = getattr(module, func_name)
return fn(self.settings, extracted, meta)
```

### Who calls `bundle.py install(...)`?
`BundleInstaller._run_python_bundle(...)`

### What arguments are passed?
Exactly these three values:

#### 1. `settings`
Type: `Settings`

Source:
- created earlier by CLI or Flask using `.env`

Contains:
- paths
- hostname
- FQDN
- Caddy paths
- NAS mount settings
- Docker root info
- timezone
- Pi-hole password

#### 2. `extracted`
Type: `Path`

Source:
- created by extracting the `.tgz`

Points to the unpacked bundle source directory.

#### 3. `meta`
Type: `dict`

Source:
- loaded from `metadata.json`

Contains app-specific metadata for installation.

So this function call:

```python
def install(settings, extracted, meta):
    return generic_docker_install(settings, extracted, meta)
```

means:
- `settings` = machine and framework config
- `extracted` = unpacked bundle folder
- `meta` = app metadata from JSON

---

## 6. `bundle_specs/<app>/bundle.py`
This file defines the per-app install behavior.

### Minimal generic bundle

```python
from homelab_py.services.bundle_runtime import generic_docker_install, generic_docker_uninstall

def install(settings, extracted, meta):
    return generic_docker_install(settings, extracted, meta)

def uninstall(settings, extracted, meta):
    return generic_docker_uninstall(settings, extracted, meta)
```

### What this means
The app is using the framework’s shared install logic.

That shared logic assumes:
- the bundle contains a `runtime/` folder
- Docker compose files are in that runtime folder
- metadata describes port/upstream/health
- Caddy reverse proxy is enough for HTTPS access

### When you would not use the generic version
Use custom logic if an app needs special behavior, for example:
- Pi-hole-specific DNS + cloudflared setup
- Control Center self-update staging and restart flow
- complex volume migrations
- one-off permissions logic
- health checks different from normal HTTP reachability

---

## 7. `homelab_py/services/bundle_runtime.py`
This is the shared install engine used by many bundle.py files.

### Function: `generic_docker_install(settings, extracted, meta, extra_dirs=None)`

This is the main common implementation.

#### Step 1: determine source and destination
```python
runtime_src = extracted / 'runtime'
runtime_dst = settings.runtime_dir / meta['id']
```

So if `meta['id'] == 'dictionary'`, then:
- source is inside the extracted bundle
- destination is something like `/mnt/nas/homelab/runtime/dictionary`

#### Step 2: create required folders
It creates app/runtime/Caddy folders using sudo.

#### Step 3: replace old runtime
If runtime already exists, it deletes and recreates it.

#### Step 4: copy runtime files
```python
sudo cp -a <bundle runtime>/. <live runtime>
```

#### Step 5: create any extra dirs
If `extra_dirs` is passed, it creates those too.

#### Step 6: start Docker compose
```python
sudo docker compose up -d --build
```
run in the live runtime directory.

#### Step 7: optional health check
If `meta['health_url']` exists, it repeatedly curls that URL until success or timeout.

#### Step 8: write Caddy reverse-proxy snippet
Uses:
- app port from `meta['port']`
- upstream from `meta['local_upstream']`
- FQDN from `settings.tailscale_fqdn`

#### Step 9: record install state
Writes files under:

```text
/mnt/nas/homelab/apps/<app-id>/
```

including:
- `metadata.json`
- `install_state.json`
- `bundle/` copy of extracted installer source

#### Step 10: return UI/CLI message
The function returns a dict like:

```python
{
  'ok': True,
  'message': 'Installed Dictionary -> https://pi-nas.taild4713b.ts.net:8455/'
}
```

---

## 8. `record_install_state(...)`
Why is this important?

Because uninstall later depends on the stored app copy.

When install completes, the framework stores:
- original metadata
- install state
- a copied `bundle/` folder under the app directory

That lets uninstall later do:
- find the installed bundle code
- call the corresponding `uninstall(...)`

---

## 9. Uninstall flow
When you run:

```bash
homelabctl remove-app --app-id dictionary --env-file .env
```

or click uninstall in UI:

- installer looks inside `settings.apps_dir / app_id`
- reads the stored metadata
- checks whether stored `bundle/bundle.py` exists
- imports that stored bundle.py
- calls `uninstall(settings, extracted, meta)`

So uninstall also uses the same three-argument pattern.

---

## 10. Control Center code flow
Control Center is special because it is both:
- an app
- the tool that installs other apps

### Runtime serving path
If running from systemd:
- systemd executes `python -m homelab_py.web`
- Flask app starts via Waitress
- UI becomes available on port 8444

### OTA path
When a Control Center OTA bundle is installed:
- its `bundle.py` or custom install logic stages files
- updates runtime/app files
- updates version markers
- restarts the service safely

This is different from generic apps, which normally just use `generic_docker_install(...)`.

---

## 11. Where to debug each kind of problem

### Problem: wrong app URLs in UI
Check:
- `homelab_py/web.py`
- `KNOWN_APPS`
- `.env`

### Problem: wrong app install path
Check:
- `metadata.json`
- `bundle.py`
- `bundle_runtime.py`

### Problem: Docker build/runtime failure
Check:
- `bundle_specs/<app>/runtime/`
- `Dockerfile`
- `docker-compose.yml`
- app logs

### Problem: HTTPS/Caddy issue
Check:
- `bundle_runtime.py`
- `/etc/caddy/apps/<app-id>.caddy`
- tailscale cert paths

### Problem: bundle not detected in UI
Check:
- bundle filename pattern in `web.py`
- file saved into `settings.installers_dir`

---

## One complete example: Dictionary install from UI

### Step A: upload
Browser uploads:

```text
dictionary.app.v1.4.5.tgz
```

Flask saves it into:

```text
/mnt/nas/homelab/installers/dictionary.app.v1.4.5.tgz
```

### Step B: click install
UI sends POST to `/api/install` with:

```json
{ "bundle_filename": "dictionary.app.v1.4.5.tgz" }
```

### Step C: Flask route
`web.py` runs:

```python
BundleInstaller(settings).install(settings.installers_dir / data['bundle_filename'])
```

### Step D: installer extracts
BundleInstaller creates temp extraction folder and unpacks the archive.

### Step E: metadata loaded
Reads `metadata.json` into `meta`.

### Step F: bundle.py imported
Installer dynamically imports:

```text
<temp>/dictionary.app.v1.4.5/bundle.py
```

### Step G: install called
Installer calls:

```python
install(settings, extracted, meta)
```

### Step H: generic install runs
If `bundle.py` returns:

```python
generic_docker_install(settings, extracted, meta)
```

then the shared runtime helper:
- copies `runtime/`
- runs Docker compose
- health checks local URL
- writes Caddy config
- records state

### Step I: result returned
The return dict bubbles back up to Flask and then back to the UI.

---

## Short summary

### Who calls `bundle.py install(settings, extracted, meta)`?
`BundleInstaller._run_python_bundle(...)`

### Where does `settings` come from?
From `.env`, loaded through `Settings.from_env_file(...)`

### Where does `extracted` come from?
From temporary extraction of the uploaded or CLI-supplied bundle file

### Where does `meta` come from?
From `metadata.json` inside the extracted bundle

### Why do many apps just call `generic_docker_install(...)`?
Because the framework centralizes common Docker + Caddy + install-state behavior there

### When should you override that?
When the app needs custom installation logic
