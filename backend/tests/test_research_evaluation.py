from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from pinguino.domain.enums import WindowKind
from pinguino.domain.errors import ErrorCode, PinguinoError
from pinguino.domain.results import WindowMetrics
from pinguino.fixtures import fixture_eligibility_policy, fixture_window_policy
from pinguino.research.evaluation import (
    ScreeningResult,
    Verdict,
    neighborhood_verdict,
    open_final_holdout,
    passes_stress,
    rank,
    screen_candidate,
)
from pinguino.research.grid import expand_grid
from pinguino.research.ledger import Ledger
from pinguino.research.windows import resolve_split, warmup_start

POLICY = fixture_eligibility_policy()
START = datetime(2020, 1, 1, tzinfo=UTC)
END = datetime(2025, 1, 1, tzinfo=UTC)


def _metrics(
    kind: WindowKind,
    *,
    start: datetime = START,
    trades: int = 50,
    net_return: str = "0.10",
    drawdown: str = "0.05",
) -> WindowMetrics:
    reasons = () if trades else ("no trade was taken in this window",)
    return WindowMetrics(
        window=kind,
        start=start,
        end=start + timedelta(days=30),
        net_return=Decimal(net_return),
        max_drawdown=Decimal(drawdown),
        trade_count=trades,
        win_rate=Decimal("0.5") if trades else None,
        profit_factor=Decimal("1.2") if trades else None,
        exposure_fraction=Decimal("0.3"),
        turnover=Decimal("1000"),
        commission_cost=Decimal("1"),
        spread_cost=Decimal("1"),
        swap_cost=Decimal("0"),
        slippage_cost=Decimal("1"),
        undefined_reasons=reasons,
    )


def _subwindows(**overrides: object) -> tuple[WindowMetrics, ...]:
    return tuple(
        _metrics(
            WindowKind.VALIDATION,
            start=START + timedelta(days=30 * index),
            trades=15,
            **overrides,  # type: ignore[arg-type]
        )
        for index in range(3)
    )


class TestSplit:
    def test_sixty_twenty_twenty_split_is_chronological_and_contiguous(self) -> None:
        split = resolve_split(fixture_window_policy(START.isoformat(), END.isoformat()))
        assert split.training.start == START
        assert split.training.end == split.validation.start
        assert split.validation.end == split.final_holdout.start
        assert split.final_holdout.end == END
        total = (END - START).total_seconds()
        training = (split.training.end - split.training.start).total_seconds()
        assert abs(training / total - 0.6) < 0.001

    def test_validation_is_partitioned_into_three_contiguous_subwindows(self) -> None:
        split = resolve_split(fixture_window_policy(START.isoformat(), END.isoformat()))
        subwindows = split.validation_subwindows
        assert len(subwindows) == 3
        assert subwindows[0].start == split.validation.start
        assert subwindows[-1].end == split.validation.end
        for earlier, later in zip(subwindows, subwindows[1:], strict=False):
            assert earlier.end == later.start

    def test_the_final_holdout_is_never_selectable(self) -> None:
        split = resolve_split(fixture_window_policy(START.isoformat(), END.isoformat()))
        assert split.final_holdout not in split.selectable
        assert all(window.kind is not WindowKind.FINAL_HOLDOUT for window in split.selectable)

    def test_warmup_precedes_the_window_it_serves(self) -> None:
        split = resolve_split(fixture_window_policy(START.isoformat(), END.isoformat()))
        begin = warmup_start(split.training, signal_bars=200, bar_duration=timedelta(hours=1))
        assert begin == split.training.start - timedelta(hours=200)


class TestScreening:
    def test_a_healthy_candidate_is_eligible(self) -> None:
        result = screen_candidate(
            candidate_id="cand-1",
            training=_metrics(WindowKind.TRAINING, trades=150),
            validation=_metrics(WindowKind.VALIDATION, trades=45),
            subwindows=_subwindows(),
            policy=POLICY,
        )
        assert result.verdict is Verdict.ELIGIBLE
        assert result.positive_subwindows == 3

    def test_too_few_training_trades_is_inconclusive_not_rejected(self) -> None:
        result = screen_candidate(
            candidate_id="cand-1",
            training=_metrics(WindowKind.TRAINING, trades=10),
            validation=_metrics(WindowKind.VALIDATION, trades=45),
            subwindows=_subwindows(),
            policy=POLICY,
        )
        assert result.verdict is Verdict.INCONCLUSIVE
        assert "training trades 10 < 100" in result.reasons[0]

    def test_too_few_positive_subwindows_is_rejected(self) -> None:
        subwindows = (
            _metrics(WindowKind.VALIDATION, trades=15, net_return="0.10"),
            _metrics(
                WindowKind.VALIDATION,
                start=START + timedelta(days=30),
                trades=15,
                net_return="-0.02",
            ),
            _metrics(
                WindowKind.VALIDATION,
                start=START + timedelta(days=60),
                trades=15,
                net_return="-0.03",
            ),
        )
        result = screen_candidate(
            candidate_id="cand-1",
            training=_metrics(WindowKind.TRAINING, trades=150),
            validation=_metrics(WindowKind.VALIDATION, trades=45),
            subwindows=subwindows,
            policy=POLICY,
        )
        assert result.verdict is Verdict.REJECTED
        assert "positive subwindows 1 < 2" in result.reasons[0]

    def test_an_excessive_subwindow_drawdown_is_rejected(self) -> None:
        result = screen_candidate(
            candidate_id="cand-1",
            training=_metrics(WindowKind.TRAINING, trades=150),
            validation=_metrics(WindowKind.VALIDATION, trades=45),
            subwindows=_subwindows(drawdown="0.30"),
            policy=POLICY,
        )
        assert result.verdict is Verdict.REJECTED
        assert any("drawdown" in reason for reason in result.reasons)


class TestRobustness:
    def test_stress_requires_a_positive_return_under_worse_costs(self) -> None:
        assert passes_stress(_metrics(WindowKind.VALIDATION), POLICY) is True
        assert passes_stress(_metrics(WindowKind.VALIDATION, net_return="-0.01"), POLICY) is False

    def test_stress_also_requires_a_bounded_drawdown(self) -> None:
        assert passes_stress(_metrics(WindowKind.VALIDATION, drawdown="0.40"), POLICY) is False

    def test_half_the_neighbors_passing_is_enough(self) -> None:
        assert (
            neighborhood_verdict((Verdict.ELIGIBLE, Verdict.REJECTED), POLICY) is Verdict.ELIGIBLE
        )
        assert (
            neighborhood_verdict((Verdict.ELIGIBLE, Verdict.REJECTED, Verdict.REJECTED), POLICY)
            is Verdict.REJECTED
        )

    def test_no_neighbor_yields_inconclusive_stability(self) -> None:
        assert neighborhood_verdict((), POLICY) is Verdict.INCONCLUSIVE


class TestRanking:
    def _result(self, candidate_id: str, positive: int, drawdown: str, net: str) -> ScreeningResult:
        return ScreeningResult(
            candidate_id=candidate_id,
            verdict=Verdict.ELIGIBLE,
            reasons=(),
            positive_subwindows=positive,
            worst_subwindow_drawdown=Decimal(drawdown),
            validation_net_return=Decimal(net),
        )

    def test_positive_subwindows_dominate_then_drawdown_then_return(self) -> None:
        ordered = rank(
            (
                self._result("c", 2, "0.01", "0.50"),
                self._result("a", 3, "0.10", "0.05"),
                self._result("b", 3, "0.05", "0.01"),
            )
        )
        assert [result.candidate_id for result in ordered] == ["b", "a", "c"]

    def test_candidate_id_breaks_ties_stably(self) -> None:
        ordered = rank(
            (
                self._result("z", 3, "0.05", "0.10"),
                self._result("a", 3, "0.05", "0.10"),
            )
        )
        assert [result.candidate_id for result in ordered] == ["a", "z"]

    def test_only_eligible_candidates_are_ranked(self) -> None:
        rejected = self._result("r", 3, "0.01", "0.90").model_copy(
            update={"verdict": Verdict.REJECTED}
        )
        assert rank((rejected, self._result("a", 1, "0.20", "0.01"))) == [
            self._result("a", 1, "0.20", "0.01")
        ]


class TestFinalHoldout:
    @pytest.fixture
    def ledger(self, tmp_path: Path) -> Ledger:
        instance = Ledger(tmp_path / "research.sqlite")
        yield instance
        instance.close()

    def _open(self, ledger: Ledger, index: int = 0, campaign_id: str = "camp-1"):
        return open_final_holdout(
            ledger=ledger,
            campaign_id=campaign_id,
            definition=expand_grid()[index],
            window_policy_id="window-1",
            dataset_ids=("ds-a",),
            requested_at=START,
            reason="frozen candidate final evaluation",
        )

    def test_access_is_logged_before_the_holdout_runs(self, ledger: Ledger) -> None:
        event = self._open(ledger)
        assert event.reused_lineage is False
        assert len(ledger.holdout_accesses("camp-1")) == 1

    def test_a_second_candidate_is_refused(self, ledger: Ledger) -> None:
        self._open(ledger, index=0)
        with pytest.raises(PinguinoError) as error:
            self._open(ledger, index=1)
        assert error.value.code is ErrorCode.HOLDOUT_ACCESS_DENIED
        assert "réservé" in error.value.french

    def test_reopening_the_same_lineage_marks_it_reused(self, ledger: Ledger) -> None:
        self._open(ledger, index=0, campaign_id="camp-1")
        event = self._open(ledger, index=0, campaign_id="camp-2")
        assert event.reused_lineage is True
