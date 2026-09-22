from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pinguino.data.quality import FindingCode, ingest_bars, qualify_dataset
from pinguino.domain.enums import DataProvenance, DatasetStatus, Symbol, Timeframe
from pinguino.fixtures import fixture_contract
from pinguino.fixtures.series import as_raw, flat_m1_series, ramp_series, with_gap

CONTRACT = fixture_contract(Symbol.EURUSD)
# A Monday, well inside the weekly session.
START = datetime(2024, 1, 8, 0, 0, tzinfo=UTC)


def _h1_series(count: int = 24):
    return ramp_series(
        start=START,
        count=count,
        timeframe=Timeframe.H1,
        session=CONTRACT.session,
        first_price=Decimal("1.10000"),
        step_price=Decimal("0.00100"),
        spread_points=Decimal("10"),
        tick_size=CONTRACT.tick_size,
    )


def _m1_series(count: int):
    return flat_m1_series(
        start=START,
        count=count,
        session=CONTRACT.session,
        price=Decimal("1.10000"),
        spread_points=Decimal("10"),
    )


def _ingest(bars, timeframe: Timeframe):
    return ingest_bars(as_raw(bars), symbol=Symbol.EURUSD, timeframe=timeframe, contract=CONTRACT)


class TestIngestion:
    def test_clean_series_is_accepted_without_findings(self) -> None:
        series = _ingest(_h1_series(), Timeframe.H1)
        assert len(series.bars) == 24
        assert series.findings == ()
        assert series.rejected_count == 0

    def test_duplicate_timestamp_is_rejected(self) -> None:
        raw = as_raw(_h1_series(5))
        raw.append(raw[2])
        series = ingest_bars(raw, symbol=Symbol.EURUSD, timeframe=Timeframe.H1, contract=CONTRACT)
        assert series.rejected_count == 1
        assert {f.code for f in series.findings} == {FindingCode.DUPLICATE_TIMESTAMP}

    def test_out_of_order_bar_is_rejected(self) -> None:
        raw = as_raw(_h1_series(5))
        raw.append(as_raw(_h1_series(1))[0] | {"open_time": "2023-12-01T00:00:00+00:00"})
        series = ingest_bars(raw, symbol=Symbol.EURUSD, timeframe=Timeframe.H1, contract=CONTRACT)
        assert FindingCode.NONMONOTONIC_TIMESTAMP in {f.code for f in series.findings}

    def test_invalid_ohlc_is_rejected(self) -> None:
        raw = as_raw(_h1_series(3))
        raw[1] = raw[1] | {"high": "1.00000"}
        series = ingest_bars(raw, symbol=Symbol.EURUSD, timeframe=Timeframe.H1, contract=CONTRACT)
        assert FindingCode.INVALID_OHLC in {f.code for f in series.findings}
        assert len(series.bars) == 2

    def test_nonfinite_price_is_rejected(self) -> None:
        raw = as_raw(_h1_series(3))
        raw[0] = raw[0] | {"close": "NaN"}
        series = ingest_bars(raw, symbol=Symbol.EURUSD, timeframe=Timeframe.H1, contract=CONTRACT)
        assert FindingCode.NONFINITE_PRICE in {f.code for f in series.findings}

    def test_undeclared_timezone_is_rejected(self) -> None:
        raw = as_raw(_h1_series(3))
        raw[0] = raw[0] | {"open_time": "2024-01-08T00:00:00"}
        series = ingest_bars(raw, symbol=Symbol.EURUSD, timeframe=Timeframe.H1, contract=CONTRACT)
        assert FindingCode.UNDECLARED_TIMEZONE in {f.code for f in series.findings}

    def test_misaligned_timestamp_is_rejected(self) -> None:
        raw = as_raw(_h1_series(3))
        raw[1] = raw[1] | {"open_time": "2024-01-08T01:30:00+00:00"}
        series = ingest_bars(raw, symbol=Symbol.EURUSD, timeframe=Timeframe.H1, contract=CONTRACT)
        assert FindingCode.MISALIGNED_TIMESTAMP in {f.code for f in series.findings}

    def test_weekend_closure_is_not_reported_as_a_gap(self) -> None:
        # 200 H1 bars from Monday span the Friday close and the Sunday reopen.
        series = _ingest(_h1_series(200), Timeframe.H1)
        assert series.findings == ()
        assert series.quarantined == ()

    def test_open_session_gap_is_quarantined_with_its_range(self) -> None:
        series = _ingest(with_gap(_h1_series(24), drop_from=5, drop_count=3), Timeframe.H1)
        assert len(series.quarantined) == 1
        start, end = series.quarantined[0]
        assert end - start == timedelta(hours=4)
        assert len(series.usable_bars) < len(series.bars)


class TestQualification:
    def _qualify(
        self, *, h1_count: int = 24, m1_count: int = 24 * 60 + 1, costs_sourced: bool = True
    ):
        return qualify_dataset(
            signal_series=_ingest(_h1_series(h1_count), Timeframe.H1),
            execution_series=_ingest(_m1_series(m1_count), Timeframe.M1),
            contract=CONTRACT,
            provenance=DataProvenance.SYNTHETIC_FIXTURE,
            requested_start=START,
            requested_end=START + timedelta(hours=h1_count - 1),
            costs_sourced=costs_sourced,
            source_note="synthetic ramp fixture",
            imported_at=START,
        )

    def test_clean_fixture_qualifies_with_a_stable_fingerprint(self) -> None:
        first, findings = self._qualify()
        second, _ = self._qualify()
        assert findings == ()
        assert first.status is DatasetStatus.QUALIFIED
        assert first.content_hash == second.content_hash
        assert first.dataset_id == second.dataset_id

    def test_provenance_is_part_of_the_fingerprint(self) -> None:
        manifest, _ = self._qualify()
        assert manifest.provenance is DataProvenance.SYNTHETIC_FIXTURE
        assert manifest.source_note

    def test_unsourced_costs_downgrade_to_approximate(self) -> None:
        manifest, findings = self._qualify(costs_sourced=False)
        assert manifest.status is DatasetStatus.APPROXIMATE
        assert FindingCode.MISSING_COST_COMPONENT in {f.code for f in findings}

    def test_missing_m1_history_rejects_instead_of_falling_back(self) -> None:
        manifest, findings = self._qualify(m1_count=60)
        assert manifest.status is DatasetStatus.REJECTED
        assert FindingCode.MISSING_EXECUTION_COVERAGE in {f.code for f in findings}

    def test_coverage_shortfall_is_reported(self) -> None:
        manifest, findings = qualify_dataset(
            signal_series=_ingest(_h1_series(24), Timeframe.H1),
            execution_series=_ingest(_m1_series(24 * 60 + 1), Timeframe.M1),
            contract=CONTRACT,
            provenance=DataProvenance.SYNTHETIC_FIXTURE,
            requested_start=START,
            requested_end=START + timedelta(days=365 * 5),
            costs_sourced=True,
            source_note="synthetic ramp fixture",
            imported_at=START,
        )
        assert manifest.status is not DatasetStatus.QUALIFIED
        assert FindingCode.COVERAGE_SHORTFALL in {f.code for f in findings}
        assert manifest.coverage.actual_end < manifest.coverage.requested_end

    def test_contract_metadata_covers_sizing_and_sessions(self) -> None:
        manifest, _ = self._qualify()
        contract = manifest.contract
        assert contract.volume_min and contract.volume_step and contract.volume_max
        assert contract.base_currency and contract.quote_currency
        assert contract.session.close_weekday == 4
