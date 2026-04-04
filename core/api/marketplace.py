
from fastapi import APIRouter
from core.config import Settings

router = APIRouter(prefix='/api/marketplace', tags=['marketplace'])
settings = Settings.from_env_file()

@router.get('')
def marketplace_summary():
    build = sorted([p.name for p in settings.build_dir.glob('*.tgz')]) if settings.build_dir.exists() else []
    cache = sorted([p.name for p in (settings.runtime_dir / 'marketplace_cache').glob('*')]) if (settings.runtime_dir / 'marketplace_cache').exists() else []
    return {'build_artifacts': build, 'marketplace_cache': cache}
