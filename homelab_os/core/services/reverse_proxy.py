from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

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

    def _run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, check=check, capture_output=True, text=True)

    def _read_caddyfile(self) -> str:
        result = self._run(["sudo", "cat", str(self.settings.caddyfile)])
        return result.stdout

    def public_port_for_plugin(self, plugin_id: str) -> int | None:
        return PLUGIN_PORT_MAP.get(plugin_id)

    def public_url_for_plugin(self, plugin_id: str) -> str | None:
        port = self.public_port_for_plugin(plugin_id)
        if not port:
            return None
        suffix = PLUGIN_PATH_SUFFIX.get(plugin_id, "")
        return f"https://{self.settings.tailscale_fqdn}:{port}{suffix}"

    def generate_snippet(self, plugin_id: str, internal_port: int) -> str | None:
        public_port = self.public_port_for_plugin(plugin_id)
        if not public_port:
            return None
        return (
            f"https://{self.settings.tailscale_fqdn}:{public_port} {{\n"
            f"    reverse_proxy 127.0.0.1:{internal_port}\n"
            f"}}\n"
        )

    def write_snippet(self, plugin_id: str, internal_port: int) -> Path | None:
        snippet_content = self.generate_snippet(plugin_id, internal_port)
        if not snippet_content:
            return None
        snippet_path = self.settings.caddy_apps_dir / f"{plugin_id}.caddy"
        self._run(["sudo", "mkdir", "-p", str(self.settings.caddy_apps_dir)])
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as tmp:
            tmp.write(snippet_content)
            tmp_path = Path(tmp.name)
        try:
            self._run(["sudo", "cp", str(tmp_path), str(snippet_path)])
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
        return snippet_path

    def verify_main_caddyfile(self) -> None:
        try:
            content = self._read_caddyfile()
        except Exception:
            return
        required_import = f"import {self.settings.caddy_apps_dir}/*.caddy"
        if required_import not in content:
            # non-blocking warning only
            print(f"[WARN] Caddyfile missing required import line: {required_import}")

    def validate_caddy(self) -> None:
        result = self._run(["sudo", "caddy", "validate", "--config", str(self.settings.caddyfile)], check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Caddy validation failed: {result.stderr or result.stdout}")

    def reload_caddy(self) -> None:
        self._run(["sudo", "systemctl", "reload", "caddy"])

    def apply_plugin_route(self, plugin_id: str, internal_port: int) -> str | None:
        if self.public_port_for_plugin(plugin_id) is None:
            return None
        self.verify_main_caddyfile()
        self.write_snippet(plugin_id, internal_port)
        self.validate_caddy()
        self.reload_caddy()
        return self.public_url_for_plugin(plugin_id)
