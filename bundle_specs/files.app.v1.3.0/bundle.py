from pathlib import Path
from homelab_platform.services.bundle_runtime import generic_docker_install, generic_docker_uninstall

def install(settings, extracted, meta):
    extra = [Path('/mnt/nas/Incoming'), Path('/mnt/nas/media/music'), Path('/mnt/nas/media/videos/Movies')]
    return generic_docker_install(settings, extracted, meta, extra_dirs=extra)

def uninstall(settings, extracted, meta):
    return generic_docker_uninstall(settings, extracted, meta)
