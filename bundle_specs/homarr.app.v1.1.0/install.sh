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
  sudo rsync -a --delete "$ROOT/runtime/" "$RUNTIME_DIR/"
else
  sudo rm -rf "$RUNTIME_DIR"/*
  sudo cp -a "$ROOT/runtime/." "$RUNTIME_DIR/"
fi
cd "$RUNTIME_DIR"
if [[ -f "$RUNTIME_DIR/init.sh" ]]; then
  sudo chmod +x "$RUNTIME_DIR/init.sh" || true
  sudo bash "$RUNTIME_DIR/init.sh"
fi
sudo docker compose up -d --build
ok=0
for _ in $(seq 1 300); do
  if curl -kfsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then ok=1; break; fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "Local service health check failed: $HEALTH_URL" >&2
  sudo docker compose logs --tail=200 || true
  exit 1
fi
cat > /tmp/${APP_ID}.caddy <<EOCADDY
https://${FQDN}:${PORT} {
  tls /etc/caddy/certs/tailscale/${FQDN}.crt /etc/caddy/certs/tailscale/${FQDN}.key
  encode gzip
  reverse_proxy ${LOCAL_UPSTREAM#http://} {
    header_up X-Forwarded-Proto https
    header_up Host {host}
    header_up X-Forwarded-For {remote_host}
  }
}
EOCADDY
sudo mv /tmp/${APP_ID}.caddy "$SNIPPET_FILE"
sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy
sudo cp "$ROOT/metadata.json" "$APP_DIR/metadata.json"
sudo cp "$ROOT/uninstall.sh" "$APP_DIR/uninstall.sh"
python3 - <<STATE | sudo tee "$APP_DIR/install_state.json" >/dev/null
import json
print(json.dumps({
  'id': ${APP_ID@Q},
  'name': ${NAME@Q},
  'installed_version': ${VERSION@Q},
  'version': ${VERSION@Q},
  'port': int(${PORT}),
  'open_path': ${OPEN_PATH@Q},
  'health_url': ${HEALTH_URL@Q},
  'local_upstream': ${LOCAL_UPSTREAM@Q},
}, indent=2))
STATE
sudo chmod +x "$APP_DIR/uninstall.sh"
sudo chown -R pi:pi "$APP_DIR" "$RUNTIME_DIR" 2>/dev/null || true

echo "[OK] ${NAME} ${VERSION} installed at https://${FQDN}:${PORT}${OPEN_PATH}"
