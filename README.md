# Raspi Homelab Python Framework

This is a production-grade Python-based homelab framework designed for Raspberry Pi.

## Core Features
- Flask-based Control Center (UI + API)
- CLI (`homelabctl`) for full control
- TGZ-based app bundle system
- Real-time watchdog (self-healing)
- Docker root enforcement (HDD)
- Fully automated recovery system
- Safe reverse proxy architecture using Caddy
- Tailscale-first secure access

---

## Architecture Overview

Browser → Tailscale → Caddy (8444) → Control Center (9000)

Docker Apps → Caddy → Public Ports (8445+)

Pi-hole → Cloudflared → Internet DNS

---

## Quick Start

```bash
python3 bootstrap.py
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env
homelabctl build-all-bundles --env-file .env
```

---

## Key Rules

1. Docker MUST use HDD
2. Caddy owns port 8444
3. No Docker restart during app install
4. Watchdog runs continuously
5. Recovery auto-triggers on failure

---

## Folder Structure

- homelab_platform/
- bundle_specs/
- dist/
- recovery/
- docs/
- systemd/

---

## How to Modify Apps

1. Edit bundle in `bundle_specs/`
2. Build `.tgz`
3. Install via CLI or UI

---

## Important Commands

```bash
homelabctl install-bundle
homelabctl remove-app
homelabctl recover-stack
homelabctl health-check
```

---

## Production Notes

- Always keep Docker root on HDD
- Never expose backend directly
- Always use Caddy reverse proxy