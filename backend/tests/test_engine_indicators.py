from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pinguino.domain.dataset import Bar
from pinguino.engine.indicators import rolling_extremes, sma, true_range, wilder_atr, wilder_rsi

START = datetime(2024, 1, 8, tzinfo=UTC)


def _bars(closes: list[str], *, span: str = "0.001") -> list[Bar]:
    half = Decimal(span) / 2
    return [
        Bar(
            open_time=START + timedelta(hours=index),
            open=Decimal(close),
            high=Decimal(close) + half,
            low=Decimal(close) - half,
            close=Decimal(close),
            spread_points=Decimal("10"),
        )
        for index, close in enumerate(closes)
    ]


class TestSma:
    def test_is_undefined_before_the_period_is_complete(self) -> None:
        values = [Decimal(n) for n in (1, 2, 3, 4)]
        assert sma(values, 3) == [None, None, Decimal(2), Decimal(3)]


class TestTrueRange:
    def test_first_bar_is_undefined_and_range_uses_the_previous_close(self) -> None:
        bars = _bars(["1.0", "1.0", "2.0"], span="0.2")
        ranges = true_range(bars)
        assert ranges[0] is None
        assert ranges[1] == Decimal("0.2")
        # High 2.1 against previous close 1.0 dominates the 0.2 bar range.
        assert ranges[2] == Decimal("1.1")


class TestWilderAtr:
    def test_constant_range_gives_exactly_that_range(self) -> None:
        bars = _bars(["1.10000"] * 30, span="0.00100")
        atr = wilder_atr(bars, 14)
        assert atr[13] is None
        assert atr[14] == Decimal("0.00100")
        assert atr[29] == Decimal("0.00100")

    def test_is_undefined_when_the_series_is_shorter_than_the_seed(self) -> None:
        assert all(value is None for value in wilder_atr(_bars(["1.0"] * 10), 14))


class TestWilderRsi:
    def test_a_pure_uptrend_seeds_at_one_hundred(self) -> None:
        closes = [Decimal(1) + Decimal(index) for index in range(20)]
        rsi = wilder_rsi(closes, 14)
        assert rsi[13] is None
        assert rsi[14] == Decimal(100)

    def test_a_pure_downtrend_seeds_at_zero(self) -> None:
        closes = [Decimal(100) - Decimal(index) for index in range(20)]
        assert wilder_rsi(closes, 14)[14] == Decimal(0)

    def test_alternating_equal_moves_sit_at_fifty(self) -> None:
        closes = [Decimal(100) + (Decimal(1) if index % 2 else Decimal(0)) for index in range(40)]
        value = wilder_rsi(closes, 14)[39]
        assert value is not None
        assert Decimal("45") < value < Decimal("55")


class TestRollingExtremes:
    def test_window_excludes_the_current_bar(self) -> None:
        bars = _bars(["1.0", "2.0", "3.0"], span="0.0")
        highs, lows = rolling_extremes(bars, 2)
        assert highs[:2] == [None, None]
        assert highs[2] == Decimal("2.0")
        assert lows[2] == Decimal("1.0")
