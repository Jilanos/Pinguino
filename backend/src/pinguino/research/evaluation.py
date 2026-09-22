"""Screening, robustness checks, ranking and the final-holdout gate.

The thresholds here are heuristic engineering settings, not statistical confidence and
not a profitability claim. A candidate that simply lacks samples is inconclusive, which
is a distinct outcome from failing a threshold. The final holdout never reorders
anything: it is opened once, for one frozen candidate, after the ranking already exists.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from pinguino.domain.campaign import HoldoutAccessEvent
from pinguino.domain.errors import ErrorCode, PinguinoError
from pinguino.domain.policy import EligibilityPolicy
from pinguino.domain.results import WindowMetrics
from pinguino.domain.strategy import StrategyDefinition
from pinguino.research.ledger import Ledger


class Verdict(StrEnum):
    ELIGIBLE = "eligible"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class ScreeningResult(BaseModel):
    """Per-candidate verdict with the reasons behind it, in evaluation order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    verdict: Verdict
    reasons: tuple[str, ...]
    positive_subwindows: int = Field(ge=0)
    worst_subwindow_drawdown: Decimal = Field(ge=0)
    validation_net_return: Decimal


def screen_candidate(
    *,
    candidate_id: str,
    training: WindowMetrics,
    validation: WindowMetrics,
    subwindows: tuple[WindowMetrics, ...],
    policy: EligibilityPolicy,
) -> ScreeningResult:
    """Apply the eligibility defaults. Missing samples yield inconclusive, not rejected."""
    reasons: list[str] = []
    inconclusive: list[str] = []

    if training.trade_count < policy.min_training_trades:
        inconclusive.append(
            f"training trades {training.trade_count} < {policy.min_training_trades}"
        )
    if validation.trade_count < policy.min_validation_trades:
        inconclusive.append(
            f"validation trades {validation.trade_count} < {policy.min_validation_trades}"
        )
    for window in subwindows:
        if window.trade_count < policy.min_trades_per_subwindow:
            inconclusive.append(
                f"subwindow starting {window.start.isoformat()} trades {window.trade_count}"
                f" < {policy.min_trades_per_subwindow}"
            )

    positive = sum(1 for window in subwindows if window.net_return > 0)
    worst_drawdown = max((window.max_drawdown for window in subwindows), default=Decimal(0))

    if positive < policy.min_positive_subwindows:
        reasons.append(f"positive subwindows {positive} < {policy.min_positive_subwindows}")
    for window in subwindows:
        if window.max_drawdown > policy.max_subwindow_drawdown:
            reasons.append(
                f"subwindow starting {window.start.isoformat()} drawdown {window.max_drawdown}"
                f" > {policy.max_subwindow_drawdown}"
            )
    if validation.max_drawdown > policy.max_validation_drawdown:
        reasons.append(
            f"validation drawdown {validation.max_drawdown} > {policy.max_validation_drawdown}"
        )

    if inconclusive:
        verdict = Verdict.INCONCLUSIVE
        reasons = inconclusive
    elif reasons:
        verdict = Verdict.REJECTED
    else:
        verdict = Verdict.ELIGIBLE

    return ScreeningResult(
        candidate_id=candidate_id,
        verdict=verdict,
        reasons=tuple(reasons),
        positive_subwindows=positive,
        worst_subwindow_drawdown=worst_drawdown,
        validation_net_return=validation.net_return,
    )


def passes_stress(stressed_validation: WindowMetrics, policy: EligibilityPolicy) -> bool:
    """Stressed costs must still leave a positive validation return and a bounded fall."""
    return (
        stressed_validation.net_return > 0
        and stressed_validation.max_drawdown <= policy.max_validation_drawdown
    )


def neighborhood_verdict(
    neighbor_verdicts: tuple[Verdict, ...], policy: EligibilityPolicy
) -> Verdict:
    """At least half the distinct neighbours must pass; no neighbour is inconclusive."""
    if not neighbor_verdicts:
        return Verdict.INCONCLUSIVE
    passing = sum(1 for verdict in neighbor_verdicts if verdict is Verdict.ELIGIBLE)
    share = Decimal(passing) / Decimal(len(neighbor_verdicts))
    return Verdict.ELIGIBLE if share >= policy.min_passing_neighbor_fraction else Verdict.REJECTED


def rank(results: tuple[ScreeningResult, ...]) -> list[ScreeningResult]:
    """Lexicographic ranking. Only eligible candidates are ranked at all."""
    eligible = [result for result in results if result.verdict is Verdict.ELIGIBLE]
    return sorted(
        eligible,
        key=lambda result: (
            -result.positive_subwindows,
            result.worst_subwindow_drawdown,
            -result.validation_net_return,
            result.candidate_id,
        ),
    )


def open_final_holdout(
    *,
    ledger: Ledger,
    campaign_id: str,
    definition: StrategyDefinition,
    window_policy_id: str,
    dataset_ids: tuple[str, ...],
    requested_at: datetime,
    reason: str,
) -> HoldoutAccessEvent:
    """Log the access before the holdout runs, and refuse a second candidate.

    The audit trail is the guarantee here. Nothing prevents an operator from reading
    their own files; what this records is that the lineage was opened, and by whom.
    """
    already = ledger.holdout_accesses(campaign_id)
    if any(row["candidate_id"] != definition.candidate_id for row in already):
        raise PinguinoError(
            ErrorCode.HOLDOUT_ACCESS_DENIED,
            "another candidate already opened the final holdout for this campaign",
        )
    event = HoldoutAccessEvent(
        campaign_id=campaign_id,
        candidate_id=definition.candidate_id,
        window_policy_id=window_policy_id,
        dataset_ids=dataset_ids,
        requested_at=requested_at,
        reused_lineage=ledger.lineage_was_used(window_policy_id, dataset_ids),
        reason=reason,
    )
    ledger.record_holdout_access(event)
    return event
