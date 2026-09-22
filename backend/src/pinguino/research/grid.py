"""Expansion of the bounded template grid.

The grid is fully enumerated before anything runs, so the previewed count is the count
the campaign will attempt. Truncation applies a seeded permutation first, which keeps a
reduced grid representative instead of favouring whichever family sorts first.
"""

from __future__ import annotations

import random
from decimal import Decimal
from itertools import product

from pinguino.domain.enums import SIGNAL_TIMEFRAMES, StrategyFamily, Symbol, Timeframe
from pinguino.domain.strategy import (
    COMMON_AXES,
    FAMILY_AXES,
    RSI_UPPER_FOR_LOWER,
    StrategyDefinition,
    StrategyParameters,
)


def expand_family(
    family: StrategyFamily, symbol: Symbol, timeframe: Timeframe
) -> list[StrategyDefinition]:
    """Every valid parameter combination of one family on one symbol and timeframe."""
    axes = FAMILY_AXES[family]
    names = list(axes)
    definitions: list[StrategyDefinition] = []
    for values in product(*(axes[name] for name in names)):
        specific: dict[str, int] = dict(zip(names, values, strict=True))
        if family is StrategyFamily.MEAN_REVERSION:
            specific["rsi_upper"] = RSI_UPPER_FOR_LOWER[specific["rsi_lower"]]
        for stop_multiple, reward_multiple in product(
            COMMON_AXES["atr_stop_multiple"], COMMON_AXES["reward_risk_multiple"]
        ):
            definitions.append(
                StrategyDefinition(
                    family=family,
                    symbol=symbol,
                    timeframe=timeframe,
                    parameters=StrategyParameters(
                        atr_stop_multiple=Decimal(stop_multiple),
                        reward_risk_multiple=Decimal(reward_multiple),
                        **specific,
                    ),
                )
            )
    return definitions


def expand_grid(
    symbols: tuple[Symbol, ...] = tuple(Symbol),
    timeframes: tuple[Timeframe, ...] = SIGNAL_TIMEFRAMES,
) -> list[StrategyDefinition]:
    """The full planned grid, in a stable declared order."""
    return [
        definition
        for symbol in symbols
        for timeframe in timeframes
        for family in StrategyFamily
        for definition in expand_family(family, symbol, timeframe)
    ]


def plan_candidates(
    definitions: list[StrategyDefinition], *, seed: int, max_candidates: int
) -> list[StrategyDefinition]:
    """Seeded permutation, then truncation. The returned order is the planned order."""
    shuffled = list(definitions)
    random.Random(seed).shuffle(shuffled)
    return shuffled[:max_candidates]


def neighbors(definition: StrategyDefinition) -> list[StrategyDefinition]:
    """Immediate neighbours along each ordered axis, one axis moved at a time."""
    axes: list[tuple[str, tuple[int | Decimal, ...]]] = [
        *FAMILY_AXES[definition.family].items(),
        *COMMON_AXES.items(),
    ]
    out: list[StrategyDefinition] = []
    for name, values in axes:
        current = getattr(definition.parameters, name)
        if current not in values:
            continue
        index = values.index(current)
        for step in (-1, 1):
            neighbor_index = index + step
            if not 0 <= neighbor_index < len(values):
                continue
            neighbor_value = values[neighbor_index]
            update: dict[str, int | Decimal] = {name: neighbor_value}
            if name == "rsi_lower":
                update["rsi_upper"] = RSI_UPPER_FOR_LOWER[int(neighbor_value)]
            parameters = definition.parameters.model_dump() | update
            payload = definition.model_dump() | {"parameters": parameters}
            out.append(StrategyDefinition.model_validate(payload))
    return out
