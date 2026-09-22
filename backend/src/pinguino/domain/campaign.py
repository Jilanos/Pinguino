"""Campaign configuration, budgets, trials and holdout access records."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pinguino.domain.enums import TERMINAL_TRIAL_STATES, TrialState
from pinguino.domain.identity import content_id
from pinguino.domain.policy import (
    CostPolicy,
    EligibilityPolicy,
    ResearchWindowPolicy,
    SizingPolicy,
)
from pinguino.domain.strategy import StrategyDefinition
from pinguino.domain.timeutil import require_utc

DEFAULT_SEED = 42
DEFAULT_MAX_CANDIDATES = 192
DEFAULT_MAX_EVALUATIONS = 2000
DEFAULT_MAX_ACTIVE_MINUTES = 30
CANCELLATION_CHECK_M1_BARS = 1000


class CampaignBudget(BaseModel):
    """Engineering budgets, not throughput promises. Exhaustion yields partial results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: int = Field(default=DEFAULT_SEED)
    workers: int = Field(ge=1, le=1, default=1)
    max_candidates: int = Field(ge=1, default=DEFAULT_MAX_CANDIDATES)
    max_evaluations: int = Field(ge=1, default=DEFAULT_MAX_EVALUATIONS)
    max_active_minutes: int = Field(ge=1, default=DEFAULT_MAX_ACTIVE_MINUTES)

    @model_validator(mode="after")
    def _check_evaluation_headroom(self) -> CampaignBudget:
        if self.max_evaluations < self.max_candidates:
            raise ValueError("max_evaluations must cover at least one run per candidate")
        return self


class CampaignConfig(BaseModel):
    """Frozen once the campaign exists: later configuration changes are rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    config_version: str = Field(min_length=1)
    dataset_ids: tuple[str, ...] = Field(min_length=1)
    cost_policy: CostPolicy
    sizing_policy: SizingPolicy
    window_policy: ResearchWindowPolicy
    eligibility_policy: EligibilityPolicy
    budget: CampaignBudget = CampaignBudget()
    resumed_from_campaign_id: str | None = None

    @field_validator("dataset_ids")
    @classmethod
    def _unique_datasets(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("dataset_ids must be unique")
        return value

    @property
    def campaign_id(self) -> str:
        return content_id("camp", self)


class CampaignPreview(BaseModel):
    """Required before starting: counts the work the configuration implies."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    campaign_id: str = Field(min_length=1)
    base_candidate_count: int = Field(ge=0)
    planned_evaluation_count: int = Field(ge=0)
    training_start: datetime
    training_end: datetime
    validation_start: datetime
    validation_end: datetime
    final_holdout_start: datetime
    final_holdout_end: datetime

    _utc = field_validator(
        "training_start",
        "training_end",
        "validation_start",
        "validation_end",
        "final_holdout_start",
        "final_holdout_end",
    )(require_utc)

    @model_validator(mode="after")
    def _check_chronology(self) -> CampaignPreview:
        boundaries = [
            self.training_start,
            self.training_end,
            self.validation_start,
            self.validation_end,
            self.final_holdout_start,
            self.final_holdout_end,
        ]
        if boundaries != sorted(boundaries):
            raise ValueError("window boundaries must be chronologically ordered")
        return self


class Trial(BaseModel):
    """One attempted evaluation. Every attempt is persisted, including failures."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trial_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    definition: StrategyDefinition
    state: TrialState
    planned_order: int = Field(ge=0)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failure_reason: str | None = None

    @model_validator(mode="after")
    def _check_state_consistency(self) -> Trial:
        if self.state in TERMINAL_TRIAL_STATES and self.state is not TrialState.INTERRUPTED:
            if self.ended_at is None:
                raise ValueError(f"{self.state} trial must record ended_at")
        if self.state is TrialState.FAILED and not self.failure_reason:
            raise ValueError("failed trial must record a failure reason")
        if self.state is TrialState.QUEUED and self.started_at is not None:
            raise ValueError("queued trial must not record started_at")
        return self


class HoldoutAccessEvent(BaseModel):
    """Audit record written before the final holdout is executed, never after."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    campaign_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    window_policy_id: str = Field(min_length=1)
    dataset_ids: tuple[str, ...] = Field(min_length=1)
    requested_at: datetime
    reused_lineage: bool
    reason: str = Field(min_length=1)

    _utc = field_validator("requested_at")(require_utc)
