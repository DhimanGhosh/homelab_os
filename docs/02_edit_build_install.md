# Edit -> Build -> Install

## Build one app
```bash
source .venv/bin/activate
homelabctl build-bundle --source-dir bundle_specs/dictionary.app.v1.4.5 --output-path dist/dictionary.app.v1.4.5.tgz
```

## Build all apps
```bash
source .venv/bin/activate
homelabctl build-all-bundles --env-file .env
```

## Install from CLI
```bash
source .venv/bin/activate
homelabctl install-bundle --bundle dist/dictionary.app.v1.4.5.tgz --env-file .env
```

## Install from UI
Upload the same `.tgz` into the Control Center.
