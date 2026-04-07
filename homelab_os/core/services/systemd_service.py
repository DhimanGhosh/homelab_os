from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from homelab_os.core.config import Settings


class CoreServiceManager:
    SERVICE_NAME = "homelab-os-core.service"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def service_unit_text(self) -> str:
        repo_root = Path.cwd()
        venv_python = repo_root / ".venv" / "bin" / "python"
        return f"""[Unit]
Description=Homelab OS Core
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory={repo_root}
Environment=PYTHONUNBUFFERED=1
ExecStart={venv_python} -m uvicorn homelab_os.core.app:app --host {self.settings.control_center_bind} --port {self.settings.control_center_port}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""

    def install_service(self) -> None:
        unit_text = self.service_unit_text()
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write(unit_text)
            tmp_path = Path(tmp.name)

        subprocess.run(["sudo", "mkdir", "-p", "/etc/systemd/system"], check=True)
        subprocess.run(["sudo", "cp", str(tmp_path), f"/etc/systemd/system/{self.SERVICE_NAME}"], check=True)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        tmp_path.unlink(missing_ok=True)

    def enable_and_start(self) -> None:
        subprocess.run(["sudo", "systemctl", "enable", self.SERVICE_NAME], check=True)
        subprocess.run(["sudo", "systemctl", "restart", self.SERVICE_NAME], check=True)

    def stop_and_disable(self) -> None:
        subprocess.run(["sudo", "systemctl", "stop", self.SERVICE_NAME], check=False)
        subprocess.run(["sudo", "systemctl", "disable", self.SERVICE_NAME], check=False)

    def status(self) -> str:
        result = subprocess.run(
            ["systemctl", "is-active", self.SERVICE_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or "unknown"
