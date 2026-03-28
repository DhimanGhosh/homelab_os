#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FQDN="${TAILSCALE_FQDN:-pi-nas.taild4713b.ts.net}"
CC_PORT="${CC_PORT:-8444}"
PIHOLE_PORT="${PIHOLE_PORT:-8447}"
PIHOLE_LOCAL="${PIHOLE_LOCAL:-127.0.0.1:8080}"
CC_LOCAL="${CC_LOCAL:-127.0.0.1:9000}"
PIHOLE_PASSWORD="${PIHOLE_PASSWORD:-admin}"
APP_DIR="/mnt/nas/homelab/apps/pihole"
LOG_DIR="${APP_DIR}/logs"
LOG_FILE="${LOG_DIR}/install.log"
SNIPPET_FILE="/etc/caddy/apps/pihole.caddy"

log(){
  local msg="[$(date '+%F %T')] $*"
  echo "$msg"
  if [[ -d "$LOG_DIR" ]]; then
    printf '%s\n' "$msg" >> "$LOG_FILE" 2>/dev/null || true
  fi
}

ensure_dirs() {
  sudo mkdir -p /etc/caddy/apps /etc/caddy/apps.disabled /etc/caddy/certs/tailscale /var/lib/caddy/.config/caddy /var/lib/caddy/.local/share/caddy "$APP_DIR" "$LOG_DIR" /mnt/nas/homelab/runtime /mnt/nas/homelab/installers
  sudo chown -R caddy:caddy /etc/caddy /var/lib/caddy 2>/dev/null || true
  sudo chown -R pi:pi /mnt/nas/homelab 2>/dev/null || true
  sudo touch "$LOG_FILE" 2>/dev/null || true
  sudo chown pi:pi "$LOG_FILE" 2>/dev/null || true
}


ensure_tailscale() {
  if ! sudo systemctl is-active --quiet tailscaled; then
    log "Starting tailscaled"
    sudo systemctl restart tailscaled
  fi
  if ! tailscale status >/dev/null 2>&1; then
    log "tailscale status failed; make sure the node is logged in"
    exit 1
  fi
}

ensure_certs() {
  if [[ ! -f "/etc/caddy/certs/tailscale/${FQDN}.crt" || ! -f "/etc/caddy/certs/tailscale/${FQDN}.key" ]]; then
    log "Generating Tailscale certificate for ${FQDN}"
    sudo tailscale cert --cert-file "/etc/caddy/certs/tailscale/${FQDN}.crt" --key-file "/etc/caddy/certs/tailscale/${FQDN}.key" "${FQDN}"
  fi
  sudo chown -R caddy:caddy /etc/caddy /var/lib/caddy 2>/dev/null || true
  sudo chmod 600 "/etc/caddy/certs/tailscale/${FQDN}.key"
}

ensure_cloudflared() {
  if ! sudo docker ps --format '{{.Names}}' | grep -qx 'cloudflared'; then
    log "Starting cloudflared DNS proxy"
    sudo docker rm -f cloudflared >/dev/null 2>&1 || true
    sudo docker run -d       --name cloudflared       --restart unless-stopped       --network host       cloudflare/cloudflared:latest       proxy-dns --address 127.0.0.1 --port 5053       --upstream https://1.1.1.1/dns-query       --upstream https://1.0.0.1/dns-query >/dev/null
    sleep 3
  fi
}

recreate_pihole() {
  log "Recreating Pi-hole with HTTPS recovery wiring"
  sudo docker rm -f pihole >/dev/null 2>&1 || true
  sudo docker run -d     --name pihole     --restart=unless-stopped     -p 53:53/tcp     -p 53:53/udp     -p 8080:80     -e TZ=Asia/Kolkata     -e WEBPASSWORD="${PIHOLE_PASSWORD}"     pihole/pihole:latest >/dev/null
  sleep 12
}

ensure_pihole_container() {
  if ! sudo docker ps --format '{{.Names}}' | grep -qx 'pihole'; then
    recreate_pihole
  fi
  if ! curl -fsS --max-time 15 "http://${PIHOLE_LOCAL}/admin/" >/dev/null 2>&1; then
    log "Local Pi-hole admin is not healthy on http://${PIHOLE_LOCAL}/admin/"
    recreate_pihole
  fi
  curl -fsS --max-time 20 "http://${PIHOLE_LOCAL}/admin/" >/dev/null 2>&1 || { log "Pi-hole UI is not healthy after recovery"; sudo docker logs --tail 120 pihole || true; exit 1; }
  log "Setting Pi-hole password"
  sudo docker exec pihole pihole setpassword "${PIHOLE_PASSWORD}" >/dev/null 2>&1 || true
}

write_caddy_snippet() {
  log "Writing Pi-hole Caddy snippet using the same HTTPS recovery routing"
  cat <<EOC | sudo tee "$SNIPPET_FILE" >/dev/null
https://${FQDN}:${PIHOLE_PORT} {
    tls /etc/caddy/certs/tailscale/${FQDN}.crt /etc/caddy/certs/tailscale/${FQDN}.key
    reverse_proxy ${PIHOLE_LOCAL}
}
EOC
  sudo caddy fmt --overwrite "$SNIPPET_FILE" >/dev/null 2>&1 || true
  sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null
  sudo systemctl restart caddy
  log "Caddy restarted"
}

write_state() {
  sudo cp "$ROOT/metadata.json" "$APP_DIR/metadata.json"
  sudo cp "$ROOT/uninstall.sh" "$APP_DIR/uninstall.sh"
  python3 - <<STATE | sudo tee "$APP_DIR/install_state.json" >/dev/null
import json
print(json.dumps({
  'id':'pihole',
  'name':'Pi-hole',
  'installed_version':'1.2.4',
  'version':'1.2.4',
  'port':8447,
  'open_path':'/admin/',
  'health_url':'http://127.0.0.1:8080/admin/',
  'local_upstream':'http://127.0.0.1:8080',
  'recovery_mode':'reset_caddy_and_pihole_bundle compatible'
}, indent=2))
STATE
  sudo chmod +x "$APP_DIR/uninstall.sh"
  sudo chown -R pi:pi "$APP_DIR" 2>/dev/null || true
}

main() {
  ensure_dirs
  ensure_tailscale
  ensure_certs
  ensure_cloudflared
  ensure_pihole_container
  write_caddy_snippet
  write_state
  echo "[OK] Pi-hole 1.2.4 installed at https://${FQDN}:${PIHOLE_PORT}/admin/"
}
main "$@"
