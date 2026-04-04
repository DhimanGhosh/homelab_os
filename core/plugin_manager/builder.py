import json
import tarfile
from pathlib import Path


class PluginBuilder:
    def _normalize_bundle_py(self, source_dir: Path) -> None:
        bundle_path = source_dir / "install.py"
        if not bundle_path.exists():
            return
        text = bundle_path.read_text(encoding="utf-8")
        text = text.replace("homelab_py.services.", "core.plugin_manager.")
        text = text.replace("from homelab_py.", "from ")
        text = text.replace("import homelab_py.", "import ")
        bundle_path.write_text(text, encoding="utf-8")

    def validate_plugin_dir(self, source_dir: Path) -> None:
        metadata_path = source_dir / "plugin.json"
        bundle_path = source_dir / "install.py"
        if not metadata_path.exists():
            raise FileNotFoundError(f"plugin.json missing in {source_dir}")
        if not bundle_path.exists():
            raise FileNotFoundError(f"install.py missing in {source_dir}")
        self._normalize_bundle_py(source_dir)
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))

        # New plugin layout: plugins may contain backend/, frontend/, docker/, assets/, migrations/.
        # Keep validation lightweight so transitional plugins still build.
        has_backend = (source_dir / "backend").exists()
        has_frontend = (source_dir / "frontend").exists()
        has_docker = (source_dir / "docker").exists()
        if not any([has_backend, has_frontend, has_docker]):
            raise FileNotFoundError(
                f"Invalid plugin structure in {source_dir}: expected at least one of backend/, frontend/, docker/"
            )
        docker_compose = source_dir / "docker" / "docker-compose.yml"
        if has_docker and docker_compose.exists() is False and meta.get("backend", {}).get("framework") == "docker":
            raise FileNotFoundError(f"docker-compose.yml missing in {source_dir / 'docker'}")

    def build_plugin_archive(self, source_dir: Path, output_path: Path) -> Path:
        self.validate_plugin_dir(source_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_path, "w:gz") as tf:
            tf.add(source_dir, arcname=source_dir.name)
        return output_path

    def build_tgz(self, source_dir: Path, output_path: Path) -> Path:
        return self.build_plugin_archive(source_dir, output_path)
