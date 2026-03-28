# raspi_homelab_python_framework v3 stable

This is a clean fixed framework snapshot meant to make `homelabctl` work for host bootstrap, bundle build, and bundle install.

## Included fixes

- bundle imports always target `homelab_platform`, never `homelab_py`
- `bundle.py` files that were stored with literal `\n` are auto-normalized
- `Settings` now includes `backups_dir`
- runtime install validates `runtime/docker-compose.yml`
- runtime replacement is backup-safe using `/mnt/nas/homelab/backups/<app>.runtime.prev`
- compose calls always use `docker compose -f <compose-file>`
- bootstrap avoids noisy `docker-compose-plugin` failures on Debian/Trixie when the package is unavailable
- Personal Library includes `runtime/data/` and startup creation of the SQLite data directory

## Recommended steps

```bash
cd ~
mv raspi_homelab_python_framework raspi_homelab_python_framework_old_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
unzip raspi_homelab_python_framework_v3_stable.zip -d ~
cd ~/raspi_homelab_python_framework_v3_stable
python3 bootstrap.py
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env
homelabctl build-all-bundles --env-file .env
```

## Clean reinstall of Personal Library

```bash
sudo rm -rf /mnt/nas/homelab/runtime/personal-library
sudo rm -rf /mnt/nas/homelab/apps/personal-library
homelabctl install-bundle --bundle dist/personal-library.app.v1.3.3.tgz --env-file .env
```

## Validate

```bash
curl -v http://127.0.0.1:8132/api/health
sudo docker compose -f /mnt/nas/homelab/runtime/personal-library/docker-compose.yml logs --no-color --tail=200
```
