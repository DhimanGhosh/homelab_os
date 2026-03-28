# Architecture

## Layers
1. Flask Control Center UI
2. Typer CLI (`homelabctl`)
3. Bundle installer/builder services
4. Runtime helpers for Docker + Caddy + Tailscale certs
5. Recovery subsystem for Docker/Caddy/Pi-hole/cloudflared

## Bundle model
Each bundle lives under `bundle_specs/<bundle-name>/` and contains `metadata.json`, `bundle.py`, and optional runtime/app files.
