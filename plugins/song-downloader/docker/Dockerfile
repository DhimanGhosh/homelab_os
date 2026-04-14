FROM nandyalu/python-ffmpeg:latest
WORKDIR /app
COPY . /app

RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    'PY_BIN=""' \
    'if command -v python3 >/dev/null 2>&1; then PY_BIN="$(command -v python3)"; fi' \
    'if [ -z "$PY_BIN" ] && command -v python >/dev/null 2>&1; then PY_BIN="$(command -v python)"; fi' \
    'if [ -z "$PY_BIN" ] && [ -x /usr/local/bin/python ]; then PY_BIN="/usr/local/bin/python"; fi' \
    'if [ -z "$PY_BIN" ]; then echo "No Python interpreter found in container PATH" >&2; exit 127; fi' \
    'exec "$PY_BIN" -u /app/app.py' \
    > /usr/local/bin/start-song-downloader && chmod +x /usr/local/bin/start-song-downloader

CMD ["/usr/local/bin/start-song-downloader"]
