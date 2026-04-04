from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests


class HomeAssistantClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("HA_URL", "").strip().rstrip("/")
        self.token = os.getenv("HA_TOKEN", "").strip()

    def is_configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def call_service(self, domain: str, service: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Home Assistant not configured. Set HA_URL and HA_TOKEN in .env")
        url = f"{self.base_url}/api/services/{domain}/{service}"
        r = requests.post(url, headers=self._headers(), json=data, timeout=10)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {"status": "ok"}


def parse_ha_intent(text: str) -> Optional[Dict[str, str]]:
    # Supports: "turn on <entity_id>" / "turn off <entity_id>"
    t = text.strip().lower()
    if t.startswith("turn on "):
        entity = t.replace("turn on ", "", 1).strip()
        return {"action": "turn_on", "entity_id": entity}
    if t.startswith("turn off "):
        entity = t.replace("turn off ", "", 1).strip()
        return {"action": "turn_off", "entity_id": entity}
    return None
