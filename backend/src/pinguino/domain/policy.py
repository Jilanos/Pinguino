"""Versioned cost, sizing, research-window and eligibility policies."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pinguino.domain.enums import ApproximationFlag
from pinguino.domain.identity import content_id
from pinguino.domain.timeutil import require_utc


class CostPolicy(BaseModel):
    """Costs applied to every fill. Zero entered explicitly differs from missing data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(min_length=1)
    sourced: bool
    commission_per_lot_per_side: Decimal = Field(ge=0)
    swap_long_points_per_day: Decimal
    swap_short_points_per_day: Decimal
    adverse_slippage_points: Decimal = Field(ge=0)
    spread_multiplier: Decimal = Field(gt=0, default=Decimal("1.0"))
    slippage_multiplier: Decimal = Field(gt=0, default=Decimal("1.0"))

    @property
    def approximation_flags(self) -> tuple[ApproximationFlag, ...]:
        if self.sourced:
            return ()
        return (ApproximationFlag.ESTIMATED_COST_PROFILE,)

    @property
    def policy_id(self) -> str:
        return content_id("cost", self)

    def stressed(self) -> CostPolicy:
        """Stress variant: spread and commission x1.5, slippage doubled."""
        return self.model_copy(
            update={
                "commission_per_lot_per_side": self.commission_per_lot_per_side * Decimal("1.5"),
                "spread_multiplier": self.spread_multiplier * Decimal("1.5"),
                "slippage_multiplier": self.slippage_multiplier * Decimal("2.0"),
            }
        )


class SizingPolicy(BaseModel):
    """Demonstration account sizing. Visible and configurable before a campaign."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(min_length=1)
    account_currency: str = Field(min_length=3, max_length=3, default="USD")
    initial_balance: Decimal = Field(gt=0)
    fixed_volume: Decimal = Field(gt=0)
    max_open_positions_per_candidate: int = Field(ge=1, le=1, default=1)

    @field_validator("account_currency")
    @classmethod
    def _supported_currency(cls, value: str) -> str:
        if value.upper() != "USD":
            raise ValueError("only USD account currency is supported in v1")
        return value.upper()

    @property
    def policy_id(self) -> str:
        return content_id("size", self)


class ResearchWindowPolicy(BaseModel):
    """Chronological split of the requested calendar span, resolved to UTC instants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(min_length=1)
    requested_start: datetime
    requested_end: datetime
    training_fraction: Decimal = Field(gt=0, lt=1, default=Decimal("0.6"))
    validation_fraction: Decimal = Field(gt=0, lt=1, default=Decimal("0.2"))
    final_holdout_fraction: Decimal = Field(gt=0, lt=1, default=Decimal("0.2"))
    validation_subwindows: int = Field(ge=1, default=3)
    warmup_signal_bars: int = Field(ge=200, default=200)

    _utc = field_validator("requested_start", "requested_end")(require_utc)

    @model_validator(mode="after")
    def _check_span(self) -> ResearchWindowPolicy:
        if self.requested_end <= self.requested_start:
            raise ValueError("requested_end must be after requested_start")
        total = self.training_fraction + self.validation_fraction + self.final_holdout_fraction
        if total != Decimal("1"):
            raise ValueError("split fractions must sum to exactly 1")
        return self

    @property
    def policy_id(self) -> str:
        return content_id("window", self)


class EligibilityPolicy(BaseModel):
    """Heuristic screening thresholds. Not a statistical or profitability guarantee."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(min_length=1)
    min_training_trades: int = Field(ge=1, default=100)
    min_validation_trades: int = Field(ge=1, default=30)
    min_trades_per_subwindow: int = Field(ge=1, default=10)
    min_positive_subwindows: int = Field(ge=1, default=2)
    max_subwindow_drawdown: Decimal = Field(gt=0, le=1, default=Decimal("0.15"))
    max_validation_drawdown: Decimal = Field(gt=0, le=1, default=Decimal("0.15"))
    min_passing_neighbor_fraction: Decimal = Field(gt=0, le=1, default=Decimal("0.5"))

    @model_validator(mode="after")
    def _check_subwindow_demand(self) -> EligibilityPolicy:
        if self.min_validation_trades < self.min_trades_per_subwindow:
            raise ValueError("min_validation_trades must cover min_trades_per_subwindow")
        return self

    @property
    def policy_id(self) -> str:
        return content_id("elig", self)
