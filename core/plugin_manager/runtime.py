import shutil
import time
from datetime import datetime
from pathlib import Path

import requests

from core.services.health import docker_is_healthy
from core.services.recovery import recover_stack
from core.services.storage import record_install_state
from core.services.process_runner import CommandError, run, sudo_write_file


def _append_log(log_path: Path | None, message: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    if not log_path:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _run_logged(command, *, cwd: Path | None = None, check: bool = True, capture: bool = True, log_path: Path | None = None, env: dict | None = None):
    env_note = ""
    if env:
        pairs = [f"{k}={v}" for k, v in sorted(env.items())]
        env_note = f" env={' '.join(pairs)}"
    _append_log(log_path, f"RUN {' '.join(map(str, command))}" + (f" (cwd={cwd})" if cwd else "") + env_note)

    def _stream_to_log(line: str):
        if not log_path:
            return
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line if line.endswith("\n") else line + "\n")

    try:
        result = run(command, cwd=cwd, check=check, capture=capture, env=env, live=True, line_callback=_stream_to_log)
    except CommandError as exc:
        if exc.stderr:
            _append_log(log_path, f"STDERR:{exc.stderr}")
        raise
    else:
        if capture and result.stderr:
            _append_log(log_path, f"STDERR:{result.stderr}")
        return result


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


def wait_health(url: str, timeout: int = 60, log_path: Path | None = None) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url, timeout=5, verify=False)
            _append_log(log_path, f"HEALTH {url} -> {response.status_code}")
            if response.status_code < 500:
                return True
        except Exception as exc:
            _append_log(log_path, f"HEALTH {url} -> exception: {exc}")
        time.sleep(1)
    return False


def _safe_backups_dir(settings) -> Path:
    return getattr(settings, "backups_dir", settings.homelab_root / "backups")


def _stage_plugin_runtime(extracted: Path, runtime_dst: Path, log_path: Path | None = None) -> Path:
    docker_src = extracted / "docker"
    backend_src = extracted / "backend"
    frontend_src = extracted / "frontend"

    if runtime_dst.exists():
        shutil.rmtree(runtime_dst, ignore_errors=True)
    runtime_dst.mkdir(parents=True, exist_ok=True)

    if docker_src.exists():
        for item in docker_src.iterdir():
            dst = runtime_dst / item.name
            if item.is_dir():
                shutil.copytree(item, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst)

    if backend_src.exists():
        # Flatten backend artifacts into runtime root because most Dockerfiles expect app.py/requirements.txt/app/... at context root.
        for name in ["app.py", "requirements.txt", "config.json", "start.sh"]:
            src = backend_src / name
            if src.exists():
                shutil.copy2(src, runtime_dst / name)
        for name in ["app", "static", "templates"]:
            src = backend_src / name
            if src.exists():
                shutil.copytree(src, runtime_dst / name, dirs_exist_ok=True)

    if frontend_src.exists():
        for name in ["static", "templates"]:
            src = frontend_src / name
            if src.exists():
                shutil.copytree(src, runtime_dst / name, dirs_exist_ok=True)
        # keep raw frontend folder too for plugins that reference it directly
        shutil.copytree(frontend_src, runtime_dst / "frontend", dirs_exist_ok=True)

    # ensure executable bits survive for start scripts
    for script_name in ["start.sh"]:
        script_path = runtime_dst / script_name
        if script_path.exists():
            script_path.chmod(0o755)

    compose_dst = runtime_dst / "docker-compose.yml"
    if not compose_dst.exists():
        raise RuntimeError(f"docker-compose.yml missing after runtime staging: {compose_dst}")
    return compose_dst


def _docker_compose_build(settings, compose_dst: Path, log_path: Path | None = None):
    _run_logged(["sudo", "docker", "compose", "-f", str(compose_dst), "build", "--pull"], log_path=log_path)


def generic_docker_install(settings, extracted: Path, meta: dict, extra_dirs: list[str] | None = None):
    log_path = Path(meta.get("_log_path")) if meta.get("_log_path") else None
    _append_log(log_path, f"Starting install for {meta.get('id')} version={meta.get('version')}")
    if not docker_is_healthy():
        recover_stack(settings)
        raise RuntimeError("Docker unstable — recovery triggered. Retry install after recovery.")

    runtime_dst = settings.runtime_dir / meta["id"]
    backup_dst = _safe_backups_dir(settings) / f"{meta['id']}.runtime.prev"
    extra_dirs = extra_dirs or []

    _run_logged([
        "sudo", "mkdir", "-p",
        str(settings.runtime_dir / "installed_plugins"),
        str(settings.runtime_dir),
        str(_safe_backups_dir(settings)),
        str(settings.caddy_apps_dir),
        str(settings.tailscale_cert_dir),
        str(getattr(settings, 'logs_dir', settings.homelab_root / 'logs')),
    ], log_path=log_path)

    if backup_dst.exists():
        shutil.rmtree(backup_dst, ignore_errors=True)
    if runtime_dst.exists():
        shutil.move(str(runtime_dst), str(backup_dst))
        _append_log(log_path, f"Moved previous runtime to backup: {backup_dst}")

    compose_dst = _stage_plugin_runtime(extracted, runtime_dst, log_path=log_path)
    (runtime_dst / "data").mkdir(parents=True, exist_ok=True)
    for rel in extra_dirs:
        (runtime_dst / rel).mkdir(parents=True, exist_ok=True)

    _run_logged(["sudo", "docker", "compose", "-f", str(compose_dst), "pull"], check=False, log_path=log_path)
    _docker_compose_build(settings, compose_dst, log_path=log_path)
    try:
        _run_logged(["sudo", "docker", "compose", "-f", str(compose_dst), "up", "-d"], log_path=log_path)
    except CommandError:
        _run_logged(["sudo", "docker", "compose", "-f", str(compose_dst), "logs", "--no-color", "--tail=200"], check=False, log_path=log_path)
        raise

    write_caddy_snippet(settings, meta)
    _run_logged(["sudo", "caddy", "validate", "--config", str(settings.caddyfile)], log_path=log_path)
    _run_logged(["sudo", "systemctl", "restart", "caddy"], log_path=log_path)

    if meta.get("health_url") and not wait_health(str(meta["health_url"]), timeout=int(meta.get("health_timeout", 60)), log_path=log_path):
        _run_logged(["sudo", "docker", "compose", "-f", str(compose_dst), "logs", "--no-color", "--tail=200"], check=False, log_path=log_path)
        raise RuntimeError(f"Health check failed for {meta['id']} at {meta['health_url']}")

    record_install_state(settings.runtime_dir / "installed_plugins", meta["id"], meta, extracted, runtime_dst, str(log_path) if log_path else None)
    return {
        "ok": True,
        "message": f"Installed {meta['name']} -> https://{settings.tailscale_fqdn}:{meta['port']}{meta.get('open_path', '/')}",
        "log_path": str(log_path) if log_path else None,
    }


def generic_docker_uninstall(settings, extracted: Path, meta: dict):
    runtime_dst = settings.runtime_dir / meta["id"]
    compose_dst = runtime_dst / "docker-compose.yml"
    if compose_dst.exists():
        run(["sudo", "docker", "compose", "-f", str(compose_dst), "down", "--remove-orphans"], check=False)
    snippet = settings.caddy_apps_dir / f"{meta['id']}.caddy"
    if snippet.exists():
        run(["sudo", "rm", "-f", str(snippet)])
    run(["sudo", "caddy", "validate", "--config", str(settings.caddyfile)], check=False)
    run(["sudo", "systemctl", "restart", "caddy"], check=False)
    return {"ok": True, "message": f"Removed {meta['name']}"}
