# Bundle System Deep Dive

Each bundle:
- metadata.json
- bundle.py
- docker-compose.yml

Installer flow:
bundle_installer → bundle_runtime → docker

No shell scripts used.