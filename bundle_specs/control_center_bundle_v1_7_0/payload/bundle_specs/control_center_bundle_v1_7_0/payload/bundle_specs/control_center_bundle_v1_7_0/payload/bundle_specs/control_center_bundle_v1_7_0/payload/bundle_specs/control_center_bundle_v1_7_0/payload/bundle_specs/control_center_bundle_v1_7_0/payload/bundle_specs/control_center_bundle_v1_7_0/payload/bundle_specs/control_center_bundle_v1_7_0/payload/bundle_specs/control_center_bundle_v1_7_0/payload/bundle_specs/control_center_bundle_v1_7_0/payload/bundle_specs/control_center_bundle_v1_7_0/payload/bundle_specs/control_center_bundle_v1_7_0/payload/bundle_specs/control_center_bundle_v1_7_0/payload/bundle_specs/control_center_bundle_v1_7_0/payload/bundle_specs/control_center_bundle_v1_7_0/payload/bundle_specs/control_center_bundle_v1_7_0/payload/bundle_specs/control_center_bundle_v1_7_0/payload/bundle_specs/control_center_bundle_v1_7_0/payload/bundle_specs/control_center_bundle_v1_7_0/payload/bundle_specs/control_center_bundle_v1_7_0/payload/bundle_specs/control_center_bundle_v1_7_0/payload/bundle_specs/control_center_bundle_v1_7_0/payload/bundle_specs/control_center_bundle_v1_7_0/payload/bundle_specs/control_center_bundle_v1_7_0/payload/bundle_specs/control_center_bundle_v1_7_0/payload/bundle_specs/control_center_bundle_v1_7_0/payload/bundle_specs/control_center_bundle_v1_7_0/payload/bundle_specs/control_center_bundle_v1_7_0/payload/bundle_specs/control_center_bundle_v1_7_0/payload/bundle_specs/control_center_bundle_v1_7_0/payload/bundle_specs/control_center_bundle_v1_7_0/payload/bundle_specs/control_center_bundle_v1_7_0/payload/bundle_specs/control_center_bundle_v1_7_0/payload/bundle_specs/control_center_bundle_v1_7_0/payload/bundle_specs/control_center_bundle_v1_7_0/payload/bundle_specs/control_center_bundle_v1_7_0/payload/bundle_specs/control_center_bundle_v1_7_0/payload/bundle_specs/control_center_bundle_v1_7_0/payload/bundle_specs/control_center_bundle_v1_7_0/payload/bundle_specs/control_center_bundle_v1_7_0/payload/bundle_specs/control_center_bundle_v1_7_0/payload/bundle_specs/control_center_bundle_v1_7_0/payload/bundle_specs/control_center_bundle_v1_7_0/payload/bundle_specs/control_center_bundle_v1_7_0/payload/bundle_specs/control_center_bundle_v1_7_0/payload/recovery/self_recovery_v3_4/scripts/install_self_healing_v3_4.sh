#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sudo install -Dm755 "$ROOT/scripts/recover_homelab_network.sh" /usr/local/bin/homelab-recover
sudo install -Dm755 "$ROOT/scripts/homelab_self_heal_v3_4.sh" /usr/local/bin/homelab-self-heal-v3_4
sudo install -Dm644 "$ROOT/systemd/homelab-self-heal-v3_4.service" /etc/systemd/system/homelab-self-heal-v3_4.service
sudo install -Dm644 "$ROOT/systemd/homelab-self-heal-v3_4.timer" /etc/systemd/system/homelab-self-heal-v3_4.timer
sudo systemctl daemon-reload
sudo systemctl enable homelab-self-heal-v3_4.timer
sudo systemctl restart homelab-self-heal-v3_4.timer
echo "Installed self-healing v3.4"
