#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
read_json(){ python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$ROOT/metadata.json" "$1"; }
APP_ID="$(read_json id)"
RUNTIME_DIR="/mnt/nas/homelab/runtime/${APP_ID}"
APP_DIR="/mnt/nas/homelab/apps/${APP_ID}"
SNIPPET_FILE="/etc/caddy/apps/${APP_ID}.caddy"
if [[ -f "$RUNTIME_DIR/docker-compose.yml" ]]; then
  cd "$RUNTIME_DIR"
  sudo docker compose down --remove-orphans || true
fi
sudo rm -f "$SNIPPET_FILE"
sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy
sudo rm -rf "$RUNTIME_DIR" "$APP_DIR"
echo "[OK] ${APP_ID} removed"
