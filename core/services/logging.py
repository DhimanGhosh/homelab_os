
from pathlib import Path
from datetime import datetime

def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}
")
