#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
read_json(){ python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$ROOT/metadata.json" "$1"; }
APP_ID="$(read_json id)"
NAME="$(read_json name)"
VERSION="$(read_json version)"
PORT="$(read_json port)"
OPEN_PATH="$(read_json open_path)"
HEALTH_URL="$(read_json health_url)"
DESCRIPTION="$(read_json description)"
LOCAL_UPSTREAM="$(read_json local_upstream)"
FQDN="${TAILSCALE_FQDN:-pi-nas.taild4713b.ts.net}"
CERT_DIR="/etc/caddy/certs/tailscale"
CERT_FILE="${CERT_DIR}/${FQDN}.crt"
KEY_FILE="${CERT_DIR}/${FQDN}.key"
APP_DIR="/mnt/nas/homelab/apps/${APP_ID}"
RUNTIME_DIR="/mnt/nas/homelab/runtime/${APP_ID}"
SNIPPET_FILE="/etc/caddy/apps/${APP_ID}.caddy"

sudo mkdir -p "$APP_DIR" "$RUNTIME_DIR" /etc/caddy/apps "$CERT_DIR"
if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
  sudo tailscale cert --cert-file "$CERT_FILE" --key-file "$KEY_FILE" "$FQDN"
fi
if command -v rsync >/dev/null 2>&1; then
  sudo rsync -a --delete --exclude '.git' --exclude '__pycache__' "$ROOT/runtime/" "$RUNTIME_DIR/"
else
  sudo rm -rf "$RUNTIME_DIR"/*
  sudo cp -a "$ROOT/runtime/." "$RUNTIME_DIR/"
fi
sudo mkdir -p /mnt/nas/Incoming /mnt/nas/media/music /mnt/nas/media/videos/Movies "$RUNTIME_DIR/database" "$RUNTIME_DIR/config"
sudo chown -R 1000:1000 /mnt/nas/Incoming /mnt/nas/media /mnt/nas/homelab "$RUNTIME_DIR/database" "$RUNTIME_DIR/config" 2>/dev/null || true
sudo chmod -R 775 /mnt/nas/Incoming /mnt/nas/media "$RUNTIME_DIR/database" "$RUNTIME_DIR/config" 2>/dev/null || true

cd "$RUNTIME_DIR"
sudo docker compose up -d --build
ok=0
for _ in $(seq 1 120); do
  if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "Local service health check failed: $HEALTH_URL" >&2
  sudo docker compose logs --tail=120 || true
  exit 1
fi

if command -v inotifywait >/dev/null 2>&1; then
  sudo install -m 0755 "$ROOT/runtime/media_ingest_watch.sh" /usr/local/bin/media_ingest_watch.sh
  sudo install -m 0644 "$ROOT/runtime/media-ingest.service" /etc/systemd/system/media-ingest.service
  sudo systemctl daemon-reload
  sudo systemctl enable media-ingest.service >/dev/null 2>&1 || true
  sudo systemctl restart media-ingest.service
fi

cat > /tmp/${APP_ID}.caddy <<EOC
https://${FQDN}:${PORT} {
  tls ${CERT_FILE} ${KEY_FILE}
  encode gzip
  reverse_proxy ${LOCAL_UPSTREAM#http://}
}
EOC
sudo mv /tmp/${APP_ID}.caddy "$SNIPPET_FILE"
sudo cp "$ROOT/metadata.json" "$APP_DIR/metadata.json"
sudo cp "$ROOT/uninstall.sh" "$APP_DIR/uninstall.sh"
cat > /tmp/${APP_ID}.install_state.json <<STATE
{
  "id": "$APP_ID",
  "name": "$NAME",
  "installed_version": "$VERSION",
  "version": "$VERSION",
  "port": $PORT,
  "open_path": "$OPEN_PATH",
  "health_url": "$HEALTH_URL",
  "local_upstream": "$LOCAL_UPSTREAM",
  "description": "$DESCRIPTION"
}
STATE
sudo mv /tmp/${APP_ID}.install_state.json "$APP_DIR/install_state.json"
sudo chmod +x "$APP_DIR/uninstall.sh"
sudo chown -R pi:pi "$APP_DIR" "$RUNTIME_DIR" 2>/dev/null || true
sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy

echo "[OK] ${NAME} ${VERSION} installed at https://${FQDN}:${PORT}${OPEN_PATH}"
