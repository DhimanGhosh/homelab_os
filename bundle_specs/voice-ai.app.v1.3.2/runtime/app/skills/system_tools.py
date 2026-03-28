from __future__ import annotations

import os
import subprocess
from typing import Any, Dict


def _run(cmd: list[str]) -> str:
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    return out.strip()


def system_status() -> Dict[str, Any]:
    temp = ""
    try:
        temp = _run(["vcgencmd", "measure_temp"])
    except Exception:
        temp = "n/a"

    uptime = _run(["uptime", "-p"])
    loadavg = _run(["cat", "/proc/loadavg"])
    mem = _run(["free", "-h"])

    # Disk: always show root, and also show NAS mount if present (common: /mnt/nas).
    disk_root = _run(["df", "-h", "/"])
    disk_nas = ""
    for p in ("/mnt/nas", "/mnt/raid1", "/srv/nas", "/mnt/storage"):
        try:
            if os.path.ismount(p):
                disk_nas = _run(["df", "-h", p])
                break
        except Exception:
            continue

    return {
        "title": "System Status",
        "temp": temp,
        "uptime": uptime,
        "loadavg": loadavg,
        "memory": mem,
        "disk_root": disk_root,
        "disk_nas": disk_nas,
    }


def disk_usage() -> Dict[str, Any]:
    return {
        "title": "Disk Usage",
        "df_h": _run(["df", "-h"]),
    }


def pihole_status() -> Dict[str, Any]:
    # Prefer `pihole` CLI if installed
    try:
        status = _run(["pihole", "status"])
        return {"title": "Pi-hole Status", "status": status}
    except Exception:
        return {"title": "Pi-hole Status", "status": "pihole CLI not found"}


def disable_pihole(minutes: int = 5) -> Dict[str, Any]:
    minutes = int(max(1, min(minutes, 120)))
    try:
        out = _run(["pihole", "disable", f"{minutes}m"])
        return {"title": "Pi-hole", "disabled_for_minutes": minutes, "output": out}
    except Exception as e:
        return {"title": "Pi-hole", "error": str(e)}


def restart_service(service_name: str) -> Dict[str, Any]:
    # IMPORTANT: requires sudoers entry or running under root service account.
    try:
        out = _run(["sudo", "systemctl", "restart", service_name])
        return {"title": "Service Restart", "service": service_name, "output": out}
    except Exception as e:
        return {"title": "Service Restart", "service": service_name, "error": str(e)}


def restart_media_ingest() -> Dict[str, Any]:
    return restart_service("media-ingest")
