
import tarfile, json, shutil
from pathlib import Path
from homelab_os.core.services.reverse_proxy import apply_config

RUNTIME = Path("/mnt/nas/homelab/runtime/installed_plugins")

class PluginInstaller:

    def __init__(self):
        RUNTIME.mkdir(parents=True, exist_ok=True)

    def install_plugin(self, archive_path):
        extract_dir = RUNTIME / Path(archive_path).stem

        if extract_dir.exists():
            shutil.rmtree(extract_dir)

        with tarfile.open(archive_path) as tf:
            tf.extractall(RUNTIME)

        plugin_dir = extract_dir
        meta = json.loads((plugin_dir / "plugin.json").read_text())

        port = meta.get("network", {}).get("internal_port")
        if not port:
            raise Exception("internal_port missing")

        public_port = apply_config(meta["id"], port)

        return {
            "name": meta["name"],
            "url": f"https://pi-nas.taild4713b.ts.net:{public_port}"
        }
