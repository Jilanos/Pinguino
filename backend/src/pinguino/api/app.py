"""Local FastAPI application.

Security posture for a single-user local tool: loopback binding, same-origin serving,
a per-launch request token on mutating calls, and no endpoint that reveals a shell or
an arbitrary filesystem path.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from pinguino import __version__
from pinguino.api.jobs import CampaignJobs
from pinguino.api.preview import preview_campaign
from pinguino.config import LOOPBACK_HOSTS, Settings, load_settings
from pinguino.data.importer import default_fixture_span, import_fixture, import_mt5
from pinguino.data.mt5_adapter import diagnose_source
from pinguino.data.store import DatasetStore, StoredDataset
from pinguino.domain.campaign import CampaignConfig
from pinguino.domain.enums import Symbol, Timeframe
from pinguino.domain.errors import FRENCH_EXPLANATIONS, ErrorCode, PinguinoError
from pinguino.domain.timeutil import require_utc
from pinguino.research.ledger import Ledger
from pinguino.research.service import (
    ACTIVE_RUN_STATES,
    CampaignStore,
    RunState,
    candidate_detail,
    candidate_payload,
    export_candidate,
    open_holdout,
    prepare_campaign,
    run_payload,
    suggest_config,
)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
REQUEST_TOKEN_HEADER = "x-pinguino-token"

_STATUS_FOR: dict[ErrorCode, int] = {
    ErrorCode.DATASET_NOT_FOUND: 404,
    ErrorCode.CAMPAIGN_NOT_FOUND: 404,
    ErrorCode.CANDIDATE_NOT_FOUND: 404,
    ErrorCode.CAMPAIGN_ALREADY_RUNNING: 409,
    ErrorCode.CAMPAIGN_IMMUTABLE: 409,
    ErrorCode.HOLDOUT_ACCESS_DENIED: 403,
    ErrorCode.PREVIEW_REQUIRED: 409,
    ErrorCode.MT5_PACKAGE_UNAVAILABLE: 503,
    ErrorCode.MT5_TERMINAL_UNAVAILABLE: 503,
    ErrorCode.MT5_TERMINAL_DISCONNECTED: 503,
    ErrorCode.MT5_SYMBOL_UNAVAILABLE: 503,
    ErrorCode.MT5_HISTORY_UNAVAILABLE: 503,
}


def _error_response(code: ErrorCode, status_code: int, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code.value, "message": FRENCH_EXPLANATIONS[code], "detail": detail},
    )


def _host_is_local(value: str | None) -> bool:
    if value is None:
        return False
    hostname = urlparse(f"//{value}").hostname
    return hostname in LOOPBACK_HOSTS


class ImportRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: Symbol
    timeframe: Timeframe
    start: datetime | None = None
    end: datetime | None = None


class HoldoutRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


def _dataset_payload(stored: StoredDataset) -> dict[str, Any]:
    manifest = stored.manifest.model_dump(mode="json")
    return {
        "dataset_id": stored.dataset_id,
        "manifest": manifest,
        "findings": [finding.model_dump(mode="json") for finding in stored.findings],
        "finding_counts": _count(finding.code.value for finding in stored.findings),
        "stored_at": stored.stored_at.isoformat(),
    }


def _count(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _span(request: ImportRequest) -> tuple[datetime, datetime]:
    if request.start is None or request.end is None:
        raise PinguinoError(ErrorCode.INVALID_RESEARCH_WINDOW, "start and end are required")
    start, end = require_utc(request.start), require_utc(request.end)
    if end <= start:
        raise PinguinoError(ErrorCode.INVALID_RESEARCH_WINDOW, "end must be after start")
    return start, end


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or load_settings()
    app = FastAPI(title="Pinguino", version=__version__, docs_url=None, redoc_url=None)
    app.state.settings = resolved

    data_dir = resolved.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    database = data_dir / "research.sqlite"
    store = DatasetStore(data_dir)
    runs = CampaignStore(database)
    ledger = Ledger(database, shared=True)
    # Nothing can be running at startup: whatever was left active belonged to a dead process.
    runs.mark_interrupted()
    ledger.reconcile_interrupted()
    jobs = CampaignJobs(data_dir, use_process=resolved.worker_process)
    previewed: set[str] = set()

    @app.exception_handler(PinguinoError)
    async def domain_error(_: Request, error: PinguinoError) -> JSONResponse:
        return _error_response(error.code, _STATUS_FOR.get(error.code, 400), error.detail)

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

    def reconcile(campaign_id: str) -> None:
        row = runs.run(campaign_id)
        if row is None:
            raise PinguinoError(ErrorCode.CAMPAIGN_NOT_FOUND, campaign_id)
        if RunState(row["state"]) in ACTIVE_RUN_STATES and not jobs.is_alive(campaign_id):
            runs.update(campaign_id, state=RunState.INTERRUPTED.value)
            ledger.reconcile_interrupted()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "locale": resolved.source_locale}

    @app.get("/api/session")
    async def session() -> dict[str, str]:
        # Same-origin only: the Host guard and the absence of CORS headers keep a foreign
        # page from reading this token.
        return {"token": resolved.request_token}

    @app.get("/api/source/diagnostic")
    async def source_diagnostic() -> dict[str, Any]:
        diagnostic = await run_in_threadpool(diagnose_source)
        payload = diagnostic.model_dump(mode="json")
        payload["synthetic_mode_only"] = diagnostic.synthetic_mode_only
        if diagnostic.code is not None:
            payload["message"] = FRENCH_EXPLANATIONS[diagnostic.code]
        return payload

    @app.get("/api/datasets")
    async def list_datasets() -> list[dict[str, Any]]:
        return [_dataset_payload(item) for item in store.list()]

    @app.get("/api/datasets/{dataset_id}")
    async def get_dataset(dataset_id: str) -> dict[str, Any]:
        stored = store.get(dataset_id)
        if stored is None:
            raise PinguinoError(ErrorCode.DATASET_NOT_FOUND, dataset_id)
        return _dataset_payload(stored)

    @app.post("/api/datasets/import/mt5")
    async def import_from_mt5(request: ImportRequest) -> dict[str, Any]:
        start, end = _span(request)
        stored = await run_in_threadpool(
            import_mt5,
            store,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=start,
            end=end,
        )
        return _dataset_payload(stored)

    @app.post("/api/datasets/import/fixture")
    async def import_from_fixture(request: ImportRequest) -> dict[str, Any]:
        if request.start is None and request.end is None:
            start, end = default_fixture_span()
        else:
            start, end = _span(request)
        stored = await run_in_threadpool(
            import_fixture,
            store,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=start,
            end=end,
        )
        return _dataset_payload(stored)

    @app.get("/api/campaigns/suggested-config")
    async def suggested_config(
        dataset_id: Annotated[list[str] | None, Query()] = None,
    ) -> dict[str, Any]:
        config = await run_in_threadpool(suggest_config, store, dataset_id or [])
        return config.model_dump(mode="json")

    @app.post("/api/campaigns/preview")
    async def campaign_preview(config: CampaignConfig) -> dict[str, Any]:
        if all(store.get(dataset_id) is None for dataset_id in config.dataset_ids):
            # No stored dataset yet: preview the declared full grid without data checks.
            preview, split = preview_campaign(config)
            return {
                "preview": preview.model_dump(mode="json"),
                "validation_subwindows": [
                    window.model_dump(mode="json") for window in split.validation_subwindows
                ],
                "datasets": [],
                "startable": False,
            }
        payload, _ = await run_in_threadpool(prepare_campaign, store, config)
        previewed.add(config.campaign_id)
        return payload | {"startable": runs.run(config.campaign_id) is None}

    @app.post("/api/campaigns")
    async def create_campaign(config: CampaignConfig) -> dict[str, Any]:
        if config.campaign_id not in previewed:
            raise PinguinoError(ErrorCode.PREVIEW_REQUIRED)
        if runs.run(config.campaign_id) is not None:
            raise PinguinoError(ErrorCode.CAMPAIGN_IMMUTABLE, config.campaign_id)
        if jobs.running_id() is not None:
            raise PinguinoError(ErrorCode.CAMPAIGN_ALREADY_RUNNING)
        payload, _ = await run_in_threadpool(prepare_campaign, store, config)
        runs.create(config, payload)
        jobs.start(config)
        row = runs.run(config.campaign_id)
        assert row is not None
        return run_payload(row, ledger)

    @app.get("/api/campaigns")
    async def list_campaigns() -> list[dict[str, Any]]:
        out = []
        for row in runs.runs():
            reconcile(row["campaign_id"])
            fresh = runs.run(row["campaign_id"])
            assert fresh is not None
            out.append(run_payload(fresh, ledger))
        return out

    @app.get("/api/campaigns/{campaign_id}")
    async def get_campaign(campaign_id: str) -> dict[str, Any]:
        reconcile(campaign_id)
        row = runs.run(campaign_id)
        assert row is not None
        return run_payload(row, ledger)

    @app.post("/api/campaigns/{campaign_id}/cancel")
    async def cancel_campaign(campaign_id: str) -> dict[str, Any]:
        reconcile(campaign_id)
        return {"campaign_id": campaign_id, "cancel_requested": jobs.cancel(campaign_id)}

    @app.post("/api/campaigns/{campaign_id}/resume")
    async def resume_campaign(campaign_id: str) -> dict[str, Any]:
        reconcile(campaign_id)
        row = runs.run(campaign_id)
        assert row is not None
        if RunState(row["state"]) in ACTIVE_RUN_STATES:
            raise PinguinoError(ErrorCode.CAMPAIGN_ALREADY_RUNNING, campaign_id)
        original = CampaignConfig.model_validate_json(row["config_json"])
        config = original.model_copy(update={"resumed_from_campaign_id": campaign_id})
        if runs.run(config.campaign_id) is not None:
            raise PinguinoError(ErrorCode.CAMPAIGN_IMMUTABLE, config.campaign_id)
        payload, _ = await run_in_threadpool(prepare_campaign, store, config)
        runs.create(config, payload)
        jobs.start(config)
        created = runs.run(config.campaign_id)
        assert created is not None
        return run_payload(created, ledger)

    @app.get("/api/campaigns/{campaign_id}/candidates")
    async def list_candidates(campaign_id: str) -> list[dict[str, Any]]:
        reconcile(campaign_id)
        return [candidate_payload(row) for row in runs.candidates(campaign_id)]

    @app.get("/api/campaigns/{campaign_id}/candidates/{candidate_id}")
    async def get_candidate(campaign_id: str, candidate_id: str) -> dict[str, Any]:
        row = runs.candidate(campaign_id, candidate_id)
        if row is None:
            raise PinguinoError(ErrorCode.CANDIDATE_NOT_FOUND, candidate_id)
        return candidate_payload(row)

    @app.get("/api/campaigns/{campaign_id}/candidates/{candidate_id}/windows/{label}")
    async def candidate_window(
        campaign_id: str,
        candidate_id: str,
        label: str,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return await run_in_threadpool(
            candidate_detail,
            store,
            runs,
            campaign_id,
            candidate_id,
            label,
            offset=offset,
            limit=limit,
        )

    @app.post("/api/campaigns/{campaign_id}/candidates/{candidate_id}/final-evaluation")
    async def final_evaluation(
        campaign_id: str, candidate_id: str, request: HoldoutRequest
    ) -> dict[str, Any]:
        reconcile(campaign_id)
        return await run_in_threadpool(
            open_holdout, store, runs, ledger, campaign_id, candidate_id, request.reason
        )

    @app.get("/api/campaigns/{campaign_id}/candidates/{candidate_id}/export")
    async def export(campaign_id: str, candidate_id: str) -> Response:
        name, payload = await run_in_threadpool(
            export_candidate, store, runs, campaign_id, candidate_id
        )
        return Response(
            content=payload,
            media_type="application/zip",
            headers={"content-disposition": f'attachment; filename="{name}"'},
        )

    ui_dir = resolved.ui_dir
    if ui_dir is not None and (ui_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app
