from dataclasses import dataclass, asdict
from pathlib import Path
import os


def parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
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
    build_dir: Path
    plugins_dir: Path
    manifests_dir: Path
    backups_dir: Path
    logs_dir: Path
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

    @property
    def dist_dir(self) -> Path:
        return self.build_dir

    @property
    def bundle_specs_dir(self) -> Path:
        return self.plugins_dir

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["control_center_local"] = self.control_center_local
        payload["dist_dir"] = str(self.dist_dir)
        payload["bundle_specs_dir"] = str(self.bundle_specs_dir)
        return payload

    @classmethod
    def from_env_file(cls, env_file: str = ".env") -> "Settings":
        env_path = Path(env_file).resolve()
        data = parse_env_file(env_path)
        base = env_path.parent

        def path_value(*names: str, default: str) -> Path:
            raw = None
            for name in names:
                raw = data.get(name)
                if raw:
                    break
            raw = raw or default
            path = Path(raw)
            return path if path.is_absolute() else (base / path).resolve()

        return cls(
            hostname=data.get("HOSTNAME", "pi-nas"),
            tailscale_fqdn=data.get("TAILSCALE_FQDN", "pi-nas.taild4713b.ts.net"),
            homelab_root=path_value("HOMELAB_ROOT", default="/mnt/nas/homelab"),
            apps_dir=path_value("APPS_DIR", default="/mnt/nas/homelab/apps"),
            runtime_dir=path_value("RUNTIME_DIR", default="/mnt/nas/homelab/runtime"),
            installers_dir=path_value("INSTALLERS_DIR", default="/mnt/nas/homelab/installers"),
            build_dir=path_value("BUILD_DIR", "DIST_DIR", default="build"),
            plugins_dir=path_value("PLUGINS_DIR", "BUNDLE_SPECS_DIR", default="plugins"),
            manifests_dir=path_value("MANIFESTS_DIR", default="manifests"),
            backups_dir=path_value("BACKUPS_DIR", default="/mnt/nas/homelab/backups"),
            logs_dir=path_value("LOGS_DIR", default="/mnt/nas/homelab/logs"),
            docker_root_dir=path_value("DOCKER_ROOT_DIR", default="/mnt/nas/homelab/docker"),
            docker_daemon_json=path_value("DOCKER_DAEMON_JSON", default="/etc/docker/daemon.json"),
            control_center_bind=data.get("CONTROL_CENTER_BIND", "127.0.0.1"),
            control_center_port=int(data.get("CONTROL_CENTER_PORT", "9000")),
            control_center_public_port=int(data.get("CONTROL_CENTER_PUBLIC_PORT", "8444")),
            control_center_service_name=data.get("CONTROL_CENTER_SERVICE_NAME", "raspi-homelab-python-framework.service"),
            watchdog_service_name=data.get("WATCHDOG_SERVICE_NAME", "raspi-homelab-watchdog.service"),
            watchdog_interval_seconds=int(data.get("WATCHDOG_INTERVAL_SECONDS", "10")),
            pihole_local=data.get("PIHOLE_LOCAL", "127.0.0.1:8080"),
            pihole_public_port=int(data.get("PIHOLE_PUBLIC_PORT", "8447")),
            pihole_password=data.get("PIHOLE_PASSWORD", "admin"),
            caddyfile=path_value("CADDYFILE", default="/etc/caddy/Caddyfile"),
            caddy_apps_dir=path_value("CADDY_APPS_DIR", default="/etc/caddy/apps"),
            caddy_disabled_dir=path_value("CADDY_DISABLED_DIR", default="/etc/caddy/apps.disabled"),
            tailscale_cert_dir=path_value("TAILSCALE_CERT_DIR", default="/etc/caddy/certs/tailscale"),
            cloudflared_image=data.get("CLOUDFLARED_IMAGE", "cloudflare/cloudflared:2026.1.2"),
            framework_cc_service=data.get("FRAMEWORK_CC_SERVICE", "raspi-homelab-python-framework.service"),
            legacy_cc_service=data.get("LEGACY_CC_SERVICE", "pi-control-center.service"),
            allow_reboot=data.get("ALLOW_REBOOT", "1") == "1",
            env_file=env_path,
        )
