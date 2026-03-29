from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import webrtcvad


@dataclass
class VadSegment:
    pcm: bytes
    duration_ms: int


class VadCollector:
    """Collects PCM16 audio frames into utterances using WebRTC VAD."""

    def __init__(
        self,
        mode: int,
        sample_rate: int,
        frame_ms: int,
        speech_start_ms: int,
        speech_end_ms: int,
        max_utterance_seconds: int,
    ) -> None:
        self.vad = webrtcvad.Vad(int(mode))
        self.sample_rate = int(sample_rate)
        self.frame_ms = int(frame_ms)

        self.frame_bytes = int(self.sample_rate * self.frame_ms / 1000) * 2  # 16-bit
        self.start_frames = max(1, int(speech_start_ms / self.frame_ms))
        self.end_frames = max(1, int(speech_end_ms / self.frame_ms))
        self.max_frames = max(1, int(max_utterance_seconds * 1000 / self.frame_ms))

        self._buf = bytearray()
        self._speech_frames = 0
        self._silence_frames = 0
        self._in_speech = False
        self._frames_in_utt = 0

    def reset(self) -> None:
        self._buf.clear()
        self._speech_frames = 0
        self._silence_frames = 0
        self._in_speech = False
        self._frames_in_utt = 0

    def push(self, pcm_frame: bytes) -> Optional[VadSegment]:
        if len(pcm_frame) != self.frame_bytes:
            # ignore malformed frames
            return None

        is_speech = self.vad.is_speech(pcm_frame, self.sample_rate)

        if not self._in_speech:
            if is_speech:
                self._speech_frames += 1
                self._buf.extend(pcm_frame)
                if self._speech_frames >= self.start_frames:
                    self._in_speech = True
                    self._frames_in_utt = self._speech_frames
                    self._silence_frames = 0
            else:
                # keep a tiny pre-roll? (optional) - we skip to keep it simple
                self._speech_frames = 0
                self._buf.clear()
            return None

        # in speech
        self._buf.extend(pcm_frame)
        self._frames_in_utt += 1

        if is_speech:
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        if self._silence_frames >= self.end_frames or self._frames_in_utt >= self.max_frames:
            seg = VadSegment(pcm=bytes(self._buf), duration_ms=self._frames_in_utt * self.frame_ms)
            self.reset()
            return seg

        return None
