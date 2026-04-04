
from fastapi import APIRouter
from core.config import Settings
from core.services.health import health_snapshot

router = APIRouter(prefix='/api/system', tags=['system'])
settings = Settings.from_env_file()

@router.get('/health')
def system_health():
    return health_snapshot(settings)
