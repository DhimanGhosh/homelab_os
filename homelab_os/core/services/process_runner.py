from __future__ import annotations

import subprocess
from pathlib import Path


class ProcessRunner:
    def _format_cmd(self, cmd: list[str]) -> str:
        return " ".join(str(part) for part in cmd)

    def _raise_with_output(self, exc: subprocess.CalledProcessError) -> None:
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        parts = [
            f"Command failed with exit code {exc.returncode}: {self._format_cmd(list(exc.cmd))}",
        ]
        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        raise RuntimeError("\n\n".join(parts)) from exc

    def run(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = True,
        capture_output: bool = True,
        text: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                check=check,
                capture_output=capture_output,
                text=text,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as exc:
            self._raise_with_output(exc)

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
