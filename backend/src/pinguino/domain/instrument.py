"""Instrument contract: the broker-or-fixture description of a tradable symbol."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pinguino.domain.enums import DataProvenance, Symbol
from pinguino.domain.identity import content_id


class WeeklySession(BaseModel):
    """Weekly trading window in UTC. Bars are only expected while the market is open."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    open_weekday: int = Field(ge=0, le=6, default=6)
    open_hour_utc: int = Field(ge=0, le=23, default=21)
    close_weekday: int = Field(ge=0, le=6, default=4)
    close_hour_utc: int = Field(ge=0, le=23, default=21)

    def is_open(self, moment: datetime) -> bool:
        """True while the weekly session is running, using UTC weekday and hour."""
        opened = (self.open_weekday, self.open_hour_utc)
        closed = (self.close_weekday, self.close_hour_utc)
        current = (moment.weekday(), moment.hour)
        if opened > closed:
            return current >= opened or current < closed
        return opened <= current < closed


class InstrumentContract(BaseModel):
    """Contract metadata required before any fill can be simulated.

    Every field is required: an absent broker value must be supplied explicitly as a
    versioned approximation rather than defaulted silently.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: Symbol
    provenance: DataProvenance
    contract_version: str = Field(min_length=1)
    digits: int = Field(ge=0, le=8)
    tick_size: Decimal = Field(gt=0)
    point_size: Decimal = Field(gt=0)
    base_currency: str = Field(min_length=3, max_length=3)
    quote_currency: str = Field(min_length=3, max_length=3)
    units_per_lot: Decimal = Field(gt=0)
    volume_min: Decimal = Field(gt=0)
    volume_max: Decimal = Field(gt=0)
    volume_step: Decimal = Field(gt=0)
    leverage: Decimal = Field(gt=0)
    stop_out_fraction: Decimal = Field(gt=0, le=1)
    session: WeeklySession = WeeklySession()
    rollover_hour_utc: int = Field(ge=0, le=23)
    triple_swap_weekday: int = Field(ge=0, le=6)

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def _upper_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must be alphabetic ISO code")
        return value.upper()

    @model_validator(mode="after")
    def _check_volume_band(self) -> InstrumentContract:
        if self.volume_max < self.volume_min:
            raise ValueError("volume_max must not be below volume_min")
        if self.point_size < self.tick_size:
            raise ValueError("point_size must not be below tick_size")
        return self

    @property
    def contract_id(self) -> str:
        return content_id("inst", self)
