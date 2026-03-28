# Control Center bundle

Edit: `bundle_specs/control_center_bundle_v1_6_6/`

Important files:
- `app/app.py`
- `app/requirements.txt`
- `systemd/pi-control-center.service`
- `bundle.py`
- `metadata.json`

Rebuild:
```bash
source .venv/bin/activate
homelabctl build-bundle --source-dir bundle_specs/control_center_bundle_v1_6_6 --output-path dist/control_center_bundle_v1_6_6.tgz
```
