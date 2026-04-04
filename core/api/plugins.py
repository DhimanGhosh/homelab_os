
from fastapi import APIRouter
from homelab_os.core.services.reverse_proxy import PORT_MAP

router = APIRouter()

@router.get("/open/{plugin_id}")
def open_plugin(plugin_id: str):
    port = PORT_MAP.get(plugin_id)
    return {"url": f"https://pi-nas.taild4713b.ts.net:{port}"}
