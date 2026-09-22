"""Fills, equity observations and reported metrics."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pinguino.domain.enums import ApproximationFlag, Direction, WindowKind
from pinguino.domain.timeutil import require_utc

#: Money is compared with this tolerance when a completed trial is replayed.
REPLAY_MONEY_TOLERANCE = Decimal("0.01")


class FillReason(StrEnum):
    ENTRY = "entry"
    PROTECTIVE_STOP = "protective_stop"
    TAKE_PROFIT = "take_profit"
    TIME_EXIT = "time_exit"
    WINDOW_END_LIQUIDATION = "window_end_liquidation"
    MARGIN_STOP_OUT = "margin_stop_out"


class Fill(BaseModel):
    """One simulated execution at an M1 instant, with its costs attributed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    executed_at: datetime
    reason: FillReason
    direction: Direction
    price: Decimal = Field(gt=0)
    volume: Decimal = Field(gt=0)
    slippage_points: Decimal = Field(ge=0)
    commission: Decimal = Field(ge=0)
    ambiguous_stop_and_target: bool = False

    _utc = field_validator("executed_at")(require_utc)


class EquityObservation(BaseModel):
    """Equity sampled at M1 closes and at fill instants. Not a tick-level series."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    observed_at: datetime
    equity: Decimal
    realized_balance: Decimal

    _utc = field_validator("observed_at")(require_utc)


class WindowMetrics(BaseModel):
    """Metrics for one evaluated window. Undefined ratios are null with a reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    window: WindowKind
    start: datetime
    end: datetime
    net_return: Decimal
    max_drawdown: Decimal = Field(ge=0, le=1)
    trade_count: int = Field(ge=0)
    win_rate: Decimal | None = Field(default=None, ge=0, le=1)
    profit_factor: Decimal | None = Field(default=None, ge=0)
    exposure_fraction: Decimal = Field(ge=0, le=1)
    turnover: Decimal = Field(ge=0)
    commission_cost: Decimal = Field(ge=0)
    spread_cost: Decimal = Field(ge=0)
    swap_cost: Decimal
    slippage_cost: Decimal = Field(ge=0)
    ambiguity_count: int = Field(ge=0, default=0)
    undefined_reasons: tuple[str, ...] = ()

    _utc = field_validator("start", "end")(require_utc)

    @model_validator(mode="after")
    def _check_window(self) -> WindowMetrics:
        if self.end <= self.start:
            raise ValueError("window end must be after its start")
        if self.trade_count == 0 and (self.win_rate is not None or self.profit_factor is not None):
            raise ValueError("ratios must be null when no trade occurred")
        if (self.win_rate is None or self.profit_factor is None) and not self.undefined_reasons:
            raise ValueError("a null ratio requires a stated reason")
        return self


class TrialResult(BaseModel):
    """Per-window metrics plus the approximation flags that qualify them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trial_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    windows: tuple[WindowMetrics, ...] = Field(min_length=1)
    approximation_flags: tuple[ApproximationFlag, ...] = ()
    inconclusive_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_no_warmup_metrics(self) -> TrialResult:
        if any(window.window is WindowKind.WARMUP for window in self.windows):
            raise ValueError("warm-up trades must not contribute reported metrics")
        return self
