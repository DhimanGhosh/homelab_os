# Deep Debugging Guide

## Docker EOF Error

Symptoms:
- docker compose fails
- EOF error

Root Cause:
- Docker daemon crash
- Storage corruption

Fix:
1. Restart docker
2. Check root dir
3. Run recovery

---

## Pi-hole not working on Tailscale

Symptoms:
- Internet not working

Root Cause:
- DNS chain broken

Fix:
- Restart cloudflared
- Ensure port 5053 listening

---

## CC not loading

Symptoms:
- 8444 unreachable

Root Cause:
- Caddy not routing

Fix:
- Restart Caddy
- Check config

---

## Random reboot

Cause:
- Recovery triggered reboot

This is intentional for:
- Docker root fix