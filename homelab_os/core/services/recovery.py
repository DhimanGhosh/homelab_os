from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable


LogFn = Callable[[str], None]
ProgressFn = Callable[[int, str], None]


class RecoveryService:
    def __init__(
        self,
        settings,
        app_catalog,
        caddy_service,
        plugin_runtime,
        plugin_registry,
        log_fn: LogFn | None = None,
        progress_fn: ProgressFn | None = None,
        plugin_start_timeout_seconds: int = 900,
    ) -> None:
        self.settings = settings
        self.app_catalog = app_catalog
        self.caddy_service = caddy_service
        self.plugin_runtime = plugin_runtime
        self.plugin_registry = plugin_registry
        self.log_fn = log_fn or (lambda _msg: None)
        self.progress_fn = progress_fn or (lambda _pct, _msg: None)
        self.plugin_start_timeout_seconds = plugin_start_timeout_seconds

    def log(self, message: str) -> None:
        self.log_fn(message)

    def progress(self, value: int, message: str) -> None:
        self.progress_fn(value, message)
        self.log(message)

    def self_heal(self) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "docker_root": str(self.settings.docker_root_dir),
            "docker_root_changed": False,
            "docker_repaired": False,
            "rebound_routes": [],
            "started_plugins": [],
            "timed_out_plugins": [],
            "warnings": [],
            "pihole": None,
        }

        self.progress(5, "Starting self-heal")
        summary["docker_root_changed"] = self._ensure_docker_root()

        self.progress(12, "Checking Docker health")
        if self._docker_needs_repair():
            self.progress(18, "Docker corruption detected — starting repair")
            repaired = self._repair_docker_root()
            summary["docker_repaired"] = repaired
            if repaired:
                self.progress(35, "Docker repair completed")
            else:
                summary["warnings"].append("Docker repair was attempted but Docker still appears unhealthy")
        else:
            self.progress(20, "Docker health check passed")

        self.progress(45, "Rebinding public routes")
        summary["rebound_routes"] = self._rebind_routes()

        plugin_ids = self._installed_plugin_ids()
        total_plugins = max(len(plugin_ids), 1)
        for index, plugin_id in enumerate(plugin_ids, start=1):
            phase_pct = 45 + int((index / total_plugins) * 40)
            self.progress(phase_pct, f"Recovering plugin {plugin_id}")
            try:
                result = self.plugin_runtime.start_plugin(
                    plugin_id,
                    timeout=self.plugin_start_timeout_seconds,
                )
                summary["started_plugins"].append(
                    {"plugin_id": plugin_id, "public_url": result.get("public_url")}
                )
                self.log(f"Recovered plugin {plugin_id}")
            except subprocess.TimeoutExpired as exc:
                warning = f"{plugin_id}: timed out after {exc.timeout}s"
                summary["timed_out_plugins"].append(plugin_id)
                summary["warnings"].append(warning)
                self.log(warning)
                continue
            except subprocess.CalledProcessError as exc:
                handled = self._try_auto_recover_plugin(plugin_id, exc)
                if handled:
                    self.log(f"Retrying plugin {plugin_id} after automatic Docker/image recovery")
                    try:
                        result = self.plugin_runtime.start_plugin(
                            plugin_id,
                            timeout=self.plugin_start_timeout_seconds,
                        )
                        summary["started_plugins"].append(
                            {"plugin_id": plugin_id, "public_url": result.get("public_url")}
                        )
                        self.log(f"Recovered plugin {plugin_id} on retry")
                        continue
                    except subprocess.TimeoutExpired as exc2:
                        warning = f"{plugin_id}: timed out after retry ({exc2.timeout}s)"
                        summary["timed_out_plugins"].append(plugin_id)
                        summary["warnings"].append(warning)
                        self.log(warning)
                    except subprocess.CalledProcessError as exc2:
                        warning = self._format_called_process_error(plugin_id, exc2)
                        summary["warnings"].append(warning)
                        self.log(warning)
                else:
                    warning = self._format_called_process_error(plugin_id, exc)
                    summary["warnings"].append(warning)
                    self.log(warning)
            except Exception as exc:  # noqa: BLE001
                warning = f"{plugin_id}: {exc}"
                summary["warnings"].append(warning)
                self.log(warning)

        self.progress(90, "Checking Pi-hole health")
        summary["pihole"] = self._check_and_fix_pihole()
        self.progress(100, "Self-heal completed")
        return summary

    def _format_called_process_error(self, plugin_id: str, exc: subprocess.CalledProcessError) -> str:
        parts = [f"{plugin_id}: command failed"]
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        if stderr:
            parts.append(f"stderr={stderr[:500]}")
        elif stdout:
            parts.append(f"stdout={stdout[:500]}")
        else:
            parts.append(str(exc))
        return " | ".join(parts)

    def _run_cmd(self, cmd: list[str], *, timeout: int = 60, check: bool = False) -> subprocess.CompletedProcess:
        self.log(f"$ {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True, check=check, timeout=timeout)

    def _ensure_docker_root(self) -> bool:
        """Ensure /etc/docker/daemon.json always points docker data-root to
        settings.docker_root_dir (default: /mnt/nas/homelab/docker).
        Returns True if the file was changed and Docker was restarted."""
        wanted = str(self.settings.docker_root_dir)
        generated = Path("/mnt/nas/homelab/generated/docker-daemon.generated.json")
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text(json.dumps({"data-root": wanted}, indent=2), encoding="utf-8")

        daemon_file = Path("/etc/docker/daemon.json")
        current: dict[str, Any] = {}
        if daemon_file.exists():
            try:
                current = json.loads(daemon_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                current = {}

        if current.get("data-root") == wanted:
            self.log(f"Docker root already set to {wanted}")
            return False

        self.log(f"Updating Docker root to {wanted}")
        current["data-root"] = wanted
        daemon_file.write_text(json.dumps(current, indent=2), encoding="utf-8")
        self._run_cmd(["sudo", "systemctl", "restart", "docker"], timeout=120, check=True)
        return True

    def _docker_needs_repair(self) -> bool:
        """Return True ONLY when Docker is genuinely broken.

        We deliberately do NOT scan journalctl for build-time phrases like
        "failed to solve" — those appear in completely normal Docker build
        output and caused catastrophic false-positives that wiped all stored
        images. Repair is only triggered when the daemon itself is unresponsive
        or the storage layer reports a hard error.
        """
        docker_info = self._run_cmd(["docker", "info"], timeout=45)
        if docker_info.returncode != 0:
            self.log("docker info failed — Docker repair required")
            return True

        images = self._run_cmd(["docker", "images"], timeout=45)
        if images.returncode != 0:
            self.log("docker images failed — Docker repair required")
            return True

        # Only match genuine storage-layer corruption in image listing output.
        # Never include build-time strings (e.g. "failed to solve").
        storage_signatures = [
            "layer does not exist",
            "failed to register layer",
            "failed to load container mount",
            "mount does not exist",
            "not restoring image",
        ]
        combined = f"{images.stdout}\n{images.stderr}".lower()
        if any(sig in combined for sig in storage_signatures):
            self.log("Docker storage corruption detected in image output")
            return True

        return False

    def _repair_docker_root(self) -> bool:
        """Stop Docker, wipe its storage directories, and restart.

        Safety guard: if any containers are currently running the wipe is
        skipped — Docker is operational enough and destroying it would take
        down live services.
        """
        docker_root = Path(self.settings.docker_root_dir)
        self.log(f"Repairing Docker root at {docker_root}")

        ps = self._run_cmd(["docker", "ps", "-q"], timeout=30)
        if ps.returncode == 0 and ps.stdout.strip():
            running = ps.stdout.strip().splitlines()
            self.log(
                f"Aborting Docker repair — {len(running)} running container(s) found. "
                "Docker is operational; wipe skipped to protect live services."
            )
            return False

        metadata_backup = docker_root.parent / "docker_recovery_metadata.json"
        metadata = {
            "docker_root": str(docker_root),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "entries_before_cleanup": sorted([p.name for p in docker_root.iterdir()]) if docker_root.exists() else [],
        }
        metadata_backup.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        self.log(f"Wrote Docker recovery metadata backup to {metadata_backup}")

        self._run_cmd(["sudo", "systemctl", "stop", "docker.socket"], timeout=90)
        self._run_cmd(["sudo", "systemctl", "stop", "docker.service"], timeout=90)

        if docker_root.exists():
            for child in list(docker_root.iterdir()):
                self.log(f"Removing Docker storage entry: {child.name}")
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    try:
                        child.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        pass
        docker_root.mkdir(parents=True, exist_ok=True)

        self._run_cmd(["sudo", "systemctl", "start", "docker.service"], timeout=120, check=True)
        self._run_cmd(["sudo", "systemctl", "start", "docker.socket"], timeout=60)

        info = self._run_cmd(["docker", "info"], timeout=45)
        if info.returncode != 0:
            self.log("Docker still unhealthy after repair")
            return False
        self.log("Docker repair verified via docker info")
        return True

    def _rebind_routes(self) -> list[dict[str, str]]:
        rebound: list[dict[str, str]] = []

        self.caddy_service.ensure_main_caddyfile()
        core_url = self.caddy_service.apply_core_route()
        if core_url:
            rebound.append({"plugin_id": "control-center", "public_url": core_url})

        for plugin_id in self._installed_plugin_ids():
            plugin = self.plugin_registry.get_plugin(plugin_id)
            if not plugin:
                continue
            internal_port = plugin.get("internal_port") or plugin.get("port")
            if not internal_port:
                public_url = plugin.get("public_url")
                if public_url:
                    rebound.append({"plugin_id": plugin_id, "public_url": public_url})
                continue
            try:
                public_url = self.caddy_service.apply_plugin_route(plugin_id, int(internal_port))
            except Exception as exc:  # noqa: BLE001
                self.log(f"Route rebind failed for {plugin_id}: {exc}")
                continue
            if public_url:
                rebound.append({"plugin_id": plugin_id, "public_url": public_url})

        return rebound

    def _installed_plugin_ids(self) -> list[str]:
        installed = self.plugin_registry.list_all()
        return sorted(installed.keys())

    def _try_auto_recover_plugin(self, plugin_id: str, exc: subprocess.CalledProcessError) -> bool:
        message = ""
        if getattr(exc, "stderr", None):
            message += str(exc.stderr)
        if getattr(exc, "stdout", None):
            message += "\n" + str(exc.stdout)
        message = message.lower()

        if any(sig in message for sig in [
            "layer does not exist",
            "unable to get image",
            "failed to register layer",
            "mount does not exist",
        ]):
            self.log(f"Detected Docker/image corruption while recovering {plugin_id}; repairing Docker")
            return self._repair_docker_root()

        return False

    def _check_and_fix_pihole(self) -> dict[str, Any]:
        plugin = self.plugin_registry.get_plugin("pihole")
        if not plugin:
            return {"ok": False, "error": "pihole not installed"}

        local_admin_url = "http://127.0.0.1:8080/admin/"
        result: dict[str, Any] = {"ok": False, "status_code": None, "url": local_admin_url}

        # Enforce the configured password on every heal.
        # Supports Pi-hole v5 (pihole setpassword) and v6 (pihole-FTL --config).
        password = (
            getattr(self.settings, "pihole_password", None)
            or os.getenv("PIHOLE_PASSWORD")
            or "admin"
        )
        subprocess.run(
            ["docker", "exec", "pihole", "pihole", "setpassword", password],
            check=False, capture_output=True, text=True,
        )
        subprocess.run(
            ["docker", "exec", "pihole", "pihole-FTL", "--config",
             f"webserver.api.password={password}"],
            check=False, capture_output=True, text=True,
        )

        try:
            req = urllib.request.Request(local_admin_url, method="GET")
            with urllib.request.urlopen(req, timeout=8) as resp:
                result["ok"] = resp.status in (200, 301, 302)
                result["status_code"] = resp.status
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)

        if result["ok"]:
            result["public_url"] = plugin.get("public_url", "")
        return result
