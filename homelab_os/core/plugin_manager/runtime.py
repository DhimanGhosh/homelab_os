from __future__ import annotations

import json
from pathlib import Path

from homelab_os.core.services.process_runner import ProcessRunner
from homelab_os.core.services.state_store import StateStore
from homelab_os.core.services.health import HealthService


class PluginRuntime:
    def __init__(self, runtime_root: Path, state_file: Path) -> None:
        self.runtime_root = runtime_root
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.runner = ProcessRunner()
        self.health = HealthService()
        self.state_store = StateStore(state_file)

    def plugin_runtime_dir(self, plugin_id: str) -> Path:
        return self.runtime_root / plugin_id

    def write_runtime_metadata(self, plugin_id: str, metadata: dict) -> Path:
        runtime_dir = self.plugin_runtime_dir(plugin_id)
        runtime_dir.mkdir(parents=True, exist_ok=True)

        runtime_file = runtime_dir / "runtime.json"
        runtime_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return runtime_file

    def read_runtime_metadata(self, plugin_id: str) -> dict | None:
        runtime_file = self.plugin_runtime_dir(plugin_id) / "runtime.json"
        if not runtime_file.exists():
            return None
        return json.loads(runtime_file.read_text(encoding="utf-8"))

    def detect_runtime_type(self, plugin_dir: Path) -> str:
        if (plugin_dir / "docker" / "docker-compose.yml").exists():
            return "docker"
        if (plugin_dir / "backend" / "app.py").exists():
            return "python"
        return "unknown"

    def start_plugin(self, plugin_id: str) -> dict:
        plugin_dir = self.plugin_runtime_dir(plugin_id)
        if not plugin_dir.exists():
            raise FileNotFoundError(f"Installed plugin not found: {plugin_dir}")

        runtime_type = self.detect_runtime_type(plugin_dir)

        if runtime_type == "docker":
            compose_dir = plugin_dir / "docker"
            result = self.runner.run(["docker", "compose", "up", "-d"], cwd=compose_dir)
            self.state_store.update_plugin_state(
                plugin_id,
                {
                    "status": "running",
                    "runtime_type": "docker",
                    "last_action": "start",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )
            return {"plugin_id": plugin_id, "runtime_type": "docker", "status": "running"}

        if runtime_type == "python":
            backend_dir = plugin_dir / "backend"
            log_dir = self.runtime_root / "_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stdout_path = log_dir / f"{plugin_id}.out.log"
            stderr_path = log_dir / f"{plugin_id}.err.log"
            stdout_file = open(stdout_path, "a", encoding="utf-8")
            stderr_file = open(stderr_path, "a", encoding="utf-8")

            process = self.runner.popen(
                ["python3", "app.py"],
                cwd=backend_dir,
                stdout=stdout_file,
                stderr=stderr_file,
            )

            self.state_store.update_plugin_state(
                plugin_id,
                {
                    "status": "running",
                    "runtime_type": "python",
                    "last_action": "start",
                    "pid": process.pid,
                    "stdout_log": str(stdout_path),
                    "stderr_log": str(stderr_path),
                },
            )
            return {"plugin_id": plugin_id, "runtime_type": "python", "status": "running", "pid": process.pid}

        raise RuntimeError(f"Unsupported runtime type for plugin '{plugin_id}'")

    def stop_plugin(self, plugin_id: str) -> dict:
        plugin_dir = self.plugin_runtime_dir(plugin_id)
        if not plugin_dir.exists():
            raise FileNotFoundError(f"Installed plugin not found: {plugin_dir}")

        runtime_type = self.detect_runtime_type(plugin_dir)
        plugin_state = self.state_store.get_plugin_state(plugin_id) or {}

        if runtime_type == "docker":
            compose_dir = plugin_dir / "docker"
            result = self.runner.run(["docker", "compose", "down"], cwd=compose_dir)
            self.state_store.update_plugin_state(
                plugin_id,
                {
                    "status": "stopped",
                    "last_action": "stop",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )
            return {"plugin_id": plugin_id, "runtime_type": "docker", "status": "stopped"}

        if runtime_type == "python":
            pid = plugin_state.get("pid")
            if pid:
                self.runner.run(["kill", str(pid)], check=False)
            self.state_store.update_plugin_state(
                plugin_id,
                {
                    "status": "stopped",
                    "last_action": "stop",
                },
            )
            return {"plugin_id": plugin_id, "runtime_type": "python", "status": "stopped"}

        raise RuntimeError(f"Unsupported runtime type for plugin '{plugin_id}'")

    def restart_plugin(self, plugin_id: str) -> dict:
        self.stop_plugin(plugin_id)
        return self.start_plugin(plugin_id)

    def healthcheck_plugin(self, plugin_id: str) -> dict:
        metadata = self.read_runtime_metadata(plugin_id)
        if not metadata:
            raise FileNotFoundError(f"runtime.json missing for plugin '{plugin_id}'")

        public_url = metadata.get("public_url")
        plugin_state = self.state_store.get_plugin_state(plugin_id) or {}

        if public_url:
            health = self.health.check_http(public_url)
            self.state_store.update_plugin_state(plugin_id, {"last_healthcheck": health})
            return health

        internal_port = (metadata.get("network") or {}).get("internal_port")
        if internal_port:
            local_url = f"http://127.0.0.1:{internal_port}/"
            health = self.health.check_http(local_url)
            self.state_store.update_plugin_state(plugin_id, {"last_healthcheck": health})
            return health

        return {
            "ok": plugin_state.get("status") == "running",
            "status_code": None,
            "url": None,
        }
