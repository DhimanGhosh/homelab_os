from homelab_platform.services.bundle_runtime import metadata_only_install, metadata_only_uninstall

def install(settings, extracted, meta):
    return metadata_only_install(settings, extracted, meta)

def uninstall(settings, extracted, meta):
    return metadata_only_uninstall(settings, extracted, meta)
