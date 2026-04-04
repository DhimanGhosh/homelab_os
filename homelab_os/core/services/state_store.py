from __future__ import annotations

import json
from pathlib import Path


class StateStore:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self.write({"plugins": {}})

    def read(self) -> dict:
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def write(self, data: dict) -> None:
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def update_plugin_state(self, plugin_id: str, payload: dict) -> None:
        data = self.read()
        data.setdefault("plugins", {})
        data["plugins"].setdefault(plugin_id, {})
        data["plugins"][plugin_id].update(payload)
        self.write(data)

    def get_plugin_state(self, plugin_id: str) -> dict | None:
        data = self.read()
        return data.get("plugins", {}).get(plugin_id)
