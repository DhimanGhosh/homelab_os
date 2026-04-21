from __future__ import annotations

import subprocess
from pathlib import Path


class ProcessRunner:
    def run(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = True,
        capture_output: bool = True,
        text: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=check,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
        )

    def popen(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        stdout=None,
        stderr=None,
    ) -> subprocess.Popen:
        return subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=stdout,
            stderr=stderr,
        )
