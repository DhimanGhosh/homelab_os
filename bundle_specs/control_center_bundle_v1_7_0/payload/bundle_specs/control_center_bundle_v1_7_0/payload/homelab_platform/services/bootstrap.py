from pathlib import Path

from homelab_platform.services.caddy_service import CaddyService
from homelab_platform.services.recovery import install_recovery_system
from homelab_platform.services.subprocesses import run, sudo_write_file

CC_TEMPLATE = '''[Unit]
Description=Raspi Homelab Python Framework Control Center
After=network-online.target docker.service

[Service]
Type=simple
WorkingDirectory={workdir}
Environment=HOMELAB_ENV_FILE={env_file}
ExecStart={python} -m homelab_platform.web
Restart=always
User={user}

[Install]
WantedBy=multi-user.target
'''

WATCHDOG_TEMPLATE = '''[Unit]
Description=Raspi Homelab Watchdog
After=network-online.target docker.service

[Service]
Type=simple
WorkingDirectory={workdir}
Environment=HOMELAB_ENV_FILE={env_file}
ExecStart={python} -m homelab_platform.watchdog_entry
Restart=always
User={user}

[Install]
WantedBy=multi-user.target
'''


class BootstrapService:
    def __init__(self, settings):
        self.settings = settings

    def install_host_dependencies(self):
        run(["sudo", "apt-get", "update"], capture=False)
        packages = ["docker.io", "caddy", "curl", "git", "python3-venv", "rsync"]
        has_plugin = run(["bash", "-lc", "apt-cache show docker-compose-plugin >/dev/null 2>&1"], check=False)
        if has_plugin.returncode == 0:
            run(["sudo", "apt-get", "install", "-y", *packages, "docker-compose-plugin"], capture=False)
        else:
            run(["sudo", "apt-get", "install", "-y", *packages], capture=False)

    def create_dirs(self):
        for path in [
            self.settings.homelab_root,
            self.settings.apps_dir,
            self.settings.runtime_dir,
            self.settings.installers_dir,
            self.settings.backups_dir,
            self.settings.caddy_apps_dir,
            self.settings.caddy_disabled_dir,
            self.settings.tailscale_cert_dir,
            self.settings.docker_root_dir,
        ]:
            run(["sudo", "mkdir", "-p", str(path)])

    def write_docker_daemon_json(self):
        sudo_write_file(
            self.settings.docker_daemon_json,
            f'{{\n  "data-root": "{self.settings.docker_root_dir}",\n  "log-driver": "json-file",\n  "log-opts": {{"max-size": "10m", "max-file": "3"}}\n}}\n',
        )
        run(["sudo", "systemctl", "daemon-reload"])
        run(["sudo", "systemctl", "restart", "containerd"], check=False)
        run(["sudo", "systemctl", "restart", "docker"], check=False)

    def install_services(self):
        user = run(["bash", "-lc", "whoami"]).stdout.strip() or "pi"
        python = (self.settings.env_file.parent / ".venv" / "bin" / "python").resolve()
        sudo_write_file(
            Path("/etc/systemd/system") / self.settings.control_center_service_name,
            CC_TEMPLATE.format(
                workdir=self.settings.env_file.parent.resolve(),
                env_file=self.settings.env_file.resolve(),
                python=python,
                user=user,
            ),
        )
        sudo_write_file(
            Path("/etc/systemd/system") / self.settings.watchdog_service_name,
            WATCHDOG_TEMPLATE.format(
                workdir=self.settings.env_file.parent.resolve(),
                env_file=self.settings.env_file.resolve(),
                python=python,
                user=user,
            ),
        )
        run(["sudo", "systemctl", "daemon-reload"])
        run(["sudo", "systemctl", "enable", self.settings.control_center_service_name])
        run(["sudo", "systemctl", "enable", self.settings.watchdog_service_name])
        run(["sudo", "systemctl", "restart", self.settings.control_center_service_name], check=False)
        run(["sudo", "systemctl", "restart", self.settings.watchdog_service_name], check=False)

    def bootstrap(self):
        self.install_host_dependencies()
        self.create_dirs()
        self.write_docker_daemon_json()
        run(["sudo", "mkdir", "-p", str(self.settings.tailscale_cert_dir)])
        run([
            "sudo", "tailscale", "cert",
            "--cert-file", str(self.settings.tailscale_cert_dir / f"{self.settings.tailscale_fqdn}.crt"),
            "--key-file", str(self.settings.tailscale_cert_dir / f"{self.settings.tailscale_fqdn}.key"),
            self.settings.tailscale_fqdn,
        ], check=False)
        caddy = CaddyService(self.settings)
        caddy.write_base()
        caddy.validate()
        caddy.restart()
        install_recovery_system(self.settings)
        self.install_services()
