# Files 1.3.0

Real Docker app bundle for Pi Control Center.

What changed:
- opens directly to `/files/Incoming/`
- no login prompt
- keeps NAS root at `/mnt/nas`
- installs an automatic media ingest watcher
- audio dropped into `Incoming` moves to `/mnt/nas/media/music`
- video dropped into `Incoming` moves to `/mnt/nas/media/videos/Movies`
