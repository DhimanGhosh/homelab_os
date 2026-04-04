# Homelab OS

Plugin-based Raspberry Pi homelab control platform.

## Step 1 status

This repo currently includes:

- bootstrap flow
- Python packaging
- CLI foundation
- config loading
- FastAPI core app foundation
- runtime directory initialization

Plugin builder, installer, runtime, reverse proxy, and migrated plugins will be added in the next steps.

## Quick start

```bash
cd ~/homelab_os
python3 bootstrap.py
source .venv/bin/activate
homelabctl bootstrap-host --env-file .env
homelabctl show-settings --env-file .env
```


## Important installation note

Always work inside the virtual environment before running `pip install -e .`:

```bash
cd ~/homelab_os
source .venv/bin/activate
pip install -e .
```

If you run `pip install -e .` outside the virtual environment on Debian/Raspberry Pi OS, you may see the `externally-managed-environment` error from PEP 668.
