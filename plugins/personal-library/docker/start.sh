#!/bin/sh
set -e
mkdir -p /opt/personal-library/data
chmod 777 /opt/personal-library/data || true
python -m uvicorn app.main:app --host 0.0.0.0 --port 8132
