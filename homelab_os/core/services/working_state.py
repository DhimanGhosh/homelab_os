from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from homelab_os.core.plugin_manager.registry import PluginRegistry
from homelab_os.core.services.state_store import StateStore


class PluginWorkingStateService:
    """Maintains last-known-good plugin code snapshots.

    The snapshots live under the NAS backup root so self-heal can restore the
    exact plugin code that was last observed as working. Runtime user data is
    never copied into these snapshots and is never removed during restore.
    """

    MAX_SNAPSHOTS_PER_PLUGIN = 5

    def __init__(self, settings, registry: PluginRegistry | None = None, state_store: StateStore | None = None) -> None:
        self.settings = settings
        self.registry = registry or PluginRegistry(settings.manifests_dir / "installed_plugins.json")
        self.state_store = state_store or StateStore(settings.manifests_dir / "plugin_state.json")
        self.base_dir = settings.backups_dir / "plugin-working-state"
        self.snapshots_dir = self.base_dir / "snapshots"
        self.index_file = self.base_dir / "working_state.json"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_file.exists():
            self._write_index({"plugins": {}})

    def _read_index(self) -> dict[str, Any]:
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            return {"plugins": {}}

    def _write_index(self, payload: dict[str, Any]) -> None:
        self.index_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _plugin_snapshot_root(self, plugin_id: str) -> Path:
        return self.snapshots_dir / plugin_id

    def _snapshot_path(self, plugin_id: str, snapshot_id: str) -> Path:
        return self._plugin_snapshot_root(plugin_id) / snapshot_id

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S%z")

    def _safe_snapshot_id(self, plugin_id: str, version: str) -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return f"{plugin_id}.v{version}.{stamp}"

    def _ignore_snapshot_files(self, _dir: str, names: list[str]) -> set[str]:
        ignored = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
        ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
        # Persistent user data must never be copied as part of a code snapshot.
        ignored.update({"data", "logs", "backups", "exports", "imports", "receipts", "models"})
        return ignored.intersection(names)

    def _directory_digest(self, root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in path.parts):
                continue
            relative = path.relative_to(root).as_posix()
            if relative.startswith(("data/", "logs/", "backups/", "exports/", "imports/", "receipts/", "models/")):
                continue
            digest.update(relative.encode("utf-8"))
            try:
                digest.update(path.read_bytes())
            except OSError:
                continue
        return digest.hexdigest()

    def list_states(self) -> dict[str, Any]:
        return self._read_index().get("plugins", {})

    def latest_for(self, plugin_id: str) -> dict[str, Any] | None:
        return self.list_states().get(plugin_id)

    def capture_plugin(self, plugin_id: str, *, reason: str = "manual", force: bool = False) -> dict[str, Any]:
        plugin = self.registry.get_plugin(plugin_id)
        if not plugin:
            raise FileNotFoundError(f"Plugin '{plugin_id}' is not installed")

        plugin_dir = Path(plugin.get("installed_dir") or self.settings.runtime_installed_plugins_dir / plugin_id)
        fallback_dir = self.settings.runtime_installed_plugins_dir / plugin_id
        if not plugin_dir.exists() and fallback_dir.exists():
            plugin_dir = fallback_dir
        if not plugin_dir.exists():
            raise FileNotFoundError(f"Installed plugin directory not found: {plugin_dir}")

        version = str(plugin.get("version") or "unknown")
        code_hash = self._directory_digest(plugin_dir)
        index = self._read_index()
        latest = index.setdefault("plugins", {}).get(plugin_id)
        if latest and latest.get("code_hash") == code_hash and not force:
            latest["last_checked_at"] = self._now()
            latest["last_reason"] = reason
            self._write_index(index)
            return {"ok": True, "changed": False, "plugin_id": plugin_id, "snapshot": latest}

        snapshot_id = self._safe_snapshot_id(plugin_id, version)
        target = self._snapshot_path(plugin_id, snapshot_id)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(plugin_dir, target / "code", ignore=self._ignore_snapshot_files)

        metadata = {
            "plugin_id": plugin_id,
            "version": version,
            "snapshot_id": snapshot_id,
            "created_at": self._now(),
            "last_checked_at": self._now(),
            "reason": reason,
            "last_reason": reason,
            "code_hash": code_hash,
            "snapshot_dir": str(target),
            "code_dir": str(target / "code"),
            "registry_entry": plugin,
        }
        (target / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        index["plugins"][plugin_id] = metadata
        self._write_index(index)
        self._prune(plugin_id)
        return {"ok": True, "changed": True, "plugin_id": plugin_id, "snapshot": metadata}


    def _container_is_running(self, plugin_id: str) -> bool:
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", plugin_id],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            return result.returncode == 0 and result.stdout.strip().lower() == "true"
        except Exception:
            return False
    def capture_running_plugins(self, *, healthy_only: bool = True, reason: str = "periodic") -> dict[str, Any]:
        states = self.state_store.get_all_plugin_states()
        results: dict[str, Any] = {}
        for plugin_id in sorted(self.registry.list_all().keys()):
            plugin_state = states.get(plugin_id, {})
            if healthy_only and plugin_state.get("status") != "running":
                results[plugin_id] = {"ok": False, "skipped": True, "reason": "plugin state is not running"}
                continue
            if healthy_only and not self._container_is_running(plugin_id):
                results[plugin_id] = {"ok": False, "skipped": True, "reason": "container is not currently running"}
                continue
            try:
                results[plugin_id] = self.capture_plugin(plugin_id, reason=reason)
            except Exception as exc:  # noqa: BLE001
                results[plugin_id] = {"ok": False, "error": str(exc)}
        return results

    def restore_plugin(self, plugin_id: str) -> dict[str, Any]:
        latest = self.latest_for(plugin_id)
        if not latest:
            raise FileNotFoundError(f"No last-known-good snapshot exists for '{plugin_id}'")

        source = Path(latest["code_dir"])
        if not source.exists():
            raise FileNotFoundError(f"Snapshot code directory missing: {source}")

        target = self.settings.runtime_installed_plugins_dir / plugin_id
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)

        entry = dict(latest.get("registry_entry") or {})
        entry["installed_dir"] = str(target)
        self.registry.upsert_plugin(entry)

        runtime_payload = {
            "id": entry.get("id", plugin_id),
            "name": entry.get("name", plugin_id),
            "version": entry.get("version"),
            "installed_dir": str(target),
            "network": entry.get("network", {}),
            "entrypoint": entry.get("entrypoint", {}),
            "public_url": entry.get("public_url"),
            "restored_from_working_state": {
                "snapshot_id": latest.get("snapshot_id"),
                "version": latest.get("version"),
                "restored_at": self._now(),
            },
        }
        (target / "runtime.json").write_text(json.dumps(runtime_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self.state_store.update_plugin_state(plugin_id, {
            "status": "restored",
            "last_action": "restore-working-state",
            "restored_version": latest.get("version"),
            "restored_snapshot_id": latest.get("snapshot_id"),
        })
        return {"ok": True, "plugin_id": plugin_id, "restored_version": latest.get("version"), "snapshot_id": latest.get("snapshot_id")}

    def _prune(self, plugin_id: str) -> None:
        root = self._plugin_snapshot_root(plugin_id)
        if not root.exists():
            return
        snapshots = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        for old in snapshots[self.MAX_SNAPSHOTS_PER_PLUGIN:]:
            shutil.rmtree(old, ignore_errors=True)
