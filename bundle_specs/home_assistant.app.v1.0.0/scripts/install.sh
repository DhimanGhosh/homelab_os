#!/usr/bin/env bash
set -Eeuo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APP_ID="home-assistant"
APP_DIR="/mnt/nas/homelab/apps/${APP_ID}"
mkdir -p "${APP_DIR}/scripts"
cp "${APP_ROOT}/metadata.json" "${APP_DIR}/metadata.json"
cat > "${APP_DIR}/app_info.json" <<EOF
{
  "id": "home-assistant",
  "name": "HA",
  "installed_version": "1.0.0",
  "version": "1.0.0",
  "port": 8450,
  "open_path": "/"
}
EOF
cp "${APP_ROOT}/scripts/uninstall.sh" "${APP_DIR}/scripts/uninstall.sh"
chmod +x "${APP_DIR}/scripts/uninstall.sh"
echo "[INFO] HA bundle installed into Control Center metadata registry"
