import shutil
from pathlib import Path

from homelab_platform.services.state import record_install_state
from homelab_platform.services.subprocesses import run


def _copy_payload(payload_dir: Path, target_root: Path):
    for item in payload_dir.iterdir():
        dst = target_root / item.name
        if item.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(item, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)


def _restart_control_center(settings):
    for service_name in [settings.framework_cc_service, settings.legacy_cc_service, settings.control_center_service_name]:
        if service_name:
            run(["sudo", "systemctl", "restart", service_name], check=False)


def install(settings, extracted, meta):
    payload_dir = extracted / "payload"
    if not payload_dir.exists():
        raise RuntimeError(f"Control Center payload missing: {payload_dir}")

    repo_root = settings.env_file.parent
    backups_dir = getattr(settings, "backups_dir", settings.homelab_root / "backups")
    backup_dst = backups_dir / "control-center.repo.prev"
    backup_dst.mkdir(parents=True, exist_ok=True)

    for rel in ["bootstrap.py", "pyproject.toml", ".env.example", "README.md", "homelab_platform", "recovery", "bundle_specs/control_center_bundle_v1_7_0"]:
        src = repo_root / rel
        if not src.exists():
            continue
        dst = backup_dst / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    _copy_payload(payload_dir, repo_root)
    _restart_control_center(settings)
    record_install_state(settings.apps_dir, meta["id"], meta, extracted, None, meta.get("_log_path"))
    return {
        "ok": True,
        "message": f"Installed {meta['name']} -> https://{settings.tailscale_fqdn}:{meta['port']}{meta.get('open_path', '/')}",
        "log_path": meta.get("_log_path"),
    }


def uninstall(settings, extracted, meta):
    backups_dir = getattr(settings, "backups_dir", settings.homelab_root / "backups")
    backup_src = backups_dir / "control-center.repo.prev"
    if not backup_src.exists():
        return {"ok": True, "message": f"Removed {meta['name']} (no backup restore available)"}

    repo_root = settings.env_file.parent
    _copy_payload(backup_src, repo_root)
    _restart_control_center(settings)
    return {"ok": True, "message": f"Removed {meta['name']} and restored previous repo backup"}
