
# Build, Install, Runtime

## Build

```bash
homelabctl build-all-plugins --env-file .env
```

Build output is written to `build/`.

## Install

```bash
homelabctl install-plugin --plugin-archive build/music_player.tgz --env-file .env
```

## Runtime

Installed plugin state is kept under `runtime/installed_plugins/`.
Logs go under `runtime/logs/`.
Backups go under `runtime/backups/`.
