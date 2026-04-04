
# Troubleshooting

## Plugin health fails after install
- inspect install log under `runtime/logs/`
- inspect generated Caddy snippet under `/etc/caddy/apps/`
- verify Docker root path matches settings

## Control shell does not start
- verify `plugins/control_center/backend/app/` exists
- verify control center requirements were installed
- verify port 8444 is not already occupied

## Tailscale cert issues
- rerun host bootstrap to regenerate certs
- verify cert files exist in `tailscale_cert_dir`
