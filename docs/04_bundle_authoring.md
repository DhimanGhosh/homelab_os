# Bundle Authoring

## Minimal Python bundle
```python
from homelab_py.services.bundle_runtime import generic_docker_install, generic_docker_uninstall

def install(settings, extracted, meta):
    return generic_docker_install(settings, extracted, meta)

def uninstall(settings, extracted, meta):
    return generic_docker_uninstall(settings, extracted, meta)
```

## Build one bundle
```bash
homelabctl build-bundle --source-dir bundle_specs/myapp.app.v1.0.0 --output-path dist/myapp.app.v1.0.0.tgz
```

## Scaffold a new bundle
```bash
homelabctl scaffold-app --app-id myapp --version 1.0.0
```
