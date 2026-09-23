"""Bar ingestion and dataset qualification.

Import is conservative: a bar that cannot be trusted is rejected with a reason, and an
unexplained gap inside an open session quarantines the range it covers rather than being
interpolated. Expected weekend closure is not a gap.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pinguino.domain.dataset import Bar, CoverageReport, DatasetManifest
from pinguino.domain.enums import DataProvenance, DatasetStatus, Symbol, Timeframe
from pinguino.domain.identity import content_hash
from pinguino.domain.instrument import InstrumentContract, WeeklySession

BAR_DURATION: dict[Timeframe, timedelta] = {
    Timeframe.M1: timedelta(minutes=1),
    Timeframe.H1: timedelta(hours=1),
    Timeframe.H4: timedelta(hours=4),
}

MANIFEST_VERSION = "1.1.0"


class FindingCode(StrEnum):
    NONFINITE_PRICE = "nonfinite_price"
    INVALID_OHLC = "invalid_ohlc"
    UNDECLARED_TIMEZONE = "undeclared_timezone"
    DUPLICATE_TIMESTAMP = "duplicate_timestamp"
    NONMONOTONIC_TIMESTAMP = "nonmonotonic_timestamp"
    MISALIGNED_TIMESTAMP = "misaligned_timestamp"
    OPEN_SESSION_GAP = "open_session_gap"
    COVERAGE_SHORTFALL = "coverage_shortfall"
    MISSING_EXECUTION_COVERAGE = "missing_execution_coverage"
    DELAYED_EXECUTION = "delayed_execution"
    MISSING_COST_COMPONENT = "missing_cost_component"


class QualityFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: FindingCode
    detail: str
    at: datetime | None = None
    range_start: datetime | None = None
    range_end: datetime | None = None


class QualifiedSeries(BaseModel):
    """Accepted bars plus every finding raised while importing them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: Symbol
    timeframe: Timeframe
    bars: tuple[Bar, ...]
    findings: tuple[QualityFinding, ...]
    quarantined: tuple[tuple[datetime, datetime], ...]
    rejected_count: int = Field(ge=0)

    @property
    def usable_bars(self) -> tuple[Bar, ...]:
        """Bars outside every quarantined range."""
        if not self.quarantined:
            return self.bars
        return tuple(
            bar
            for bar in self.bars
            if not any(start <= bar.open_time < end for start, end in self.quarantined)
        )


def _parse_bar(raw: dict[str, Any]) -> tuple[Bar | None, QualityFinding | None]:
    try:
        return Bar.model_validate(raw), None
    except (ValidationError, InvalidOperation, ValueError) as error:
        message = str(error)
        if "timezone" in message or "must be UTC" in message:
            code = FindingCode.UNDECLARED_TIMEZONE
        elif "finite" in message or "not a valid decimal" in message.lower():
            code = FindingCode.NONFINITE_PRICE
        else:
            code = FindingCode.INVALID_OHLC
        at = raw.get("open_time")
        return None, QualityFinding(
            code=code,
            detail=message.splitlines()[0],
            at=at if isinstance(at, datetime) and at.utcoffset() is not None else None,
        )


def _is_nonfinite(raw: dict[str, Any]) -> bool:
    for key in ("open", "high", "low", "close"):
        value = raw.get(key)
        if isinstance(value, float) and value != value:
            return True
        if isinstance(value, Decimal) and not value.is_finite():
            return True
        if isinstance(value, str) and value.strip().lower() in {"nan", "inf", "-inf"}:
            return True
    return False


def _expected_next(previous: datetime, timeframe: Timeframe, session: Any) -> datetime:
    """Next timestamp the session is expected to produce after ``previous``."""
    step = BAR_DURATION[timeframe]
    candidate = previous + step
    guard = 0
    while not session.is_open(candidate) and guard < 20_160:
        candidate += step
        guard += 1
    return candidate


def ingest_bars(
    raw_bars: Iterable[dict[str, Any]],
    *,
    symbol: Symbol,
    timeframe: Timeframe,
    contract: InstrumentContract,
) -> QualifiedSeries:
    """Validate, order and gap-check raw bars without repairing any of them."""
    accepted: list[Bar] = []
    findings: list[QualityFinding] = []
    rejected = 0
    seen: set[datetime] = set()
    step = BAR_DURATION[timeframe]

    for raw in raw_bars:
        if _is_nonfinite(raw):
            rejected += 1
            findings.append(
                QualityFinding(code=FindingCode.NONFINITE_PRICE, detail="nonfinite price in bar")
            )
            continue
        bar, finding = _parse_bar(raw)
        if bar is None:
            rejected += 1
            findings.append(finding)  # type: ignore[arg-type]
            continue
        if bar.open_time in seen:
            rejected += 1
            findings.append(
                QualityFinding(
                    code=FindingCode.DUPLICATE_TIMESTAMP,
                    detail="duplicate bar timestamp",
                    at=bar.open_time,
                )
            )
            continue
        if accepted and bar.open_time < accepted[-1].open_time:
            rejected += 1
            findings.append(
                QualityFinding(
                    code=FindingCode.NONMONOTONIC_TIMESTAMP,
                    detail="bar timestamp precedes the previous bar",
                    at=bar.open_time,
                )
            )
            continue
        if (bar.open_time - datetime.min.replace(tzinfo=bar.open_time.tzinfo)) % step:
            rejected += 1
            findings.append(
                QualityFinding(
                    code=FindingCode.MISALIGNED_TIMESTAMP,
                    detail=f"bar is not aligned to the native {timeframe} boundary",
                    at=bar.open_time,
                )
            )
            continue
        seen.add(bar.open_time)
        accepted.append(bar)

    # Only the missing span is quarantined; the bars on either side stay usable.
    quarantined: list[tuple[datetime, datetime]] = []
    for previous, current in zip(accepted, accepted[1:], strict=False):
        expected = _expected_next(previous.open_time, timeframe, contract.session)
        if current.open_time > expected:
            quarantined.append((expected, current.open_time))
            findings.append(
                QualityFinding(
                    code=FindingCode.OPEN_SESSION_GAP,
                    detail="unexplained gap while the session was open",
                    range_start=expected,
                    range_end=current.open_time,
                )
            )

    return QualifiedSeries(
        symbol=symbol,
        timeframe=timeframe,
        bars=tuple(accepted),
        findings=tuple(findings),
        quarantined=tuple(quarantined),
        rejected_count=rejected,
    )


def _covered_signal_bars(
    signal_bars: Sequence[Bar],
    execution_bars: Sequence[Bar],
    timeframe: Timeframe,
    session: WeeklySession,
) -> list[QualityFinding]:
    """Check that each in-session signal close has an executable M1 bar.

    Entry happens at the first M1 open at or after the close within the same session.
    A missing close minute with a later M1 in the session only delays the entry; a close
    outside the M1 history cannot trade at all and is reported as one range per side.
    Execution never falls back to H1/H4. A bar closing exactly on the weekly session
    close has no next M1 bar by design and is not a finding.
    """
    if not execution_bars:
        return [
            QualityFinding(
                code=FindingCode.MISSING_EXECUTION_COVERAGE,
                detail="no M1 execution history was supplied",
            )
        ]
    execution_times = [bar.open_time for bar in execution_bars]
    first_execution, last_execution = execution_times[0], execution_times[-1]
    step = BAR_DURATION[timeframe]
    before: list[datetime] = []
    after: list[datetime] = []
    findings: list[QualityFinding] = []
    for bar in signal_bars:
        close_time = bar.open_time + step
        if not session.is_open(close_time):
            continue
        if close_time < first_execution:
            before.append(close_time)
            continue
        if close_time > last_execution:
            after.append(close_time)
            continue
        index = bisect_left(execution_times, close_time)
        next_open = execution_times[index]
        if next_open == close_time:
            continue
        if session.is_open_throughout(close_time, next_open):
            findings.append(
                QualityFinding(
                    code=FindingCode.DELAYED_EXECUTION,
                    detail=f"no M1 bar at the signal close; entry waits until {next_open:%H:%M}",
                    at=close_time,
                )
            )
        else:
            findings.append(
                QualityFinding(
                    code=FindingCode.MISSING_EXECUTION_COVERAGE,
                    detail="no M1 bar before the session closes; this signal cannot trade",
                    at=close_time,
                )
            )
    for closes, side in ((before, "before the start"), (after, "after the end")):
        if closes:
            findings.append(
                QualityFinding(
                    code=FindingCode.MISSING_EXECUTION_COVERAGE,
                    detail=f"{len(closes)} signal closes fall {side} of the M1 history",
                    range_start=closes[0],
                    range_end=closes[-1],
                )
            )
    return findings


def qualify_dataset(
    *,
    signal_series: QualifiedSeries,
    execution_series: QualifiedSeries,
    contract: InstrumentContract,
    provenance: DataProvenance,
    requested_start: datetime,
    requested_end: datetime,
    costs_sourced: bool,
    source_note: str,
    imported_at: datetime,
) -> tuple[DatasetManifest, tuple[QualityFinding, ...]]:
    """Produce the manifest and the findings that determine its status.

    A dataset is ``qualified`` only when nothing was quarantined or rejected, the
    requested span is covered and every signal bar has its M1 execution bar. Missing
    cost sourcing downgrades it to ``approximate``; missing execution coverage or an
    empty accepted series rejects it.
    """
    findings: list[QualityFinding] = [*signal_series.findings, *execution_series.findings]
    usable = signal_series.usable_bars

    findings.extend(
        _covered_signal_bars(
            usable, execution_series.usable_bars, signal_series.timeframe, contract.session
        )
    )

    if not usable:
        actual_start, actual_end = requested_start, requested_start
    else:
        actual_start, actual_end = usable[0].open_time, usable[-1].open_time
        if actual_start > requested_start or actual_end < requested_end:
            findings.append(
                QualityFinding(
                    code=FindingCode.COVERAGE_SHORTFALL,
                    detail="actual coverage is shorter than the requested span",
                    range_start=actual_start,
                    range_end=actual_end,
                )
            )

    if not costs_sourced:
        findings.append(
            QualityFinding(
                code=FindingCode.MISSING_COST_COMPONENT,
                detail="cost profile is an explicit approximation, not sourced history",
            )
        )

    codes = {finding.code for finding in findings}
    execution = execution_series.usable_bars
    overlap = bool(execution) and any(
        execution[0].open_time
        <= bar.open_time + BAR_DURATION[signal_series.timeframe]
        <= execution[-1].open_time
        for bar in usable
    )
    # Partial M1 coverage leaves a usable dataset; only no executable overlap rejects it.
    if not usable or not overlap:
        status = DatasetStatus.REJECTED
    elif codes:
        status = DatasetStatus.APPROXIMATE
    else:
        status = DatasetStatus.QUALIFIED

    coverage = CoverageReport(
        requested_start=requested_start,
        requested_end=requested_end,
        actual_start=actual_start,
        actual_end=actual_end,
        bar_count=len(usable),
        quarantined_ranges=signal_series.quarantined + execution_series.quarantined,
        rejected_bar_count=signal_series.rejected_count + execution_series.rejected_count,
        execution_start=execution[0].open_time if execution else None,
        execution_end=execution[-1].open_time if execution else None,
    )

    manifest = DatasetManifest(
        manifest_version=MANIFEST_VERSION,
        symbol=signal_series.symbol,
        timeframe=signal_series.timeframe,
        provenance=provenance,
        status=status,
        contract=contract,
        coverage=coverage,
        content_hash=content_hash([bar.model_dump(mode="json") for bar in usable]),
        source_note=source_note,
        imported_at=imported_at,
    )
    return manifest, tuple(findings)
