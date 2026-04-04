
from fastapi import APIRouter
from pathlib import Path
from core.services.jobs import load_json_jobs

router = APIRouter(prefix='/api/jobs', tags=['jobs'])

@router.get('')
def list_jobs():
    return {'jobs': load_json_jobs(Path('runtime/jobs/jobs.json'))}
