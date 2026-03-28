from homelab_platform.services.subprocesses import run

def install(settings, extracted, meta):
    project_root=settings.env_file.parent
    run(['bash','-lc', f'source {project_root}/.venv/bin/activate && homelabctl build-all-bundles --env-file {settings.env_file}'], capture=False)
    run(['sudo','systemctl','restart', settings.control_center_service_name], check=False)
    run(['sudo','systemctl','restart', settings.watchdog_service_name], check=False)
    run(['sudo','systemctl','restart', 'caddy'], check=False)
    return {'ok':True,'message':f'Control Center refreshed -> https://{settings.tailscale_fqdn}:{settings.control_center_public_port}/'}

def uninstall(settings, extracted, meta):
    return {'ok':True,'message':'Control Center bundle uninstall is disabled for safety.'}
