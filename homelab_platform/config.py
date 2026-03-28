from dataclasses import dataclass, asdict
from pathlib import Path
import os


def parse_env_file(path: Path) -> dict[str, str]:
    data = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    merged = dict(data)
    merged.update(os.environ)
    return merged


@dataclass
class Settings:
    hostname: str
    tailscale_fqdn: str
    homelab_root: Path
    apps_dir: Path
    runtime_dir: Path
    installers_dir: Path
    dist_dir: Path
    bundle_specs_dir: Path
    backups_dir: Path
    docker_root_dir: Path
    docker_daemon_json: Path
    control_center_bind: str
    control_center_port: int
    control_center_public_port: int
    control_center_service_name: str
    watchdog_service_name: str
    watchdog_interval_seconds: int
    pihole_local: str
    pihole_public_port: int
    pihole_password: str
    caddyfile: Path
    caddy_apps_dir: Path
    caddy_disabled_dir: Path
    tailscale_cert_dir: Path
    cloudflared_image: str
    framework_cc_service: str
    legacy_cc_service: str
    allow_reboot: bool
    env_file: Path

    @property
    def control_center_local(self) -> str:
        return f"{self.control_center_bind}:{self.control_center_port}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_env_file(cls, env_file: str = ".env") -> "Settings":
        env_path = Path(env_file).resolve()
        data = parse_env_file(env_path)
        base = env_path.parent

        def p(name: str, default: str) -> Path:
            raw = data.get(name, default)
            path = Path(raw)
            return path if path.is_absolute() else (base / path).resolve()

        return cls(
            hostname=data.get("HOSTNAME", "pi-nas"),
            tailscale_fqdn=data.get("TAILSCALE_FQDN", "pi-nas.taild4713b.ts.net"),
            homelab_root=p("HOMELAB_ROOT", "/mnt/nas/homelab"),
            apps_dir=p("APPS_DIR", "/mnt/nas/homelab/apps"),
            runtime_dir=p("RUNTIME_DIR", "/mnt/nas/homelab/runtime"),
            installers_dir=p("INSTALLERS_DIR", "/mnt/nas/homelab/installers"),
            dist_dir=p("DIST_DIR", "dist"),
            bundle_specs_dir=p("BUNDLE_SPECS_DIR", "bundle_specs"),
            backups_dir=p("BACKUPS_DIR", "/mnt/nas/homelab/backups"),
            docker_root_dir=p("DOCKER_ROOT_DIR", "/mnt/nas/homelab/docker"),
            docker_daemon_json=p("DOCKER_DAEMON_JSON", "/etc/docker/daemon.json"),
            control_center_bind=data.get("CONTROL_CENTER_BIND", "127.0.0.1"),
            control_center_port=int(data.get("CONTROL_CENTER_PORT", "9000")),
            control_center_public_port=int(data.get("CONTROL_CENTER_PUBLIC_PORT", "8444")),
            control_center_service_name=data.get("CONTROL_CENTER_SERVICE_NAME", "raspi-homelab-python-framework.service"),
            watchdog_service_name=data.get("WATCHDOG_SERVICE_NAME", "raspi-homelab-watchdog.service"),
            watchdog_interval_seconds=int(data.get("WATCHDOG_INTERVAL_SECONDS", "10")),
            pihole_local=data.get("PIHOLE_LOCAL", "127.0.0.1:8080"),
            pihole_public_port=int(data.get("PIHOLE_PUBLIC_PORT", "8447")),
            pihole_password=data.get("PIHOLE_PASSWORD", "admin"),
            caddyfile=p("CADDYFILE", "/etc/caddy/Caddyfile"),
            caddy_apps_dir=p("CADDY_APPS_DIR", "/etc/caddy/apps"),
            caddy_disabled_dir=p("CADDY_DISABLED_DIR", "/etc/caddy/apps.disabled"),
            tailscale_cert_dir=p("TAILSCALE_CERT_DIR", "/etc/caddy/certs/tailscale"),
            cloudflared_image=data.get("CLOUDFLARED_IMAGE", "cloudflare/cloudflared:2026.1.2"),
            framework_cc_service=data.get("FRAMEWORK_CC_SERVICE", "raspi-homelab-python-framework.service"),
            legacy_cc_service=data.get("LEGACY_CC_SERVICE", "pi-control-center.service"),
            allow_reboot=data.get("ALLOW_REBOOT", "1") == "1",
            env_file=env_path,
        )
