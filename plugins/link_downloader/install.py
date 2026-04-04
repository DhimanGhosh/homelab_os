from core.plugin_manager.runtime import generic_docker_install, generic_docker_uninstall

def install(settings, extracted, meta):
    return generic_docker_install(settings, extracted, meta, extra_dirs=["data"])

def _unused_uninstall(settings, extracted, meta):
    return generic_docker_uninstall(settings, extracted, meta)
