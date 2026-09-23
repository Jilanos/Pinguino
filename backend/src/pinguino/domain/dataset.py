"""Dataset manifests and quality reports for imported bar history."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pinguino.domain.enums import DataProvenance, DatasetStatus, Symbol, Timeframe
from pinguino.domain.identity import content_id
from pinguino.domain.instrument import InstrumentContract
from pinguino.domain.timeutil import require_utc


class Bar(BaseModel):
    """One completed bid bar. Timestamps are UTC open instants, never shifted again."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    spread_points: Decimal = Field(ge=0)

    _utc = field_validator("open_time")(require_utc)

    @model_validator(mode="after")
    def _check_ohlc(self) -> Bar:
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError("open and close must lie within the low-high range")
        if self.low > self.high:
            raise ValueError("low must not exceed high")
        return self


class CoverageReport(BaseModel):
    """Actual coverage obtained, which may fall short of the requested span."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_start: datetime
    requested_end: datetime
    actual_start: datetime
    actual_end: datetime
    bar_count: int = Field(ge=0)
    quarantined_ranges: tuple[tuple[datetime, datetime], ...] = ()
    rejected_bar_count: int = Field(ge=0, default=0)
    #: M1 execution history actually available; signals outside it cannot trade.
    execution_start: datetime | None = None
    execution_end: datetime | None = None

    _utc = field_validator("requested_start", "requested_end", "actual_start", "actual_end")(
        require_utc
    )

    @model_validator(mode="after")
    def _check_bounds(self) -> CoverageReport:
        if self.actual_end < self.actual_start:
            raise ValueError("actual_end must not precede actual_start")
        return self


class DatasetManifest(BaseModel):
    """Canonical description of one immutable stored bar file.

    ``content_hash`` covers the normalized bar payload; the manifest identifier covers
    the metadata as well, so provenance changes always produce a new dataset.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    manifest_version: str = Field(min_length=1)
    symbol: Symbol
    timeframe: Timeframe
    provenance: DataProvenance
    status: DatasetStatus
    contract: InstrumentContract
    coverage: CoverageReport
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_note: str = Field(min_length=1)
    imported_at: datetime

    _utc = field_validator("imported_at")(require_utc)

    @model_validator(mode="after")
    def _check_consistency(self) -> DatasetManifest:
        if self.contract.symbol is not self.symbol:
            raise ValueError("contract symbol must match dataset symbol")
        if self.contract.provenance is not self.provenance:
            raise ValueError("contract provenance must match dataset provenance")
        if self.status is not DatasetStatus.REJECTED and self.coverage.bar_count == 0:
            raise ValueError("a non-rejected dataset must contain at least one bar")
        return self

    @property
    def dataset_id(self) -> str:
        return content_id("ds", self)
