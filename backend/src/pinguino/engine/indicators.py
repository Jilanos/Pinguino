"""Indicators over closed bid bars.

Every series is index-aligned with its input and holds ``None`` wherever the value is
still undefined, so a strategy can never read a value that its warm-up has not produced.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pinguino.domain.dataset import Bar


def sma(values: Sequence[Decimal], period: int) -> list[Decimal | None]:
    """Arithmetic trailing mean, defined from the ``period``-th value onwards."""
    if period < 1:
        raise ValueError("period must be positive")
    out: list[Decimal | None] = [None] * len(values)
    running = Decimal(0)
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        if index >= period - 1:
            out[index] = running / period
    return out


def true_range(bars: Sequence[Bar]) -> list[Decimal | None]:
    """True range needs the previous close, so the first bar is undefined."""
    out: list[Decimal | None] = [None] * len(bars)
    for index in range(1, len(bars)):
        previous_close = bars[index - 1].close
        current = bars[index]
        out[index] = max(
            current.high - current.low,
            abs(current.high - previous_close),
            abs(current.low - previous_close),
        )
    return out


def wilder_atr(bars: Sequence[Bar], period: int = 14) -> list[Decimal | None]:
    """Wilder-smoothed ATR seeded by the simple average of the first ``period`` ranges."""
    ranges = true_range(bars)
    out: list[Decimal | None] = [None] * len(bars)
    seed_end = period  # ranges[1..period] are the first `period` defined values
    if len(bars) <= seed_end:
        return out
    seed_values = [value for value in ranges[1 : seed_end + 1] if value is not None]
    if len(seed_values) < period:
        return out
    current = sum(seed_values, Decimal(0)) / period
    out[seed_end] = current
    for index in range(seed_end + 1, len(bars)):
        value = ranges[index]
        if value is None:
            continue
        current = (current * (period - 1) + value) / period
        out[index] = current
    return out


def wilder_rsi(closes: Sequence[Decimal], period: int = 14) -> list[Decimal | None]:
    """Wilder-smoothed RSI seeded by the simple averages of the first ``period`` moves."""
    out: list[Decimal | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = [max(closes[i] - closes[i - 1], Decimal(0)) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], Decimal(0)) for i in range(1, len(closes))]
    average_gain = sum(gains[:period], Decimal(0)) / period
    average_loss = sum(losses[:period], Decimal(0)) / period
    out[period] = _rsi_value(average_gain, average_loss)
    for index in range(period + 1, len(closes)):
        gain, loss = gains[index - 1], losses[index - 1]
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
        out[index] = _rsi_value(average_gain, average_loss)
    return out


def _rsi_value(average_gain: Decimal, average_loss: Decimal) -> Decimal:
    if average_loss == 0:
        return Decimal(100) if average_gain > 0 else Decimal(50)
    rs = average_gain / average_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + rs)


def rolling_extremes(
    bars: Sequence[Bar], lookback: int
) -> tuple[list[Decimal | None], list[Decimal | None]]:
    """Highest high and lowest low of the ``lookback`` bars *before* each bar."""
    highs: list[Decimal | None] = [None] * len(bars)
    lows: list[Decimal | None] = [None] * len(bars)
    for index in range(lookback, len(bars)):
        window = bars[index - lookback : index]
        highs[index] = max(bar.high for bar in window)
        lows[index] = min(bar.low for bar in window)
    return highs, lows
