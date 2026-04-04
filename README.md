# Homelab OS

A plugin-based Raspberry Pi homelab control OS with a simple operator-friendly bootstrap flow.

## Quick start

This repo intentionally restores the simple workflow you were using earlier.

```bash
cd ~/homelab_os
python3 bootstrap.py
source .venv/bin/activate
homelabctl build-all-plugins --env-file .env
```

### Old command compatibility

The CLI also keeps the legacy-style aliases so the following still work:

```bash
homelabctl bootstrap-host --env-file .env
homelabctl build-all-bundles --env-file .env
homelabctl install-bundle --bundle build/music_player.tgz --env-file .env
homelabctl remove-app --app-id music-player --env-file .env
homelabctl run-control-center --env-file .env
```

## What `bootstrap.py` now does

Running `python3 bootstrap.py` will:

1. create `.venv` if missing
2. install the project into that virtual environment
3. create `.env` if missing
4. run `homelabctl bootstrap-host --env-file .env`

That means it still has the operator-friendly behavior you wanted:
- venv creation
- package install
- `.env` creation
- host bootstrap
- Caddy / Docker / watchdog setup through the CLI bootstrap service

### Optional flags

```bash
python3 bootstrap.py --skip-host
python3 bootstrap.py --build-all
```

## Main commands

```bash
homelabctl show-settings --env-file .env
homelabctl list-plugins --env-file .env
homelabctl build-all-plugins --env-file .env
homelabctl install-plugin --plugin-archive build/music_player.tgz --env-file .env
homelabctl remove-plugin --plugin-id music-player --env-file .env
homelabctl run-control-shell --env-file .env
homelabctl health-check --env-file .env
homelabctl recover-stack --env-file .env
```

## Repo layout

```text
homelab_os/
├── bootstrap.py
├── .env
├── core/
├── plugins/
├── runtime/
├── manifests/
├── docs/
├── tests/
├── systemd/
└── recovery/
```

## Why both old and new command names exist

The repository was restructured into a plugin-based OS model, but the CLI keeps several legacy command aliases so your daily operator flow stays simple and familiar.

## Notes

- `.env` is included directly so you can edit it immediately.
- `.env.example` is also kept as a reference copy.
- `build-all-bundles` now maps to `build-all-plugins`.
- `install-bundle` now maps to `install-plugin`.


## Current operator flow

```bash
cd ~/homelab_os
python3 bootstrap.py
source .venv/bin/activate
homelabctl build-all-plugins --env-file .env
```

This repo uses the plugin layout under `plugins/` and the builder/runtime now stages plugin `backend/`, `frontend/`, and `docker/` content into runnable archives and runtime directories.
