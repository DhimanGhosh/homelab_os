import requests, subprocess
from core.services.process_runner import docker_healthy, docker_root, is_port_listening

def enforce_docker_root(settings) -> bool:
    current = docker_root()
    return bool(current) and current == str(settings.docker_root_dir)

def check_caddy(settings) -> bool:
    return is_port_listening(settings.control_center_public_port)

def check_cc_backend(settings) -> bool:
    try:
        r = requests.get(f'http://{settings.control_center_local}/api/health', timeout=3)
        return r.status_code < 500
    except Exception:
        return False

def check_pihole(settings) -> bool:
    try:
        r = requests.get(f'http://{settings.pihole_local}/admin/', timeout=4)
        return r.status_code < 500
    except Exception:
        return False

def check_cloudflared() -> bool:
    return ':5053' in subprocess.run(['ss', '-lntup'], text=True, capture_output=True).stdout

def check_8444_owned_by_caddy() -> bool:
    owner = subprocess.run(['bash', '-lc', "ss -lntp | awk '$4 ~ /:8444$/ {print $0}' | head -n1"], text=True, capture_output=True).stdout
    return bool(owner.strip()) and 'users:(("caddy"' in owner

def docker_is_healthy() -> bool:
    return docker_healthy()

def health_snapshot(settings) -> dict:
    return {
        'docker_healthy': docker_is_healthy(),
        'docker_root_ok': enforce_docker_root(settings),
        'caddy_port_ok': check_caddy(settings),
        'cc_backend_ok': check_cc_backend(settings),
        'pihole_ok': check_pihole(settings),
        'cloudflared_ok': check_cloudflared(),
        'port_8444_owned_by_caddy': check_8444_owned_by_caddy(),
    }
