# Quickstart

## Fresh machine bootstrap

```bash
python3 bootstrap.py
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env
```

## Main URLs

- Control Center: `https://pi-nas.taild4713b.ts.net:8444/`
- Pi-hole: `https://pi-nas.taild4713b.ts.net:8447/admin/`

## Build and install

```bash
homelabctl build-all-bundles --env-file .env
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env
```
