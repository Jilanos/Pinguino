"""Auditable export of one candidate.

An export is self-describing: it carries the strategy definition, the policies, the
resolved chronological windows, the dataset hashes it relied on and every limitation
that qualifies the numbers. It references local dataset hashes and never bundles the
history itself or any credential.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pinguino.domain.campaign import CampaignConfig
from pinguino.domain.enums import ApproximationFlag
from pinguino.domain.identity import canonical_json, content_hash
from pinguino.domain.results import WindowMetrics
from pinguino.domain.strategy import StrategyDefinition
from pinguino.engine.simulator import SimulationResult
from pinguino.research.evaluation import ScreeningResult

EXPORT_VERSION = "1.0.0"

FRENCH_LIMITATIONS: tuple[str, str] = (
    "Résultats de recherche historique. Aucun ordre n'a été transmis.",
    "L'exécution est simulée sur des bougies M1 : ce n'est pas une preuve au tick.",
)

FRENCH_FLAG_LABELS: dict[ApproximationFlag, str] = {
    ApproximationFlag.ASK_DERIVED_FROM_BAR_SPREAD: (
        "Le prix demandé est reconstruit à partir du spread déclaré de la bougie."
    ),
    ApproximationFlag.ESTIMATED_COST_PROFILE: (
        "Le profil de coûts est une approximation versionnée, non sourcée."
    ),
    ApproximationFlag.BAR_LEVEL_DRAWDOWN: (
        "Le drawdown est mesuré sur les clôtures M1, pas au tick."
    ),
    ApproximationFlag.APPROXIMATE_MARGIN_MODEL: (
        "Le modèle de marge et de stop-out est approximatif."
    ),
    ApproximationFlag.STOP_TARGET_AMBIGUITY: (
        "Des bougies atteignaient à la fois le stop et l'objectif : le stop a été retenu."
    ),
    ApproximationFlag.DELAYED_ENTRY: (
        "Certaines entrées ont eu lieu à la première minute M1 disponible après une minute"
        " absente de l'historique."
    ),
}


class CandidateExport(BaseModel):
    """The canonical export payload. Its hash is the reproducibility reference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    export_version: str = Field(default=EXPORT_VERSION, min_length=1)
    exported_at: datetime
    campaign_id: str = Field(min_length=1)
    definition: StrategyDefinition
    config: CampaignConfig
    dataset_hashes: tuple[str, ...]
    windows: tuple[WindowMetrics, ...]
    screening: ScreeningResult
    approximation_flags: tuple[ApproximationFlag, ...]
    ambiguity_count: int = Field(ge=0)
    limitations: tuple[str, ...] = FRENCH_LIMITATIONS

    @property
    def export_hash(self) -> str:
        return content_hash(self)


def build_export(
    *,
    campaign_id: str,
    definition: StrategyDefinition,
    config: CampaignConfig,
    dataset_hashes: tuple[str, ...],
    windows: tuple[WindowMetrics, ...],
    screening: ScreeningResult,
    result: SimulationResult,
    exported_at: datetime,
) -> CandidateExport:
    return CandidateExport(
        exported_at=exported_at,
        campaign_id=campaign_id,
        definition=definition,
        config=config,
        dataset_hashes=dataset_hashes,
        windows=windows,
        screening=screening,
        approximation_flags=result.approximation_flags,
        ambiguity_count=result.ambiguity_count,
    )


def strategy_json(export: CandidateExport) -> str:
    """The definition and policies alone, enough to replay the candidate."""
    return canonical_json(
        {
            "export_version": export.export_version,
            "definition": export.definition.model_dump(mode="json"),
            "cost_policy": export.config.cost_policy.model_dump(mode="json"),
            "sizing_policy": export.config.sizing_policy.model_dump(mode="json"),
            "window_policy": export.config.window_policy.model_dump(mode="json"),
            "dataset_hashes": list(export.dataset_hashes),
        }
    )


def metrics_json(export: CandidateExport) -> str:
    return canonical_json(
        {
            "candidate_id": export.definition.candidate_id,
            "windows": [window.model_dump(mode="json") for window in export.windows],
            "screening": export.screening.model_dump(mode="json"),
            "approximation_flags": [flag.value for flag in export.approximation_flags],
            "ambiguity_count": export.ambiguity_count,
        }
    )


def trades_csv(result: SimulationResult) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "opened_at",
            "closed_at",
            "direction",
            "volume",
            "entry_price",
            "exit_price",
            "exit_reason",
            "gross_pnl",
            "commission",
            "swap",
            "spread_cost",
            "slippage_cost",
            "net_pnl",
            "ambiguous",
        ]
    )
    for trade in result.trades:
        writer.writerow(
            [
                trade.opened_at.isoformat(),
                trade.closed_at.isoformat(),
                trade.direction.value,
                trade.volume,
                trade.entry_price,
                trade.exit_price,
                trade.exit_reason.value,
                trade.gross_pnl,
                trade.commission,
                trade.swap,
                trade.spread_cost,
                trade.slippage_cost,
                trade.net_pnl,
                int(trade.ambiguous),
            ]
        )
    return buffer.getvalue()


def equity_csv(result: SimulationResult) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["observed_at", "equity", "realized_balance"])
    for observation in result.equity_curve:
        writer.writerow(
            [
                observation.observed_at.isoformat(),
                observation.equity,
                observation.realized_balance,
            ]
        )
    return buffer.getvalue()


def html_report(export: CandidateExport) -> str:
    """A standalone French report. No external asset, no embedded history, no credential."""
    rows = "".join(
        "<tr>"
        f"<td>{escape(window.window.value)}</td>"
        f"<td>{escape(window.start.isoformat())}</td>"
        f"<td>{escape(window.end.isoformat())}</td>"
        f"<td>{_percent(window.net_return)}</td>"
        f"<td>{_percent(window.max_drawdown)}</td>"
        f"<td>{window.trade_count}</td>"
        "</tr>"
        for window in export.windows
    )
    limitations = "".join(
        f"<li>{escape(item)}</li>"
        for item in (
            *export.limitations,
            *(FRENCH_FLAG_LABELS[flag] for flag in export.approximation_flags),
        )
    )
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in export.screening.reasons)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Rapport de candidat {escape(export.definition.candidate_id)}</title>
</head>
<body>
<h1>Rapport de recherche</h1>
<p>Candidat {escape(export.definition.candidate_id)} &mdash;
campagne {escape(export.campaign_id)}</p>
<p>Exporté le {escape(export.exported_at.isoformat())} &mdash;
empreinte {escape(export.export_hash)}</p>
<h2>Verdict</h2>
<p>{escape(export.screening.verdict.value)}</p>
<ul>{reasons}</ul>
<h2>Fenêtres chronologiques</h2>
<table>
<thead><tr><th>Fenêtre</th><th>Début</th><th>Fin</th>
<th>Rendement net</th><th>Drawdown</th><th>Transactions</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<h2>Jeux de données référencés</h2>
<ul>{"".join(f"<li>{escape(value)}</li>" for value in export.dataset_hashes)}</ul>
<h2>Limites</h2>
<ul>{limitations}</ul>
</body>
</html>
"""


def replay_inputs(payload: str) -> dict[str, Any]:
    """Parse a strategy export back into the inputs needed to replay it."""
    import json

    data: dict[str, Any] = json.loads(payload)
    return {
        "definition": StrategyDefinition.model_validate(data["definition"]),
        "dataset_hashes": tuple(data["dataset_hashes"]),
    }


def _percent(value: Decimal) -> str:
    return f"{value * 100:.2f}&nbsp;%"
