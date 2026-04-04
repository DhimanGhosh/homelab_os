from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import typer

from homelab_os.core.config import ensure_runtime_dirs, load_settings
from homelab_os.core.plugin_manager import PluginBuilder, PluginInstaller
from homelab_os.core.plugin_manager.runtime import PluginRuntime
from homelab_os.core.services.jobs import JobStore
from homelab_os.core.services.logging_service import LoggingService

app = typer.Typer(help="homelab_os command line interface")


def _job_services(env_file: str):
    settings = load_settings(env_file)
    ensure_runtime_dirs(settings)
    job_store = JobStore(settings.manifests_dir / "jobs.json")
    logger = LoggingService(settings.runtime_jobs_dir)
    return settings, job_store, logger


@app.command("bootstrap-host")
def bootstrap_host(env_file: str = ".env") -> None:
    settings = load_settings(env_file)
    ensure_runtime_dirs(settings)

    typer.echo("Host bootstrap completed.")
    typer.echo("")
    typer.echo("Resolved settings:")
    typer.echo(f"  Hostname           : {settings.hostname}")
    typer.echo(f"  LAN IP             : {settings.lan_ip}")
    typer.echo(f"  Tailscale IP       : {settings.tailscale_ip}")
    typer.echo(f"  Tailscale FQDN     : {settings.tailscale_fqdn}")
    typer.echo(f"  NAS mount          : {settings.nas_mount}")
    typer.echo(f"  Docker root dir    : {settings.docker_root_dir}")
    typer.echo(f"  Build dir          : {settings.build_dir}")
    typer.echo(f"  Plugins dir        : {settings.plugins_dir}")
    typer.echo(f"  Runtime dir        : {settings.runtime_dir}")


@app.command("show-settings")
def show_settings(env_file: str = ".env") -> None:
    settings = load_settings(env_file)
    ensure_runtime_dirs(settings)

    for key, value in asdict(settings).items():
        typer.echo(f"{key}: {value}")


@app.command("build-all-plugins")
def build_all_plugins(env_file: str = ".env") -> None:
    settings, job_store, logger = _job_services(env_file)
    builder = PluginBuilder()
    count = 0

    job = job_store.create_job("build_all_plugins", "all", {"plugins_dir": str(settings.plugins_dir)})
    logger.append_job_log(job["job_id"], "Starting build-all-plugins")

    try:
        if not settings.plugins_dir.exists():
            logger.append_job_log(job["job_id"], f"Plugins directory does not exist: {settings.plugins_dir}")
            job_store.update_job(job["job_id"], status="failed", progress=100)
            typer.echo(f"Plugins directory does not exist: {settings.plugins_dir}")
            raise typer.Exit(code=1)

        plugin_dirs = [
            source_dir for source_dir in sorted(settings.plugins_dir.iterdir())
            if source_dir.is_dir() and (source_dir / "plugin.json").exists()
        ]
        total = max(len(plugin_dirs), 1)

        for index, source_dir in enumerate(plugin_dirs, start=1):
            archive_path = settings.build_dir / f"{source_dir.name}.tgz"
            logger.append_job_log(job["job_id"], f"Building {source_dir.name} -> {archive_path}")
            builder.build_plugin_archive(source_dir, archive_path)
            typer.echo(f"Built {archive_path}")
            count += 1
            progress = int((index / total) * 100)
            job_store.update_job(job["job_id"], status="running", progress=progress)

        logger.append_job_log(job["job_id"], f"Built {count} plugin archives")
        job_store.update_job(job["job_id"], status="completed", progress=100, result={"count": count})
        typer.echo(f"Built {count} plugin archives")
    except Exception as exc:
        logger.append_job_log(job["job_id"], f"Build failed: {exc}")
        job_store.update_job(job["job_id"], status="failed", progress=100, error=str(exc))
        raise


@app.command("install-plugin")
def install_plugin(plugin_archive: Path, env_file: str = ".env") -> None:
    settings, job_store, logger = _job_services(env_file)
    installer = PluginInstaller(
        settings=settings,
        installed_plugins_dir=settings.runtime_installed_plugins_dir,
        registry_file=settings.manifests_dir / "installed_plugins.json",
        state_file=settings.manifests_dir / "plugin_state.json",
    )

    job = job_store.create_job("install_plugin", str(plugin_archive), {"archive": str(plugin_archive)})
    logger.append_job_log(job["job_id"], f"Starting install for {plugin_archive}")

    try:
        job_store.update_job(job["job_id"], status="running", progress=10)
        result = installer.install_plugin(plugin_archive)
        logger.append_job_log(job["job_id"], f"Installed plugin: {result['name']} ({result['version']})")
        logger.append_job_log(job["job_id"], f"Installed dir: {result['installed_dir']}")
        if result.get("public_url"):
            logger.append_job_log(job["job_id"], f"Open URL: {result['public_url']}")
        job_store.update_job(job["job_id"], status="completed", progress=100, result=result)

        typer.echo(f"Installed plugin: {result['name']} ({result['version']})")
        typer.echo(f"Installed dir: {result['installed_dir']}")
        if result.get("public_url"):
            typer.echo(f"Open URL: {result['public_url']}")
        typer.echo(f"Job ID: {job['job_id']}")
    except Exception as exc:
        logger.append_job_log(job["job_id"], f"Install failed: {exc}")
        job_store.update_job(job["job_id"], status="failed", progress=100, error=str(exc))
        raise


@app.command("start-plugin")
def start_plugin(plugin_id: str, env_file: str = ".env") -> None:
    settings, job_store, logger = _job_services(env_file)
    runtime = PluginRuntime(
        settings.runtime_installed_plugins_dir,
        settings.manifests_dir / "plugin_state.json",
    )
    job = job_store.create_job("start_plugin", plugin_id, {"plugin_id": plugin_id})
    logger.append_job_log(job["job_id"], f"Starting plugin {plugin_id}")

    try:
        job_store.update_job(job["job_id"], status="running", progress=25)
        result = runtime.start_plugin(plugin_id)
        logger.append_job_log(job["job_id"], str(result))
        job_store.update_job(job["job_id"], status="completed", progress=100, result=result)
        typer.echo(str(result))
        typer.echo(f"Job ID: {job['job_id']}")
    except Exception as exc:
        logger.append_job_log(job["job_id"], f"Start failed: {exc}")
        job_store.update_job(job["job_id"], status="failed", progress=100, error=str(exc))
        raise


@app.command("stop-plugin")
def stop_plugin(plugin_id: str, env_file: str = ".env") -> None:
    settings, job_store, logger = _job_services(env_file)
    runtime = PluginRuntime(
        settings.runtime_installed_plugins_dir,
        settings.manifests_dir / "plugin_state.json",
    )
    job = job_store.create_job("stop_plugin", plugin_id, {"plugin_id": plugin_id})
    logger.append_job_log(job["job_id"], f"Stopping plugin {plugin_id}")

    try:
        job_store.update_job(job["job_id"], status="running", progress=25)
        result = runtime.stop_plugin(plugin_id)
        logger.append_job_log(job["job_id"], str(result))
        job_store.update_job(job["job_id"], status="completed", progress=100, result=result)
        typer.echo(str(result))
        typer.echo(f"Job ID: {job['job_id']}")
    except Exception as exc:
        logger.append_job_log(job["job_id"], f"Stop failed: {exc}")
        job_store.update_job(job["job_id"], status="failed", progress=100, error=str(exc))
        raise


@app.command("restart-plugin")
def restart_plugin(plugin_id: str, env_file: str = ".env") -> None:
    settings, job_store, logger = _job_services(env_file)
    runtime = PluginRuntime(
        settings.runtime_installed_plugins_dir,
        settings.manifests_dir / "plugin_state.json",
    )
    job = job_store.create_job("restart_plugin", plugin_id, {"plugin_id": plugin_id})
    logger.append_job_log(job["job_id"], f"Restarting plugin {plugin_id}")

    try:
        job_store.update_job(job["job_id"], status="running", progress=25)
        result = runtime.restart_plugin(plugin_id)
        logger.append_job_log(job["job_id"], str(result))
        job_store.update_job(job["job_id"], status="completed", progress=100, result=result)
        typer.echo(str(result))
        typer.echo(f"Job ID: {job['job_id']}")
    except Exception as exc:
        logger.append_job_log(job["job_id"], f"Restart failed: {exc}")
        job_store.update_job(job["job_id"], status="failed", progress=100, error=str(exc))
        raise


@app.command("healthcheck-plugin")
def healthcheck_plugin(plugin_id: str, env_file: str = ".env") -> None:
    settings, job_store, logger = _job_services(env_file)
    runtime = PluginRuntime(
        settings.runtime_installed_plugins_dir,
        settings.manifests_dir / "plugin_state.json",
    )
    job = job_store.create_job("healthcheck_plugin", plugin_id, {"plugin_id": plugin_id})
    logger.append_job_log(job["job_id"], f"Healthchecking plugin {plugin_id}")

    try:
        job_store.update_job(job["job_id"], status="running", progress=25)
        result = runtime.healthcheck_plugin(plugin_id)
        logger.append_job_log(job["job_id"], str(result))
        job_store.update_job(job["job_id"], status="completed", progress=100, result=result)
        typer.echo(str(result))
        typer.echo(f"Job ID: {job['job_id']}")
    except Exception as exc:
        logger.append_job_log(job["job_id"], f"Healthcheck failed: {exc}")
        job_store.update_job(job["job_id"], status="failed", progress=100, error=str(exc))
        raise


@app.command("run-control-shell")
def run_control_shell(env_file: str = ".env") -> None:
    settings = load_settings(env_file)
    ensure_runtime_dirs(settings)
    typer.echo(
        f"Control shell placeholder. Target bind: "
        f"{settings.control_center_bind}:{settings.control_center_port}"
    )


if __name__ == "__main__":
    app()
