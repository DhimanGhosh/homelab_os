#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="/mnt/nas/homelab/apps/home-assistant"
rm -rf "${APP_DIR}"
echo "[INFO] HA uninstalled"
