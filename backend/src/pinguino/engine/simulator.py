"""Deterministic reference simulator.

Signals come from completed H1/H4 bid bars; execution happens on M1 bars. Every
ambiguous situation resolves the conservative way and is counted, and M1 OHLC is treated
as an approximation of the intrabar path, never as tick-level evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from pydantic import BaseModel, ConfigDict, Field

from pinguino.data.quality import BAR_DURATION
from pinguino.domain.dataset import Bar
from pinguino.domain.enums import ApproximationFlag, Direction, Timeframe
from pinguino.domain.instrument import InstrumentContract
from pinguino.domain.policy import CostPolicy, SizingPolicy
from pinguino.domain.results import EquityObservation, Fill, FillReason
from pinguino.domain.strategy import TIME_EXIT_SIGNAL_BARS, StrategyDefinition
from pinguino.engine.signals import Signal, evaluate

MONEY = Decimal("0.01")


class RejectedSignal(BaseModel):
    """A signal the engine declined to act on, with the reason it was declined."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    reason: str


class Trade(BaseModel):
    """One completed round trip, in account currency."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: Direction
    opened_at: datetime
    closed_at: datetime
    entry_price: Decimal
    exit_price: Decimal
    exit_reason: FillReason
    gross_pnl: Decimal
    commission: Decimal
    swap: Decimal
    net_pnl: Decimal
    ambiguous: bool = False


class SimulationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    equity_curve: tuple[EquityObservation, ...]
    rejected_signals: tuple[RejectedSignal, ...]
    ambiguity_count: int = Field(ge=0)
    forced_liquidation: bool
    approximation_flags: tuple[ApproximationFlag, ...]

    @property
    def final_equity(self) -> Decimal:
        return self.equity_curve[-1].equity if self.equity_curve else Decimal(0)


@dataclass
class _Position:
    direction: Direction
    entry_price: Decimal
    volume: Decimal
    units: Decimal
    stop: Decimal
    target: Decimal
    entry_signal_index: int
    opened_at: datetime
    commission: Decimal
    swap: Decimal = Decimal(0)
    ambiguous: bool = False
    last_swap_charged: datetime | None = None


@dataclass
class _Book:
    balance: Decimal
    fills: list[Fill] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[EquityObservation] = field(default_factory=list)
    rejected: list[RejectedSignal] = field(default_factory=list)
    ambiguity_count: int = 0
    forced_liquidation: bool = False


class _Market:
    """Bid bars plus the declared spread, which is how the ask path is approximated."""

    def __init__(self, contract: InstrumentContract, costs: CostPolicy) -> None:
        self.contract = contract
        self.costs = costs
        self.point = contract.point_size
        self.slippage = costs.adverse_slippage_points * costs.slippage_multiplier * self.point

    def spread(self, bar: Bar) -> Decimal:
        return bar.spread_points * self.costs.spread_multiplier * self.point

    def ask(self, bid_price: Decimal, bar: Bar) -> Decimal:
        return bid_price + self.spread(bar)

    def round_down(self, price: Decimal) -> Decimal:
        return (price / self.point).to_integral_value(ROUND_FLOOR) * self.point

    def round_up(self, price: Decimal) -> Decimal:
        return (price / self.point).to_integral_value(ROUND_CEILING) * self.point

    def to_account_currency(self, quote_amount: Decimal, bar: Bar) -> Decimal:
        """Convert a quote-currency amount using contemporaneous simulated prices."""
        if self.contract.quote_currency == "USD":
            return quote_amount
        if self.contract.base_currency != "USD":
            raise ValueError("only USD-quoted or USD-based pairs are supported in v1")
        rate = self.ask(bar.close, bar) if quote_amount > 0 else bar.close
        return quote_amount / rate

    def notional_usd(self, units: Decimal, bar: Bar) -> Decimal:
        if self.contract.base_currency == "USD":
            return units
        return units * bar.close


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY)


def simulate(
    *,
    definition: StrategyDefinition,
    signal_bars: Sequence[Bar],
    execution_bars: Sequence[Bar],
    contract: InstrumentContract,
    costs: CostPolicy,
    sizing: SizingPolicy,
    window_start: datetime,
    window_end: datetime,
    signals: Sequence[Signal] | None = None,
) -> SimulationResult:
    """Replay one candidate over ``[window_start, window_end)``.

    ``signal_bars`` must extend before ``window_start`` by the candidate's warm-up, and
    no warm-up bar produces a trade because only signals closing inside the window act.
    Passing ``signals`` replaces evaluation with an explicit list, which lets a fixture
    pin entry timing and ATR to hand-calculated values.
    """
    market = _Market(contract, costs)
    book = _Book(balance=sizing.initial_balance)
    step = BAR_DURATION[Timeframe(definition.timeframe)]

    signals_by_close: dict[datetime, Signal] = {
        signal_bars[signal.bar_index].open_time + step: signal
        for signal in (evaluate(definition, signal_bars) if signals is None else signals)
    }
    time_exit_deadline: dict[int, datetime] = {
        index: signal_bars[index].open_time + step * (TIME_EXIT_SIGNAL_BARS + 1)
        for index in range(len(signal_bars))
    }

    window_bars = [bar for bar in execution_bars if window_start <= bar.open_time < window_end]
    position: _Position | None = None
    pending_stop_out = False

    for bar_number, bar in enumerate(window_bars):
        is_last = bar_number == len(window_bars) - 1

        if position is not None:
            position = _charge_swap(position, bar, market)

        if position is not None and pending_stop_out:
            position = _close(
                position,
                bar,
                market,
                book,
                FillReason.MARGIN_STOP_OUT,
                _market_exit(position, bar, market),
            )
            pending_stop_out = False

        if position is not None:
            position = _open_price_exits(position, bar, market, book, time_exit_deadline)

        signal = signals_by_close.get(bar.open_time)
        if signal is not None:
            if position is not None:
                book.rejected.append(
                    RejectedSignal(at=bar.open_time, reason="a position is already open")
                )
            else:
                position = _open_position(signal, bar, market, book, sizing, definition)

        if position is not None:
            position = _intrabar_exits(position, bar, market, book)

        if position is not None and is_last:
            exit_price = _market_exit(position, bar, market, price=bar.close)
            position = _close(
                position, bar, market, book, FillReason.WINDOW_END_LIQUIDATION, exit_price
            )
            book.forced_liquidation = True

        equity = _equity(book, position, bar, market)
        book.equity_curve.append(
            EquityObservation(
                observed_at=bar.open_time + BAR_DURATION[Timeframe.M1],
                equity=_money(equity),
                realized_balance=_money(book.balance),
            )
        )
        if position is not None:
            used_margin = market.notional_usd(position.units, bar) / contract.leverage
            if used_margin > 0 and equity <= contract.stop_out_fraction * used_margin:
                pending_stop_out = True

    flags = [
        ApproximationFlag.ASK_DERIVED_FROM_BAR_SPREAD,
        ApproximationFlag.BAR_LEVEL_DRAWDOWN,
        ApproximationFlag.APPROXIMATE_MARGIN_MODEL,
        *costs.approximation_flags,
    ]
    if book.ambiguity_count:
        flags.append(ApproximationFlag.STOP_TARGET_AMBIGUITY)

    return SimulationResult(
        fills=tuple(book.fills),
        trades=tuple(book.trades),
        equity_curve=tuple(book.equity_curve),
        rejected_signals=tuple(book.rejected),
        ambiguity_count=book.ambiguity_count,
        forced_liquidation=book.forced_liquidation,
        approximation_flags=tuple(dict.fromkeys(flags)),
    )


def _open_position(
    signal: Signal,
    bar: Bar,
    market: _Market,
    book: _Book,
    sizing: SizingPolicy,
    definition: StrategyDefinition,
) -> _Position | None:
    contract = market.contract
    volume = sizing.fixed_volume
    if not (contract.volume_min <= volume <= contract.volume_max):
        book.rejected.append(
            RejectedSignal(at=bar.open_time, reason="volume outside the contract band")
        )
        return None
    if (volume / contract.volume_step) % 1 != 0:
        book.rejected.append(
            RejectedSignal(at=bar.open_time, reason="volume is not a multiple of the step")
        )
        return None

    if signal.direction is Direction.LONG:
        entry = market.round_up(market.ask(bar.open, bar) + market.slippage)
    else:
        entry = market.round_down(bar.open - market.slippage)

    units = volume * contract.units_per_lot
    margin = market.notional_usd(units, bar) / contract.leverage
    if margin > book.balance:
        book.rejected.append(RejectedSignal(at=bar.open_time, reason="insufficient free margin"))
        return None

    distance = signal.atr * definition.parameters.atr_stop_multiple
    if distance <= 0:
        book.rejected.append(RejectedSignal(at=bar.open_time, reason="invalid stop distance"))
        return None
    reward = distance * definition.parameters.reward_risk_multiple
    if signal.direction is Direction.LONG:
        stop = market.round_down(entry - distance)
        target = market.round_up(entry + reward)
    else:
        stop = market.round_up(entry + distance)
        target = market.round_down(entry - reward)

    commission = market.costs.commission_per_lot_per_side * volume
    book.balance -= commission
    book.fills.append(
        Fill(
            executed_at=bar.open_time,
            reason=FillReason.ENTRY,
            direction=signal.direction,
            price=entry,
            volume=volume,
            slippage_points=market.costs.adverse_slippage_points * market.costs.slippage_multiplier,
            commission=commission,
        )
    )
    return _Position(
        direction=signal.direction,
        entry_price=entry,
        volume=volume,
        units=units,
        stop=stop,
        target=target,
        entry_signal_index=signal.bar_index,
        opened_at=bar.open_time,
        commission=commission,
        last_swap_charged=bar.open_time,
    )


def _market_exit(
    position: _Position, bar: Bar, market: _Market, *, price: Decimal | None = None
) -> Decimal:
    """Market exit price: long sells the bid, short buys the ask, both slipped adversely."""
    reference = bar.open if price is None else price
    if position.direction is Direction.LONG:
        return market.round_down(reference - market.slippage)
    return market.round_up(market.ask(reference, bar) + market.slippage)


def _open_price_exits(
    position: _Position,
    bar: Bar,
    market: _Market,
    book: _Book,
    time_exit_deadline: dict[int, datetime],
) -> _Position | None:
    """At an M1 open: gap stop first, then gap target, then the time exit."""
    if position.direction is Direction.LONG:
        gapped_stop = bar.open <= position.stop
        gapped_target = bar.open >= position.target
    else:
        open_ask = market.ask(bar.open, bar)
        gapped_stop = open_ask >= position.stop
        gapped_target = open_ask <= position.target

    if gapped_stop:
        return _close(
            position,
            bar,
            market,
            book,
            FillReason.PROTECTIVE_STOP,
            _market_exit(position, bar, market),
        )
    if gapped_target:
        return _close(position, bar, market, book, FillReason.TAKE_PROFIT, position.target)

    deadline = time_exit_deadline.get(position.entry_signal_index)
    if deadline is not None and bar.open_time >= deadline:
        return _close(
            position, bar, market, book, FillReason.TIME_EXIT, _market_exit(position, bar, market)
        )
    return position


def _intrabar_exits(
    position: _Position, bar: Bar, market: _Market, book: _Book
) -> _Position | None:
    """Within an M1 bar: if both levels are reachable, the stop is taken first."""
    if position.direction is Direction.LONG:
        stop_hit = bar.low <= position.stop
        target_hit = bar.high >= position.target
    else:
        stop_hit = market.ask(bar.high, bar) >= position.stop
        target_hit = market.ask(bar.low, bar) <= position.target

    if stop_hit and target_hit:
        book.ambiguity_count += 1
        position.ambiguous = True
    if stop_hit:
        price = (
            market.round_down(position.stop - market.slippage)
            if position.direction is Direction.LONG
            else market.round_up(position.stop + market.slippage)
        )
        return _close(position, bar, market, book, FillReason.PROTECTIVE_STOP, price)
    if target_hit:
        return _close(position, bar, market, book, FillReason.TAKE_PROFIT, position.target)
    return position


def _charge_swap(position: _Position, bar: Bar, market: _Market) -> _Position:
    """Charge swap once per crossed rollover instant, tripled on the declared weekday."""
    contract = market.contract
    last = position.last_swap_charged or position.opened_at
    rollover = _next_rollover(last, contract.rollover_hour_utc)
    while rollover <= bar.open_time:
        days = 3 if rollover.weekday() == contract.triple_swap_weekday else 1
        points = (
            market.costs.swap_long_points_per_day
            if position.direction is Direction.LONG
            else market.costs.swap_short_points_per_day
        )
        quote_amount = points * market.point * position.units * days
        position.swap += market.to_account_currency(quote_amount, bar)
        position.last_swap_charged = rollover
        rollover = _next_rollover(rollover, contract.rollover_hour_utc)
    return position


def _next_rollover(after: datetime, hour: int) -> datetime:
    candidate = after.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= after:
        candidate += timedelta(days=1)
    return candidate


def _gross_pnl(position: _Position, exit_price: Decimal, bar: Bar, market: _Market) -> Decimal:
    difference = (
        exit_price - position.entry_price
        if position.direction is Direction.LONG
        else position.entry_price - exit_price
    )
    return market.to_account_currency(difference * position.units, bar)


def _close(
    position: _Position,
    bar: Bar,
    market: _Market,
    book: _Book,
    reason: FillReason,
    exit_price: Decimal,
) -> _Position | None:
    """Settle the position and return the new (always flat) position state."""
    gross = _gross_pnl(position, exit_price, bar, market)
    commission = market.costs.commission_per_lot_per_side * position.volume
    net = gross - commission + position.swap
    book.balance += net
    slippage_points = (
        Decimal(0)
        if reason is FillReason.TAKE_PROFIT
        else market.costs.adverse_slippage_points * market.costs.slippage_multiplier
    )
    exit_direction = Direction.SHORT if position.direction is Direction.LONG else Direction.LONG
    book.fills.append(
        Fill(
            executed_at=bar.open_time,
            reason=reason,
            direction=exit_direction,
            price=exit_price,
            volume=position.volume,
            slippage_points=slippage_points,
            commission=commission,
            ambiguous_stop_and_target=position.ambiguous,
        )
    )
    book.trades.append(
        Trade(
            direction=position.direction,
            opened_at=position.opened_at,
            closed_at=bar.open_time,
            entry_price=position.entry_price,
            exit_price=exit_price,
            exit_reason=reason,
            gross_pnl=_money(gross),
            commission=_money(position.commission + commission),
            swap=_money(position.swap),
            net_pnl=_money(net - position.commission),
            ambiguous=position.ambiguous,
        )
    )
    book.equity_curve.append(
        EquityObservation(
            observed_at=bar.open_time,
            equity=_money(book.balance),
            realized_balance=_money(book.balance),
        )
    )
    return None


def _equity(book: _Book, position: _Position | None, bar: Bar, market: _Market) -> Decimal:
    if position is None:
        return book.balance
    liquidation = bar.close if position.direction is Direction.LONG else market.ask(bar.close, bar)
    return book.balance + _gross_pnl(position, liquidation, bar, market) + position.swap
