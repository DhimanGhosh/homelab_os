#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p ./appdata
if [[ ! -f ./.env ]]; then echo "SECRET_ENCRYPTION_KEY=$(openssl rand -hex 32)" > ./.env; fi
