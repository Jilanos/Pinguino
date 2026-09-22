"""Campaign preview.

Preview is required before a campaign starts: it resolves the chronological boundaries
and counts the work the configuration implies, including the robustness replays, so the
operator sees the real size of the run before committing to it.
"""

from __future__ import annotations

from pinguino.domain.campaign import CampaignConfig, CampaignPreview
from pinguino.domain.enums import SIGNAL_TIMEFRAMES, Symbol
from pinguino.research.grid import expand_grid, neighbors, plan_candidates
from pinguino.research.windows import ResolvedSplit, resolve_split


def preview_campaign(
    config: CampaignConfig,
    *,
    symbols: tuple[Symbol, ...] = tuple(Symbol),
) -> tuple[CampaignPreview, ResolvedSplit]:
    split = resolve_split(config.window_policy)
    planned = plan_candidates(
        expand_grid(symbols, SIGNAL_TIMEFRAMES),
        seed=config.budget.seed,
        max_candidates=config.budget.max_candidates,
    )

    # Each candidate is evaluated on training, whole validation and each subwindow.
    per_candidate = 2 + config.window_policy.validation_subwindows
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
