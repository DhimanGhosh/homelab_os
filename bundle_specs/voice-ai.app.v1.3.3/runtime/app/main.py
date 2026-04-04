from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import load_config
from .security import get_token_from_env
from .skills.router import IntentRouter
from .vad import VadCollector
from .whisper_runner import WhisperRunner
from .ws_audio import WsContext, handle_audio_ws

load_dotenv()
APP_NAME = os.getenv('APP_NAME', 'Voice AI')
APP_VERSION = os.getenv('APP_VERSION', '1.3.3')

ROOT = Path(__file__).resolve().parent.parent

cfg = load_config(ROOT / "config.json")
TOKEN = get_token_from_env(cfg.token_env_key)

app = FastAPI(title=APP_NAME, version=APP_VERSION, title="Pi Voice AI")

app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse((ROOT / "static" / "index.html").read_text(encoding="utf-8"))


@app.get("/config/client")
def client_config() -> JSONResponse:
    return JSONResponse(
        {
            "ws_path": "/ws/audio",
            "token": TOKEN,
            "sample_rate": cfg.vad.sample_rate,
            "frame_ms": cfg.vad.frame_ms,
        }
    )


def _check_ws_token(ws: WebSocket) -> None:
    token = ws.query_params.get("token", "")
    if token != TOKEN:
        raise HTTPException(status_code=401, detail="bad token")


@app.websocket("/ws/audio")
async def ws_audio(ws: WebSocket) -> None:
    await ws.accept()
    try:
        _check_ws_token(ws)
    except HTTPException:
        await ws.send_text(json.dumps({"type": "error", "message": "Unauthorized"}))
        await ws.close(code=1008)
        return

    # Client may send the *actual* browser AudioContext sample rate.
    # WebRTC VAD supports only 8000/16000/32000/48000.
    sr_raw = ws.query_params.get("sr")
    frame_ms_raw = ws.query_params.get("frame_ms")
    try:
        client_sr = int(sr_raw) if sr_raw else int(cfg.vad.sample_rate)
    except ValueError:
        client_sr = int(cfg.vad.sample_rate)

    if client_sr not in (8000, 16000, 32000, 48000):
        client_sr = int(cfg.vad.sample_rate)

    try:
        client_frame_ms = int(frame_ms_raw) if frame_ms_raw else int(cfg.vad.frame_ms)
    except ValueError:
        client_frame_ms = int(cfg.vad.frame_ms)

    runner = WhisperRunner(
        bin_path=cfg.whisper.bin_path,
        model_path=cfg.whisper.model_path,
        threads=cfg.whisper.threads,
        language=cfg.whisper.language,
    )
    vad = VadCollector(
        mode=cfg.vad.mode,
        sample_rate=client_sr,
        frame_ms=client_frame_ms,
        speech_start_ms=cfg.vad.speech_start_ms,
        speech_end_ms=cfg.vad.speech_end_ms,
        max_utterance_seconds=cfg.vad.max_utterance_seconds,
    )
    router = IntentRouter()

    ctx = WsContext(runner=runner, vad=vad, router=router)
    await handle_audio_ws(ws, ctx)
