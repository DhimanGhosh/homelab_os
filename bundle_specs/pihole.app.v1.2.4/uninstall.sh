#!/usr/bin/env bash
set -Eeuo pipefail
sudo rm -f /etc/caddy/apps/pihole.caddy
sudo caddy validate --config /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy || sudo systemctl restart caddy
sudo rm -rf /mnt/nas/homelab/apps/pihole
echo "[OK] pihole HTTPS snippet removed"
