# Folder map

See README for quick start.

- homelab_platform/cli.py - CLI entrypoints
- homelab_platform/web.py - Control Center Flask backend
- homelab_platform/services/bundle_runtime.py - shared Python install helpers
- bundle_specs/control_center_bundle_v1_6_6/ - Control Center OTA source
- bundle_specs/pihole.app.v1.2.4/ - Pi-hole source
- bundle_specs/dictionary.app.v1.4.5/ - safe Python test app
- bundle_specs/<app>/runtime/ - Dockerfile, compose, app code
- bundle_specs/<app>/bundle.py - Python installer
- reference_uploads/ - original uploaded files used as references
