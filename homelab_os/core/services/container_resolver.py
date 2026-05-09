from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from homelab_os.core.plugin_manager.registry import PluginRegistry


class DockerContainerResolver:
    """Resolve the real Docker container behind a plugin id.

    Several homelab plugins use a Docker Compose project id that differs from
    the final container name, e.g. plugin id ``files`` uses container name
    ``homelab-files`` and plugin id ``status`` uses ``pi-statusboard``.
    Recovery and working-state logic must therefore resolve containers using:

    1. Docker Compose project labels.
    2. docker-compose.yml service names and explicit ``container_name``.
    3. Exact plugin-id fallback.
    """

    COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
    COMPOSE_SERVICE_LABEL = "com.docker.compose.service"

    def __init__(self, settings, registry: PluginRegistry | None = None) -> None:
        self.settings = settings
        self.registry = registry or PluginRegistry(settings.manifests_dir / "installed_plugins.json")

    def _run(self, cmd: list[str], *, timeout: int = 8) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)

    def _inspect(self, ref: str) -> dict[str, Any] | None:
        if not ref:
            return None
        try:
            result = self._run(["docker", "inspect", ref], timeout=10)
        except Exception:
            return None
        if result.returncode != 0:
            return None
        try:
            payload = json.loads(result.stdout or "[]")
        except Exception:
            return None
        if not payload:
            return None
        return payload[0]

    def _compose_file_for(self, plugin_id: str) -> Path | None:
        plugin = self.registry.get_plugin(plugin_id) or {}
        paths: list[Path] = []
        installed_dir = plugin.get("installed_dir")
        if installed_dir:
            paths.append(Path(installed_dir) / "docker" / "docker-compose.yml")
        paths.append(self.settings.runtime_installed_plugins_dir / plugin_id / "docker" / "docker-compose.yml")
        paths.append(self.settings.plugins_dir / plugin_id / "docker" / "docker-compose.yml")
        for path in paths:
            if path.exists():
                return path
        return None

    def _compose_names(self, plugin_id: str) -> tuple[list[str], list[str]]:
        """Return candidate container names and service names from compose."""
        names: list[str] = []
        services: list[str] = []
        compose_path = self._compose_file_for(plugin_id)
        if not compose_path:
            return names, services
        try:
            payload = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return names, services
        service_map = payload.get("services") or {}
        if not isinstance(service_map, dict):
            return names, services
        for service_name, service_cfg in service_map.items():
            service_name = str(service_name)
            services.append(service_name)
            names.extend([
                service_name,
                f"{plugin_id}-{service_name}-1",
                f"{plugin_id}_{service_name}_1",
            ])
            if isinstance(service_cfg, dict):
                container_name = service_cfg.get("container_name")
                if container_name:
                    names.append(str(container_name))
                networks = service_cfg.get("networks")
                if isinstance(networks, dict):
                    for network_cfg in networks.values():
                        if isinstance(network_cfg, dict):
                            aliases = network_cfg.get("aliases") or []
                            if isinstance(aliases, list):
                                names.extend(str(alias) for alias in aliases)
        return self._unique(names), self._unique(services)

    def _containers_by_compose_label(self, plugin_id: str, service_names: list[str]) -> list[dict[str, Any]]:
        try:
            result = self._run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"label={self.COMPOSE_PROJECT_LABEL}={plugin_id}",
                    "--format",
                    "{{.ID}}",
                ],
                timeout=10,
            )
        except Exception:
            return []
        containers: list[dict[str, Any]] = []
        for container_id in [line.strip() for line in result.stdout.splitlines() if line.strip()]:
            inspected = self._inspect(container_id)
            if inspected:
                containers.append(inspected)

        # Some compose invocations or legacy containers may use a service label
        # even when the project label does not match the plugin id.
        for service_name in service_names:
            try:
                service_result = self._run(
                    [
                        "docker",
                        "ps",
                        "-a",
                        "--filter",
                        f"label={self.COMPOSE_SERVICE_LABEL}={service_name}",
                        "--format",
                        "{{.ID}}",
                    ],
                    timeout=10,
                )
            except Exception:
                continue
            for container_id in [line.strip() for line in service_result.stdout.splitlines() if line.strip()]:
                if any(item.get("Id", "").startswith(container_id) for item in containers):
                    continue
                inspected = self._inspect(container_id)
                if inspected:
                    containers.append(inspected)
        return containers

    def _unique(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            value = str(value or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _is_running(self, inspected: dict[str, Any] | None) -> bool:
        if not inspected:
            return False
        return bool((inspected.get("State") or {}).get("Running"))

    def _to_summary(self, plugin_id: str, inspected: dict[str, Any] | None, *, source: str, candidates: list[str]) -> dict[str, Any]:
        if not inspected:
            return {
                "plugin_id": plugin_id,
                "found": False,
                "running": False,
                "container_name": None,
                "container_id": None,
                "status": "not-found",
                "health": None,
                "health_source": "not-found",
                "source": source,
                "candidates": candidates,
            }
        state = inspected.get("State") or {}
        labels = (inspected.get("Config") or {}).get("Labels") or {}
        raw_name = str(inspected.get("Name") or "").lstrip("/")
        health = state.get("Health") or {}
        health_status = health.get("Status")
        running = bool(state.get("Running"))
        if health_status:
            health_source = "docker-healthcheck"
            display_status = "running" if running and health_status in {"healthy", "starting"} else str(state.get("Status") or "unknown")
        elif running:
            health_source = "docker-running"
            display_status = "running"
        else:
            health_source = "docker-state"
            display_status = str(state.get("Status") or "stopped")
        return {
            "plugin_id": plugin_id,
            "found": True,
            "running": running,
            "container_name": raw_name,
            "container_id": str(inspected.get("Id") or "")[:12],
            "status": display_status,
            "health": health_status,
            "health_source": health_source,
            "source": source,
            "candidates": candidates,
            "compose_project": labels.get(self.COMPOSE_PROJECT_LABEL),
            "compose_service": labels.get(self.COMPOSE_SERVICE_LABEL),
        }

    def resolve_plugin(self, plugin_id: str) -> dict[str, Any]:
        compose_names, service_names = self._compose_names(plugin_id)
        candidates = self._unique([plugin_id, *compose_names])

        inspected_candidates: list[tuple[str, dict[str, Any]]] = []
        for name in candidates:
            inspected = self._inspect(name)
            if inspected:
                inspected_candidates.append((name, inspected))

        for name, inspected in inspected_candidates:
            if self._is_running(inspected):
                source = "container-name" if name != plugin_id else "exact-plugin-id"
                return self._to_summary(plugin_id, inspected, source=source, candidates=candidates)

        label_matches = self._containers_by_compose_label(plugin_id, service_names)
        for inspected in label_matches:
            if self._is_running(inspected):
                return self._to_summary(plugin_id, inspected, source="compose-label", candidates=candidates)

        if inspected_candidates:
            name, inspected = inspected_candidates[0]
            source = "container-name" if name != plugin_id else "exact-plugin-id"
            return self._to_summary(plugin_id, inspected, source=source, candidates=candidates)
        if label_matches:
            return self._to_summary(plugin_id, label_matches[0], source="compose-label", candidates=candidates)

        return self._to_summary(plugin_id, None, source="not-found", candidates=candidates)

    def is_running(self, plugin_id: str) -> bool:
        return bool(self.resolve_plugin(plugin_id).get("running"))
