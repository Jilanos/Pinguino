from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from pinguino.domain.campaign import CampaignBudget, CampaignConfig, Trial
from pinguino.domain.dataset import Bar, CoverageReport, DatasetManifest
from pinguino.domain.enums import (
    DataProvenance,
    DatasetStatus,
    StrategyFamily,
    Symbol,
    Timeframe,
    TrialState,
)
from pinguino.domain.identity import canonical_json, content_hash
from pinguino.domain.policy import EligibilityPolicy, ResearchWindowPolicy, SizingPolicy
from pinguino.domain.strategy import StrategyDefinition, StrategyParameters
from pinguino.fixtures import (
    fixture_contract,
    fixture_cost_policy,
    fixture_eligibility_policy,
    fixture_sizing_policy,
    fixture_window_policy,
)

START = datetime(2020, 1, 1, tzinfo=UTC)
END = datetime(2025, 1, 1, tzinfo=UTC)


def _trend_definition() -> StrategyDefinition:
    return StrategyDefinition(
        family=StrategyFamily.TREND,
        symbol=Symbol.EURUSD,
        timeframe=Timeframe.H1,
        parameters=StrategyParameters(
            atr_stop_multiple=Decimal("1.5"),
            reward_risk_multiple=Decimal("2.0"),
            sma_fast=10,
            sma_slow=50,
        ),
    )


class TestInstrumentContract:
    def test_fixture_contracts_are_complete_for_every_symbol(self) -> None:
        for symbol in Symbol:
            contract = fixture_contract(symbol)
            assert contract.provenance is DataProvenance.SYNTHETIC_FIXTURE
            assert contract.contract_id.startswith("inst-")

    def test_missing_required_field_is_rejected(self) -> None:
        payload = fixture_contract(Symbol.EURUSD).model_dump()
        del payload["units_per_lot"]
        with pytest.raises(ValidationError):
            type(fixture_contract(Symbol.EURUSD))(**payload)

    def test_volume_band_must_be_ordered(self) -> None:
        payload = fixture_contract(Symbol.EURUSD).model_dump()
        payload["volume_max"] = Decimal("0.001")
        with pytest.raises(ValidationError, match="volume_max"):
            type(fixture_contract(Symbol.EURUSD))(**payload)

    def test_synthetic_and_broker_contracts_have_distinct_identifiers(self) -> None:
        synthetic = fixture_contract(Symbol.EURUSD)
        broker = synthetic.model_copy(update={"provenance": DataProvenance.MT5_TERMINAL})
        assert synthetic.contract_id != broker.contract_id


class TestPolicies:
    def test_split_fractions_must_sum_to_one(self) -> None:
        with pytest.raises(ValidationError, match="sum to exactly 1"):
            ResearchWindowPolicy(
                policy_version="v1",
                requested_start=START,
                requested_end=END,
                training_fraction=Decimal("0.7"),
                validation_fraction=Decimal("0.2"),
                final_holdout_fraction=Decimal("0.2"),
            )

    def test_naive_timestamps_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            ResearchWindowPolicy(
                policy_version="v1",
                requested_start=datetime(2020, 1, 1),
                requested_end=END,
            )

    def test_non_utc_timestamps_are_rejected(self) -> None:
        paris = datetime(2020, 1, 1, tzinfo=ZoneInfo("Europe/Paris"))
        with pytest.raises(ValidationError, match="must be UTC"):
            ResearchWindowPolicy(policy_version="v1", requested_start=paris, requested_end=END)

    def test_end_must_follow_start(self) -> None:
        with pytest.raises(ValidationError, match="after requested_start"):
            ResearchWindowPolicy(policy_version="v1", requested_start=END, requested_end=START)

    def test_eligibility_subwindow_demand_must_be_coherent(self) -> None:
        with pytest.raises(ValidationError, match="min_trades_per_subwindow"):
            EligibilityPolicy(
                policy_version="v1", min_validation_trades=5, min_trades_per_subwindow=10
            )

    def test_unsourced_cost_policy_flags_approximation(self) -> None:
        policy = fixture_cost_policy()
        assert policy.approximation_flags
        assert policy.sourced is False

    def test_stress_variant_scales_costs_without_touching_other_assumptions(self) -> None:
        base = fixture_cost_policy().model_copy(
            update={"commission_per_lot_per_side": Decimal("4")}
        )
        stressed = base.stressed()
        assert stressed.commission_per_lot_per_side == Decimal("6.0")
        assert stressed.spread_multiplier == Decimal("1.5")
        assert stressed.slippage_multiplier == Decimal("2.0")
        assert stressed.adverse_slippage_points == base.adverse_slippage_points

    def test_non_usd_account_currency_is_rejected(self) -> None:
        payload = fixture_sizing_policy().model_dump() | {"account_currency": "EUR"}
        with pytest.raises(ValidationError, match="USD"):
            SizingPolicy.model_validate(payload)


class TestStrategyDefinition:
    def test_trend_definition_exposes_a_stable_candidate_id(self) -> None:
        first = _trend_definition().candidate_id
        second = _trend_definition().candidate_id
        assert first == second and first.startswith("cand-")

    def test_family_parameters_must_match_the_family_axes(self) -> None:
        with pytest.raises(ValidationError, match="requires exactly"):
            StrategyDefinition(
                family=StrategyFamily.BREAKOUT,
                symbol=Symbol.EURUSD,
                timeframe=Timeframe.H1,
                parameters=StrategyParameters(
                    atr_stop_multiple=Decimal("1.5"),
                    reward_risk_multiple=Decimal("1.0"),
                    sma_fast=10,
                    sma_slow=50,
                ),
            )

    def test_signals_may_not_use_the_execution_timeframe(self) -> None:
        payload = _trend_definition().model_dump() | {"timeframe": "M1"}
        with pytest.raises(ValidationError, match="H1 or H4"):
            StrategyDefinition.model_validate(payload)

    def test_warmup_covers_the_longest_indicator_lookback(self) -> None:
        assert _trend_definition().warmup_signal_bars == 50


class TestDataset:
    def test_bar_rejects_invalid_ohlc(self) -> None:
        with pytest.raises(ValidationError, match="within the low-high range"):
            Bar(
                open_time=START,
                open=Decimal("1.5"),
                high=Decimal("1.2"),
                low=Decimal("1.0"),
                close=Decimal("1.1"),
                spread_points=Decimal("10"),
            )

    def test_manifest_requires_matching_provenance(self) -> None:
        coverage = CoverageReport(
            requested_start=START,
            requested_end=END,
            actual_start=START,
            actual_end=END,
            bar_count=10,
        )
        with pytest.raises(ValidationError, match="provenance"):
            DatasetManifest(
                manifest_version="v1",
                symbol=Symbol.EURUSD,
                timeframe=Timeframe.H1,
                provenance=DataProvenance.MT5_TERMINAL,
                status=DatasetStatus.QUALIFIED,
                contract=fixture_contract(Symbol.EURUSD),
                coverage=coverage,
                content_hash="0" * 64,
                source_note="fixture",
                imported_at=START,
            )


class TestCampaign:
    def _config(self) -> CampaignConfig:
        return CampaignConfig(
            config_version="v1",
            dataset_ids=("ds-a",),
            cost_policy=fixture_cost_policy(),
            sizing_policy=fixture_sizing_policy(),
            window_policy=fixture_window_policy(
                "2020-01-01T00:00:00+00:00", "2025-01-01T00:00:00+00:00"
            ),
            eligibility_policy=fixture_eligibility_policy(),
        )

    def test_campaign_config_is_frozen(self) -> None:
        config = self._config()
        with pytest.raises(ValidationError):
            config.config_version = "v2"  # type: ignore[misc]

    def test_duplicate_datasets_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            self._config().model_validate(
                self._config().model_dump() | {"dataset_ids": ["ds-a", "ds-a"]}
            )

    def test_evaluation_budget_must_cover_the_candidates(self) -> None:
        with pytest.raises(ValidationError, match="max_evaluations"):
            CampaignBudget(max_candidates=192, max_evaluations=10)

    def test_failed_trial_requires_a_reason(self) -> None:
        with pytest.raises(ValidationError, match="failure reason"):
            Trial(
                trial_id="t1",
                campaign_id="c1",
                definition=_trend_definition(),
                state=TrialState.FAILED,
                planned_order=0,
                ended_at=END,
            )


class TestIdentity:
    def test_canonical_json_is_order_independent(self) -> None:
        assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})

    def test_content_hash_is_stable_across_equal_models(self) -> None:
        assert content_hash(_trend_definition()) == content_hash(_trend_definition())
