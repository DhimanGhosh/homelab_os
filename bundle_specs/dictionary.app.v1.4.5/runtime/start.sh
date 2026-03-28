#!/bin/sh
set -e
mkdir -p /opt/offline-dictionary/data /opt/offline-dictionary/data/nltk_data
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8133
