"""Chronological split of a research span.

Boundaries are resolved to explicit UTC instants at preview time and then persisted, so
a campaign is never re-split differently later. The final holdout is the last segment and
is hidden from every selection step.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pinguino.domain.enums import WindowKind
from pinguino.domain.policy import ResearchWindowPolicy
from pinguino.domain.timeutil import require_utc


class ResolvedWindow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: WindowKind
    start: datetime
    end: datetime
    subwindow_index: int | None = Field(default=None, ge=0)

    _utc = field_validator("start", "end")(require_utc)

    @model_validator(mode="after")
    def _check_order(self) -> ResolvedWindow:
        if self.end <= self.start:
            raise ValueError("window end must be after its start")
        return self


class ResolvedSplit(BaseModel):
    """The whole split. ``selectable`` deliberately excludes the final holdout."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    training: ResolvedWindow
    validation: ResolvedWindow
    validation_subwindows: tuple[ResolvedWindow, ...]
    final_holdout: ResolvedWindow

    @property
    def selectable(self) -> tuple[ResolvedWindow, ...]:
        return (self.training, self.validation, *self.validation_subwindows)


def resolve_split(policy: ResearchWindowPolicy) -> ResolvedSplit:
    """Split the requested span by the policy fractions, in chronological order."""
    total = policy.requested_end - policy.requested_start
    training_end = policy.requested_start + _fraction(total, policy.training_fraction)
    validation_end = training_end + _fraction(total, policy.validation_fraction)

    subwindow_span = (validation_end - training_end) / policy.validation_subwindows
    subwindows = tuple(
        ResolvedWindow(
            kind=WindowKind.VALIDATION,
            start=training_end + subwindow_span * index,
            end=(
                training_end + subwindow_span * (index + 1)
                if index < policy.validation_subwindows - 1
                else validation_end
            ),
            subwindow_index=index,
        )
        for index in range(policy.validation_subwindows)
    )

    return ResolvedSplit(
        training=ResolvedWindow(
            kind=WindowKind.TRAINING, start=policy.requested_start, end=training_end
        ),
        validation=ResolvedWindow(
            kind=WindowKind.VALIDATION, start=training_end, end=validation_end
        ),
        validation_subwindows=subwindows,
        final_holdout=ResolvedWindow(
            kind=WindowKind.FINAL_HOLDOUT, start=validation_end, end=policy.requested_end
        ),
    )


def warmup_start(window: ResolvedWindow, *, signal_bars: int, bar_duration: timedelta) -> datetime:
    """Start of the pre-window warm-up. No trade inside it contributes to metrics."""
    return window.start - bar_duration * signal_bars


def _fraction(total: timedelta, share: Decimal) -> timedelta:
    return timedelta(seconds=float(Decimal(int(total.total_seconds())) * share))
