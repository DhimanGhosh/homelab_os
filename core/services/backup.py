
import tarfile
from pathlib import Path
from datetime import datetime

def create_snapshot(source_root: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target = backups_dir / f'homelab_snapshot_{stamp}.tar.gz'
    with tarfile.open(target, 'w:gz') as tf:
        tf.add(source_root, arcname=source_root.name)
    return target
