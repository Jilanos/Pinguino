from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from pinguino.domain.campaign import CampaignBudget, CampaignConfig
from pinguino.domain.dataset import Bar
from pinguino.domain.enums import SIGNAL_TIMEFRAMES, StrategyFamily, Symbol, TrialState
from pinguino.domain.strategy import StrategyDefinition
from pinguino.fixtures import (
    fixture_contract,
    fixture_cost_policy,
    fixture_eligibility_policy,
    fixture_sizing_policy,
    fixture_window_policy,
)
from pinguino.research.grid import expand_family, expand_grid, neighbors, plan_candidates
from pinguino.research.ledger import Ledger
from pinguino.research.runner import CancellationToken, MarketData, run_campaign

START = datetime(2024, 1, 8, tzinfo=UTC)
CONTRACT = fixture_contract(Symbol.EURUSD)


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    instance = Ledger(tmp_path / "research.sqlite")
    yield instance
    instance.close()


def _config(**budget_overrides: object) -> CampaignConfig:
    return CampaignConfig(
        config_version="v1",
        dataset_ids=("ds-eurusd-h1",),
        cost_policy=fixture_cost_policy(),
        sizing_policy=fixture_sizing_policy(),
        window_policy=fixture_window_policy(
            "2024-01-08T00:00:00+00:00", "2024-02-08T00:00:00+00:00"
        ),
        eligibility_policy=fixture_eligibility_policy(),
        budget=CampaignBudget(max_candidates=8, max_evaluations=8, **budget_overrides),  # type: ignore[arg-type]
    )


def _bars(count: int, minutes: int) -> list[Bar]:
    return [
        Bar(
            open_time=START + timedelta(minutes=index * minutes),
            open=Decimal("1.10000"),
            high=Decimal("1.10050"),
            low=Decimal("1.09950"),
            close=Decimal("1.10000"),
            spread_points=Decimal("10"),
        )
        for index in range(count)
    ]


def _market(_: StrategyDefinition) -> MarketData:
    return MarketData(contract=CONTRACT, signal_bars=_bars(60, 60), execution_bars=_bars(120, 1))


class TestGrid:
    def test_each_family_expands_to_its_declared_variant_count(self) -> None:
        counts = {
            family: len(expand_family(family, Symbol.EURUSD, SIGNAL_TIMEFRAMES[0]))
            for family in StrategyFamily
        }
        assert counts == {
            StrategyFamily.TREND: 16,
            StrategyFamily.MEAN_REVERSION: 8,
            StrategyFamily.BREAKOUT: 8,
        }

    def test_the_full_grid_holds_one_hundred_and_ninety_two_candidates(self) -> None:
        grid = expand_grid()
        assert len(grid) == 192
        assert len({definition.candidate_id for definition in grid}) == 192

    def test_thirty_two_candidates_per_symbol_and_timeframe(self) -> None:
        grid = expand_grid()
        for symbol in Symbol:
            for timeframe in SIGNAL_TIMEFRAMES:
                subset = [
                    definition
                    for definition in grid
                    if definition.symbol is symbol and definition.timeframe is timeframe
                ]
                assert len(subset) == 32

    def test_truncation_permutes_deterministically_before_cutting(self) -> None:
        grid = expand_grid()
        first = plan_candidates(grid, seed=42, max_candidates=20)
        second = plan_candidates(grid, seed=42, max_candidates=20)
        other = plan_candidates(grid, seed=7, max_candidates=20)
        assert [d.candidate_id for d in first] == [d.candidate_id for d in second]
        assert [d.candidate_id for d in first] != [d.candidate_id for d in other]
        assert len({d.family for d in first}) == 3

    def test_neighbors_move_one_axis_at_a_time(self) -> None:
        definition = expand_family(StrategyFamily.BREAKOUT, Symbol.EURUSD, SIGNAL_TIMEFRAMES[0])[0]
        for neighbor in neighbors(definition):
            differences = [
                name
                for name in definition.parameters.model_dump()
                if getattr(neighbor.parameters, name) != getattr(definition.parameters, name)
            ]
            assert len(differences) == 1


class TestLedger:
    def test_every_planned_trial_is_persisted_before_any_runs(self, ledger: Ledger) -> None:
        config = _config()
        campaign_id = ledger.create_campaign(config)
        definitions = plan_candidates(expand_grid(), seed=42, max_candidates=8)
        ledger.enqueue(campaign_id, definitions)
        trials = ledger.trials(campaign_id)
        assert len(trials) == 8
        assert all(trial.state is TrialState.QUEUED for trial in trials)
        assert [trial.planned_order for trial in trials] == list(range(8))

    def test_running_trials_are_reconciled_to_interrupted_on_restart(self, tmp_path: Path) -> None:
        database = tmp_path / "research.sqlite"
        first = Ledger(database)
        campaign_id = first.create_campaign(_config())
        trial_ids = first.enqueue(
            campaign_id, plan_candidates(expand_grid(), seed=42, max_candidates=3)
        )
        first.transition(trial_ids[0], TrialState.RUNNING)
        first.close()

        restarted = Ledger(database)
        stale = restarted.reconcile_interrupted()
        assert stale == [trial_ids[0]]
        states = {trial.trial_id: trial.state for trial in restarted.trials(campaign_id)}
        assert states[trial_ids[0]] is TrialState.INTERRUPTED
        assert states[trial_ids[1]] is TrialState.QUEUED
        restarted.close()

    def test_holdout_access_is_recorded_and_lineage_reuse_is_detectable(
        self, ledger: Ledger
    ) -> None:
        from pinguino.domain.campaign import HoldoutAccessEvent

        event = HoldoutAccessEvent(
            campaign_id="camp-1",
            candidate_id="cand-1",
            window_policy_id="window-1",
            dataset_ids=("ds-a",),
            requested_at=START,
            reused_lineage=False,
            reason="frozen candidate final evaluation",
        )
        assert ledger.lineage_was_used("window-1", ("ds-a",)) is False
        ledger.record_holdout_access(event)
        assert ledger.lineage_was_used("window-1", ("ds-a",)) is True
        assert len(ledger.holdout_accesses("camp-1")) == 1


class TestRunner:
    def _definitions(self, count: int) -> list[StrategyDefinition]:
        return plan_candidates(expand_grid(), seed=42, max_candidates=count)

    def test_a_full_run_completes_every_planned_trial(self, ledger: Ledger) -> None:
        outcome = run_campaign(
            ledger=ledger,
            config=_config(),
            definitions=self._definitions(4),
            market=_market,
            window_start=START,
            window_end=START + timedelta(hours=2),
        )
        assert outcome.completed == 4
        assert outcome.not_run == 0
        assert outcome.partial is False

    def test_cancellation_leaves_the_remaining_trials_unrun(self, ledger: Ledger) -> None:
        token = CancellationToken()
        token.cancel()
        outcome = run_campaign(
            ledger=ledger,
            config=_config(),
            definitions=self._definitions(4),
            market=_market,
            window_start=START,
            window_end=START + timedelta(hours=2),
            token=token,
        )
        assert outcome.completed == 0
        assert outcome.not_run == 4

    def test_cancellation_during_a_trial_marks_it_cancelled(self, ledger: Ledger) -> None:
        token = CancellationToken()

        def cancelling_market(definition: StrategyDefinition) -> MarketData:
            token.cancel()
            return _market(definition)

        outcome = run_campaign(
            ledger=ledger,
            config=_config(),
            definitions=self._definitions(2),
            market=cancelling_market,
            window_start=START,
            window_end=START + timedelta(hours=2),
            token=token,
        )
        assert outcome.cancelled == 1
        assert outcome.not_run == 1
        assert outcome.partial is True

    def test_an_exhausted_time_budget_yields_a_partial_campaign(self, ledger: Ledger) -> None:
        ticks = iter([0.0, 10_000.0, 10_000.0, 10_000.0])
        outcome = run_campaign(
            ledger=ledger,
            config=_config(),
            definitions=self._definitions(4),
            market=_market,
            window_start=START,
            window_end=START + timedelta(hours=2),
            clock=lambda: next(ticks),
        )
        assert outcome.budget_exhausted == "max_active_minutes"
        assert outcome.partial is True
        assert outcome.not_run == 4

    def test_an_exhausted_evaluation_budget_stops_the_campaign(self, ledger: Ledger) -> None:
        config = _config().model_copy(
            update={"budget": CampaignBudget(max_candidates=2, max_evaluations=2)}
        )
        outcome = run_campaign(
            ledger=ledger,
            config=config,
            definitions=self._definitions(4),
            market=_market,
            window_start=START,
            window_end=START + timedelta(hours=2),
        )
        assert outcome.evaluations_used == 2
        assert outcome.budget_exhausted == "max_evaluations"
        assert outcome.not_run == 2

    def test_a_failing_candidate_is_recorded_without_aborting_the_campaign(
        self, ledger: Ledger
    ) -> None:
        definitions = self._definitions(3)

        def flaky_market(definition: StrategyDefinition) -> MarketData:
            if definition is definitions[1]:
                raise RuntimeError("dataset unavailable")
            return _market(definition)

        outcome = run_campaign(
            ledger=ledger,
            config=_config(),
            definitions=definitions,
            market=flaky_market,
            window_start=START,
            window_end=START + timedelta(hours=2),
        )
        assert outcome.completed == 2
        assert outcome.failed == 1
        assert outcome.not_run == 0
        failed = [
            trial
            for trial in ledger.trials(outcome.campaign_id)
            if trial.state is TrialState.FAILED
        ]
        assert failed[0].failure_reason == "dataset unavailable"

    def test_an_empty_dataset_produces_a_completed_trial_with_no_trade(
        self, ledger: Ledger
    ) -> None:
        def empty_market(definition: StrategyDefinition) -> MarketData:
            return MarketData(contract=CONTRACT, signal_bars=[], execution_bars=[])

        results: list[int] = []
        outcome = run_campaign(
            ledger=ledger,
            config=_config(),
            definitions=self._definitions(2),
            market=empty_market,
            window_start=START,
            window_end=START + timedelta(hours=2),
            on_result=lambda _, result: results.append(len(result.trades)),
        )
        assert outcome.completed == 2
        assert results == [0, 0]
