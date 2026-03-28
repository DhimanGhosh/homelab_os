
from pathlib import Path
from homelab_platform.services.subprocesses import run, sudo_write_text

def install(settings, extracted, meta):
    base = settings.homelab_root / 'control-center'
    app = base / 'app'
    app_new = base / 'app.new'
    app_prev = base / 'app.prev'
    venv = base / 'venv'
    data = base / 'data'
    logs = base / 'logs'
    run(['sudo','mkdir','-p',str(base),str(data),str(logs),str(settings.installers_dir),str(settings.apps_dir),str(settings.caddy_snippets_dir),str(settings.caddy_certs_dir)])
    if app_new.exists(): run(['sudo','rm','-rf',str(app_new)])
    run(['sudo','mkdir','-p',str(app_new)])
    run(['sudo','cp','-a',str(extracted/'app') + '/.', str(app_new)])
    if not venv.exists(): run(['python3','-m','venv',str(venv)])
    pip = venv / 'bin' / 'pip'
    run([str(pip), 'install', '--upgrade', 'pip'])
    run([str(pip), 'install', '-r', str(app_new/'requirements.txt')])
    if app_prev.exists(): run(['sudo','rm','-rf',str(app_prev)])
    if app.exists(): run(['sudo','mv',str(app),str(app_prev)])
    run(['sudo','mv',str(app_new),str(app)])
    (base/'VERSION').write_text(meta['version'])
    service = f"[Unit]
Description=Pi Control Center
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory={app}
Environment=PYTHONUNBUFFERED=1
Environment=TAILSCALE_FQDN={settings.tailscale_fqdn}
ExecStart={venv}/bin/python -m uvicorn app:app --host 127.0.0.1 --port 9000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"
    sudo_write_text(Path('/etc/systemd/system/pi-control-center.service'), service)
    run(['sudo','systemctl','daemon-reload'])
    run(['sudo','systemctl','enable','pi-control-center'], check=False)
    run(['sudo','systemctl','restart','pi-control-center'], check=False)
    return {'ok': True, 'message': f"Installed Control Center {meta['version']}"}

def uninstall(settings, extracted, meta):
    return {'ok': False, 'message': 'Control Center uninstall disabled'}
