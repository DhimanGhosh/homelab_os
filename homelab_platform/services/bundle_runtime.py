import shutil
import time
from pathlib import Path

import requests

from homelab_platform.services.health import docker_is_healthy
from homelab_platform.services.recovery import recover_stack
from homelab_platform.services.state import record_install_state
from homelab_platform.services.subprocesses import run, sudo_write_file


def write_caddy_snippet(settings, meta: dict) -> Path:
    upstream = str(meta["local_upstream"]).replace("http://", "").replace("https://", "")
    content = f"""https://{settings.tailscale_fqdn}:{int(meta['port'])} {{
    tls {settings.tailscale_cert_dir / (settings.tailscale_fqdn + '.crt')} {settings.tailscale_cert_dir / (settings.tailscale_fqdn + '.key')}
    encode gzip
    reverse_proxy {upstream} {{
        header_up X-Forwarded-Proto https
        header_up Host {{host}}
        header_up X-Forwarded-For {{remote_host}}
    }}
}}
"""
    path = settings.caddy_apps_dir / f"{meta['id']}.caddy"
    sudo_write_file(path, content)
    return path


def wait_health(url: str, timeout: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url, timeout=5, verify=False)
            if response.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _safe_backups_dir(settings) -> Path:
    return getattr(settings, "backups_dir", settings.homelab_root / "backups")


def generic_docker_install(settings, extracted: Path, meta: dict):
    if not docker_is_healthy():
        recover_stack(settings)
        raise RuntimeError("Docker unstable — recovery triggered. Retry install after recovery.")

    runtime_src = extracted / "runtime"
    runtime_dst = settings.runtime_dir / meta["id"]
    backup_dst = _safe_backups_dir(settings) / f"{meta['id']}.runtime.prev"

    run([
        "sudo", "mkdir", "-p",
        str(settings.apps_dir),
        str(settings.runtime_dir),
        str(_safe_backups_dir(settings)),
        str(settings.caddy_apps_dir),
        str(settings.tailscale_cert_dir),
    ])

    if not runtime_src.exists() or not runtime_src.is_dir():
        raise RuntimeError(f"Bundle runtime directory missing: {runtime_src}")
    compose_src = runtime_src / "docker-compose.yml"
    if not compose_src.exists():
        raise RuntimeError(f"docker-compose.yml missing in bundle runtime: {compose_src}")

    if backup_dst.exists():
        shutil.rmtree(backup_dst)
    if runtime_dst.exists():
        shutil.move(str(runtime_dst), str(backup_dst))

    shutil.copytree(runtime_src, runtime_dst, dirs_exist_ok=True)
    (runtime_dst / "data").mkdir(parents=True, exist_ok=True)

    compose_dst = runtime_dst / "docker-compose.yml"
    if not compose_dst.exists():
        if runtime_dst.exists():
            shutil.rmtree(runtime_dst, ignore_errors=True)
        if backup_dst.exists():
            shutil.move(str(backup_dst), str(runtime_dst))
        raise RuntimeError(f"docker-compose.yml missing after runtime copy: {compose_dst}")

    run(["sudo", "docker", "compose", "-f", str(compose_dst), "pull"], check=False)
    run(["sudo", "docker", "compose", "-f", str(compose_dst), "build"])
    run(["sudo", "docker", "compose", "-f", str(compose_dst), "up", "-d"])

    write_caddy_snippet(settings, meta)
    run(["sudo", "caddy", "validate", "--config", str(settings.caddyfile)])
    run(["sudo", "systemctl", "restart", "caddy"])

    if meta.get("health_url") and not wait_health(str(meta["health_url"]), timeout=int(meta.get("health_timeout", 60))):
        run(["sudo", "docker", "compose", "-f", str(compose_dst), "logs", "--no-color", "--tail=200"], check=False)
        raise RuntimeError(f"Health check failed for {meta['id']} at {meta['health_url']}")

    record_install_state(settings.apps_dir, meta["id"], meta, extracted, runtime_dst)
    return {
        "ok": True,
        "message": f"Installed {meta['name']} -> https://{settings.tailscale_fqdn}:{meta['port']}{meta.get('open_path', '/')}"
    }


def generic_docker_uninstall(settings, extracted: Path, meta: dict):
    runtime_dst = settings.runtime_dir / meta["id"]
    compose_dst = runtime_dst / "docker-compose.yml"
    if compose_dst.exists():
        run(["sudo", "docker", "compose", "-f", str(compose_dst), "down", "--remove-orphans"], check=False)
    snippet = settings.caddy_apps_dir / f"{meta['id']}.caddy"
    if snippet.exists():
        run(["sudo", "rm", "-f", str(snippet)])
    run(["sudo", "caddy", "validate", "--config", str(settings.caddyfile)])
    run(["sudo", "systemctl", "restart", "caddy"])
    return {"ok": True, "message": f"Removed {meta['name']}"}
