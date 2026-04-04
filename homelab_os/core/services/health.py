from __future__ import annotations

from urllib.request import urlopen
from urllib.error import URLError, HTTPError


class HealthService:
    def check_http(self, url: str, timeout: int = 5) -> dict:
        try:
            with urlopen(url, timeout=timeout) as response:
                return {
                    "ok": 200 <= response.status < 400,
                    "status_code": response.status,
                    "url": url,
                }
        except HTTPError as exc:
            return {
                "ok": False,
                "status_code": exc.code,
                "url": url,
                "error": str(exc),
            }
        except URLError as exc:
            return {
                "ok": False,
                "status_code": None,
                "url": url,
                "error": str(exc),
            }
