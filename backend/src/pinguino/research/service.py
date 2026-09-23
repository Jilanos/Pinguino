"""Campaign service: the research pipeline behind the local API.

A campaign runs in a worker process, one trial at a time. Each trial replays the
candidate on training, whole validation and each validation subwindow, every window
starting flat. Robustness checks and the ranking follow the screening. Trade and equity
detail is never cached: it is replayed on demand from the stored definition, which is
also how an export proves it can be reproduced.
"""

from __future__ import annotations

import ctypes
import io
import json
import sqlite3
import sys
import time
import zipfile
from collections.abc import Callable, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from pinguino.api.preview import FIXED_WINDOWS_PER_TRIAL, planned_definitions, preview_campaign
from pinguino.data.quality import BAR_DURATION
from pinguino.data.store import DatasetStore, StoredDataset, dataset_key
from pinguino.domain.campaign import CampaignConfig
from pinguino.domain.enums import ApproximationFlag, DatasetStatus, Symbol, Timeframe
from pinguino.domain.errors import ErrorCode, PinguinoError
from pinguino.domain.identity import canonical_json
from pinguino.domain.policy import CostPolicy
from pinguino.domain.results import WindowMetrics
from pinguino.domain.strategy import StrategyDefinition
from pinguino.engine.simulator import SimulationCancelled, SimulationResult, simulate
from pinguino.research.evaluation import (
    ScreeningResult,
    Verdict,
    neighborhood_verdict,
    open_final_holdout,
    passes_stress,
    rank,
    screen_candidate,
)
from pinguino.research.export import (
    build_export,
    equity_csv,
    html_report,
    metrics_json,
    strategy_json,
    trades_csv,
)
from pinguino.research.grid import neighbors
from pinguino.research.ledger import Ledger
from pinguino.research.metrics import max_drawdown, window_metrics
from pinguino.research.runner import CancellationToken, MarketData, run_campaign
from pinguino.research.windows import ResolvedSplit, ResolvedWindow, resolve_split

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign_runs (
    campaign_id TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    preview_json TEXT NOT NULL,
    state TEXT NOT NULL,
    phase TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    outcome_json TEXT,
    baselines_json TEXT,
    error TEXT,
    duration_seconds REAL
);
CREATE TABLE IF NOT EXISTS candidate_results (
    campaign_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    trial_id TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    windows_json TEXT NOT NULL,
    screening_json TEXT NOT NULL,
    stress_passed INTEGER,
    neighborhood TEXT,
    final_verdict TEXT NOT NULL,
    final_reasons_json TEXT NOT NULL,
    rank INTEGER,
    flags_json TEXT NOT NULL,
    ambiguity_count INTEGER NOT NULL,
    holdout_json TEXT,
    PRIMARY KEY (campaign_id, candidate_id)
);
"""

MAX_TRADE_PAGE = 200
M1_STEP = BAR_DURATION[Timeframe.M1]
EQUITY_CHART_POINTS = 400


class RunState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


ACTIVE_RUN_STATES = frozenset({RunState.QUEUED, RunState.RUNNING})


class CandidateEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    labels: tuple[str, ...]
    windows: tuple[WindowMetrics, ...]
    screening: ScreeningResult
    flags: tuple[ApproximationFlag, ...]
    ambiguity_count: int


def window_labels(split: ResolvedSplit) -> tuple[str, ...]:
    return (
        "training",
        "validation",
        *(f"validation_{index + 1}" for index in range(len(split.validation_subwindows))),
    )


def _window_for(split: ResolvedSplit, label: str) -> ResolvedWindow:
    windows = dict(zip(window_labels(split), split.selectable, strict=True))
    windows["final_holdout"] = split.final_holdout
    if label not in windows:
        raise PinguinoError(ErrorCode.INVALID_RESEARCH_WINDOW, label)
    return windows[label]


def _simulate(
    definition: StrategyDefinition,
    data: MarketData,
    config: CampaignConfig,
    window: ResolvedWindow,
    *,
    costs: CostPolicy | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> SimulationResult:
    return simulate(
        definition=definition,
        signal_bars=data.signal_bars,
        execution_bars=data.execution_bars,
        contract=data.contract,
        costs=costs or config.cost_policy,
        sizing=config.sizing_policy,
        window_start=window.start,
        window_end=window.end,
        should_cancel=should_cancel,
    )


def evaluate_candidate(
    definition: StrategyDefinition,
    data: MarketData,
    config: CampaignConfig,
    split: ResolvedSplit,
    should_cancel: Callable[[], bool] | None = None,
) -> CandidateEvaluation:
    metrics: list[WindowMetrics] = []
    flags: set[ApproximationFlag] = set()
    ambiguity = 0
    for window in split.selectable:
        result = _simulate(definition, data, config, window, should_cancel=should_cancel)
        metrics.append(
            window_metrics(
                result,
                window,
                initial_balance=config.sizing_policy.initial_balance,
                units_per_lot=data.contract.units_per_lot,
            )
        )
        flags.update(result.approximation_flags)
        ambiguity += result.ambiguity_count
    screening = screen_candidate(
        candidate_id=definition.candidate_id,
        training=metrics[0],
        validation=metrics[1],
        subwindows=tuple(metrics[2:]),
        policy=config.eligibility_policy,
    )
    return CandidateEvaluation(
        labels=window_labels(split),
        windows=tuple(metrics),
        screening=screening,
        flags=tuple(sorted(flags)),
        ambiguity_count=ambiguity,
    )


def always_long_baseline(
    data: MarketData, config: CampaignConfig, window: ResolvedWindow
) -> dict[str, Any]:
    """Fixed-size long exposure held across the window, marked at bid on M1 closes.

    Swap and margin are not modelled here; the baseline shows market exposure, not a
    strategy, and is compared within the same symbol and timeframe only.
    """
    bars = [bar for bar in data.execution_bars if window.start <= bar.open_time < window.end]
    if not bars:
        return {"net_return": None, "max_drawdown": None, "reason": "no M1 bar in window"}
    contract = data.contract
    units = config.sizing_policy.fixed_volume * contract.units_per_lot
    spread = bars[0].spread_points * contract.point_size * config.cost_policy.spread_multiplier
    entry = bars[0].open + spread
    balance = config.sizing_policy.initial_balance
    commission = config.cost_policy.commission_per_lot_per_side * config.sizing_policy.fixed_volume
    peak = balance
    worst = Decimal(0)
    equity = balance
    for bar in bars:
        pnl = (bar.close - entry) * units
        if contract.quote_currency != "USD":
            pnl = pnl / bar.close
        equity = balance + pnl - commission * 2
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak)
    return {
        "net_return": str((equity - balance) / balance),
        "max_drawdown": str(worst),
        "reason": None,
    }


class CampaignStore:
    """Run status and per-candidate results, in the same SQLite file as the ledger."""

    def __init__(self, database: Path) -> None:
        self.connection = sqlite3.connect(database, check_same_thread=False, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def create(self, config: CampaignConfig, preview: dict[str, Any]) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO campaign_runs(campaign_id, config_json, preview_json, state,"
                " created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    config.campaign_id,
                    canonical_json(config),
                    canonical_json(preview),
                    RunState.QUEUED.value,
                    _now(),
                ),
            )

    def update(self, campaign_id: str, **fields: Any) -> None:
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self.connection:
            self.connection.execute(
                f"UPDATE campaign_runs SET {assignments} WHERE campaign_id = ?",
                (*fields.values(), campaign_id),
            )

    def run(self, campaign_id: str) -> sqlite3.Row | None:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute("SELECT * FROM campaign_runs WHERE campaign_id = ?", (campaign_id,))
            row: sqlite3.Row | None = cursor.fetchone()
            return row

    def runs(self) -> list[sqlite3.Row]:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute("SELECT * FROM campaign_runs ORDER BY created_at DESC")
            return cursor.fetchall()

    def mark_interrupted(self) -> list[str]:
        """Runs owned by a process that no longer exists cannot be trusted as running."""
        stale = [
            row["campaign_id"] for row in self.runs() if RunState(row["state"]) in ACTIVE_RUN_STATES
        ]
        for campaign_id in stale:
            self.update(campaign_id, state=RunState.INTERRUPTED.value, ended_at=_now())
        return stale

    def save_candidate(
        self,
        campaign_id: str,
        trial_id: str,
        definition: StrategyDefinition,
        evaluation: CandidateEvaluation,
    ) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO candidate_results(campaign_id, candidate_id, trial_id,"
                " definition_json, windows_json, screening_json, final_verdict,"
                " final_reasons_json, flags_json, ambiguity_count)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    campaign_id,
                    definition.candidate_id,
                    trial_id,
                    canonical_json(definition),
                    json.dumps(
                        [
                            {"label": label, **window.model_dump(mode="json")}
                            for label, window in zip(
                                evaluation.labels, evaluation.windows, strict=True
                            )
                        ]
                    ),
                    evaluation.screening.model_dump_json(),
                    evaluation.screening.verdict.value,
                    json.dumps(list(evaluation.screening.reasons)),
                    json.dumps([flag.value for flag in evaluation.flags]),
                    evaluation.ambiguity_count,
                ),
            )

    def set_robustness(
        self,
        campaign_id: str,
        candidate_id: str,
        *,
        stress_passed: bool | None,
        neighborhood: Verdict | None,
        final_verdict: Verdict,
        reasons: Sequence[str],
    ) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE candidate_results SET stress_passed = ?, neighborhood = ?,"
                " final_verdict = ?, final_reasons_json = ?"
                " WHERE campaign_id = ? AND candidate_id = ?",
                (
                    None if stress_passed is None else int(stress_passed),
                    None if neighborhood is None else neighborhood.value,
                    final_verdict.value,
                    json.dumps(list(reasons)),
                    campaign_id,
                    candidate_id,
                ),
            )

    def set_rank(self, campaign_id: str, candidate_id: str, position: int) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE candidate_results SET rank = ? WHERE campaign_id = ? AND candidate_id = ?",
                (position, campaign_id, candidate_id),
            )

    def set_holdout(self, campaign_id: str, candidate_id: str, payload: dict[str, Any]) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE candidate_results SET holdout_json = ?"
                " WHERE campaign_id = ? AND candidate_id = ?",
                (json.dumps(payload), campaign_id, candidate_id),
            )

    def candidates(self, campaign_id: str) -> list[sqlite3.Row]:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT * FROM candidate_results WHERE campaign_id = ?"
                " ORDER BY rank IS NULL, rank, candidate_id",
                (campaign_id,),
            )
            return cursor.fetchall()

    def candidate(self, campaign_id: str, candidate_id: str) -> sqlite3.Row | None:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT * FROM candidate_results WHERE campaign_id = ? AND candidate_id = ?",
                (campaign_id, candidate_id),
            )
            row: sqlite3.Row | None = cursor.fetchone()
            return row


def peak_memory_mb() -> float | None:
    """Peak resident memory of this process, measured by the operating system."""
    if sys.platform == "win32":

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        windll: Any = getattr(ctypes, "windll")  # noqa: B009
        # Declared types keep the 64-bit pseudo-handle from being truncated to an int.
        windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        query = windll.psapi.GetProcessMemoryInfo
        query.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        handle = windll.kernel32.GetCurrentProcess()
        if not query(handle, ctypes.byref(counters), counters.cb):
            return None
        return round(float(counters.PeakWorkingSetSize) / 2**20, 1)
    import resource

    # ru_maxrss is kilobytes on Linux and bytes on macOS.
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (2**20 if sys.platform == "darwin" else 2**10), 1)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class MarketCache:
    """Loads each dataset's bars once per process."""

    store: DatasetStore
    datasets: dict[tuple[Symbol, Timeframe], StoredDataset]
    _loaded: dict[tuple[Symbol, Timeframe], MarketData] = field(default_factory=dict)

    def __call__(self, definition: StrategyDefinition) -> MarketData:
        return self.for_key((definition.symbol, definition.timeframe))

    def for_key(self, key: tuple[Symbol, Timeframe]) -> MarketData:
        if key not in self._loaded:
            stored = self.datasets[key]
            signal, execution = self.store.load_bars(stored)
            self._loaded[key] = MarketData(
                contract=stored.manifest.contract, signal_bars=signal, execution_bars=execution
            )
        return self._loaded[key]


def resolve_datasets(
    store: DatasetStore, config: CampaignConfig
) -> dict[tuple[Symbol, Timeframe], StoredDataset]:
    datasets: dict[tuple[Symbol, Timeframe], StoredDataset] = {}
    for dataset_id in config.dataset_ids:
        stored = store.get(dataset_id)
        if stored is None:
            raise PinguinoError(ErrorCode.DATASET_NOT_FOUND, dataset_id)
        if stored.manifest.status is DatasetStatus.REJECTED:
            raise PinguinoError(ErrorCode.DATASET_REJECTED, dataset_id)
        key = dataset_key(stored)
        if key in datasets:
            raise PinguinoError(
                ErrorCode.INVALID_CAMPAIGN_CONFIG, f"two datasets for {key[0]} {key[1]}"
            )
        datasets[key] = stored
    return datasets


def check_coverage(store: DatasetStore, stored: StoredDataset, config: CampaignConfig) -> None:
    """The dataset must hold the warm-up bars before the span and reach its end."""
    policy = config.window_policy
    duration = BAR_DURATION[stored.manifest.timeframe]
    signal, _ = store.load_bars(stored)
    before = sum(1 for bar in signal if bar.open_time < policy.requested_start)
    if before < policy.warmup_signal_bars:
        raise PinguinoError(
            ErrorCode.DATASET_COVERAGE_INSUFFICIENT,
            f"{before} warm-up bars before the span, {policy.warmup_signal_bars} required",
        )
    if stored.manifest.coverage.actual_end + duration < policy.requested_end:
        raise PinguinoError(
            ErrorCode.DATASET_COVERAGE_INSUFFICIENT,
            "the dataset ends before the requested span",
        )
    coverage = stored.manifest.coverage
    if coverage.execution_start is not None and policy.requested_start < coverage.execution_start:
        raise PinguinoError(
            ErrorCode.DATASET_COVERAGE_INSUFFICIENT,
            f"M1 execution history starts at {coverage.execution_start.isoformat()}",
        )
    if (
        coverage.execution_end is not None
        and coverage.execution_end + M1_STEP < policy.requested_end
    ):
        raise PinguinoError(
            ErrorCode.DATASET_COVERAGE_INSUFFICIENT,
            f"M1 execution history ends at {coverage.execution_end.isoformat()}",
        )


def prepare_campaign(
    store: DatasetStore, config: CampaignConfig
) -> tuple[dict[str, Any], dict[tuple[Symbol, Timeframe], StoredDataset]]:
    """Validate datasets and coverage, then preview. Nothing is persisted here."""
    datasets = resolve_datasets(store, config)
    for stored in datasets.values():
        check_coverage(store, stored, config)
    preview, split = preview_campaign(config, keys=set(datasets))
    payload = {
        "preview": preview.model_dump(mode="json"),
        "validation_subwindows": [w.model_dump(mode="json") for w in split.validation_subwindows],
        "datasets": [
            {
                "dataset_id": stored.dataset_id,
                "symbol": key[0].value,
                "timeframe": key[1].value,
                "status": stored.manifest.status.value,
                "provenance": stored.manifest.provenance.value,
            }
            for key, stored in datasets.items()
        ],
    }
    return payload, datasets


class _EventToken(CancellationToken):
    def __init__(self, is_set: Callable[[], bool]) -> None:
        super().__init__()
        self._is_set = is_set

    @property
    def cancelled(self) -> bool:
        return self._cancelled or self._is_set()


def execute_campaign(
    data_dir: Path,
    config: CampaignConfig,
    *,
    is_cancelled: Callable[[], bool] = lambda: False,
    clock: Callable[[], float] = time.monotonic,
) -> RunState:
    """Run one campaign to its end state. Safe to call in a worker process."""
    database = data_dir / "research.sqlite"
    store = DatasetStore(data_dir)
    runs = CampaignStore(database)
    ledger = Ledger(database)
    campaign_id = config.campaign_id
    started = clock()
    runs.update(campaign_id, state=RunState.RUNNING.value, phase="screening", started_at=_now())
    try:
        state = _execute(store, runs, ledger, config, is_cancelled, clock)
        runs.update(
            campaign_id,
            state=state.value,
            phase="done",
            ended_at=_now(),
            duration_seconds=clock() - started,
        )
        return state
    except Exception as error:
        runs.update(
            campaign_id,
            state=RunState.FAILED.value,
            error=str(error)[:500],
            ended_at=_now(),
            duration_seconds=clock() - started,
        )
        raise
    finally:
        ledger.close()
        runs.close()
        store.close()


def _execute(
    store: DatasetStore,
    runs: CampaignStore,
    ledger: Ledger,
    config: CampaignConfig,
    is_cancelled: Callable[[], bool],
    clock: Callable[[], float],
) -> RunState:
    campaign_id = config.campaign_id
    datasets = resolve_datasets(store, config)
    market = MarketCache(store, datasets)
    split = resolve_split(config.window_policy)
    definitions = planned_definitions(config, set(datasets))
    token = _EventToken(is_cancelled)
    deadline = clock() + config.budget.max_active_minutes * 60
    per_trial = FIXED_WINDOWS_PER_TRIAL + config.window_policy.validation_subwindows

    evaluations: dict[str, CandidateEvaluation] = {}
    by_trial = {f"{campaign_id}:{order:04d}": d for order, d in enumerate(definitions)}

    def on_result(trial_id: str, evaluation: CandidateEvaluation) -> None:
        definition = by_trial[trial_id]
        evaluations[definition.candidate_id] = evaluation
        runs.save_candidate(campaign_id, trial_id, definition, evaluation)

    outcome = run_campaign(
        ledger=ledger,
        config=config,
        definitions=definitions,
        market=market,
        window_start=split.training.start,
        window_end=split.validation.end,
        token=token,
        clock=clock,
        on_result=on_result,
        evaluate=lambda d, data, cancel: evaluate_candidate(d, data, config, split, cancel),
        evaluations_per_trial=per_trial,
    )

    runs.update(campaign_id, phase="robustness")
    used = outcome.evaluations_used
    exhausted = outcome.budget_exhausted
    eligible_screenings: list[ScreeningResult] = []

    for definition in definitions:
        evaluation = evaluations.get(definition.candidate_id)
        if evaluation is None or evaluation.screening.verdict is not Verdict.ELIGIBLE:
            continue
        if token.cancelled:
            break
        data = market(definition)
        reasons: list[str] = []

        stress_passed: bool | None = None
        if used + 1 <= config.budget.max_evaluations and clock() < deadline:
            used += 1
            stressed = _simulate(
                definition, data, config, split.validation, costs=config.cost_policy.stressed()
            )
            stress_metrics = window_metrics(
                stressed,
                split.validation,
                initial_balance=config.sizing_policy.initial_balance,
                units_per_lot=data.contract.units_per_lot,
            )
            stress_passed = passes_stress(stress_metrics, config.eligibility_policy)
            if not stress_passed:
                reasons.append("stressed costs break validation return or drawdown")
        else:
            exhausted = exhausted or "max_evaluations"
            reasons.append("budget exhausted before the stress check")

        verdicts: list[Verdict] = []
        for neighbor in neighbors(definition):
            known = evaluations.get(neighbor.candidate_id)
            if known is None:
                if used + per_trial > config.budget.max_evaluations or clock() >= deadline:
                    exhausted = exhausted or "max_evaluations"
                    continue
                used += per_trial
                try:
                    known = evaluate_candidate(
                        neighbor, data, config, split, lambda: token.cancelled
                    )
                except SimulationCancelled:
                    break
            verdicts.append(known.screening.verdict)
        neighborhood = neighborhood_verdict(tuple(verdicts), config.eligibility_policy)
        if neighborhood is Verdict.REJECTED:
            reasons.append("fewer than the required share of neighbours pass validation")
        elif neighborhood is Verdict.INCONCLUSIVE:
            reasons.append("no neighbour could be evaluated")

        if stress_passed is False or neighborhood is Verdict.REJECTED:
            final = Verdict.REJECTED
        elif stress_passed is None or neighborhood is Verdict.INCONCLUSIVE:
            final = Verdict.INCONCLUSIVE
        else:
            final = Verdict.ELIGIBLE
            eligible_screenings.append(evaluation.screening)
        runs.set_robustness(
            campaign_id,
            definition.candidate_id,
            stress_passed=stress_passed,
            neighborhood=neighborhood,
            final_verdict=final,
            reasons=reasons or ["eligible after screening, stress and neighbourhood checks"],
        )

    for position, screening in enumerate(rank(tuple(eligible_screenings)), start=1):
        runs.set_rank(campaign_id, screening.candidate_id, position)

    baselines = []
    for key, stored in datasets.items():
        data = market.for_key(key)
        baselines.append(
            {
                "symbol": key[0].value,
                "timeframe": key[1].value,
                "dataset_id": stored.dataset_id,
                "cash": {"net_return": "0", "max_drawdown": "0"},
                "always_long": {
                    label: always_long_baseline(data, config, window)
                    for label, window in zip(window_labels(split), split.selectable, strict=True)
                },
            }
        )

    runs.update(
        campaign_id,
        outcome_json=json.dumps(
            outcome.model_dump(mode="json")
            | {
                "evaluations_used": used,
                "budget_exhausted": exhausted,
                "worker_peak_memory_mb": peak_memory_mb(),
                "platform": sys.platform,
            }
        ),
        baselines_json=json.dumps(baselines),
    )
    if token.cancelled:
        return RunState.CANCELLED
    if exhausted is not None or outcome.not_run > 0:
        return RunState.PARTIAL
    return RunState.COMPLETED


# --- read side ---------------------------------------------------------------------


def _load_run(runs: CampaignStore, campaign_id: str) -> tuple[sqlite3.Row, CampaignConfig]:
    row = runs.run(campaign_id)
    if row is None:
        raise PinguinoError(ErrorCode.CAMPAIGN_NOT_FOUND, campaign_id)
    return row, CampaignConfig.model_validate_json(row["config_json"])


def _load_candidate(
    runs: CampaignStore, campaign_id: str, candidate_id: str
) -> tuple[sqlite3.Row, StrategyDefinition]:
    row = runs.candidate(campaign_id, candidate_id)
    if row is None:
        raise PinguinoError(ErrorCode.CANDIDATE_NOT_FOUND, candidate_id)
    return row, StrategyDefinition.model_validate_json(row["definition_json"])


def candidate_payload(row: sqlite3.Row) -> dict[str, Any]:
    definition = json.loads(row["definition_json"])
    return {
        "candidate_id": row["candidate_id"],
        "trial_id": row["trial_id"],
        "definition": definition,
        "windows": json.loads(row["windows_json"]),
        "screening": json.loads(row["screening_json"]),
        "stress_passed": None if row["stress_passed"] is None else bool(row["stress_passed"]),
        "neighborhood": row["neighborhood"],
        "verdict": row["final_verdict"],
        "reasons": json.loads(row["final_reasons_json"]),
        "rank": row["rank"],
        "approximation_flags": json.loads(row["flags_json"]),
        "ambiguity_count": row["ambiguity_count"],
        "final_holdout": json.loads(row["holdout_json"]) if row["holdout_json"] else None,
    }


def run_payload(row: sqlite3.Row, ledger: Ledger) -> dict[str, Any]:
    counts = ledger.state_counts(row["campaign_id"])
    return {
        "campaign_id": row["campaign_id"],
        "state": row["state"],
        "phase": row["phase"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "duration_seconds": row["duration_seconds"],
        "error": row["error"],
        "config": json.loads(row["config_json"]),
        "preview": json.loads(row["preview_json"]),
        "trial_counts": {state.value: total for state, total in counts.items()},
        "outcome": json.loads(row["outcome_json"]) if row["outcome_json"] else None,
        "baselines": json.loads(row["baselines_json"]) if row["baselines_json"] else None,
    }


def _replay(
    store: DatasetStore,
    config: CampaignConfig,
    definition: StrategyDefinition,
    window: ResolvedWindow,
) -> tuple[SimulationResult, MarketData]:
    datasets = resolve_datasets(store, config)
    data = MarketCache(store, datasets)(definition)
    return _simulate(definition, data, config, window), data


def _holdout_guard(row: sqlite3.Row, label: str) -> None:
    if label == "final_holdout" and not row["holdout_json"]:
        raise PinguinoError(
            ErrorCode.HOLDOUT_ACCESS_DENIED, "open the final evaluation for this candidate first"
        )


def candidate_detail(
    store: DatasetStore,
    runs: CampaignStore,
    campaign_id: str,
    candidate_id: str,
    label: str,
    *,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Replay one window of one candidate: a page of trades and a bounded equity curve."""
    _, config = _load_run(runs, campaign_id)
    row, definition = _load_candidate(runs, campaign_id, candidate_id)
    _holdout_guard(row, label)
    window = _window_for(resolve_split(config.window_policy), label)
    result, _ = _replay(store, config, definition, window)
    limit = max(1, min(limit, MAX_TRADE_PAGE))
    offset = max(0, offset)
    curve = result.equity_curve
    stride = max(1, -(-len(curve) // EQUITY_CHART_POINTS))
    sampled = list(curve[::stride])
    if curve and sampled[-1] is not curve[-1]:
        sampled.append(curve[-1])
    return {
        "candidate_id": candidate_id,
        "window": label,
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
        "trade_total": len(result.trades),
        "offset": offset,
        "limit": limit,
        "trades": [
            trade.model_dump(mode="json") for trade in result.trades[offset : offset + limit]
        ],
        "equity": [
            {"observed_at": point.observed_at.isoformat(), "equity": str(point.equity)}
            for point in sampled
        ],
        "equity_point_total": len(curve),
        "max_drawdown": str(max_drawdown(result)),
    }


def open_holdout(
    store: DatasetStore,
    runs: CampaignStore,
    ledger: Ledger,
    campaign_id: str,
    candidate_id: str,
    reason: str,
) -> dict[str, Any]:
    """Log access first, then run the final holdout once for one frozen candidate."""
    run, config = _load_run(runs, campaign_id)
    if RunState(run["state"]) in ACTIVE_RUN_STATES:
        raise PinguinoError(ErrorCode.CAMPAIGN_ALREADY_RUNNING, campaign_id)
    row, definition = _load_candidate(runs, campaign_id, candidate_id)
    if row["holdout_json"]:
        return json.loads(row["holdout_json"])  # type: ignore[no-any-return]
    split = resolve_split(config.window_policy)
    event = open_final_holdout(
        ledger=ledger,
        campaign_id=campaign_id,
        definition=definition,
        window_policy_id=config.window_policy.policy_id,
        dataset_ids=config.dataset_ids,
        requested_at=datetime.now(UTC),
        reason=reason,
    )
    result, data = _replay(store, config, definition, split.final_holdout)
    metrics = window_metrics(
        result,
        split.final_holdout,
        initial_balance=config.sizing_policy.initial_balance,
        units_per_lot=data.contract.units_per_lot,
    )
    payload = {
        "metrics": metrics.model_dump(mode="json"),
        "access": event.model_dump(mode="json"),
        "note": "L'échantillon final ne modifie pas le classement.",
    }
    runs.set_holdout(campaign_id, candidate_id, payload)
    return payload


def export_candidate(
    store: DatasetStore, runs: CampaignStore, campaign_id: str, candidate_id: str
) -> tuple[str, bytes]:
    """Zip of strategy/configuration JSON, metrics JSON, trades/equity CSV and HTML report."""
    _, config = _load_run(runs, campaign_id)
    row, definition = _load_candidate(runs, campaign_id, candidate_id)
    split = resolve_split(config.window_policy)
    datasets = resolve_datasets(store, config)
    data = MarketCache(store, datasets)(definition)
    validation = _simulate(definition, data, config, split.validation)
    windows = tuple(
        WindowMetrics.model_validate({k: v for k, v in item.items() if k != "label"})
        for item in json.loads(row["windows_json"])
    )
    stored = datasets[(definition.symbol, definition.timeframe)]
    export = build_export(
        campaign_id=campaign_id,
        definition=definition,
        config=config,
        dataset_hashes=(stored.manifest.content_hash,),
        windows=windows,
        screening=ScreeningResult.model_validate_json(row["screening_json"]).model_copy(
            update={
                "verdict": Verdict(row["final_verdict"]),
                "reasons": tuple(json.loads(row["final_reasons_json"])),
            }
        ),
        result=validation,
        exported_at=datetime.now(UTC).replace(microsecond=0),
    )
    training = _simulate(definition, data, config, split.training)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("strategy.json", strategy_json(export))
        archive.writestr("configuration.json", canonical_json(config))
        archive.writestr("metrics.json", metrics_json(export))
        archive.writestr("trades_training.csv", trades_csv(training))
        archive.writestr("trades_validation.csv", trades_csv(validation))
        archive.writestr("equity_validation.csv", equity_csv(validation))
        archive.writestr("report.html", html_report(export))
        archive.writestr(
            "manifest.json",
            canonical_json(
                {
                    "export_hash": export.export_hash,
                    "final_verdict": row["final_verdict"],
                    "final_reasons": json.loads(row["final_reasons_json"]),
                    "dataset_provenance": stored.manifest.provenance.value,
                    "dataset_status": stored.manifest.status.value,
                    "final_holdout": json.loads(row["holdout_json"])
                    if row["holdout_json"]
                    else None,
                }
            ),
        )
    return f"pinguino-{candidate_id}.zip", buffer.getvalue()


APPROXIMATE_COST_VERSION = "approximation-1.0.0"


def suggest_config(store: DatasetStore, dataset_ids: Sequence[str]) -> CampaignConfig:
    """A startable default: the widest span every dataset covers after its warm-up.

    Costs are an explicit, unsourced approximation whatever the source, so the results
    stay flagged approximate until the operator supplies sourced values.
    """
    from pinguino.domain.policy import ResearchWindowPolicy
    from pinguino.fixtures import (
        fixture_cost_policy,
        fixture_eligibility_policy,
        fixture_sizing_policy,
    )

    if not dataset_ids:
        raise PinguinoError(ErrorCode.INVALID_CAMPAIGN_CONFIG, "select at least one dataset")
    warmup = ResearchWindowPolicy.model_fields["warmup_signal_bars"].default
    starts: list[datetime] = []
    ends: list[datetime] = []
    for dataset_id in dataset_ids:
        stored = store.get(dataset_id)
        if stored is None:
            raise PinguinoError(ErrorCode.DATASET_NOT_FOUND, dataset_id)
        signal, _ = store.load_bars(stored)
        if len(signal) <= warmup:
            raise PinguinoError(
                ErrorCode.DATASET_COVERAGE_INSUFFICIENT,
                f"{len(signal)} signal bars, more than {warmup} required",
            )
        coverage = stored.manifest.coverage
        start = signal[warmup].open_time
        end = coverage.actual_end + BAR_DURATION[stored.manifest.timeframe]
        # Only the span with M1 execution history can be evaluated.
        if coverage.execution_start is not None:
            start = max(start, coverage.execution_start)
        if coverage.execution_end is not None:
            end = min(end, coverage.execution_end + M1_STEP)
        starts.append(start)
        ends.append(end)
    start, end = max(starts), min(ends)
    if end <= start:
        raise PinguinoError(ErrorCode.DATASET_COVERAGE_INSUFFICIENT, "datasets do not overlap")
    costs = fixture_cost_policy().model_copy(update={"policy_version": APPROXIMATE_COST_VERSION})
    return CampaignConfig(
        config_version="1.0.0",
        dataset_ids=tuple(dataset_ids),
        cost_policy=costs,
        sizing_policy=fixture_sizing_policy(),
        window_policy=ResearchWindowPolicy(
            policy_version="1.0.0", requested_start=start, requested_end=end
        ),
        eligibility_policy=fixture_eligibility_policy(),
    )
