import json
import shutil
import tarfile
from pathlib import Path


class BundleBuilder:
    def _normalize_bundle_py(self, source_dir: Path) -> None:
        bundle_path = source_dir / "bundle.py"
        if not bundle_path.exists():
            return
        text = bundle_path.read_text(encoding="utf-8")
        if "\n" in text and "" not in text.strip():
            text = text.encode("utf-8").decode("unicode_escape")
        text = text.replace("homelab_py.services.", "homelab_platform.services.")
        text = text.replace("from homelab_py.", "from homelab_platform.")
        text = text.replace("import homelab_py.", "import homelab_platform.")
        bundle_path.write_text(text, encoding="utf-8")

    def _materialize_control_center_payload(self, source_dir: Path) -> None:
        metadata_path = source_dir / "metadata.json"
        if not metadata_path.exists():
            return
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        if meta.get("id") != "control-center":
            return

        repo_root = source_dir.parent.parent
        payload_dir = source_dir / "payload"
        if payload_dir.exists():
            shutil.rmtree(payload_dir)
        payload_dir.mkdir(parents=True, exist_ok=True)

        includes = [
            "bootstrap.py",
            "pyproject.toml",
            ".env.example",
            "README.md",
            "homelab_platform",
            "recovery",
            "bundle_specs/control_center_bundle_v1_7_0",
        ]

        for rel in includes:
            src = repo_root / rel
            if not src.exists():
                continue
            dst = payload_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

    def validate_bundle_dir(self, source_dir: Path) -> None:
        metadata_path = source_dir / "metadata.json"
        bundle_path = source_dir / "bundle.py"
        if not metadata_path.exists():
            raise FileNotFoundError(f"metadata.json missing in {source_dir}")
        if not bundle_path.exists():
            raise FileNotFoundError(f"bundle.py missing in {source_dir}")
        self._normalize_bundle_py(source_dir)
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))

        if meta.get("id") == "control-center":
            self._materialize_control_center_payload(source_dir)
            payload_dir = source_dir / "payload"
            if not payload_dir.exists():
                raise FileNotFoundError(f"payload missing in {source_dir}")
            return

        runtime_dir = source_dir / "runtime"
        if runtime_dir.exists() and not (runtime_dir / "docker-compose.yml").exists():
            raise FileNotFoundError(f"docker-compose.yml missing in {runtime_dir}")
        if meta.get("id") == "personal-library":
            (runtime_dir / "data").mkdir(parents=True, exist_ok=True)

    def build_tgz(self, source_dir: Path, output_path: Path) -> Path:
        self.validate_bundle_dir(source_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_path, "w:gz") as tf:
            tf.add(source_dir, arcname=source_dir.name)
        return output_path
