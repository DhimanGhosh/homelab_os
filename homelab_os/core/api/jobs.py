from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from homelab_os.core.config import load_settings
from homelab_os.core.services.jobs import JobStore
from homelab_os.core.services.logging_service import LoggingService


router = APIRouter()


def _job_store() -> JobStore:
    settings = load_settings(".env")
    return JobStore(settings.manifests_dir / "jobs.json")


def _logging_service() -> LoggingService:
    settings = load_settings(".env")
    return LoggingService(settings.runtime_jobs_dir)


@router.get("/jobs")
def list_jobs() -> dict:
    store = _job_store()
    return {"jobs": store.list_jobs()}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    store = _job_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/logs")
def get_job_logs(job_id: str) -> dict:
    store = _job_store()
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    logger = _logging_service()
    return {"job_id": job_id, "logs": logger.read_job_log(job_id)}


@router.websocket("/jobs/ws/{job_id}")
async def job_ws(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    store = _job_store()
    logger = _logging_service()

    try:
        while True:
            job = store.get_job(job_id)
            if not job:
                await websocket.send_json({"error": "Job not found"})
                break

            await websocket.send_json(
                {
                    "job": job,
                    "logs": logger.read_job_log(job_id),
                }
            )

            if job.get("status") in {"completed", "failed"}:
                break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
