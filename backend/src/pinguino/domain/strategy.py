"""Strategy definitions and the versioned bounded template grid.

Templates are declarative: parameters are stored and interpreted, never emitted as
executable generated code.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pinguino.domain.enums import StrategyFamily, Symbol, Timeframe
from pinguino.domain.identity import content_id

TEMPLATE_VERSION = "1.0.0"

#: Ordered parameter axes per family. Order is meaningful: neighborhood checks move one
#: step along a single axis at a time.
FAMILY_AXES: dict[StrategyFamily, dict[str, tuple[int, ...]]] = {
    StrategyFamily.TREND: {"sma_fast": (10, 20), "sma_slow": (50, 100)},
    StrategyFamily.MEAN_REVERSION: {"rsi_lower": (25, 30)},
    StrategyFamily.BREAKOUT: {"breakout_lookback": (20, 50)},
}

#: Axes shared by every family.
COMMON_AXES: dict[str, tuple[Decimal, ...]] = {
    "atr_stop_multiple": (Decimal("1.5"), Decimal("2.0")),
    "reward_risk_multiple": (Decimal("1.0"), Decimal("2.0")),
}

ATR_PERIOD = 14
RSI_PERIOD = 14
TIME_EXIT_SIGNAL_BARS = 20

#: RSI thresholds are symmetric: the lower bound implies its upper counterpart.
RSI_UPPER_FOR_LOWER: dict[int, int] = {25: 75, 30: 70}


class StrategyParameters(BaseModel):
    """Expanded parameter set. Only the axes of the declared family may be present."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    atr_stop_multiple: Decimal = Field(gt=0)
    reward_risk_multiple: Decimal = Field(gt=0)
    sma_fast: int | None = Field(default=None, gt=0)
    sma_slow: int | None = Field(default=None, gt=0)
    rsi_lower: int | None = Field(default=None, gt=0, lt=50)
    rsi_upper: int | None = Field(default=None, gt=50, lt=100)
    breakout_lookback: int | None = Field(default=None, gt=1)


class StrategyDefinition(BaseModel):
    """A single candidate: family, instrument, signal timeframe and parameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_version: str = Field(default=TEMPLATE_VERSION, min_length=1)
    family: StrategyFamily
    symbol: Symbol
    timeframe: Timeframe
    parameters: StrategyParameters

    @model_validator(mode="after")
    def _check_family_parameters(self) -> StrategyDefinition:
        if self.timeframe not in (Timeframe.H1, Timeframe.H4):
            raise ValueError("signals require an H1 or H4 timeframe")
        required = set(FAMILY_AXES[self.family])
        if self.family is StrategyFamily.MEAN_REVERSION:
            required.add("rsi_upper")
        optional_all = {"sma_fast", "sma_slow", "rsi_lower", "rsi_upper", "breakout_lookback"}
        present = {name for name in optional_all if getattr(self.parameters, name) is not None}
        if present != required:
            raise ValueError(
                f"{self.family} requires exactly {sorted(required)}, got {sorted(present)}"
            )
        fast, slow = self.parameters.sma_fast, self.parameters.sma_slow
        if fast is not None and slow is not None and fast >= slow:
            raise ValueError("sma_fast must be strictly below sma_slow")
        lower, upper = self.parameters.rsi_lower, self.parameters.rsi_upper
        if lower is not None and upper is not None and lower >= upper:
            raise ValueError("rsi_lower must be strictly below rsi_upper")
        return self

    @property
    def warmup_signal_bars(self) -> int:
        """Longest indicator lookback the definition needs before it may emit a signal."""
        lookbacks = [ATR_PERIOD]
        if self.parameters.sma_slow is not None:
            lookbacks.append(self.parameters.sma_slow)
        if self.parameters.rsi_lower is not None:
            lookbacks.append(RSI_PERIOD)
        if self.parameters.breakout_lookback is not None:
            lookbacks.append(self.parameters.breakout_lookback)
        return max(lookbacks)

    @property
    def candidate_id(self) -> str:
        return content_id("cand", self)
