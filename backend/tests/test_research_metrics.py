from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pinguino.domain.enums import Symbol, WindowKind
from pinguino.domain.results import EquityObservation
from pinguino.engine.simulator import SimulationResult
from pinguino.fixtures import fixture_contract
from pinguino.research.metrics import max_drawdown, window_metrics
from pinguino.research.windows import ResolvedWindow

START = datetime(2024, 1, 8, tzinfo=UTC)
WINDOW = ResolvedWindow(kind=WindowKind.VALIDATION, start=START, end=START + timedelta(days=1))
UNITS_PER_LOT = fixture_contract(Symbol.EURUSD).units_per_lot


def _result(equities: list[str]) -> SimulationResult:
    return SimulationResult(
        fills=(),
        trades=(),
        equity_curve=tuple(
            EquityObservation(
                observed_at=START + timedelta(minutes=index),
                equity=Decimal(value),
                realized_balance=Decimal(value),
            )
            for index, value in enumerate(equities)
        ),
        rejected_signals=(),
        ambiguity_count=0,
        forced_liquidation=False,
        approximation_flags=(),
    )


class TestDrawdown:
    def test_is_the_largest_peak_to_trough_fall(self) -> None:
        # Peak 12 000 falling to 9 000 is a 25% fall, worse than 10 000 -> 9 500.
        assert max_drawdown(_result(["10000", "9500", "12000", "9000", "11000"])) == Decimal("0.25")

    def test_a_monotonic_rise_has_no_drawdown(self) -> None:
        assert max_drawdown(_result(["10000", "10500", "11000"])) == Decimal(0)


class TestWindowMetrics:
    def test_a_window_without_trades_reports_null_ratios_with_reasons(self) -> None:
        metrics = window_metrics(
            _result(["10000", "10000"]),
            WINDOW,
            initial_balance=Decimal("10000"),
            units_per_lot=UNITS_PER_LOT,
        )
        assert metrics.trade_count == 0
        assert metrics.win_rate is None
        assert metrics.profit_factor is None
        assert metrics.undefined_reasons
        assert metrics.net_return == Decimal(0)

    def test_net_return_is_measured_against_the_initial_balance(self) -> None:
        metrics = window_metrics(
            _result(["10000", "10500"]),
            WINDOW,
            initial_balance=Decimal("10000"),
            units_per_lot=UNITS_PER_LOT,
        )
        assert metrics.net_return == Decimal("0.05")
