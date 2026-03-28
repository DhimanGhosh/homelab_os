from pathlib import Path
from homelab_platform.services.subprocesses import run

def install_recovery_system(settings):
    recovery_root = Path(__file__).resolve().parents[2] / 'recovery' / 'self_recovery_v3_4'
    run(['bash', str(recovery_root / 'scripts' / 'install_self_healing_v3_4.sh')], capture=False)

def recover_stack(settings):
    env = [
        f'PIHOLE_PASSWORD={settings.pihole_password}',
        f'DOCKER_ROOT_DIR={settings.docker_root_dir}',
        f'CLOUDFLARED_IMAGE={settings.cloudflared_image}',
        f'FRAMEWORK_CC_SERVICE={settings.framework_cc_service}',
        f'LEGACY_CC_SERVICE={settings.legacy_cc_service}',
        f'ALLOW_REBOOT={1 if settings.allow_reboot else 0}',
    ]
    run(['sudo', 'env', *env, '/usr/local/bin/homelab-recover'], capture=False)
