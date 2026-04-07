from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from rapidfuzz import fuzz, process

from .homeassistant import HomeAssistantClient
from .system_tools import (
    disable_pihole,
    disk_usage,
    pihole_status,
    restart_media_ingest,
    system_status,
)


@dataclass(frozen=True)
class ToolResult:
    name: str
    result: Any


@dataclass(frozen=True)
class AssistantResult:
    text: str
    tool: Optional[ToolResult] = None


def normalize_text(text: str) -> str:
    t = text.strip().lower()
    # common STT confusions (tiny model + accents)
    t = t.replace("the whole", "pihole")
    t = t.replace("pee hole", "pihole")
    t = t.replace("pi hole", "pihole")
    t = re.sub(r"[^a-z0-9\s:-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class IntentRouter:
    """Routes transcripts to tools using fuzzy matching + a few patterns."""

    def __init__(self) -> None:
        self.ha = HomeAssistantClient()

        self._commands: Dict[str, Callable[[str], ToolResult]] = {
            "system status": lambda _: ToolResult("system_status", system_status()),
            "disk usage": lambda _: ToolResult("disk_usage", disk_usage()),
            "pihole status": lambda _: ToolResult("pihole_status", pihole_status()),
            "restart media ingest": lambda _: ToolResult("restart_media_ingest", restart_media_ingest()),
            "disable pihole": self._disable_pihole,
            "homeassistant": self._homeassistant,
        }

        # phrases we match against
        self._choices = [
            "system status",
            "disk usage",
            "pihole status",
            "restart media ingest",
            "disable pihole",
            "turn on",
            "turn off",
        ]

    def route(self, transcript: str) -> AssistantResult:
        """Return a user-facing response, optionally with tool output.

        The WebSocket layer expects a stable object shape. Earlier versions of
        this project returned a raw tuple, which caused UI crashes like:
        "'tuple' object has no attribute 'assistant_text'".
        """

        t = normalize_text(transcript)
        if not t:
            return AssistantResult("I didn't catch that. Try again.")

        tool: Optional[ToolResult] = None

        # quick patterns first
        if t.startswith("disable pihole"):
            tool = self._disable_pihole(t)
        elif t.startswith("turn on") or t.startswith("turn off"):
            tool = self._homeassistant(t)
        else:
            # fuzzy match command phrases
            best = process.extractOne(t, self._choices, scorer=fuzz.WRatio)
            if best:
                choice, score, _ = best
                if score >= 78:
                    if choice in ("turn on", "turn off"):
                        tool = self._homeassistant(t)
                    else:
                        fn = self._commands.get(choice)
                        if fn:
                            tool = fn(t)

        if tool is None:
            return AssistantResult(
                "I can help with: system status, disk usage, pihole status, restart media ingest, disable pihole, turn on <entity>, turn off <entity>."
            )

        # Human-friendly assistant text
        pretty = self._format_assistant_text(tool)
        return AssistantResult(pretty, tool=tool)

    @staticmethod
    def _format_assistant_text(tool: ToolResult) -> str:
        name = tool.name
        payload = tool.result

        if name in ("system_status", "disk_usage", "pihole_status") and isinstance(payload, dict):
            lines = []
            title = name.replace("_", " ").title()
            lines.append(f"{title}:")
            for k, v in payload.items():
                if v is None:
                    continue
                if isinstance(v, str) and not v.strip():
                    continue
                lines.append(f"- {k}: {v}")
            return "\n".join(lines)

        if name == "restart_media_ingest":
            return "Media ingest service restart requested."

        if name == "disable_pihole" and isinstance(payload, dict):
            mins = payload.get("minutes")
            if mins:
                return f"Pi-hole disabled for {mins} minutes."
            return "Pi-hole disable requested."

        if name == "homeassistant" and isinstance(payload, dict):
            if payload.get("ok") is False:
                return str(payload.get("error") or "Home Assistant request failed.")
            action = payload.get("action", "")
            entity_id = payload.get("entity_id", "")
            act = "turned on" if action == "turn_on" else "turned off" if action == "turn_off" else action
            return f"Home Assistant: {act} {entity_id}".strip()

        # fallback
        return f"Done: {name}"

    def _disable_pihole(self, t: str) -> ToolResult:
        # "disable pihole for 5 minutes"
        minutes = 5
        m = re.search(r"(\d{1,3})\s*(minute|minutes|min)", t)
        if m:
            minutes = max(1, min(120, int(m.group(1))))
        return ToolResult("disable_pihole", disable_pihole(minutes))

    def _homeassistant(self, t: str) -> ToolResult:
        if not self.ha.is_configured():
            return ToolResult(
                "homeassistant",
                {
                    "ok": False,
                    "error": "Home Assistant not configured. Set HA_URL and HA_TOKEN in /opt/pi-voice-ai/.env",
                },
            )

        action = "turn_on" if "turn on" in t else "turn_off"
        # Accept either entity_id directly or a friendly name that you map in HA
        entity = t.split("turn on", 1)[-1] if action == "turn_on" else t.split("turn off", 1)[-1]
        entity = entity.strip().replace(" ", "_")

        # If user already spoke an entity_id like light.kitchen, keep it
        if "." not in entity:
            # default domain guess
            entity_id = f"switch.{entity}"
        else:
            entity_id = entity

        res = self.ha.call_service("homeassistant", action, {"entity_id": entity_id})
        return ToolResult("homeassistant", {"ok": True, "action": action, "entity_id": entity_id, "response": res})
