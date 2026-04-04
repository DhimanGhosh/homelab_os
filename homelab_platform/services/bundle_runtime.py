import shutil
import time
from datetime import datetime
from pathlib import Path

import requests

from homelab_platform.services.health import docker_is_healthy
from homelab_platform.services.recovery import recover_stack
from homelab_platform.services.state import record_install_state
from homelab_platform.services.subprocesses import CommandError, run, sudo_write_file


def _append_log(log_path: Path | None, message: str):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    if not log_path:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _run_logged(command, *, cwd: Path | None = None, check: bool = True, capture: bool = True, log_path: Path | None = None, label: str | None = None, env: dict | None = None):
    env_note = ""
    if env:
        pairs = [f"{k}={v}" for k, v in sorted(env.items())]
        env_note = f" env={' '.join(pairs)}"
    _append_log(log_path, f"RUN {' '.join(command)}" + (f" (cwd={cwd})" if cwd else "") + env_note)

    def _stream_to_log(line: str):
        if not log_path:
            return
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line if line.endswith("\n") else line + "\n")

    try:
        result = run(command, cwd=cwd, check=check, capture=capture, env=env, live=True, line_callback=_stream_to_log)
    except CommandError as exc:
        if exc.stdout:
            _append_log(log_path, "COMMAND FAILED AFTER LIVE STREAMING OUTPUT")
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
        time.sleep(2)
    return False


def _should_retry_legacy_builder(exc: CommandError) -> bool:
    text = f"{exc}\n{exc.stdout}\n{exc.stderr}".lower()
    retry_markers = [
        'exec: "/bin/sh": stat /bin/sh: no such file or directory',
        'runc run failed: unable to start container process',
        'failed to solve: process "/bin/sh -c',
        'overlayfs',
    ]
    return any(marker in text for marker in retry_markers)


def _docker_compose_build(settings, compose_dst: Path, log_path: Path | None = None):
    cmd = ["sudo", "docker", "compose", "-f", str(compose_dst), "build"]
    try:
        return _run_logged(cmd, log_path=log_path)
    except CommandError as exc:
        if not _should_retry_legacy_builder(exc):
            raise
        _append_log(log_path, 'BuildKit-style build failed with a known container runtime error; retrying with legacy builder and --no-cache')
        env = dict(__import__('os').environ)
        env['DOCKER_BUILDKIT'] = '0'
        env['COMPOSE_DOCKER_CLI_BUILD'] = '0'
        _run_logged(["sudo", "docker", "builder", "prune", "-af"], check=False, log_path=log_path, env=env)
        return _run_logged(cmd + ["--no-cache"], log_path=log_path, env=env)


def _safe_backups_dir(settings) -> Path:
    return getattr(settings, "backups_dir", settings.homelab_root / "backups")


def _inject_bundle_env(compose_path: Path, meta: dict, log_path: Path | None = None):
    text = compose_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    env_inserted = False
    services_seen = False
    service_indent = None
    for i, line in enumerate(lines):
        out.append(line)
        stripped = line.strip()
        if stripped == 'services:':
            services_seen = True
            continue
        if services_seen and service_indent is None and line.startswith('  ') and stripped.endswith(':'):
            service_indent = '  '
            continue
        if services_seen and stripped == 'environment:' and line.startswith('    '):
            out.append('      APP_NAME: "{}"'.format(str(meta.get('name','')).replace('"','\"')))
            out.append('      APP_VERSION: "{}"'.format(str(meta.get('version','')).replace('"','\"')))
            env_inserted = True
            break
    if not env_inserted and services_seen:
        # add env under first service
        rebuilt=[]
        inserted=False
        service_found=False
        for line in lines:
            rebuilt.append(line)
            stripped=line.strip()
            if not service_found and line.startswith('  ') and stripped.endswith(':') and stripped != 'services:':
                service_found=True
                continue
            if service_found and not inserted and (line.startswith('    ') and (stripped.startswith('build:') or stripped.startswith('image:') or stripped.startswith('container_name:') or stripped.startswith('restart:') or stripped.startswith('network_mode:') or stripped.startswith('ports:') or stripped.startswith('volumes:') or stripped.startswith('env_file:') or stripped.startswith('command:'))):
                rebuilt.append('    environment:')
                rebuilt.append('      APP_NAME: "{}"'.format(str(meta.get('name','')).replace('"','\"')))
                rebuilt.append('      APP_VERSION: "{}"'.format(str(meta.get('version','')).replace('"','\"')))
                inserted=True
        if inserted:
            text='\n'.join(rebuilt) + ('\n' if text.endswith('\n') else '')
        else:
            text='\n'.join(lines) + ('\n' if text.endswith('\n') else '')
    else:
        text='\n'.join(out + lines[len(out):]) + ('\n' if text.endswith('\n') else '')
    compose_path.write_text(text, encoding='utf-8')
    _append_log(log_path, f'Injected APP_NAME/APP_VERSION into {compose_path.name}')


def generic_docker_install(settings, extracted: Path, meta: dict, extra_dirs: list[str] | None = None):
    log_path = Path(meta.get("_log_path")) if meta.get("_log_path") else None
    _append_log(log_path, f"Starting install for {meta.get('id')} version={meta.get('version')}")
    if not docker_is_healthy():
        recover_stack(settings)
        raise RuntimeError("Docker unstable — recovery triggered. Retry install after recovery.")

    runtime_src = extracted / "runtime"
    runtime_dst = settings.runtime_dir / meta["id"]
    backup_dst = _safe_backups_dir(settings) / f"{meta['id']}.runtime.prev"
    extra_dirs = extra_dirs or []

    _run_logged([
        "sudo", "mkdir", "-p",
        str(settings.apps_dir),
        str(settings.runtime_dir),
        str(_safe_backups_dir(settings)),
        str(settings.caddy_apps_dir),
        str(settings.tailscale_cert_dir),
        str(getattr(settings, 'logs_dir', settings.homelab_root / 'logs')),
    ], log_path=log_path)

    if not runtime_src.exists() or not runtime_src.is_dir():
        raise RuntimeError(f"Bundle runtime directory missing: {runtime_src}")
    compose_src = runtime_src / "docker-compose.yml"
    if not compose_src.exists():
        raise RuntimeError(f"docker-compose.yml missing in bundle runtime: {compose_src}")

    if backup_dst.exists():
        shutil.rmtree(backup_dst)
    if runtime_dst.exists():
        shutil.move(str(runtime_dst), str(backup_dst))
        _append_log(log_path, f"Moved previous runtime to backup: {backup_dst}")

    shutil.copytree(runtime_src, runtime_dst, dirs_exist_ok=True)
    (runtime_dst / "data").mkdir(parents=True, exist_ok=True)
    for rel in extra_dirs:
        (runtime_dst / rel).mkdir(parents=True, exist_ok=True)

    compose_dst = runtime_dst / "docker-compose.yml"
    if not compose_dst.exists():
        if runtime_dst.exists():
            shutil.rmtree(runtime_dst, ignore_errors=True)
        if backup_dst.exists():
            shutil.move(str(backup_dst), str(runtime_dst))
        raise RuntimeError(f"docker-compose.yml missing after runtime copy: {compose_dst}")

    _inject_bundle_env(compose_dst, meta, log_path=log_path)

    if meta["id"] == "dictionary":
        dockerfile = runtime_dst / "Dockerfile"
        if dockerfile.exists():
            text = dockerfile.read_text(encoding="utf-8")
            if 'CMD ["python",' in text:
                text = text.replace('CMD ["python",', 'CMD ["python3",')
                dockerfile.write_text(text, encoding='utf-8')
                _append_log(log_path, 'Patched dictionary Dockerfile to use python3 in CMD')

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

    record_install_state(settings.apps_dir, meta["id"], meta, extracted, runtime_dst, str(log_path) if log_path else None)
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
    run(["sudo", "caddy", "validate", "--config", str(settings.caddyfile)])
    run(["sudo", "systemctl", "restart", "caddy"])
    return {"ok": True, "message": f"Removed {meta['name']}"}
