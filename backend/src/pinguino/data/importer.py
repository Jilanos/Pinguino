"""Import pipelines: raw rows in, qualified and stored dataset out.

Both sources go through the same ingestion and qualification. A synthetic fixture is
labelled synthetic in its provenance, contract and source note, so it can never pass
for broker history.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pinguino.data.mt5_adapter import fetch_history
from pinguino.data.quality import BAR_DURATION, ingest_bars, qualify_dataset
from pinguino.data.store import DatasetStore, StoredDataset
from pinguino.domain.dataset import Bar
from pinguino.domain.enums import DataProvenance, Symbol, Timeframe
from pinguino.domain.instrument import InstrumentContract
from pinguino.fixtures import FIXTURE_SPREAD_POINTS, fixture_contract
from pinguino.fixtures.series import as_raw, walk_open_times

_FIXTURE_ANCHOR: dict[Symbol, Decimal] = {
    Symbol.EURUSD: Decimal("1.10000"),
    Symbol.GBPUSD: Decimal("1.27000"),
    Symbol.USDJPY: Decimal("148.000"),
}


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _store(
    store: DatasetStore,
    *,
    symbol: Symbol,
    timeframe: Timeframe,
    contract: InstrumentContract,
    provenance: DataProvenance,
    signal_rows: list[dict[str, object]] | tuple[dict[str, object], ...],
    execution_rows: list[dict[str, object]] | tuple[dict[str, object], ...],
    start: datetime,
    end: datetime,
    source_note: str,
) -> StoredDataset:
    signal = ingest_bars(signal_rows, symbol=symbol, timeframe=timeframe, contract=contract)
    execution = ingest_bars(
        execution_rows, symbol=symbol, timeframe=Timeframe.M1, contract=contract
    )
    # The last requested signal bar must close by ``end``; incomplete bars are dropped.
    requested_end = end - BAR_DURATION[timeframe]
    complete = tuple(bar for bar in signal.bars if bar.open_time <= requested_end)
    signal = signal.model_copy(update={"bars": complete})
    imported_at = _now()
    manifest, findings = qualify_dataset(
        signal_series=signal,
        execution_series=execution,
        contract=contract,
        provenance=provenance,
        requested_start=start,
        requested_end=requested_end,
        costs_sourced=False,
        source_note=source_note,
        imported_at=imported_at,
    )
    return store.save(
        manifest=manifest,
        findings=findings,
        signal_bars=signal.bars,
        execution_bars=execution.bars,
        stored_at=imported_at,
    )


def import_mt5(
    store: DatasetStore, *, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime
) -> StoredDataset:
    history = fetch_history(symbol, timeframe, start, end)
    note = (
        f"MetaTrader 5 terminal build {history.terminal_build}, package"
        f" {history.package_version}, broker symbol {history.broker_symbol}."
        f" Approximations: {'; '.join(history.approximations)}."
    )
    return _store(
        store,
        symbol=symbol,
        timeframe=timeframe,
        contract=history.contract,
        provenance=DataProvenance.MT5_TERMINAL,
        signal_rows=history.signal_rows,
        execution_rows=history.execution_rows,
        start=start,
        end=end,
        source_note=note,
    )


def _oscillating(
    symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime
) -> tuple[Bar, ...]:
    """Deterministic triangle wave, so every template family finds signals."""
    contract = fixture_contract(symbol)
    step = BAR_DURATION[timeframe]
    count = int((end - start) / step)
    anchor = _FIXTURE_ANCHOR[symbol]
    tick = contract.tick_size
    # One full oscillation spans 40 H1 bars whatever the bar size.
    period_minutes = 40 * 60
    amplitude = tick * 1000
    bars: list[Bar] = []
    for open_time in walk_open_times(start, count, timeframe, contract.session):
        if open_time >= end:
            break
        minute = int((open_time - start).total_seconds() // 60) % period_minutes
        half = period_minutes // 2
        level = minute if minute < half else period_minutes - minute
        price = anchor + (amplitude * level / half).quantize(tick)
        bars.append(
            Bar(
                open_time=open_time,
                open=price,
                high=price + tick * 50,
                low=price - tick * 50,
                close=price,
                spread_points=FIXTURE_SPREAD_POINTS[symbol],
            )
        )
    return tuple(bars)


def import_fixture(
    store: DatasetStore, *, symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime
) -> StoredDataset:
    contract = fixture_contract(symbol)
    return _store(
        store,
        symbol=symbol,
        timeframe=timeframe,
        contract=contract,
        provenance=DataProvenance.SYNTHETIC_FIXTURE,
        signal_rows=as_raw(_oscillating(symbol, timeframe, start, end)),
        execution_rows=as_raw(_oscillating(symbol, Timeframe.M1, start, end)),
        start=start,
        end=end,
        source_note="Synthetic oscillating fixture generated locally. Not broker history.",
    )


def default_fixture_span() -> tuple[datetime, datetime]:
    # Sunday session open to Friday session close, so the span ends on a trading bar.
    start = datetime(2024, 1, 7, 21, tzinfo=UTC)
    return start, start + timedelta(days=89)
