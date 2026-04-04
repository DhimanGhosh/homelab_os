
from pathlib import Path
import subprocess

BASE_DOMAIN = "pi-nas.taild4713b.ts.net"
CADDY_APPS_DIR = Path("/etc/caddy/apps")

PORT_MAP = {
    "control-center": 8444,
    "pihole": 8447,
    "files": 8449,
    "status": 8451,
    "voice-ai": 8452,
    "homarr": 8453,
    "personal-library": 8454,
    "dictionary": 8455,
    "api-gateway": 8456,
    "music-player": 8459,
    "link-downloader": 8460
}

def apply_config(plugin_id, internal_port):
    public_port = PORT_MAP.get(plugin_id)
    if not public_port:
        raise Exception(f"No port mapping for {plugin_id}")

    config = f"{BASE_DOMAIN}:{public_port} {{ reverse_proxy 127.0.0.1:{internal_port} }}"

    CADDY_APPS_DIR.mkdir(parents=True, exist_ok=True)
    (CADDY_APPS_DIR / f"{plugin_id}.caddy").write_text(config)

    subprocess.run(["sudo", "systemctl", "reload", "caddy"])

    return public_port
