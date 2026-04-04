
from dataclasses import dataclass

@dataclass
class Event:
    event: str
    plugin_id: str
    timestamp: str
    payload: dict
