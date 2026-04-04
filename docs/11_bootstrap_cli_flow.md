# Bootstrap + CLI + Plugin Flow

## Recommended operator flow

```bash
cd ~/homelab_os
python3 bootstrap.py
source .venv/bin/activate
homelabctl build-all-plugins --env-file .env
```

## What changed

The repo now uses plugin-oriented naming internally, but the operator flow remains intentionally simple.

## Legacy compatibility aliases

These commands are still supported:

```bash
homelabctl build-all-bundles --env-file .env
homelabctl install-bundle --bundle build/music_player.tgz --env-file .env
homelabctl remove-app --app-id music-player --env-file .env
homelabctl run-control-center --env-file .env
```

## Why `.env` is included directly

You asked to avoid an unnecessary `.env.example`-only workflow. The repo now ships with `.env` directly, while `.env.example` remains as a reference copy.
