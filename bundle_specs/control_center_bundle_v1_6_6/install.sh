#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/install.log"

# Keep output visible to Control Center while also persisting locally.
exec > >(tee -a "$LOG_FILE") 2>&1

printf '[INFO] Starting Control Center OTA installer wrapper\n'

find "$SCRIPT_DIR/scripts" -type f -name '*.sh' -exec sed -i 's/\r$//' {} +
find "$SCRIPT_DIR/scripts" -type f -name '*.sh' -exec chmod +x {} +
chmod +x "$SCRIPT_DIR/install.sh"

SCRIPT="$SCRIPT_DIR/scripts/rebuild_control_center_v1_6_4.sh"
if [[ ! -f "$SCRIPT" ]]; then
  printf '[ERROR] Missing rebuild script: %s\n' "$SCRIPT"
  exit 1
fi

sudo bash "$SCRIPT"
