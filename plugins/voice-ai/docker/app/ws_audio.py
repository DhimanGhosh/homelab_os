from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

from fastapi import WebSocket

from .skills.router import AssistantResult, IntentRouter, ToolResult
from .vad import VadCollector
from .whisper_runner import WhisperRunner


@dataclass
class WsContext:
    runner: WhisperRunner
    vad: VadCollector
    router: IntentRouter


async def handle_audio_ws(ws: WebSocket, ctx: WsContext) -> None:
    """Handle binary PCM16 frames sent over websocket.

    Notes:
      - The websocket must already be accepted by the caller.
      - Authentication/authorization must be done by the caller.
    """

    await ws.send_text(json.dumps({"type": "ready"}))

    try:
        while True:
            data = await ws.receive_bytes()
            # VadCollector expects *exactly* one frame of size frame_bytes.
            # The browser worklet sends Int16 PCM frames (ArrayBuffer) matching cfg.vad.frame_ms at cfg.vad.sample_rate.
            segment = ctx.vad.push(data)
            if segment is None:
                continue

            await ws.send_text(json.dumps({"type": "event", "message": "Transcribing…"}))
            text = await asyncio.to_thread(ctx.runner.transcribe_pcm16, segment.pcm, ctx.vad.sample_rate)
            text = (text or "").strip()
            if not text:
                await ws.send_text(json.dumps({"type": "event", "message": "No speech detected"}))
                continue

            await ws.send_text(json.dumps({"type": "stt", "text": text}))

            routed = await asyncio.to_thread(ctx.router.route, text)

            # Backwards compatibility: older router implementations returned a raw tuple
            # (tool_result, assistant_text). The UI expects a stable shape.
            if isinstance(routed, tuple):
                tool, msg = routed  # type: ignore[misc]
                routed = AssistantResult(text=(msg or ""), tool=tool)  # type: ignore[arg-type]

            if not isinstance(routed, AssistantResult):
                # ultra-safe fallback
                routed = AssistantResult(text=str(routed))

            await ws.send_text(json.dumps({"type": "assistant", "text": routed.text}))
            if routed.tool is not None:
                await ws.send_text(
                    json.dumps({"type": "tool", "name": routed.tool.name, "result": routed.tool.result})
                )


            # One-shot mode: after we finish a single utterance, tell the browser to stop streaming.
            await ws.send_text(json.dumps({"type": "done"}))
            await ws.close()
            break
    except Exception as ex:
        try:
            await ws.send_text(json.dumps({"type": "error", "message": str(ex)}))
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass
