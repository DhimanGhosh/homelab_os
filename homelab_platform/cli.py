import json, os
from pathlib import Path
import typer
from homelab_platform.config import Settings
from homelab_platform.services.bootstrap import BootstrapService
from homelab_platform.services.bundle_builder import BundleBuilder
from homelab_platform.services.bundle_installer import BundleInstaller
from homelab_platform.services.recovery import recover_stack
from homelab_platform.services.subprocesses import is_port_listening
from homelab_platform.services.health import health_snapshot
app = typer.Typer(help='Raspi Homelab Python Framework CLI')
@app.command('bootstrap-host')
def bootstrap_host(env_file:str='.env'):
    BootstrapService(Settings.from_env_file(env_file)).bootstrap(); typer.echo('Host bootstrap completed.')
@app.command('show-settings')
def show_settings(env_file:str='.env'): typer.echo(json.dumps(Settings.from_env_file(env_file).to_dict(), indent=2, default=str))
@app.command('list-bundles')
def list_bundles(env_file:str='.env'):
    s=Settings.from_env_file(env_file); typer.echo('\n'.join(sorted([p.name for p in s.dist_dir.glob('*.tgz')])) if s.dist_dir.exists() else '')
@app.command('build-bundle')
def build_bundle(source_dir:str=typer.Option(...), output_path:str=typer.Option(...), env_file:str='.env'):
    Settings.from_env_file(env_file); typer.echo(f'Built {BundleBuilder().build_tgz(Path(source_dir), Path(output_path))}')
@app.command('build-all-bundles')
def build_all_bundles(env_file:str='.env'):
    s=Settings.from_env_file(env_file); count=0
    for src in sorted(s.bundle_specs_dir.iterdir()):
        if src.is_dir() and (src/'metadata.json').exists():
            out=s.dist_dir/f'{src.name}.tgz'; BundleBuilder().build_tgz(src, out); typer.echo(f'Built {out}'); count+=1
    typer.echo(f'Built {count} bundles')
@app.command('install-bundle')
def install_bundle(bundle:str=typer.Option(...), env_file:str='.env'): typer.echo(BundleInstaller(Settings.from_env_file(env_file)).install(Path(bundle))['message'])
@app.command('remove-app')
def remove_app(app_id:str=typer.Option(...), env_file:str='.env'): typer.echo(BundleInstaller(Settings.from_env_file(env_file)).remove_app(app_id)['message'])
@app.command('run-control-center')
def run_control_center(env_file:str='.env'):
    s=Settings.from_env_file(env_file)
    if is_port_listening(s.control_center_public_port): typer.echo(f'Port {s.control_center_public_port} is already in use.'); raise typer.Exit(code=0)
    os.environ['HOMELAB_ENV_FILE']=env_file
    from homelab_platform.web import app as flask_app
    from waitress import serve
    serve(flask_app, host=s.control_center_bind, port=s.control_center_port)
@app.command('health-check')
def health_check(env_file:str='.env'): typer.echo(json.dumps(health_snapshot(Settings.from_env_file(env_file)), indent=2))
@app.command('recover-stack')
def recover_stack_command(env_file:str='.env'): recover_stack(Settings.from_env_file(env_file))
