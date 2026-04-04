from pathlib import Path
from core.plugin_manager.runtime import generic_docker_install, generic_docker_uninstall

def _unused_install(settings, extracted, meta):
    extra = [Path('/mnt/nas/Incoming'), Path('/mnt/nas/media/music'), Path('/mnt/nas/media/videos/Movies')]
    return generic_docker_install(settings, extracted, meta, extra_dirs=extra)

def uninstall(settings, extracted, meta):
    return generic_docker_uninstall(settings, extracted, meta)
