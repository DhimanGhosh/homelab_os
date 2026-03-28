import json
import tarfile
import tempfile
import types
import zipfile
from pathlib import Path

from homelab_platform.services.health import docker_is_healthy
from homelab_platform.services.recovery import recover_stack
from homelab_platform.services.state import load_installed_apps


class BundleInstaller:
    def __init__(self, settings):
        self.settings = settings

    def extract_bundle(self, bundle_path: Path) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="ccbundle-"))
        if bundle_path.suffix == ".zip":
            with zipfile.ZipFile(bundle_path) as zf:
                zf.extractall(temp_dir)
        else:
            with tarfile.open(bundle_path, "r:*") as tf:
                tf.extractall(temp_dir)
        children = list(temp_dir.iterdir())
        return children[0] if len(children) == 1 and children[0].is_dir() else temp_dir

    def load_metadata(self, extracted: Path) -> dict:
        path = extracted / "metadata.json"
        if not path.exists():
            raise FileNotFoundError(f"metadata.json missing in {extracted}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _normalize_bundle_source(self, bundle_path: Path) -> str:
        source = bundle_path.read_text(encoding="utf-8")
        if "\\n" in source and "\n" not in source.strip():
            source = source.encode("utf-8").decode("unicode_escape")
        source = source.replace("homelab_py.services.", "homelab_platform.services.")
        source = source.replace("from homelab_py.", "from homelab_platform.")
        source = source.replace("import homelab_py.", "import homelab_platform.")
        bundle_path.write_text(source, encoding="utf-8")
        return source

    def _run_python_bundle(self, extracted: Path, meta: dict, func_name: str):
        bundle_path = extracted / "bundle.py"
        if not bundle_path.exists():
            raise FileNotFoundError(f"bundle.py missing in {extracted}")
        source = self._normalize_bundle_source(bundle_path)
        module = types.ModuleType("bundle_module")
        module.__file__ = str(bundle_path)
        code = compile(source, str(bundle_path), "exec")
        exec(code, module.__dict__)
        func = getattr(module, func_name, None)
        if func is None:
            raise AttributeError(f"{func_name} not found in {bundle_path}")
        return func(self.settings, extracted, meta)

    def install(self, bundle_path: Path):
        if not docker_is_healthy():
            recover_stack(self.settings)
            raise RuntimeError("Docker unstable — recovery triggered. Retry install.")
        extracted = self.extract_bundle(bundle_path)
        meta = self.load_metadata(extracted)
        return self._run_python_bundle(extracted, meta, "install")

    def remove_app(self, app_id: str):
        bundle_dir = self.settings.apps_dir / app_id / "bundle"
        meta_path = self.settings.apps_dir / app_id / "metadata.json"
        if not bundle_dir.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Installed bundle not found for {app_id}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return self._run_python_bundle(bundle_dir, meta, "uninstall")

    def list_installed(self):
        return load_installed_apps(self.settings.apps_dir)
