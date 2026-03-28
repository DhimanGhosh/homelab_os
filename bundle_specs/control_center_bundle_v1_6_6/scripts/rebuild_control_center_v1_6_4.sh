#!/usr/bin/env bash
set -Eeuo pipefail
BASE="/mnt/nas/homelab/control-center"
APP_DIR="$BASE/app"
VENV_DIR="$BASE/venv"
DATA_DIR="$BASE/data"
LOG_DIR="$BASE/logs"
INSTALLERS_DIR="/mnt/nas/homelab/installers"
APPS_DIR="/mnt/nas/homelab/apps"
FQDN="${TAILSCALE_FQDN:-pi-nas.taild4713b.ts.net}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CADDY_CERT_DIR="/etc/caddy/certs/tailscale"
CADDYFILE_PATH="/etc/caddy/Caddyfile"

printf "[INFO] Installing Control Center v1.6.4\n"
CURRENT_DOCKER_ROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
printf "[INFO] Keeping Docker data root unchanged at %s during this upgrade\n" "$CURRENT_DOCKER_ROOT"
sudo mkdir -p /mnt/nas/homelab/docker /mnt/nas/homelab/runtime /mnt/nas/homelab/installers /mnt/nas/homelab/apps || true
sudo mkdir -p "$APP_DIR" "$DATA_DIR" "$LOG_DIR" "$INSTALLERS_DIR" "$APPS_DIR" /etc/caddy/apps "$CADDY_CERT_DIR" /var/lib/caddy/.config/caddy /var/lib/caddy/.local/share/caddy
sudo cp -r "$ROOT_DIR/app/." "$APP_DIR/"
echo "1.6.4" | sudo tee "$BASE/VERSION" >/dev/null
sudo chown -R pi:pi /mnt/nas/homelab 2>/dev/null || true
sudo chown -R caddy:caddy /etc/caddy /var/lib/caddy 2>/dev/null || true
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
sudo tailscale cert --cert-file "$CADDY_CERT_DIR/${FQDN}.crt" --key-file "$CADDY_CERT_DIR/${FQDN}.key" "$FQDN"

sudo tee "$CADDYFILE_PATH" >/dev/null <<EOF2
{
  auto_https off
}

https://${FQDN}:8444 {
  tls ${CADDY_CERT_DIR}/${FQDN}.crt ${CADDY_CERT_DIR}/${FQDN}.key
  encode gzip
  reverse_proxy 127.0.0.1:9000
}

import /etc/caddy/apps/*.caddy
EOF2

sudo cp "$ROOT_DIR/systemd/pi-control-center.service" /etc/systemd/system/pi-control-center.service
sudo systemctl daemon-reload
sudo systemctl enable pi-control-center >/dev/null 2>&1 || true
sudo caddy fmt --overwrite "$CADDYFILE_PATH" >/dev/null 2>&1 || true
sudo caddy validate --config "$CADDYFILE_PATH"
sudo systemctl restart caddy

printf "[INFO] Scheduling Control Center service restart\n"
sudo bash -lc 'nohup bash -lc "sleep 3; systemctl daemon-reload; systemctl restart pi-control-center" >/dev/null 2>&1 &'

printf "[INFO] Control Center v1.6.4 installed on https://%s:8444\n" "$FQDN"
printf "[INFO] Control Center service will restart automatically in a few seconds\n"
