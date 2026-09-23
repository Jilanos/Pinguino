"""Read-only MetaTrader 5 boundary.

The package is imported lazily and only here: the domain engine stays portable and a
missing package or terminal produces a diagnostic instead of a failure. Nothing in this
module submits orders, changes terminal settings, switches accounts or reads credentials.
"""

from __future__ import annotations

import importlib
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import ModuleType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pinguino.domain.enums import DataProvenance, Symbol, Timeframe
from pinguino.domain.errors import ErrorCode, PinguinoError
from pinguino.domain.instrument import InstrumentContract, WeeklySession

MT5_MODULE_NAME = "MetaTrader5"


class SourceDiagnostic(BaseModel):
    """Why the MT5 source is or is not usable right now."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_available: bool
    terminal_available: bool
    platform: str
    terminal_connected: bool = False
    terminal_build: int | None = None
    package_version: str | None = None
    available_symbols: dict[str, str] = Field(default_factory=dict)
    code: ErrorCode | None = None
    detail: str | None = None

    @property
    def synthetic_mode_only(self) -> bool:
        return not (self.package_available and self.terminal_available)


def _load_module() -> ModuleType | None:
    try:
        return importlib.import_module(MT5_MODULE_NAME)
    except ImportError:
        return None


def diagnose_source() -> SourceDiagnostic:
    """Inspect availability without mutating the terminal or requiring one."""
    module = _load_module()
    if module is None:
        return SourceDiagnostic(
            package_available=False,
            terminal_available=False,
            platform=sys.platform,
            code=ErrorCode.MT5_PACKAGE_UNAVAILABLE,
            detail=f"{MT5_MODULE_NAME} is not installed in this environment",
        )
    initialized = bool(module.initialize())
    try:
        if not initialized:
            return SourceDiagnostic(
                package_available=True,
                terminal_available=False,
                platform=sys.platform,
                code=ErrorCode.MT5_TERMINAL_UNAVAILABLE,
                detail=str(module.last_error()),
            )
        info = module.terminal_info()
        connected = bool(getattr(info, "connected", False))
        return SourceDiagnostic(
            package_available=True,
            terminal_available=True,
            platform=sys.platform,
            terminal_connected=connected,
            terminal_build=getattr(info, "build", None),
            package_version=getattr(module, "__version__", None),
            available_symbols=_resolved_symbols(module),
            code=None if connected else ErrorCode.MT5_TERMINAL_DISCONNECTED,
            detail=None if connected else "terminal is running but not connected to a server",
        )
    finally:
        if initialized:
            module.shutdown()


def _resolved_symbols(module: Any) -> dict[str, str]:
    """Map each supported pair to a broker symbol already present in the terminal.

    Symbols are only enumerated, never added to Market Watch: selecting them is a manual
    setup step so the adapter does not change terminal state.
    """
    names = [item.name for item in (module.symbols_get() or ())]
    resolved: dict[str, str] = {}
    for symbol in Symbol:
        exact = [name for name in names if name == symbol.value]
        prefixed = sorted(name for name in names if name.startswith(symbol.value))
        match = (exact or prefixed or [None])[0]
        if match is not None:
            resolved[symbol.value] = match
    return resolved


class Mt5History(BaseModel):
    """Raw bars and the contract read from the terminal for one pair."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    broker_symbol: str
    contract: InstrumentContract
    signal_rows: tuple[dict[str, Any], ...]
    execution_rows: tuple[dict[str, Any], ...]
    terminal_build: int | None
    package_version: str | None
    approximations: tuple[str, ...]


_TIMEFRAME_ATTRIBUTE: dict[Timeframe, str] = {
    Timeframe.M1: "TIMEFRAME_M1",
    Timeframe.H1: "TIMEFRAME_H1",
    Timeframe.H4: "TIMEFRAME_H4",
}

#: The terminal's own timeline is used as provided: its day starts at 00:00, which is
#: where MT5 books the rollover.
TERMINAL_ROLLOVER_HOUR = 0
MT5_CONTRACT_VERSION = "mt5-1.1.0"
#: A pause at least this long between two M1 bars is a weekly closure, not a gap.
WEEKEND_MIN_PAUSE = timedelta(hours=24)

#: Request span per call, well below the terminal's default 100,000-bar limit.
FETCH_CHUNK: dict[Timeframe, timedelta] = {
    Timeframe.M1: timedelta(days=20),
    Timeframe.H1: timedelta(days=1500),
    Timeframe.H4: timedelta(days=6000),
}


def _rows(
    module: Any, broker_symbol: str, timeframe: Timeframe, start: datetime, end: datetime
) -> tuple[dict[str, Any], ...]:
    """Bars with ``start <= open < end``, read in chunks.

    The terminal refuses a single request larger than its bar limit, and may answer an
    out-of-history chunk with bars outside it, so each chunk is filtered to its own range.
    """
    step = FETCH_CHUNK[timeframe]
    by_time: dict[int, Any] = {}
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + step, end)
        rates = module.copy_rates_range(
            broker_symbol, getattr(module, _TIMEFRAME_ATTRIBUTE[timeframe]), cursor, chunk_end
        )
        if rates is None:
            raise PinguinoError(ErrorCode.MT5_HISTORY_UNAVAILABLE, str(module.last_error()))
        low, high = int(cursor.timestamp()), int(chunk_end.timestamp())
        for rate in rates:
            moment = int(rate["time"])
            if low <= moment < high:
                by_time[moment] = rate
        cursor = chunk_end
    # Bar times are kept exactly as the terminal provides them; nothing is shifted.
    return tuple(
        {
            "open_time": datetime.fromtimestamp(moment, UTC),
            "open": Decimal(repr(float(rate["open"]))),
            "high": Decimal(repr(float(rate["high"]))),
            "low": Decimal(repr(float(rate["low"]))),
            "close": Decimal(repr(float(rate["close"]))),
            "spread_points": Decimal(int(rate["spread"])),
        }
        for moment, rate in sorted(by_time.items())
    )


def infer_session(rows: Sequence[dict[str, Any]]) -> WeeklySession | None:
    """The weekly session as the M1 history shows it, in the terminal's own timeline.

    Each pause of a day or more is a weekend: the bar after it gives the weekly open and
    the close of the bar before it gives the weekly close. The most frequent boundary wins,
    so a holiday week does not move the session.
    """
    opens: Counter[tuple[int, int]] = Counter()
    closes: Counter[tuple[int, int]] = Counter()
    minute = timedelta(minutes=1)
    for previous, current in zip(rows, rows[1:], strict=False):
        before, after = previous["open_time"], current["open_time"]
        if after - before < WEEKEND_MIN_PAUSE:
            continue
        opens[(after.weekday(), after.hour)] += 1
        closed = before + minute
        if closed.minute or closed.second:
            closed = closed.replace(minute=0, second=0) + timedelta(hours=1)
        closes[(closed.weekday(), closed.hour)] += 1
    if not opens:
        return None
    (open_weekday, open_hour), _ = opens.most_common(1)[0]
    (close_weekday, close_hour), _ = closes.most_common(1)[0]
    return WeeklySession(
        open_weekday=open_weekday,
        open_hour_utc=open_hour,
        close_weekday=close_weekday,
        close_hour_utc=close_hour,
    )


def _contract(
    module: Any,
    symbol: Symbol,
    broker_symbol: str,
    execution_rows: Sequence[dict[str, Any]],
) -> tuple[InstrumentContract, list[str]]:
    info = module.symbol_info(broker_symbol)
    if info is None:
        raise PinguinoError(
            ErrorCode.MT5_HISTORY_UNAVAILABLE, f"no symbol info for {broker_symbol}"
        )
    account = module.account_info()
    approximations = [
        "timestamps kept as provided by the terminal, not shifted",
        f"rollover at {TERMINAL_ROLLOVER_HOUR:02d}:00 in the terminal timeline",
    ]
    session = infer_session(execution_rows)
    if session is None:
        session = WeeklySession()
        approximations.append("no weekend in the M1 history; default weekly session assumed")
    else:
        approximations.append(
            "weekly session inferred from the M1 history: weekday"
            f" {session.open_weekday} {session.open_hour_utc:02d}:00 to weekday"
            f" {session.close_weekday} {session.close_hour_utc:02d}:00"
        )
    leverage = Decimal(getattr(account, "leverage", 0) or 0)
    if leverage <= 0:
        leverage = Decimal(30)
        approximations.append("account leverage unavailable, 30:1 assumed")
    stop_out = Decimal(str(getattr(account, "margin_so_so", 0) or 0)) / Decimal(100)
    if not Decimal(0) < stop_out <= Decimal(1):
        stop_out = Decimal("0.5")
        approximations.append("stop-out level unavailable as a percentage, 50% assumed")
    tick_size = Decimal(repr(float(info.trade_tick_size)))
    point = Decimal(repr(float(info.point)))
    contract = InstrumentContract(
        symbol=symbol,
        provenance=DataProvenance.MT5_TERMINAL,
        contract_version=MT5_CONTRACT_VERSION,
        digits=int(info.digits),
        tick_size=tick_size,
        point_size=max(point, tick_size),
        base_currency=str(info.currency_base),
        quote_currency=str(info.currency_profit),
        units_per_lot=Decimal(repr(float(info.trade_contract_size))),
        volume_min=Decimal(repr(float(info.volume_min))),
        volume_max=Decimal(repr(float(info.volume_max))),
        volume_step=Decimal(repr(float(info.volume_step))),
        leverage=leverage,
        stop_out_fraction=stop_out,
        session=session,
        rollover_hour_utc=TERMINAL_ROLLOVER_HOUR,
        triple_swap_weekday=_triple_swap_weekday(int(getattr(info, "swap_rollover3days", 3))),
    )
    return contract, approximations


def _triple_swap_weekday(mt5_day: int) -> int:
    """MT5 counts Sunday as 0; the domain uses Python weekdays with Monday as 0."""
    return (mt5_day - 1) % 7


def fetch_history(
    symbol: Symbol, timeframe: Timeframe, start: datetime, end: datetime
) -> Mt5History:
    """Read the contract, signal bars and M1 bars for one pair. Read-only."""
    module = _load_module()
    if module is None:
        raise PinguinoError(ErrorCode.MT5_PACKAGE_UNAVAILABLE)
    if not module.initialize():
        raise PinguinoError(ErrorCode.MT5_TERMINAL_UNAVAILABLE, str(module.last_error()))
    try:
        broker_symbol = _resolved_symbols(module).get(symbol.value)
        if broker_symbol is None:
            raise PinguinoError(ErrorCode.MT5_SYMBOL_UNAVAILABLE, symbol.value)
        execution_rows = _rows(module, broker_symbol, Timeframe.M1, start, end)
        contract, approximations = _contract(module, symbol, broker_symbol, execution_rows)
        info = module.terminal_info()
        return Mt5History(
            broker_symbol=broker_symbol,
            contract=contract,
            signal_rows=_rows(module, broker_symbol, timeframe, start, end),
            execution_rows=execution_rows,
            terminal_build=getattr(info, "build", None),
            package_version=getattr(module, "__version__", None),
            approximations=tuple(approximations),
        )
    finally:
        module.shutdown()
