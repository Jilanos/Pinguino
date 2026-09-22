"""Signal evaluation over completed bid bars.

A signal for bar *i* may only read bars 0..i. The engine acts on it at the next M1 open
at or after bar *i*'s close, which is what makes the simulation causal.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from pinguino.domain.dataset import Bar
from pinguino.domain.enums import Direction, StrategyFamily
from pinguino.domain.strategy import (
    ATR_PERIOD,
    RSI_PERIOD,
    RSI_UPPER_FOR_LOWER,
    StrategyDefinition,
)
from pinguino.engine.indicators import rolling_extremes, sma, wilder_atr, wilder_rsi


class Signal(BaseModel):
    """A decision taken at the close of one completed signal bar."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bar_index: int
    direction: Direction
    atr: Decimal


def evaluate(definition: StrategyDefinition, bars: Sequence[Bar]) -> list[Signal]:
    """One decision per completed bar, in chronological order."""
    atr = wilder_atr(bars, ATR_PERIOD)
    match definition.family:
        case StrategyFamily.TREND:
            directions = _trend_directions(definition, bars)
        case StrategyFamily.MEAN_REVERSION:
            directions = _mean_reversion_directions(definition, bars)
        case StrategyFamily.BREAKOUT:
            directions = _breakout_directions(definition, bars)
    signals: list[Signal] = []
    for index, direction in enumerate(directions):
        value = atr[index]
        if direction is None or value is None or value <= 0:
            continue
        signals.append(Signal(bar_index=index, direction=direction, atr=value))
    return signals


def _trend_directions(
    definition: StrategyDefinition, bars: Sequence[Bar]
) -> list[Direction | None]:
    fast_period = definition.parameters.sma_fast
    slow_period = definition.parameters.sma_slow
    if fast_period is None or slow_period is None:
        raise ValueError("trend definition requires both SMA periods")
    closes = [bar.close for bar in bars]
    fast = sma(closes, fast_period)
    slow = sma(closes, slow_period)
    out: list[Direction | None] = [None] * len(bars)
    for index in range(1, len(bars)):
        previous_fast, previous_slow = fast[index - 1], slow[index - 1]
        current_fast, current_slow = fast[index], slow[index]
        if None in (previous_fast, previous_slow, current_fast, current_slow):
            continue
        if previous_fast <= previous_slow and current_fast > current_slow:  # type: ignore[operator]
            out[index] = Direction.LONG
        elif previous_fast >= previous_slow and current_fast < current_slow:  # type: ignore[operator]
            out[index] = Direction.SHORT
    return out


def _mean_reversion_directions(
    definition: StrategyDefinition, bars: Sequence[Bar]
) -> list[Direction | None]:
    lower = definition.parameters.rsi_lower
    if lower is None:
        raise ValueError("mean reversion definition requires an RSI lower threshold")
    upper = definition.parameters.rsi_upper or RSI_UPPER_FOR_LOWER[lower]
    rsi = wilder_rsi([bar.close for bar in bars], RSI_PERIOD)
    out: list[Direction | None] = [None] * len(bars)
    for index in range(1, len(bars)):
        previous, current = rsi[index - 1], rsi[index]
        if previous is None or current is None:
            continue
        if previous < lower <= current:
            out[index] = Direction.LONG
        elif previous > upper >= current:
            out[index] = Direction.SHORT
    return out


def _breakout_directions(
    definition: StrategyDefinition, bars: Sequence[Bar]
) -> list[Direction | None]:
    lookback = definition.parameters.breakout_lookback
    if lookback is None:
        raise ValueError("breakout definition requires a lookback")
    highs, lows = rolling_extremes(bars, lookback)
    out: list[Direction | None] = [None] * len(bars)
    for index, bar in enumerate(bars):
        high, low = highs[index], lows[index]
        if high is None or low is None:
            continue
        if bar.close > high:
            out[index] = Direction.LONG
        elif bar.close < low:
            out[index] = Direction.SHORT
    return out
