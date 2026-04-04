
from dataclasses import asdict
from pathlib import Path
import json
from core.models.event import Event

class EventBus:
    def __init__(self, log_path: Path):
        self.log_path = log_path

    def emit(self, event: Event) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(asdict(event)) + '
')
