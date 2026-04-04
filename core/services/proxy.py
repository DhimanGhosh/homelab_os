from core.services.process_runner import run, sudo_write_file


class CaddyService:
    def __init__(self, settings):
        self.settings = settings

    def write_base(self):
        content = f"""{{
    auto_https off
}}

import {self.settings.caddy_apps_dir}/*.caddy
"""
        sudo_write_file(self.settings.caddyfile, content)

    def validate(self):
        run(['sudo', 'caddy', 'validate', '--config', str(self.settings.caddyfile)])

    def restart(self):
        run(['sudo', 'systemctl', 'restart', 'caddy'])



from pathlib import Path
from core.services.process_runner import sudo_write_file, run

def write_plugin_snippet(settings, plugin_meta: dict) -> Path:
    upstream = str(plugin_meta["local_upstream"]).replace("http://", "").replace("https://", "")
    content = f"""https://{settings.tailscale_fqdn}:{int(plugin_meta['network']['public_port'])} {{
    tls {settings.tailscale_cert_dir / (settings.tailscale_fqdn + '.crt')} {settings.tailscale_cert_dir / (settings.tailscale_fqdn + '.key')}
    encode gzip
    reverse_proxy {upstream} {{
        header_up X-Forwarded-Proto https
        header_up Host {host}
        header_up X-Forwarded-For {remote_host}
    }}
}}
"""
    path = settings.caddy_apps_dir / f"{plugin_meta['id']}.caddy"
    sudo_write_file(path, content)
    return path
