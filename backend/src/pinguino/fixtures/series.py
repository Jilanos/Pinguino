"""Deterministic synthetic bar fixtures.

These series are labelled synthetic end to end. They exist to prove engine behaviour,
never to stand in for broker history.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

from pinguino.data.quality import BAR_DURATION
from pinguino.domain.dataset import Bar
from pinguino.domain.enums import Timeframe
from pinguino.domain.instrument import WeeklySession


def walk_open_times(
    start: datetime, count: int, timeframe: Timeframe, session: WeeklySession
) -> Iterator[datetime]:
    """Yield ``count`` aligned open timestamps, skipping the weekly closed session."""
    step = BAR_DURATION[timeframe]
    moment = start
    emitted = 0
    while emitted < count:
        if session.is_open(moment):
            yield moment
            emitted += 1
        moment += step


def ramp_series(
    *,
    start: datetime,
    count: int,
    timeframe: Timeframe,
    session: WeeklySession,
    first_price: Decimal,
    step_price: Decimal,
    spread_points: Decimal,
    tick_size: Decimal,
) -> tuple[Bar, ...]:
    """A monotonic ramp: every bar moves by ``step_price`` with a fixed bar range."""
    bars: list[Bar] = []
    price = first_price
    half_range = abs(step_price) if step_price else tick_size
    for open_time in walk_open_times(start, count, timeframe, session):
        close = price + step_price
        bars.append(
            Bar(
                open_time=open_time,
                open=price,
                high=max(price, close) + half_range,
                low=min(price, close) - half_range,
                close=close,
                spread_points=spread_points,
            )
        )
        price = close
    return tuple(bars)


def flat_m1_series(
    *,
    start: datetime,
    count: int,
    session: WeeklySession,
    price: Decimal,
    spread_points: Decimal,
) -> tuple[Bar, ...]:
    """Execution history at a constant price, so fills isolate cost and rule effects."""
    return tuple(
        Bar(
            open_time=open_time,
            open=price,
            high=price,
            low=price,
            close=price,
            spread_points=spread_points,
        )
        for open_time in walk_open_times(start, count, Timeframe.M1, session)
    )


def with_gap(bars: tuple[Bar, ...], *, drop_from: int, drop_count: int) -> tuple[Bar, ...]:
    """Remove a run of bars to simulate an unexplained open-session gap."""
    return bars[:drop_from] + bars[drop_from + drop_count :]


def with_variable_spread(
    bars: tuple[Bar, ...], *, wide_spread_points: Decimal, every: int
) -> tuple[Bar, ...]:
    """Widen the spread on every ``every``-th bar, keeping prices untouched."""
    return tuple(
        bar.model_copy(update={"spread_points": wide_spread_points}) if index % every == 0 else bar
        for index, bar in enumerate(bars)
    )


def as_raw(bars: tuple[Bar, ...]) -> list[dict[str, object]]:
    """Fixture bars in the shape the importer consumes."""
    return [bar.model_dump(mode="json") for bar in bars]


def minutes(count: int) -> timedelta:
    return timedelta(minutes=count)
