from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from homelab_os.core.config import Settings


PLUGIN_PORT_MAP = {
    "control-center": 8444,
    "pihole": 8447,
    "files": 8449,
    "status": 8451,
    "voice-ai": 8452,
    "homarr": 8453,
    "personal-library": 8454,
    "dictionary": 8455,
    "api-gateway": 8456,
    "music-player": 8459,
    "link-downloader": 8460,
}

PLUGIN_PATH_SUFFIX = {
    "control-center": "",
    "pihole": "/admin/",
    "files": "",
    "status": "",
    "voice-ai": "/",
    "homarr": "/",
    "personal-library": "/",
    "dictionary": "/",
    "api-gateway": "/docs",
    "music-player": "/",
    "link-downloader": "/",
}


class ReverseProxyService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)

    def read_caddyfile(self) -> str:
        result = self._run(["sudo", "cat", str(self.settings.caddyfile)])
        return result.stdout

    def has_public_route(self, plugin_id: str) -> bool:
        return plugin_id in PLUGIN_PORT_MAP

    def public_port_for_plugin(self, plugin_id: str) -> int:
        if plugin_id not in PLUGIN_PORT_MAP:
            raise KeyError(f"No public port mapping defined for plugin '{plugin_id}'")
        return PLUGIN_PORT_MAP[plugin_id]

    def public_url_for_plugin(self, plugin_id: str) -> str | None:
        if not self.has_public_route(plugin_id):
            return None
        port = self.public_port_for_plugin(plugin_id)
        suffix = PLUGIN_PATH_SUFFIX.get(plugin_id, "")
        return f"https://{self.settings.tailscale_fqdn}:{port}{suffix}"

    def _snippet_tls_block(self) -> str:
        cert = self.settings.tailscale_cert_dir / f"{self.settings.tailscale_fqdn}.crt"
        key = self.settings.tailscale_cert_dir / f"{self.settings.tailscale_fqdn}.key"
        return f"    tls {cert} {key}\n"

    def generate_snippet(self, plugin_id: str, internal_port: int) -> str:
        public_port = self.public_port_for_plugin(plugin_id)
        return (
            f"https://{self.settings.tailscale_fqdn}:{public_port} {{\n"
            f"{self._snippet_tls_block()}"
            f"    reverse_proxy 127.0.0.1:{internal_port}\n"
            f"}}\n"
        )

    def generate_core_snippet(self) -> str:
        return (
            f"https://{self.settings.tailscale_fqdn}:{self.settings.control_center_public_port} {{\n"
            f"{self._snippet_tls_block()}"
            f"    reverse_proxy {self.settings.control_center_bind}:{self.settings.control_center_port}\n"
            f"}}\n"
        )

    def write_snippet_file(self, filename: str, content: str) -> Path:
        snippet_path = self.settings.caddy_apps_dir / filename
        self._run(["sudo", "mkdir", "-p", str(self.settings.caddy_apps_dir)])
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        self._run(["sudo", "cp", str(tmp_path), str(snippet_path)])
        tmp_path.unlink(missing_ok=True)
        return snippet_path

    def remove_snippet_file(self, filename: str) -> None:
        snippet_path = self.settings.caddy_apps_dir / filename
        self._run(["sudo", "rm", "-f", str(snippet_path)])

    def write_snippet(self, plugin_id: str, internal_port: int) -> Path:
        return self.write_snippet_file(f"{plugin_id}.caddy", self.generate_snippet(plugin_id, internal_port))

    def write_core_snippet(self) -> Path:
        return self.write_snippet_file("control-center.caddy", self.generate_core_snippet())

    def verify_main_caddyfile(self) -> None:
        try:
            content = self.read_caddyfile()
        except Exception as exc:
            print(f"[WARN] Could not read Caddyfile: {exc}")
            return
        required_import = f"import {self.settings.caddy_apps_dir}/*.caddy"
        if required_import not in content:
            print(f"[WARN] Missing import in Caddyfile: {required_import}")

    def validate_caddy(self) -> None:
        self._run(["sudo", "caddy", "validate", "--config", str(self.settings.caddyfile)])

    def reload_caddy(self) -> None:
        self._run(["sudo", "systemctl", "reload", "caddy"])

    def apply_plugin_route(self, plugin_id: str, internal_port: int) -> str | None:
        if not self.has_public_route(plugin_id):
            return None
        self.verify_main_caddyfile()
        self.write_snippet(plugin_id, internal_port)
        self.validate_caddy()
        self.reload_caddy()
        return self.public_url_for_plugin(plugin_id)

    def remove_plugin_route(self, plugin_id: str) -> None:
        if not self.has_public_route(plugin_id):
            return
        self.remove_snippet_file(f"{plugin_id}.caddy")
        self.validate_caddy()
        self.reload_caddy()

    def apply_core_route(self) -> str:
        self.verify_main_caddyfile()
        self.write_core_snippet()
        self.validate_caddy()
        self.reload_caddy()
        return f"https://{self.settings.tailscale_fqdn}:{self.settings.control_center_public_port}"
