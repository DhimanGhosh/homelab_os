#!/usr/bin/env bash
set -euo pipefail
INCOMING="/mnt/nas/Incoming"
VIDEO_MOVIES_DIR="/mnt/nas/media/videos/Movies"
MUSIC_DIR="/mnt/nas/media/music"
mkdir -p "$INCOMING" "$VIDEO_MOVIES_DIR" "$MUSIC_DIR"
chown -R 1000:1000 "$INCOMING" "$VIDEO_MOVIES_DIR" "$MUSIC_DIR" 2>/dev/null || true
chmod -R 775 "$INCOMING" "$VIDEO_MOVIES_DIR" "$MUSIC_DIR" 2>/dev/null || true
log(){ printf '[Ingest] %s %s
' "$(date '+%F %T')" "$*"; }
is_stable(){ local f="$1"; [[ -f "$f" ]] || return 1; local s1 s2; s1=$(stat -c '%s' "$f" 2>/dev/null || echo 0); sleep 2; s2=$(stat -c '%s' "$f" 2>/dev/null || echo 0); [[ "$s1" -eq "$s2" ]]; }
dest_for(){ local f="$1" lower; lower="$(basename "$f" | tr '[:upper:]' '[:lower:]')"; case "$lower" in *.mp4|*.mkv|*.avi|*.mov|*.webm|*.m4v) echo "$VIDEO_MOVIES_DIR";; *.mp3|*.flac|*.wav|*.m4a|*.aac|*.ogg) echo "$MUSIC_DIR";; *) echo "";; esac; }
ingest_one(){ local path="$1"; [[ -f "$path" ]] || return 0; local dest_dir base dest; dest_dir="$(dest_for "$path")"; [[ -n "$dest_dir" ]] || return 0; is_stable "$path" || return 0; base="$(basename "$path")"; dest="$dest_dir/$base"; if [[ -e "$dest" ]]; then local ts; ts="$(date '+%Y%m%d_%H%M%S')"; dest="$dest_dir/${base%.*}.${ts}.${base##*.}"; fi; mv -f -- "$path" "$dest"; chown 1000:1000 "$dest" 2>/dev/null || true; chmod 664 "$dest" 2>/dev/null || true; log "MOVED: $path -> $dest"; }
process_existing(){ shopt -s nullglob; local f; for f in "$INCOMING"/*; do ingest_one "$f" || true; done; }
if command -v inotifywait >/dev/null 2>&1; then
  process_existing || true
  inotifywait -m -q -e close_write,moved_to,create,attrib --format '%w%f' "$INCOMING" | while read -r p; do ingest_one "$p" || true; done
else
  while true; do process_existing || true; sleep 30; done
fi
