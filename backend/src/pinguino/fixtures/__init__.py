"""Synthetic fixture profiles.

These constants are illustrative and must never be reused silently for broker history:
a real contract fetched from a terminal always overrides them.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pinguino.domain.enums import DataProvenance, Symbol
from pinguino.domain.instrument import InstrumentContract
from pinguino.domain.policy import (
    CostPolicy,
    EligibilityPolicy,
    ResearchWindowPolicy,
    SizingPolicy,
)

FIXTURE_CONTRACT_VERSION = "synthetic-1.0.0"

_TICK_SIZES: dict[Symbol, Decimal] = {
    Symbol.EURUSD: Decimal("0.00001"),
    Symbol.GBPUSD: Decimal("0.00001"),
    Symbol.USDJPY: Decimal("0.001"),
}

#: Illustrative spreads in points, used only by labelled fixtures.
FIXTURE_SPREAD_POINTS: dict[Symbol, Decimal] = {
    Symbol.EURUSD: Decimal("10"),
    Symbol.GBPUSD: Decimal("15"),
    Symbol.USDJPY: Decimal("10"),
}

_CURRENCIES: dict[Symbol, tuple[str, str]] = {
    Symbol.EURUSD: ("EUR", "USD"),
    Symbol.GBPUSD: ("GBP", "USD"),
    Symbol.USDJPY: ("USD", "JPY"),
}


def fixture_contract(symbol: Symbol) -> InstrumentContract:
    base, quote = _CURRENCIES[symbol]
    tick = _TICK_SIZES[symbol]
    return InstrumentContract(
        symbol=symbol,
        provenance=DataProvenance.SYNTHETIC_FIXTURE,
        contract_version=FIXTURE_CONTRACT_VERSION,
        digits=5 if symbol is not Symbol.USDJPY else 3,
        tick_size=tick,
        point_size=tick,
        base_currency=base,
        quote_currency=quote,
        units_per_lot=Decimal("100000"),
        volume_min=Decimal("0.01"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.01"),
        leverage=Decimal("30"),
        stop_out_fraction=Decimal("0.5"),
        rollover_hour_utc=21,
        triple_swap_weekday=2,
    )


def fixture_cost_policy() -> CostPolicy:
    """Zero commission and swap are explicit fixture values, not missing data."""
    return CostPolicy(
        policy_version=FIXTURE_CONTRACT_VERSION,
        sourced=False,
        commission_per_lot_per_side=Decimal("0"),
        swap_long_points_per_day=Decimal("0"),
        swap_short_points_per_day=Decimal("0"),
        adverse_slippage_points=Decimal("1"),
    )


def fixture_sizing_policy() -> SizingPolicy:
    return SizingPolicy(
        policy_version=FIXTURE_CONTRACT_VERSION,
        initial_balance=Decimal("10000"),
        fixed_volume=Decimal("0.01"),
    )


def fixture_eligibility_policy() -> EligibilityPolicy:
    return EligibilityPolicy(policy_version=FIXTURE_CONTRACT_VERSION)


def fixture_window_policy(start: str, end: str) -> ResearchWindowPolicy:
    return ResearchWindowPolicy(
        policy_version=FIXTURE_CONTRACT_VERSION,
        requested_start=datetime.fromisoformat(start),
        requested_end=datetime.fromisoformat(end),
    )
