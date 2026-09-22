"""Local FastAPI application.

Security posture for a single-user local tool: loopback binding, same-origin serving,
a per-launch request token on mutating calls, and no endpoint that reveals a shell or
an arbitrary filesystem path.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pinguino import __version__
from pinguino.config import LOOPBACK_HOSTS, Settings, load_settings
from pinguino.data.mt5_adapter import diagnose_source
from pinguino.domain.errors import FRENCH_EXPLANATIONS, ErrorCode

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
REQUEST_TOKEN_HEADER = "x-pinguino-token"


def _error_response(code: ErrorCode, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code.value, "message": FRENCH_EXPLANATIONS[code]},
    )


def _host_is_local(value: str | None) -> bool:
    if value is None:
        return False
    hostname = urlparse(f"//{value}").hostname
    return hostname in LOOPBACK_HOSTS


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or load_settings()
    app = FastAPI(title="Pinguino", version=__version__, docs_url=None, redoc_url=None)
    app.state.settings = resolved

    @app.middleware("http")
    async def guard_local_origin(request: Request, call_next: Any) -> Any:
        if not _host_is_local(request.headers.get("host")):
            return _error_response(ErrorCode.FOREIGN_ORIGIN_REJECTED, 403)
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            if origin is not None and origin not in resolved.allowed_origins:
                return _error_response(ErrorCode.FOREIGN_ORIGIN_REJECTED, 403)
            if request.headers.get(REQUEST_TOKEN_HEADER) != resolved.request_token:
                return _error_response(ErrorCode.REQUEST_TOKEN_INVALID, 401)
        return await call_next(request)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "locale": resolved.source_locale}

    @app.get("/api/source/diagnostic")
    async def source_diagnostic() -> dict[str, Any]:
        diagnostic = diagnose_source()
        payload = diagnostic.model_dump(mode="json")
        payload["synthetic_mode_only"] = diagnostic.synthetic_mode_only
        if diagnostic.code is not None:
            payload["message"] = FRENCH_EXPLANATIONS[diagnostic.code]
        return payload

    return app


app = create_app()
