"""Campaign execution against the ledger.

Budgets bound the work, not the meaning of a result: exhausting one leaves the remaining
candidates unrun and the campaign partial, which is a valid outcome rather than a
failure. Cancellation is observed between candidates and inside a trial, and a cancelled
partial trial never contributes to a ranking.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pinguino.domain.campaign import CampaignConfig
from pinguino.domain.dataset import Bar
from pinguino.domain.enums import TrialState
from pinguino.domain.instrument import InstrumentContract
from pinguino.domain.strategy import StrategyDefinition
from pinguino.engine.simulator import SimulationCancelled, SimulationResult, simulate
from pinguino.research.ledger import Ledger


class CancellationToken:
    """Cooperative cancellation. Requesting it never interrupts a write in progress."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class CampaignOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    campaign_id: str
    completed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    failed: int = Field(ge=0)
    not_run: int = Field(ge=0)
    evaluations_used: int = Field(ge=0)
    budget_exhausted: str | None = None

    @property
    def partial(self) -> bool:
        return self.budget_exhausted is not None or self.not_run > 0


@dataclass(frozen=True)
class MarketData:
    contract: InstrumentContract
    signal_bars: Sequence[Bar]
    execution_bars: Sequence[Bar]


def run_campaign(
    *,
    ledger: Ledger,
    config: CampaignConfig,
    definitions: Sequence[StrategyDefinition],
    market: Callable[[StrategyDefinition], MarketData],
    window_start: datetime,
    window_end: datetime,
    token: CancellationToken | None = None,
    clock: Callable[[], float] = time.monotonic,
    on_result: Callable[[str, Any], None] | None = None,
    evaluate: Callable[[StrategyDefinition, MarketData, Callable[[], bool]], Any] | None = None,
    evaluations_per_trial: int = 1,
) -> CampaignOutcome:
    """Run the planned order, one trial at a time, until a budget or cancellation stops it.

    ``evaluate`` replaces the single simulation over ``[window_start, window_end)`` when a
    trial covers several windows; ``evaluations_per_trial`` is then charged to the budget.
    """
    cancellation = token or CancellationToken()
    campaign_id = ledger.create_campaign(config)
    trial_ids = ledger.enqueue(campaign_id, list(definitions))

    budget = config.budget
    deadline = clock() + budget.max_active_minutes * 60
    evaluations = 0
    exhausted: str | None = None

    for trial_id, definition in zip(trial_ids, definitions, strict=True):
        if cancellation.cancelled:
            break
        if evaluations + evaluations_per_trial > budget.max_evaluations:
            exhausted = "max_evaluations"
            break
        if clock() >= deadline:
            exhausted = "max_active_minutes"
            break

        ledger.transition(trial_id, TrialState.RUNNING)
        evaluations += evaluations_per_trial
        try:
            data = market(definition)
            if evaluate is not None:
                result = evaluate(definition, data, lambda: cancellation.cancelled)
            else:
                result = _simulate_once(
                    definition, data, config, window_start, window_end, cancellation
                )
        except SimulationCancelled:
            ledger.transition(trial_id, TrialState.CANCELLED)
            continue
        except Exception as error:  # a broken candidate must not abort the campaign
            ledger.transition(trial_id, TrialState.FAILED, failure_reason=str(error)[:200])
            continue

        ledger.transition(trial_id, TrialState.COMPLETED)
        if on_result is not None:
            on_result(trial_id, result)

    counts = ledger.state_counts(campaign_id)
    return CampaignOutcome(
        campaign_id=campaign_id,
        completed=counts.get(TrialState.COMPLETED, 0),
        cancelled=counts.get(TrialState.CANCELLED, 0),
        failed=counts.get(TrialState.FAILED, 0),
        not_run=counts.get(TrialState.QUEUED, 0),
        evaluations_used=evaluations,
        budget_exhausted=exhausted,
    )


def _simulate_once(
    definition: StrategyDefinition,
    data: MarketData,
    config: CampaignConfig,
    window_start: datetime,
    window_end: datetime,
    cancellation: CancellationToken,
) -> SimulationResult:
    return simulate(
        definition=definition,
        signal_bars=data.signal_bars,
        execution_bars=data.execution_bars,
        contract=data.contract,
        costs=config.cost_policy,
        sizing=config.sizing_policy,
        window_start=window_start,
        window_end=window_end,
        should_cancel=lambda: cancellation.cancelled,
    )
