"""Campaign preview.

Preview is required before a campaign starts: it resolves the chronological boundaries
and counts the work the configuration implies, including the robustness replays, so the
operator sees the real size of the run before committing to it.
"""

from __future__ import annotations

from collections.abc import Collection

from pinguino.domain.campaign import CampaignConfig, CampaignPreview
from pinguino.domain.enums import SIGNAL_TIMEFRAMES, Symbol, Timeframe
from pinguino.domain.strategy import StrategyDefinition
from pinguino.research.grid import expand_grid, neighbors, plan_candidates
from pinguino.research.windows import ResolvedSplit, resolve_split

#: Trial windows: training, whole validation, then each validation subwindow.
FIXED_WINDOWS_PER_TRIAL = 2


def planned_definitions(
    config: CampaignConfig, keys: Collection[tuple[Symbol, Timeframe]] | None = None
) -> list[StrategyDefinition]:
    """The planned order, restricted to the symbol/timeframe pairs that have data."""
    grid = expand_grid(tuple(Symbol), SIGNAL_TIMEFRAMES)
    if keys is not None:
        grid = [item for item in grid if (item.symbol, item.timeframe) in keys]
    return plan_candidates(
        grid, seed=config.budget.seed, max_candidates=config.budget.max_candidates
    )


def preview_campaign(
    config: CampaignConfig,
    *,
    keys: Collection[tuple[Symbol, Timeframe]] | None = None,
) -> tuple[CampaignPreview, ResolvedSplit]:
    split = resolve_split(config.window_policy)
    planned = planned_definitions(config, keys)

    # Each candidate is evaluated on training, whole validation and each subwindow.
    per_candidate = FIXED_WINDOWS_PER_TRIAL + config.window_policy.validation_subwindows
    stress_and_neighbors = sum(1 + len(neighbors(definition)) for definition in planned)
    planned_evaluations = min(
        len(planned) * per_candidate + stress_and_neighbors,
        config.budget.max_evaluations,
    )

    preview = CampaignPreview(
        campaign_id=config.campaign_id,
        base_candidate_count=len(planned),
        planned_evaluation_count=planned_evaluations,
        training_start=split.training.start,
        training_end=split.training.end,
        validation_start=split.validation.start,
        validation_end=split.validation.end,
        final_holdout_start=split.final_holdout.start,
        final_holdout_end=split.final_holdout.end,
    )
    return preview, split
