from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path

import yaml

from homelab_os.core.plugin_manager.registry import PluginRegistry
from homelab_os.core.services.process_runner import ProcessRunner
from homelab_os.core.services.reverse_proxy import ReverseProxyService
from homelab_os.core.services.state_store import StateStore


class PluginInstaller:
    def __init__(
        self,
        settings,
        installed_plugins_dir: Path,
        registry_file: Path,
        state_file: Path,
    ) -> None:
        self.settings = settings
        self.installed_plugins_dir = installed_plugins_dir
        self.registry = PluginRegistry(registry_file)
        self.state_store = StateStore(state_file)
        self.runner = ProcessRunner()
        self.proxy = ReverseProxyService(settings)
        self.installed_plugins_dir.mkdir(parents=True, exist_ok=True)

    def _read_manifest(self, plugin_dir: Path) -> dict:
        manifest_path = plugin_dir / "plugin.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"plugin.json not found in {plugin_dir}")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def _docker_compose_cmd(self, plugin_id: str, *args: str) -> list[str]:
        return ["docker", "compose", "-p", plugin_id, *args]

    def _prepare_public_url(self, plugin_id: str, manifest: dict) -> str | None:
        internal_port = manifest.get("network", {}).get("internal_port")
        if not internal_port:
            return None
        return self.proxy.apply_plugin_route(plugin_id, int(internal_port))

    def _safe_runtime_roots(self, plugin_id: str) -> list[Path]:
        return [
            self.settings.nas_mount / "homelab" / "runtime" / plugin_id,
            self.settings.runtime_dir / plugin_id,
        ]

    def _is_safe_plugin_data_path(self, plugin_id: str, host_path: Path) -> bool:
        try:
            resolved = host_path.resolve(strict=False)
        except Exception:
            resolved = host_path
        for root in self._safe_runtime_roots(plugin_id):
            try:
                resolved.relative_to(root.resolve(strict=False))
                return True
            except Exception:
                continue
        return False

    def _collect_plugin_data_paths(self, plugin_id: str, plugin_dir: Path) -> list[Path]:
        candidates: set[Path] = set()
        compose_path = plugin_dir / "docker" / "docker-compose.yml"
        if compose_path.exists():
            try:
                compose = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
            except Exception:
                compose = {}
            for service in (compose.get("services") or {}).values():
                for volume in service.get("volumes") or []:
                    if isinstance(volume, str):
                        host_part = volume.split(":", 1)[0].strip()
                        if host_part.startswith("/"):
                            candidates.add(Path(host_part))
        for root in self._safe_runtime_roots(plugin_id):
            candidates.add(root)
        return sorted(
            [path for path in candidates if self._is_safe_plugin_data_path(plugin_id, path)],
            key=lambda item: len(str(item)),
            reverse=True,
        )

    def _remove_plugin_data_paths(self, plugin_id: str, plugin_dir: Path) -> None:
        for path in self._collect_plugin_data_paths(plugin_id, plugin_dir):
            if not path.exists():
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _stop_plugin_containers(self, plugin_id: str, plugin_dir: Path) -> None:
        """Stop and remove containers for a plugin WITHOUT touching persistent data."""
        compose_dir = plugin_dir / "docker"
        if compose_dir.exists() and (compose_dir / "docker-compose.yml").exists():
            # No "-v" flag: named Docker volumes are kept.
            # Bind-mount data on the NAS is never touched here.
            self.runner.run(
                self._docker_compose_cmd(plugin_id, "down", "--remove-orphans"),
                cwd=compose_dir,
                check=False,
            )
        self.runner.run(["docker", "rm", "-f", plugin_id], check=False)

    def _cleanup_existing_install(self, plugin_id: str) -> None:
        """Prepare for a fresh install / update.

        IMPORTANT — Persistent Storage Contract
        ─────────────────────────────���──────────
        Each plugin stores its user data under:
            /mnt/nas/homelab/runtime/<plugin-id>/data/

        This directory is bind-mounted into the container via docker-compose.yml
        and MUST survive plugin updates.  We therefore split two cases:

        • Update (plugin already in registry):
            Stop containers, wipe the *code* directory, keep the data directory.

        • Orphan cleanup (plugin NOT in registry but directory exists):
            Wipe everything — containers, code directory, AND data directory —
            because there is no prior install to upgrade from.
        """
        plugin_dir = self.installed_plugins_dir / plugin_id
        existing = self.registry.get_plugin(plugin_id)

        if existing:
            # ── UPDATE PATH: preserve user data ──────────────────────────────
            # Stop containers (no -v so Docker volumes stay intact)
            self._stop_plugin_containers(plugin_id, plugin_dir)
            # Remove only the plugin code directory, NOT the NAS data directory
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
            self.state_store.remove_plugin_state(plugin_id)
            try:
                self.proxy.remove_plugin_route(plugin_id)
            except Exception:
                pass
            # Data directory is intentionally left untouched
        else:
            # ── ORPHAN CLEANUP: nothing to preserve ─────────────────���────────
            self._stop_plugin_containers(plugin_id, plugin_dir)
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
            self._remove_plugin_data_paths(plugin_id, plugin_dir)
            self.state_store.remove_plugin_state(plugin_id)
            try:
                self.proxy.remove_plugin_route(plugin_id)
            except Exception:
                pass

    def install_plugin(self, archive_path: Path) -> dict:
        if not archive_path.exists():
            raise FileNotFoundError(f"Plugin archive not found: {archive_path}")

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(temp_dir)

            extracted_roots = [p for p in temp_dir.iterdir() if p.is_dir()]
            if len(extracted_roots) != 1:
                raise RuntimeError(f"Expected exactly one root directory in archive {archive_path}")

            source_dir = extracted_roots[0]
            manifest = self._read_manifest(source_dir)
            plugin_id = manifest["id"]
            target_dir = self.installed_plugins_dir / plugin_id

            self._cleanup_existing_install(plugin_id)
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

        public_url = self._prepare_public_url(plugin_id, manifest)
        entry = {
            "id": manifest["id"],
            "name": manifest["name"],
            "version": manifest["version"],
            "installed_dir": str(target_dir),
            "network": manifest.get("network", {}),
            "entrypoint": manifest.get("entrypoint", {}),
            "public_url": public_url,
        }
        self.registry.upsert_plugin(entry)
        runtime_metadata = {
            "id": manifest["id"],
            "name": manifest["name"],
            "version": manifest["version"],
            "installed_dir": str(target_dir),
            "network": manifest.get("network", {}),
            "entrypoint": manifest.get("entrypoint", {}),
            "public_url": public_url,
        }
        (target_dir / "runtime.json").write_text(json.dumps(runtime_metadata, indent=2), encoding="utf-8")
        return entry

    def uninstall_plugin(self, plugin_id: str) -> dict:
        """Explicit uninstall requested by the user — removes containers AND data."""
        plugin_entry = self.registry.get_plugin(plugin_id)
        plugin_dir = self.installed_plugins_dir / plugin_id

        # Stop containers.  Data on the NAS is handled below via
        # _remove_plugin_data_paths; named Docker volumes are removed with -v.
        self._stop_plugin_containers(plugin_id, plugin_dir)
        compose_dir = plugin_dir / "docker"
        if compose_dir.exists() and (compose_dir / "docker-compose.yml").exists():
            self.runner.run(
                self._docker_compose_cmd(plugin_id, "down", "--remove-orphans", "-v"),
                cwd=compose_dir,
                check=False,
            )

        self.runner.run(["docker", "rm", "-f", plugin_id], check=False)
        self.proxy.remove_plugin_route(plugin_id)
        self._remove_plugin_data_paths(plugin_id, plugin_dir)

        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)

        self.registry.remove_plugin(plugin_id)
        self.state_store.remove_plugin_state(plugin_id)

        if not plugin_entry:
            return {"ok": True, "plugin_id": plugin_id, "message": "Plugin already absent"}
        return {"ok": True, "plugin_id": plugin_id}
