"""End-to-end synthetic campaign.

Import fixtures, qualify them, run a bounded campaign, screen the candidates, export one
and replay it from its own export. The series is synthetic and short, so the run is
deliberately inconclusive: it proves the workflow, not a strategy.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from pinguino.data.quality import ingest_bars, qualify_dataset
from pinguino.domain.campaign import CampaignBudget, CampaignConfig
from pinguino.domain.dataset import Bar
from pinguino.domain.enums import (
    DataProvenance,
    DatasetStatus,
    StrategyFamily,
    Symbol,
    Timeframe,
    TrialState,
)
from pinguino.domain.strategy import StrategyDefinition
from pinguino.engine.simulator import SimulationResult, simulate
from pinguino.fixtures import (
    fixture_contract,
    fixture_cost_policy,
    fixture_eligibility_policy,
    fixture_sizing_policy,
    fixture_window_policy,
)
from pinguino.fixtures.series import as_raw, walk_open_times
from pinguino.research.evaluation import Verdict, screen_candidate
from pinguino.research.export import (
    build_export,
    equity_csv,
    html_report,
    metrics_json,
    replay_inputs,
    strategy_json,
    trades_csv,
)
from pinguino.research.grid import expand_family, plan_candidates
from pinguino.research.ledger import Ledger
from pinguino.research.metrics import window_metrics
from pinguino.research.runner import MarketData, run_campaign
from pinguino.research.windows import resolve_split

CONTRACT = fixture_contract(Symbol.EURUSD)
START = datetime(2024, 1, 8, tzinfo=UTC)
CAMPAIGN_END = START + timedelta(days=10)


def _oscillating(timeframe: Timeframe, count: int) -> tuple[Bar, ...]:
    """A slow triangle wave, so trend and breakout templates both find crossings."""
    bars: list[Bar] = []
    for index, open_time in enumerate(walk_open_times(START, count, timeframe, CONTRACT.session)):
        phase = index % 40
        offset = Decimal(phase if phase < 20 else 40 - phase) * Decimal("0.00050")
        price = Decimal("1.10000") + offset
        bars.append(
            Bar(
                open_time=open_time,
                open=price,
                high=price + Decimal("0.00100"),
                low=price - Decimal("0.00100"),
                close=price,
                spread_points=Decimal("10"),
            )
        )
    return tuple(bars)


@pytest.fixture(scope="module")
def market_data() -> dict[Timeframe, tuple[Bar, ...]]:
    return {
        Timeframe.H1: _oscillating(Timeframe.H1, 24 * 10),
        Timeframe.M1: _oscillating(Timeframe.M1, 60 * 24 * 11),
    }


class TestSyntheticCampaign:
    def test_a_campaign_runs_end_to_end_and_exports_a_reproducible_candidate(
        self, tmp_path: Path, market_data: dict[Timeframe, tuple[Bar, ...]]
    ) -> None:
        signal_bars, execution_bars = market_data[Timeframe.H1], market_data[Timeframe.M1]

        # 1. Import and qualify.
        signal_series = ingest_bars(
            as_raw(signal_bars), symbol=Symbol.EURUSD, timeframe=Timeframe.H1, contract=CONTRACT
        )
        execution_series = ingest_bars(
            as_raw(execution_bars), symbol=Symbol.EURUSD, timeframe=Timeframe.M1, contract=CONTRACT
        )
        manifest, findings = qualify_dataset(
            signal_series=signal_series,
            execution_series=execution_series,
            contract=CONTRACT,
            provenance=DataProvenance.SYNTHETIC_FIXTURE,
            requested_start=START,
            requested_end=signal_bars[-1].open_time,
            costs_sourced=False,
            source_note="synthetic oscillating fixture",
            imported_at=START,
        )
        # Fixture costs are an explicit approximation, so the dataset is approximate.
        assert manifest.status is DatasetStatus.APPROXIMATE
        assert manifest.content_hash

        # 2. Configure and split.
        config = CampaignConfig(
            config_version="v1",
            dataset_ids=(manifest.dataset_id,),
            cost_policy=fixture_cost_policy(),
            sizing_policy=fixture_sizing_policy(),
            window_policy=fixture_window_policy(START.isoformat(), CAMPAIGN_END.isoformat()),
            eligibility_policy=fixture_eligibility_policy(),
            budget=CampaignBudget(max_candidates=4, max_evaluations=4),
        )
        split = resolve_split(config.window_policy)
        assert split.final_holdout.end == CAMPAIGN_END

        # 3. Run the bounded campaign over training and validation only.
        definitions = plan_candidates(
            expand_family(StrategyFamily.TREND, Symbol.EURUSD, Timeframe.H1),
            seed=config.budget.seed,
            max_candidates=config.budget.max_candidates,
        )
        results: dict[str, SimulationResult] = {}
        ledger = Ledger(tmp_path / "research.sqlite")
        outcome = run_campaign(
            ledger=ledger,
            config=config,
            definitions=definitions,
            market=lambda _: MarketData(
                contract=CONTRACT, signal_bars=signal_bars, execution_bars=execution_bars
            ),
            window_start=split.training.start,
            window_end=split.validation.end,
            on_result=lambda trial_id, result: results.__setitem__(trial_id, result),
        )
        assert outcome.completed == 4
        assert outcome.partial is False
        assert all(
            trial.state is TrialState.COMPLETED for trial in ledger.trials(outcome.campaign_id)
        )

        # 4. Screen one candidate over its windows.
        definition = definitions[0]
        trial_id, result = next(iter(results.items()))
        windows = tuple(
            window_metrics(
                _simulate(definition, signal_bars, execution_bars, config, window),
                window,
                initial_balance=config.sizing_policy.initial_balance,
                units_per_lot=CONTRACT.units_per_lot,
            )
            for window in (split.training, split.validation, *split.validation_subwindows)
        )
        screening = screen_candidate(
            candidate_id=definition.candidate_id,
            training=windows[0],
            validation=windows[1],
            subwindows=windows[2:],
            policy=config.eligibility_policy,
        )
        # A ten-day synthetic fixture cannot reach the evidence thresholds.
        assert screening.verdict is Verdict.INCONCLUSIVE

        # 5. Export, and confirm every artefact is produced.
        export = build_export(
            campaign_id=outcome.campaign_id,
            definition=definition,
            config=config,
            dataset_hashes=(manifest.content_hash,),
            windows=windows,
            screening=screening,
            result=result,
            exported_at=START,
        )
        report = html_report(export)
        # The report escapes its text, so the apostrophe is checked in escaped form.
        assert "Aucun ordre n&#x27;a été transmis" in report
        assert manifest.content_hash in report
        assert "Rendement net" in report
        assert trades_csv(result).splitlines()[0].startswith("opened_at,")
        assert equity_csv(result).splitlines()[0] == "observed_at,equity,realized_balance"
        assert definition.candidate_id in metrics_json(export)

        # 6. Replay the candidate from its own export.
        replayed = replay_inputs(strategy_json(export))
        assert replayed["definition"] == definition
        assert replayed["dataset_hashes"] == (manifest.content_hash,)
        replayed_result = _simulate(
            replayed["definition"], signal_bars, execution_bars, config, split.training
        )
        original = _simulate(definition, signal_bars, execution_bars, config, split.training)
        assert replayed_result.fills == original.fills
        assert replayed_result.final_equity == original.final_equity

        ledger.close()

    def test_the_export_carries_no_credential_and_no_raw_history(
        self, market_data: dict[Timeframe, tuple[Bar, ...]]
    ) -> None:
        signal_bars = market_data[Timeframe.H1]
        config = CampaignConfig(
            config_version="v1",
            dataset_ids=("ds-a",),
            cost_policy=fixture_cost_policy(),
            sizing_policy=fixture_sizing_policy(),
            window_policy=fixture_window_policy(START.isoformat(), CAMPAIGN_END.isoformat()),
            eligibility_policy=fixture_eligibility_policy(),
        )
        payload = strategy_json(
            build_export(
                campaign_id="camp-1",
                definition=expand_family(StrategyFamily.TREND, Symbol.EURUSD, Timeframe.H1)[0],
                config=config,
                dataset_hashes=("a" * 64,),
                windows=(),
                screening=screen_candidate(
                    candidate_id="cand-1",
                    training=window_metrics(
                        _empty_result(),
                        resolve_split(config.window_policy).training,
                        initial_balance=Decimal("10000"),
                        units_per_lot=CONTRACT.units_per_lot,
                    ),
                    validation=window_metrics(
                        _empty_result(),
                        resolve_split(config.window_policy).validation,
                        initial_balance=Decimal("10000"),
                        units_per_lot=CONTRACT.units_per_lot,
                    ),
                    subwindows=(),
                    policy=fixture_eligibility_policy(),
                ),
                result=_empty_result(),
                exported_at=START,
            )
        )
        for forbidden in ("password", "token", "login", "account_number"):
            assert forbidden not in payload
        assert str(signal_bars[0].close) not in payload


def _simulate(
    definition: StrategyDefinition,
    signal_bars: tuple[Bar, ...],
    execution_bars: tuple[Bar, ...],
    config: CampaignConfig,
    window: object,
) -> SimulationResult:
    return simulate(
        definition=definition,
        signal_bars=signal_bars,
        execution_bars=execution_bars,
        contract=CONTRACT,
        costs=config.cost_policy,
        sizing=config.sizing_policy,
        window_start=window.start,  # type: ignore[attr-defined]
        window_end=window.end,  # type: ignore[attr-defined]
    )


def _empty_result() -> SimulationResult:
    return SimulationResult(
        fills=(),
        trades=(),
        equity_curve=(),
        rejected_signals=(),
        ambiguity_count=0,
        forced_liquidation=False,
        approximation_flags=(),
    )
