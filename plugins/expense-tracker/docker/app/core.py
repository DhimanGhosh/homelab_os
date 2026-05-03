from __future__ import annotations
from pathlib import Path
from fastapi.templating import Jinja2Templates

_BASE = Path(__file__).parent.parent.resolve()
templates = Jinja2Templates(directory=str(_BASE / "templates"))
