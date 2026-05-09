# Homelab OS v3.2.1 — Recovery hardening patch

## Why this patch exists

During recovery, Docker containers were running but working-state sync skipped some plugins because the code checked only the plugin id as the Docker container name. In the real system, some plugin ids and container names differ:

- `files` plugin id -> `homelab-files` container
- `status` plugin id -> `pi-statusboard` container

This caused `homelabctl sync-working-state --healthy-only` to skip working apps and left no snapshot for self-heal to restore.

## Fixes included

1. Working-state sync now resolves containers using:
   - Docker Compose project label `com.docker.compose.project`.
   - Docker Compose service label `com.docker.compose.service`.
   - Explicit `container_name` from `docker-compose.yml`.
   - Compose service names and generated names.
   - Exact plugin id fallback.
2. Install rollback no longer throws a large traceback when there is no last-known-good snapshot.
3. Control Center cards now show:
   - Actual resolved container name.
   - Container lookup source.
   - Health source (`docker-healthcheck`, `docker-running`, `docker-state`, or `not-found`).
4. Working-state metadata stores resolved container details.
5. `/` now permanently redirects to `/api/control-center` through code instead of requiring a manual edit.

## Completed recovery runbook

Use this if plugin installation fails because of Docker/BuildKit or NAS write instability.

### 1. Stop watchdog before recovery or plugin installs

```bash
cd ~/homelab_os
source .venv/bin/activate
sudo systemctl stop homelab-watchdog.service 2>/dev/null || true
```

### 2. Stop non-Pi-hole containers before Docker cache cleanup

```bash
docker ps --format '{{.Names}}' | grep -v '^pihole$' | xargs -r docker stop
```

### 3. Clean Docker build cache

```bash
docker builder prune -af
docker buildx prune -af 2>/dev/null || true
docker system prune -af
```

### 4. Restart Docker

```bash
sudo systemctl restart docker
sleep 10
docker info >/dev/null && echo "Docker is back"
```

### 5. Pull common base images manually

```bash
docker pull python:3.11-slim
docker pull python:3.11
```

### 6. If a heavy plugin still fails with BuildKit metadata/blob errors

Reset only BuildKit cache:

```bash
sudo systemctl stop homelab-watchdog.service 2>/dev/null || true
sudo systemctl stop docker.socket docker
sudo rm -rf /mnt/nas/homelab/docker/buildkit
sudo systemctl start docker
sleep 10
docker pull python:3.11
docker pull python:3.11-slim
```

For a heavy plugin such as Song Downloader, retry with BuildKit disabled:

```bash
cd ~/homelab_os/runtime/installed_plugins/song-downloader/docker
DOCKER_BUILDKIT=0 docker compose -p song-downloader build --pull --no-cache
DOCKER_BUILDKIT=0 docker compose -p song-downloader up -d --force-recreate --remove-orphans
```

### 7. If NAS/Docker root shows I/O errors

Stop writers:

```bash
sudo systemctl stop homelab-watchdog.service 2>/dev/null || true
sudo systemctl stop homelab-os-core.service 2>/dev/null || true
sudo systemctl stop docker.socket docker 2>/dev/null || true
sudo systemctl stop caddy 2>/dev/null || true
```

Unmount and repair:

```bash
sudo umount /mnt/nas
findmnt /mnt/nas || echo "/mnt/nas is unmounted"
findmnt /dev/sda1 || echo "/dev/sda1 is unmounted"
sudo e2fsck -f -y /dev/sda1
sudo mount /mnt/nas
```

Test writes:

```bash
sudo touch /mnt/nas/homelab/docker/.write_test
sudo rm /mnt/nas/homelab/docker/.write_test
echo "NAS docker write OK"
```

### 8. Restore Tailscale/MagicDNS self-resolution on the Pi

```bash
TS_IP="$(tailscale ip -4 | head -n1)"
sudo cp /etc/hosts /etc/hosts.bak.$(date +%Y%m%d_%H%M%S)
sudo sed -i '/pi-nas.taild4713b.ts.net/d' /etc/hosts
sudo sed -i '/ pi-nas$/d' /etc/hosts
echo "$TS_IP pi-nas.taild4713b.ts.net pi-nas" | sudo tee -a /etc/hosts
getent hosts pi-nas.taild4713b.ts.net
```

### 9. Give Docker containers Tailscale DNS first

```bash
sudo python3 - <<'PY'
import json
from pathlib import Path
path = Path('/etc/docker/daemon.json')
data = json.loads(path.read_text()) if path.exists() else {}
data['data-root'] = data.get('data-root', '/mnt/nas/homelab/docker')
data['log-driver'] = data.get('log-driver', 'json-file')
data['log-opts'] = data.get('log-opts', {'max-size': '10m', 'max-file': '3'})
data['dns'] = ['100.100.100.100', '1.1.1.1', '8.8.8.8']
path.write_text(json.dumps(data, indent=2))
print(path.read_text())
PY
sudo systemctl restart docker
sleep 10
```

### 10. Start Pi-hole and Caddy first

```bash
homelabctl start-plugin pihole --env-file .env
sudo systemctl restart caddy
sudo systemctl restart homelab-os-core.service
```

Verify:

```bash
curl -I http://127.0.0.1:8080/admin/ || true
sudo ss -ltnp | grep -E ':8444|:8447|:8080'
```

### 11. Start/reinstall plugins one by one

Start existing containers first:

```bash
homelabctl start-plugin status --env-file .env
homelabctl start-plugin files --env-file .env
homelabctl start-plugin api-gateway --env-file .env
homelabctl start-plugin dictionary --env-file .env
homelabctl start-plugin expense-tracker --env-file .env
homelabctl start-plugin link-downloader --env-file .env
homelabctl start-plugin personal-library --env-file .env
homelabctl start-plugin music-player --env-file .env
```

Install only the plugin that fails to start, rather than bulk reinstalling everything.

### 12. Save working state only after apps open correctly

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
homelabctl sync-working-state --env-file .env --healthy-only
homelabctl list-working-state --env-file .env
```

### 13. Restart watchdog last

```bash
sudo systemctl start homelab-watchdog.service
sudo systemctl status homelab-watchdog.service --no-pager
```
