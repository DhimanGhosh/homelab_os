
from homelab_platform.services.bundle_runtime import ensure_tailscale_cert, write_caddy_snippet, record_install_state, remove_caddy_snippet
from homelab_platform.services.subprocesses import run

def install(settings, extracted, meta):
    run(['sudo','mkdir','-p',str(settings.apps_dir/meta['id']), str(settings.runtime_dir), str(settings.caddy_snippets_dir), str(settings.caddy_certs_dir)])
    ensure_tailscale_cert(settings)
    run(['sudo','docker','rm','-f','cloudflared'], check=False)
    run(['sudo','docker','run','-d','--name','cloudflared','--restart','unless-stopped','--network','host','cloudflare/cloudflared:latest','proxy-dns','--address','127.0.0.1','--port','5053','--upstream','https://1.1.1.1/dns-query','--upstream','https://1.0.0.1/dns-query'], check=False)
    run(['sudo','docker','rm','-f','pihole'], check=False)
    run(['sudo','docker','run','-d','--name','pihole','--restart=unless-stopped','-p','53:53/tcp','-p','53:53/udp','-p','8080:80','-e',f'TZ={settings.tz}','-e',f'WEBPASSWORD={settings.pihole_password}','pihole/pihole:latest'])
    write_caddy_snippet(settings, meta)
    record_install_state(settings, extracted, meta, {'recovery_mode':'python port of reset_caddy_and_pihole_bundle'})
    return {'ok': True, 'message': f"Installed Pi-hole -> https://{settings.tailscale_fqdn}:{meta['port']}{meta['open_path']}"}

def uninstall(settings, extracted, meta):
    remove_caddy_snippet(settings, meta['id'])
    run(['sudo','docker','rm','-f','pihole'], check=False)
    run(['sudo','rm','-rf',str(settings.apps_dir/meta['id'])], check=False)
    return {'ok': True, 'message': 'Removed pihole'}
