from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def prepare_install_target(installed_plugins_root: str | Path, plugin_id: str, archive_version: str | None = None) -> dict[str, Any]:
    """
    Ensures plugin install target is in a clean state before extraction/copy.
    If an old directory exists from a failed install, it is moved aside first.
    """
    root = Path(installed_plugins_root)
    target = root / plugin_id
    backup = None

    if target.exists():
        backup = root / f"_{plugin_id}_stale"
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        target.rename(backup)

    return {
        "ok": True,
        "target": str(target),
        "backup": str(backup) if backup else None,
        "plugin_id": plugin_id,
        "archive_version": archive_version,
    }


<<<<<<< HEAD
def cleanup_stale_backup(installed_plugins_root: str | Path, plugin_id: str) -> dict[str, Any]:
    root = Path(installed_plugins_root)
    backup = root / f"_{plugin_id}_stale"
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
        return {"ok": True, "removed": str(backup)}
    return {"ok": True, "removed": None}
=======
    def _cleanup_existing_install(self, plugin_id: str) -> None:
        existing = self.registry.get_plugin(plugin_id)
        if existing:
            self.uninstall_plugin(plugin_id)
        else:
            plugin_dir = self.installed_plugins_dir / plugin_id
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir, ignore_errors=True)
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
        plugin_entry = self.registry.get_plugin(plugin_id)
        plugin_dir = self.installed_plugins_dir / plugin_id

        compose_dir = plugin_dir / "docker"
        if compose_dir.exists() and (compose_dir / "docker-compose.yml").exists():
            self.runner.run(
                self._docker_compose_cmd(plugin_id, "down", "--remove-orphans", "-v"),
                cwd=compose_dir,
                check=False,
            )

        self.runner.run(["docker", "rm", "-f", plugin_id], check=False)
        self.proxy.remove_plugin_route(plugin_id)

        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)

        self.registry.remove_plugin(plugin_id)
        self.state_store.remove_plugin_state(plugin_id)

        if not plugin_entry:
            return {"ok": True, "plugin_id": plugin_id, "message": "Plugin already absent"}
        return {"ok": True, "plugin_id": plugin_id}
>>>>>>> 4c9d2e2
