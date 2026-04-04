
from uninstall import uninstall
from install import install

def upgrade(settings, extracted, meta):
    try:
        uninstall(settings, extracted, meta)
    except Exception:
        pass
    return install(settings, extracted, meta)
