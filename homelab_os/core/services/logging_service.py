from __future__ import annotations

from datetime import datetime
from pathlib import Path


class LoggingService:
    def __init__(self, logs_root: Path) -> None:
        self.logs_root = logs_root
        self.logs_root.mkdir(parents=True, exist_ok=True)

    def job_log_path(self, job_id: str) -> Path:
        return self.logs_root / f"{job_id}.log"

    def append_job_log(self, job_id: str, message: str) -> Path:
        path = self.job_log_path(job_id)
        timestamp = datetime.now().isoformat(timespec="seconds")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
        return path

    def read_job_log(self, job_id: str) -> str:
        path = self.job_log_path(job_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
