from homelab_platform.services.subprocesses import run, sudo_write_file
class CaddyService:
    def __init__(self, settings): self.settings = settings
    def write_base(self):
        content = f'''{{
    auto_https off
}}

https://{self.settings.tailscale_fqdn}:{self.settings.control_center_public_port} {{
    tls {self.settings.tailscale_cert_dir/(self.settings.tailscale_fqdn+'.crt')} {self.settings.tailscale_cert_dir/(self.settings.tailscale_fqdn+'.key')}
    reverse_proxy {self.settings.control_center_local}
}}

https://{self.settings.tailscale_fqdn}:{self.settings.pihole_public_port} {{
    tls {self.settings.tailscale_cert_dir/(self.settings.tailscale_fqdn+'.crt')} {self.settings.tailscale_cert_dir/(self.settings.tailscale_fqdn+'.key')}
    reverse_proxy {self.settings.pihole_local}
}}

import {self.settings.caddy_apps_dir}/*.caddy
'''
        sudo_write_file(self.settings.caddyfile, content)
    def validate(self): run(['sudo','caddy','validate','--config',str(self.settings.caddyfile)])
    def restart(self): run(['sudo','systemctl','restart','caddy'])
