#!/usr/bin/env bash
set -Eeuo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_ID="nextcloud"
APP_DIR="/mnt/nas/homelab/apps/${APP_ID}"
mkdir -p "${APP_DIR}/scripts"
cp "${APP_ROOT}/metadata.json" "${APP_DIR}/metadata.json"
cat > "${APP_DIR}/app_info.json" <<EOF
{
  "id": "nextcloud",
  "name": "Nextcloud",
  "installed_version": "1.0.0",
  "version": "1.0.0",
  "port": 8448,
  "open_path": "/"
}
EOF
cp "${APP_ROOT}/scripts/uninstall.sh" "${APP_DIR}/scripts/uninstall.sh"
chmod +x "${APP_DIR}/scripts/uninstall.sh"
echo "[INFO] Nextcloud bundle installed into Control Center metadata registry"
