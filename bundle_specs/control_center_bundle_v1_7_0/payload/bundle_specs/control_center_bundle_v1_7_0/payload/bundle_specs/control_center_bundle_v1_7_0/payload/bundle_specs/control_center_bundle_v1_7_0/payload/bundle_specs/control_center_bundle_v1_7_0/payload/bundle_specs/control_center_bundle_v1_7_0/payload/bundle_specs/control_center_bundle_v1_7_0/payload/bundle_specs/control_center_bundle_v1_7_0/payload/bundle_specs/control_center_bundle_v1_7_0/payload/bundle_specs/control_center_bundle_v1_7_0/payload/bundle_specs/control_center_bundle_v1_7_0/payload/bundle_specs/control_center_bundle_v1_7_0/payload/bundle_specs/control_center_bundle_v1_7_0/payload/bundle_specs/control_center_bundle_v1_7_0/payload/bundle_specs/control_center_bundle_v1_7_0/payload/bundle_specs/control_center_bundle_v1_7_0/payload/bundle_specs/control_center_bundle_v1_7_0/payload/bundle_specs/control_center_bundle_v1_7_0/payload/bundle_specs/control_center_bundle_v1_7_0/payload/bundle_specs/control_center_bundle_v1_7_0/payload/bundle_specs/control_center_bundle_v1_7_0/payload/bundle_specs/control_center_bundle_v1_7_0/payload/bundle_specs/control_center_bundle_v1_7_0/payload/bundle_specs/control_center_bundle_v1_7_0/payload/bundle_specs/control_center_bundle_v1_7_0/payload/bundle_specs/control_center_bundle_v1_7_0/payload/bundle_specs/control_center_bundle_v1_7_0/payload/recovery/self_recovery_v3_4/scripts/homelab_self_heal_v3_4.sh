#!/usr/bin/env bash
set -Eeuo pipefail
LOG_FILE="/var/log/homelab-self-heal-v3.4.log"
echo "Watchdog timer trigger" | tee -a "$LOG_FILE"
/usr/local/bin/homelab-recover >> "$LOG_FILE" 2>&1 || true
