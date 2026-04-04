from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Optional


class WhisperRunner:
    """Thin wrapper around whisper.cpp CLI.

    Expects PCM16 mono 16kHz bytes.
    """

    def __init__(self, bin_path: str, model_path: str, threads: int = 4, language: str = "en") -> None:
        self.bin_path = str(bin_path)
        self.model_path = str(model_path)
        self.threads = int(threads)
        self.language = str(language)

    def transcribe_pcm16(self, pcm: bytes, sample_rate: int) -> str:
        if not pcm:
            return ""

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            self._write_wav(tmp.name, pcm, sample_rate)
            return self._run_whisper(tmp.name)

    @staticmethod
    def _write_wav(path: str, pcm: bytes, sample_rate: int) -> None:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(int(sample_rate))
            wf.writeframes(pcm)

    def _run_whisper(self, wav_path: str) -> str:
        # whisper-cli outputs text; we keep it minimal
        cmd = [
            self.bin_path,
            "-m",
            self.model_path,
            "-f",
            wav_path,
            "-t",
            str(self.threads),
            "-l",
            self.language,
            "--no-timestamps",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = (proc.stdout or "").strip()

        # whisper.cpp sometimes prints timings / info lines.
        # We want the *actual* transcript, not lines like:
        #   "whisper_print_timings: total time = ..."
        raw_lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if not raw_lines:
            return ""

        def is_noise_line(ln: str) -> bool:
            lower = ln.lower()
            if lower.startswith("whisper_"):
                return True
            if "whisper_print" in lower:
                return True
            if lower.startswith("system_info") or lower.startswith("main:"):
                return True
            if "ggml" in lower and "=" in lower:
                return True
            if "total time" in lower and "ms" in lower:
                return True
            return False

        # Prefer the last line that doesn't look like a log/timing line.
        candidates = [ln for ln in raw_lines if not is_noise_line(ln)]
        if not candidates:
            # All lines were logs/timings; treat as no speech.
            return ""
        lines = candidates

        # Remove common prefixes like [00:00.00 --> ...]
        text = lines[-1]
        if text.startswith("[") and "]" in text:
            text = text.split("]", 1)[-1].strip()
        return text
