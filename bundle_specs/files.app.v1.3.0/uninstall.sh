#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
read_json(){ python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$ROOT/metadata.json" "$1"; }
APP_ID="$(read_json id)"
APP_DIR="/mnt/nas/homelab/apps/${APP_ID}"
RUNTIME_DIR="/mnt/nas/homelab/runtime/${APP_ID}"
SNIPPET_FILE="/etc/caddy/apps/${APP_ID}.caddy"
if [[ -d "$RUNTIME_DIR" && -f "$RUNTIME_DIR/docker-compose.yml" ]]; then
  cd "$RUNTIME_DIR"
  sudo docker compose down --remove-orphans -v || true
fi
if [[ -f /etc/systemd/system/media-ingest.service ]]; then
  sudo systemctl stop media-ingest.service || true
  sudo systemctl disable media-ingest.service || true
  sudo rm -f /etc/systemd/system/media-ingest.service /usr/local/bin/media_ingest_watch.sh
  sudo systemctl daemon-reload || true
fi
sudo rm -f "$SNIPPET_FILE"
sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy
sudo rm -rf "$APP_DIR" "$RUNTIME_DIR"
