
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PluginManifest:
    id: str
    name: str
    version: str
    category: str = 'general'
    entrypoint: dict[str, Any] = field(default_factory=dict)
    backend: dict[str, Any] = field(default_factory=dict)
    ui: dict[str, Any] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    healthcheck: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
