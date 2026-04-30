from __future__ import annotations

import threading
import time
import uuid

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def now() -> float:
    return time.time()


def new_job(kind: str, payload: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {
            'id':             job_id,
            'kind':           kind,
            'status':         'queued',
            'progress':       0.0,
            'message':        'Queued',
            'created_at':     now(),
            'updated_at':     now(),
            'payload':        payload,
            'output_path':    None,
            'output_name':    None,
            'output_relative': None,
            'log':            [],
        }
    return job_id


def update_job(job_id: str, **fields) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        log_line = fields.pop('log_line', None)
        job.update(fields)
        job['updated_at'] = now()
        if log_line:
            job.setdefault('log', []).append(log_line)
            if len(job['log']) > 120:
                job['log'] = job['log'][-120:]


def clear_finished_jobs() -> int:
    with JOBS_LOCK:
        remove_ids = [
            jid for jid, job in JOBS.items()
            if job.get('status') in ('completed', 'failed')
        ]
        for jid in remove_ids:
            JOBS.pop(jid, None)
        return len(remove_ids)
