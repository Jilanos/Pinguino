"""Read-only MT5 adapter, exercised against a strict stand-in module.

The stand-in exposes only market-data calls. Any other attribute access fails, which
proves the adapter never reaches for order, settings or account-switching functions.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pinguino.data import mt5_adapter
from pinguino.data.importer import import_mt5
from pinguino.data.store import DatasetStore
from pinguino.domain.enums import DataProvenance, Symbol, Timeframe
from pinguino.domain.errors import ErrorCode, PinguinoError

START = datetime(2024, 1, 8, tzinfo=UTC)
ALLOWED = {
    "initialize",
    "shutdown",
    "last_error",
    "terminal_info",
    "symbols_get",
    "symbol_info",
    "account_info",
    "copy_rates_range",
    "TIMEFRAME_M1",
    "TIMEFRAME_H1",
    "TIMEFRAME_H4",
    "__version__",
}


def _rates(step: timedelta, count: int) -> list[dict[str, Any]]:
    rows = []
    for index in range(count):
        moment = START + step * index
        price = 1.1 + (index % 7) * 0.0001
        rows.append(
            {
                "time": int(moment.timestamp()),
                "open": price,
                "high": price + 0.0002,
                "low": price - 0.0002,
                "close": price,
                "spread": 12,
            }
        )
    return rows


class StrictMt5:
    TIMEFRAME_M1, TIMEFRAME_H1, TIMEFRAME_H4 = 1, 16385, 16388
    __version__ = "5.0.test"

    def __init__(self, *, connected: bool = True, symbols: tuple[str, ...] = ("EURUSD.r",)):
        self.connected = connected
        self.symbols = symbols
        self.calls: list[str] = []

    def __getattribute__(self, name: str) -> Any:
        if not name.startswith("_") and name not in ALLOWED | {"connected", "symbols", "calls"}:
            raise AttributeError(f"forbidden MT5 call: {name}")
        return object.__getattribute__(self, name)

    def initialize(self) -> bool:
        self.calls.append("initialize")
        return True

    def shutdown(self) -> None:
        self.calls.append("shutdown")

    def last_error(self) -> tuple[int, str]:
        return (1, "ok")

    def terminal_info(self) -> SimpleNamespace:
        return SimpleNamespace(connected=self.connected, build=4755)

    def symbols_get(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=name) for name in (*self.symbols, "XAUUSD")]

    def symbol_info(self, name: str) -> SimpleNamespace:
        return SimpleNamespace(
            digits=5,
            point=0.00001,
            trade_tick_size=0.00001,
            currency_base="EUR",
            currency_profit="USD",
            trade_contract_size=100000.0,
            volume_min=0.01,
            volume_max=500.0,
            volume_step=0.01,
            swap_rollover3days=3,
        )

    def account_info(self) -> SimpleNamespace:
        return SimpleNamespace(leverage=100, margin_so_so=50.0)

    def copy_rates_range(self, name: str, timeframe: int, start: datetime, end: datetime) -> Any:
        self.calls.append(f"copy_rates_range:{timeframe}")
        if timeframe == self.TIMEFRAME_M1:
            return _rates(timedelta(minutes=1), 60 * 24)
        return _rates(timedelta(hours=1), 24)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> StrictMt5:
    module = StrictMt5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", module)
    return module


class TestDiagnostic:
    def test_a_connected_terminal_reports_resolved_broker_symbols(self, fake: StrictMt5) -> None:
        diagnostic = mt5_adapter.diagnose_source()
        assert diagnostic.synthetic_mode_only is False
        assert diagnostic.terminal_connected is True
        assert diagnostic.available_symbols == {"EURUSD": "EURUSD.r"}
        assert diagnostic.terminal_build == 4755
        assert fake.calls[-1] == "shutdown"

    def test_a_disconnected_terminal_is_diagnosed_not_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "MetaTrader5", StrictMt5(connected=False))
        diagnostic = mt5_adapter.diagnose_source()
        assert diagnostic.code is ErrorCode.MT5_TERMINAL_DISCONNECTED


class TestHistory:
    def test_history_is_read_with_utc_times_and_the_broker_contract(self, fake: StrictMt5) -> None:
        history = mt5_adapter.fetch_history(
            Symbol.EURUSD, Timeframe.H1, START, START + timedelta(days=1)
        )
        assert history.broker_symbol == "EURUSD.r"
        assert history.signal_rows[0]["open_time"] == START
        assert history.signal_rows[0]["spread_points"] == 12
        contract = history.contract
        assert contract.provenance is DataProvenance.MT5_TERMINAL
        assert contract.leverage == 100
        assert contract.stop_out_fraction == pytest.approx(0.5)
        assert contract.volume_max == 500
        # MT5 Wednesday (3) is Python weekday 2.
        assert contract.triple_swap_weekday == 2
        assert any("rollover" in item for item in history.approximations)
        assert contract.rollover_hour_utc == 0

    def test_a_symbol_missing_from_the_terminal_is_not_added(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "MetaTrader5", StrictMt5(symbols=()))
        with pytest.raises(PinguinoError) as error:
            mt5_adapter.fetch_history(Symbol.GBPUSD, Timeframe.H1, START, START + timedelta(1))
        assert error.value.code is ErrorCode.MT5_SYMBOL_UNAVAILABLE

    def test_an_mt5_import_is_stored_with_terminal_provenance(
        self, fake: StrictMt5, tmp_path: Path
    ) -> None:
        store = DatasetStore(tmp_path)
        stored = import_mt5(
            store,
            symbol=Symbol.EURUSD,
            timeframe=Timeframe.H1,
            start=START,
            end=START + timedelta(days=1),
        )
        assert stored.manifest.provenance is DataProvenance.MT5_TERMINAL
        assert "EURUSD.r" in stored.manifest.source_note
        signal, execution = store.load_bars(stored)
        assert len(signal) == 24
        assert len(execution) == 60 * 24


class TestNoOrderSurface:
    def test_the_adapter_source_names_no_order_or_credential_function(self) -> None:
        source = Path(mt5_adapter.__file__).read_text(encoding="utf-8")
        for forbidden in ("order_send", "order_check", "positions_", "login", "password"):
            assert forbidden not in source


class TestSessionInference:
    def test_the_weekly_session_is_read_from_the_bars_as_provided(self) -> None:
        # Terminal timeline: Monday 00:00 to a last bar at Friday 23:59, three weeks.
        rows = []
        monday = datetime(2026, 8, 31, tzinfo=UTC)
        for week in range(3):
            start = monday + timedelta(weeks=week)
            for minute in range(0, 5 * 24 * 60, 30):
                rows.append({"open_time": start + timedelta(minutes=minute)})
            rows.append({"open_time": start + timedelta(days=4, hours=23, minutes=59)})
        session = mt5_adapter.infer_session(rows)
        assert session is not None
        assert (session.open_weekday, session.open_hour_utc) == (0, 0)
        assert (session.close_weekday, session.close_hour_utc) == (5, 0)
        assert session.is_open(monday + timedelta(days=4, hours=23, minutes=30))
        assert not session.is_open(monday + timedelta(days=6, hours=22))

    def test_a_span_without_a_weekend_falls_back_to_the_default_session(self) -> None:
        rows = [{"open_time": START + timedelta(minutes=m)} for m in range(60)]
        assert mt5_adapter.infer_session(rows) is None
