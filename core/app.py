
from fastapi import FastAPI
from core.api.system import router as system_router
from core.api.plugins import router as plugins_router
from core.api.jobs import router as jobs_router
from core.api.marketplace import router as marketplace_router

app = FastAPI(title='Homelab OS Core')
app.include_router(system_router)
app.include_router(plugins_router)
app.include_router(jobs_router)
app.include_router(marketplace_router)

@app.get('/')
def root():
    return {'name': 'Homelab OS Core', 'status': 'ok'}
