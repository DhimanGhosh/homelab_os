from __future__ import annotations

import subprocess
from pathlib import Path
import os

import yaml

from homelab_os.core.config import Settings
from homelab_os.core.plugin_manager.registry import PluginRegistry
from homelab_os.core.plugin_manager.runtime import PluginRuntime
from homelab_os.core.services.network_stack import NetworkStackService


class RecoveryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.stack = NetworkStackService(settings)
        self.runtime = PluginRuntime(settings.runtime_installed_plugins_dir, settings.manifests_dir / 'plugin_state.json', settings=settings)
        self.registry = PluginRegistry(settings.manifests_dir / 'installed_plugins.json')

    def _run(self, cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check, capture_output=True, text=True)

    def _docker_root(self) -> tuple[str, bool]:
        current = ''
        try:
            result = self._run(['docker', 'info', '--format', '{{.DockerRootDir}}'], check=False)
            current = (result.stdout or '').strip()
        except Exception:
            current = ''
        target = str(self.settings.docker_root_dir)
        return current or target, current != target if current else False

    def _compose_dir(self, plugin_id: str) -> Path:
        return self.settings.runtime_installed_plugins_dir / plugin_id / 'docker'

    def _compose_images(self, plugin_id: str) -> list[str]:
        compose_file = self._compose_dir(plugin_id) / 'docker-compose.yml'
        if not compose_file.exists():
            return []
        payload = yaml.safe_load(compose_file.read_text(encoding='utf-8')) or {}
        services = payload.get('services', {}) or {}
        return [str(service.get('image')) for service in services.values() if service.get('image')]

    def _layer_issue(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return 'layer does not exist' in text or 'unable to get image' in text

    def _repair_images(self, plugin_id: str) -> None:
        self._run(['docker', 'system', 'prune', '-a', '--volumes', '-f'], check=False)
        self._run(['systemctl', 'restart', 'docker'], check=False)
        for image in self._compose_images(plugin_id):
            self._run(['docker', 'pull', image], check=False)

    def _reset_pihole_password(self) -> None:
        password = os.getenv('PIHOLE_PASSWORD', 'admin').strip()
        if not password:
            return
        self._run(['docker', 'exec', 'pihole', 'pihole', 'setpassword', password], check=False)

    def _start_with_repair(self, plugin_id: str) -> dict:
        try:
            return self.runtime.start_plugin(plugin_id)
        except subprocess.CalledProcessError as exc:
            if not self._layer_issue(exc):
                raise
            self._repair_images(plugin_id)
            return self.runtime.start_plugin(plugin_id)

    def run(self) -> dict:
        docker_root, changed = self._docker_root()
        rebound = self.stack.reconcile_routes(include_core=True)
        started: dict[str, str] = {}
        repaired: list[str] = []
        warnings: list[str] = []
        for plugin_id in sorted(self.registry.list_all().keys()):
            try:
                result = self._start_with_repair(plugin_id)
                if result.get('public_url'):
                    started[plugin_id] = result['public_url']
            except subprocess.CalledProcessError as exc:
                if self._layer_issue(exc):
                    repaired.append(plugin_id)
                    try:
                        result = self.runtime.start_plugin(plugin_id)
                        if result.get('public_url'):
                            started[plugin_id] = result['public_url']
                    except Exception as retry_exc:
                        warnings.append(f"{plugin_id}: {retry_exc}")
                else:
                    warnings.append(f"{plugin_id}: {exc}")
            except Exception as exc:
                warnings.append(f"{plugin_id}: {exc}")
        pihole = None
        if 'pihole' in self.registry.list_all():
            try:
                self._reset_pihole_password()
                pihole = self.runtime.healthcheck_plugin('pihole')
            except Exception as exc:
                warnings.append(f"pihole password/health: {exc}")
        return {
            'docker_root': docker_root,
            'docker_root_changed': changed,
            'rebound_routes': rebound,
            'started_plugins': started,
            'repaired_plugins': repaired,
            'warnings': warnings,
            'pihole': pihole,
        }
