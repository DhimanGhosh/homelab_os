from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class WhisperConfig:
    bin_path: str
    model_path: str
    threads: int = 4
    language: str = "en"


@dataclass(frozen=True)
class VadConfig:
    mode: int = 2
    sample_rate: int = 16000
    frame_ms: int = 20
    speech_start_ms: int = 300
    speech_end_ms: int = 800
    max_utterance_seconds: int = 12


@dataclass(frozen=True)
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 8124
    token_env_key: str = "PI_VOICE_AI_TOKEN"
    whisper: WhisperConfig | None = None
    vad: VadConfig = VadConfig()


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path)
    raw: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    whisper_raw = raw.get("whisper") or {}
    whisper = WhisperConfig(
        bin_path=str(whisper_raw.get("bin_path", "/opt/whisper.cpp/whisper-cli")),
        model_path=str(whisper_raw.get("model_path", "/opt/whisper.cpp/models/ggml-tiny.bin")),
        threads=int(whisper_raw.get("threads", 4)),
        language=str(whisper_raw.get("language", "en")),
    )

    vad_raw = raw.get("vad") or {}
    vad = VadConfig(
        mode=int(vad_raw.get("mode", 2)),
        sample_rate=int(vad_raw.get("sample_rate", 16000)),
        frame_ms=int(vad_raw.get("frame_ms", 20)),
        speech_start_ms=int(vad_raw.get("speech_start_ms", 300)),
        speech_end_ms=int(vad_raw.get("speech_end_ms", 800)),
        max_utterance_seconds=int(vad_raw.get("max_utterance_seconds", 12)),
    )

    return AppConfig(
        host=str(raw.get("host", "0.0.0.0")),
        port=int(raw.get("port", 8124)),
        token_env_key=str(raw.get("token_env_key", "PI_VOICE_AI_TOKEN")),
        whisper=whisper,
        vad=vad,
    )
