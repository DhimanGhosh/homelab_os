#!/usr/bin/env bash
set -Eeuo pipefail
APP_DIR="/mnt/nas/homelab/apps/nextcloud"
rm -rf "${APP_DIR}"
echo "[INFO] Nextcloud uninstalled"
