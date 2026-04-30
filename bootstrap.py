#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE_FILE = ROOT / ".env.example"

# Keys that must exist in .env with their default values.
# If a key is missing from an existing .env, it is appended automatically.
REQUIRED_ENV_KEYS: dict[str, str] = {
    "HOSTNAME": "pi-nas",
    "LAN_IP": "192.168.88.10",
    "TAILSCALE_IP": "100.66.127.27",
    "TAILSCALE_FQDN": "pi-nas.taild4713b.ts.net",
    "NAS_MOUNT": "/mnt/nas",
    "HOMELAB_ROOT": "/mnt/nas/homelab",
    "DOCKER_ROOT_DIR": "/mnt/nas/homelab/docker",
    "CONTROL_CENTER_BIND": "127.0.0.1",
    "CONTROL_CENTER_PORT": "9000",
    "CONTROL_CENTER_PUBLIC_PORT": "8444",
    "BUILD_DIR": "build",
    "PLUGINS_DIR": "plugins",
    "MANIFESTS_DIR": "manifests",
    "RUNTIME_DIR": "runtime",
    "LOGS_DIR": "/mnt/nas/homelab/logs",
    "BACKUPS_DIR": "/mnt/nas/homelab/backups",
    "CADDYFILE": "/etc/caddy/Caddyfile",
    "CADDY_APPS_DIR": "/etc/caddy/apps",
    "CADDY_DISABLED_DIR": "/etc/caddy/apps.disabled",
    "TAILSCALE_CERT_DIR": "/etc/caddy/certs/tailscale",
    # Pi-hole — always set so docker-compose and recovery both have the value
    "PIHOLE_PASSWORD": "admin",
    "PIHOLE_UPSTREAMS": "1.1.1.1;1.0.0.1",
    "TZ": "Asia/Kolkata",
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def ensure_venv() -> tuple[Path, Path]:
    if not VENV_DIR.exists():
        print("[bootstrap] creating virtual environment")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])

    py = VENV_DIR / "bin" / "python"
    pip = VENV_DIR / "bin" / "pip"
    return py, pip


def ensure_env_file() -> None:
    """Create .env if missing, or patch an existing one with any missing keys."""
    if not ENV_FILE.exists():
        if ENV_EXAMPLE_FILE.exists():
            print("[bootstrap] creating .env from .env.example")
            ENV_FILE.write_text(ENV_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            print("[bootstrap] creating default .env")
            lines = [f"{k}={v}" for k, v in REQUIRED_ENV_KEYS.items()]
            ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Patch: append any keys that are missing from an existing .env
    existing_text = ENV_FILE.read_text(encoding="utf-8")
    existing_keys: set[str] = set()
    for line in existing_text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            existing_keys.add(line.split("=", 1)[0].strip())

    missing = {k: v for k, v in REQUIRED_ENV_KEYS.items() if k not in existing_keys}
    if missing:
        print(f"[bootstrap] patching .env with missing keys: {', '.join(missing)}")
        patch_lines = "\n".join(f"{k}={v}" for k, v in missing.items())
        with ENV_FILE.open("a", encoding="utf-8") as f:
            f.write(f"\n# Added by bootstrap\n{patch_lines}\n")


def install_project(pip: Path, py: Path) -> None:
    print("[bootstrap] installing project into virtual environment")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    run([str(pip), "install", "-e", str(ROOT)])


def run_host_bootstrap() -> None:
    """Run homelabctl bootstrap-host which:
    - Reconciles Caddy routes
    - Installs/updates the homelab-watchdog systemd service automatically
    """
    homelabctl = VENV_DIR / "bin" / "homelabctl"
    print("[bootstrap] running host bootstrap (routes + watchdog)")
    run([str(homelabctl), "bootstrap-host", "--env-file", ".env"])


def main() -> None:
    py, pip = ensure_venv()
    ensure_env_file()
    install_project(pip, py)
    run_host_bootstrap()

    print("\nBootstrap completed.\n")
    print("The homelab-watchdog service is now installed and monitoring:")
    print("  - homelab-os-core.service  (Control Center)")
    print("  - pihole Docker container")
    print("")
    print("Recommended next steps:")
    print("  source .venv/bin/activate")
    print("  homelabctl build-all-plugins --env-file .env")
    print("  homelabctl run-control-shell --env-file .env")
    print("")
    print("To check watchdog status:")
    print("  systemctl status homelab-watchdog")
    print("  tail -f /mnt/nas/homelab/logs/watchdog.log")


if __name__ == "__main__":
    main()
