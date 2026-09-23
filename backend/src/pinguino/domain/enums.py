"""Closed vocabularies shared by the domain contracts."""

from __future__ import annotations

from enum import StrEnum


class Symbol(StrEnum):
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"


class Timeframe(StrEnum):
    """Signal timeframes. M1 is execution-only and never emits signals."""

    M1 = "M1"
    H1 = "H1"
    H4 = "H4"


SIGNAL_TIMEFRAMES: tuple[Timeframe, ...] = (Timeframe.H1, Timeframe.H4)


class DatasetStatus(StrEnum):
    QUALIFIED = "qualified"
    APPROXIMATE = "approximate"
    REJECTED = "rejected"


class TrialState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


TERMINAL_TRIAL_STATES: frozenset[TrialState] = frozenset(
    {TrialState.COMPLETED, TrialState.FAILED, TrialState.CANCELLED, TrialState.INTERRUPTED}
)


class DataProvenance(StrEnum):
    """Where bars came from. Synthetic fixtures never masquerade as broker history."""

    SYNTHETIC_FIXTURE = "synthetic_fixture"
    MT5_TERMINAL = "mt5_terminal"


class StrategyFamily(StrEnum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"


class WindowKind(StrEnum):
    WARMUP = "warmup"
    TRAINING = "training"
    VALIDATION = "validation"
    FINAL_HOLDOUT = "final_holdout"


class ApproximationFlag(StrEnum):
    """Every flag marks a documented modelling shortcut, surfaced with results."""

    ASK_DERIVED_FROM_BAR_SPREAD = "ask_derived_from_bar_spread"
    ESTIMATED_COST_PROFILE = "estimated_cost_profile"
    BAR_LEVEL_DRAWDOWN = "bar_level_drawdown"
    APPROXIMATE_MARGIN_MODEL = "approximate_margin_model"
    STOP_TARGET_AMBIGUITY = "stop_target_ambiguity"
    DELAYED_ENTRY = "delayed_entry"
