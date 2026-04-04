
from dataclasses import dataclass

@dataclass
class Job:
    id: str
    app_id: str
    status: str
    message: str = ''
    progress: int = 0
