"""Hand-calculated reference fixtures.

EURUSD fixture arithmetic, used throughout:

    point size    0.00001        volume 0.01 lot -> 1 000 base units
    bar spread    10 points   =  0.00010
    slippage       1 point    =  0.00001
    ATR           100 points  =  0.00100, stop multiple 1.5 -> 0.00150
                                          reward multiple 2.0 -> 0.00300

A long entering on a bar whose bid open is 1.10000 therefore pays
1.10000 + 0.00010 + 0.00001 = 1.10011, protects at 1.09861 and targets 1.10311.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from pinguino.domain.dataset import Bar
from pinguino.domain.enums import ApproximationFlag, Direction, StrategyFamily, Symbol, Timeframe
from pinguino.domain.results import REPLAY_MONEY_TOLERANCE, FillReason
from pinguino.domain.strategy import StrategyDefinition, StrategyParameters
from pinguino.engine.signals import Signal
from pinguino.engine.simulator import simulate
from pinguino.fixtures import fixture_contract, fixture_cost_policy, fixture_sizing_policy

START = datetime(2024, 1, 8, tzinfo=UTC)
ATR = Decimal("0.00100")
SPREAD_POINTS = Decimal("10")

EURUSD = fixture_contract(Symbol.EURUSD)
USDJPY = fixture_contract(Symbol.USDJPY)


def _definition(direction_family: StrategyFamily = StrategyFamily.TREND) -> StrategyDefinition:
    return StrategyDefinition(
        family=direction_family,
        symbol=Symbol.EURUSD,
        timeframe=Timeframe.H1,
        parameters=StrategyParameters(
            atr_stop_multiple=Decimal("1.5"),
            reward_risk_multiple=Decimal("2.0"),
            sma_fast=10,
            sma_slow=50,
        ),
    )


def _signal_bars(count: int = 40) -> list[Bar]:
    return [
        Bar(
            open_time=START + timedelta(hours=index),
            open=Decimal("1.10000"),
            high=Decimal("1.10050"),
            low=Decimal("1.09950"),
            close=Decimal("1.10000"),
            spread_points=SPREAD_POINTS,
        )
        for index in range(count)
    ]


def _m1(offset: int, o: str, h: str, low: str, c: str, spread: Decimal = SPREAD_POINTS) -> Bar:
    return Bar(
        open_time=START + timedelta(minutes=offset),
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(low),
        close=Decimal(c),
        spread_points=spread,
    )


def _flat(offset: int, price: str = "1.10000") -> Bar:
    return _m1(offset, price, price, price, price)


def _run(
    execution_bars: list[Bar],
    *,
    direction: Direction = Direction.LONG,
    signal_index: int = 0,
    contract=EURUSD,
    costs=None,
    definition: StrategyDefinition | None = None,
    signal_bars: list[Bar] | None = None,
):
    bars = signal_bars if signal_bars is not None else _signal_bars()
    return simulate(
        definition=definition or _definition(),
        signal_bars=bars,
        execution_bars=execution_bars,
        contract=contract,
        costs=costs or fixture_cost_policy(),
        sizing=fixture_sizing_policy(),
        window_start=execution_bars[0].open_time,
        window_end=execution_bars[-1].open_time + timedelta(minutes=1),
        signals=[Signal(bar_index=signal_index, direction=direction, atr=ATR)],
    )


class TestEntry:
    def test_long_enters_at_the_next_m1_open_paying_ask_plus_slippage(self) -> None:
        # The signal bar opens at 00:00 and closes at 01:00, so entry is the 01:00 M1 bar.
        result = _run([_flat(60), _flat(61), _flat(62)])
        entry = result.fills[0]
        assert entry.reason is FillReason.ENTRY
        assert entry.executed_at == START + timedelta(minutes=60)
        assert entry.price == Decimal("1.10011")

    def test_short_enters_at_the_bid_minus_slippage(self) -> None:
        result = _run([_flat(60), _flat(61)], direction=Direction.SHORT)
        assert result.fills[0].price == Decimal("1.09999")

    def test_a_signal_without_a_tradable_m1_bar_never_fills(self) -> None:
        result = _run([_flat(0), _flat(1)])
        assert result.fills == ()

    def test_a_missing_close_minute_delays_the_entry_to_the_next_m1_open(self) -> None:
        result = _run([_flat(59), _flat(62), _flat(63)])
        assert result.fills[0].executed_at == START + timedelta(minutes=62)
        assert ApproximationFlag.DELAYED_ENTRY in result.approximation_flags

    def test_an_entry_never_waits_across_a_session_closure(self) -> None:
        # Friday 20:00 bar closes at 21:00 UTC, when the fixture session closes.
        friday = START + timedelta(days=4, hours=20)
        bars = [
            Bar(
                open_time=friday + timedelta(hours=index),
                open=Decimal("1.10000"),
                high=Decimal("1.10050"),
                low=Decimal("1.09950"),
                close=Decimal("1.10000"),
                spread_points=SPREAD_POINTS,
            )
            for index in range(1)
        ]
        monday = [_flat(offset) for offset in (7 * 24 * 60, 7 * 24 * 60 + 1)]
        result = simulate(
            definition=_definition(),
            signal_bars=bars,
            execution_bars=[_flat(4 * 24 * 60 + 20 * 60 + 59), *monday],
            contract=EURUSD,
            costs=fixture_cost_policy(),
            sizing=fixture_sizing_policy(),
            window_start=friday,
            window_end=START + timedelta(days=8),
            signals=[Signal(bar_index=0, direction=Direction.LONG, atr=ATR)],
        )
        assert result.fills == ()
        assert ApproximationFlag.DELAYED_ENTRY not in result.approximation_flags

    def test_a_second_signal_is_ignored_while_positioned(self) -> None:
        bars = [_flat(offset) for offset in range(60, 125)]
        result = simulate(
            definition=_definition(),
            signal_bars=_signal_bars(),
            execution_bars=bars,
            contract=EURUSD,
            costs=fixture_cost_policy(),
            sizing=fixture_sizing_policy(),
            window_start=bars[0].open_time,
            window_end=bars[-1].open_time + timedelta(minutes=1),
            signals=[
                Signal(bar_index=0, direction=Direction.LONG, atr=ATR),
                Signal(bar_index=1, direction=Direction.SHORT, atr=ATR),
            ],
        )
        assert len([fill for fill in result.fills if fill.reason is FillReason.ENTRY]) == 1
        assert result.rejected_signals[0].reason == "a position is already open"


class TestProtectiveExits:
    def test_target_fills_at_its_exact_price_without_gap_improvement(self) -> None:
        result = _run([_flat(60), _m1(61, "1.10400", "1.10500", "1.10400", "1.10450")])
        exit_fill = result.fills[1]
        assert exit_fill.reason is FillReason.TAKE_PROFIT
        assert exit_fill.price == Decimal("1.10311")
        assert exit_fill.slippage_points == Decimal("0")
        assert result.trades[0].net_pnl == Decimal("3.00")

    def test_intrabar_stop_fills_one_point_beyond_the_stop(self) -> None:
        result = _run([_flat(60), _m1(61, "1.10000", "1.10000", "1.09800", "1.09900")])
        exit_fill = result.fills[1]
        assert exit_fill.reason is FillReason.PROTECTIVE_STOP
        assert exit_fill.price == Decimal("1.09860")
        assert result.trades[0].net_pnl == Decimal("-1.51")

    def test_gap_below_the_stop_fills_at_the_worse_open_plus_slippage(self) -> None:
        result = _run([_flat(60), _m1(61, "1.09800", "1.09850", "1.09800", "1.09820")])
        exit_fill = result.fills[1]
        assert exit_fill.reason is FillReason.PROTECTIVE_STOP
        assert exit_fill.price == Decimal("1.09799")
        assert result.trades[0].net_pnl == Decimal("-2.12")

    def test_both_levels_reachable_takes_the_stop_and_counts_the_ambiguity(self) -> None:
        result = _run([_flat(60), _m1(61, "1.10000", "1.10400", "1.09800", "1.10200")])
        assert result.fills[1].reason is FillReason.PROTECTIVE_STOP
        assert result.ambiguity_count == 1
        assert result.fills[1].ambiguous_stop_and_target is True
        assert ApproximationFlag.STOP_TARGET_AMBIGUITY in result.approximation_flags

    def test_short_stop_uses_the_ask_path(self) -> None:
        # Short stop 1.10149 is reached once the bid high plus the 10-point spread crosses it.
        result = _run(
            [_flat(60), _m1(61, "1.10000", "1.10140", "1.10000", "1.10100")],
            direction=Direction.SHORT,
        )
        assert result.fills[1].reason is FillReason.PROTECTIVE_STOP
        assert result.fills[1].price == Decimal("1.10150")
        assert result.trades[0].net_pnl == Decimal("-1.51")


class TestTimeAndWindowExits:
    def test_time_exit_closes_after_twenty_completed_signal_bars(self) -> None:
        # Entry at 01:00; the twentieth signal bar completed after entry closes at 21:00.
        bars = [_flat(offset) for offset in range(60, 60 * 23)]
        result = _run(bars)
        exit_fill = result.fills[-1]
        assert exit_fill.reason is FillReason.TIME_EXIT
        assert exit_fill.executed_at == START + timedelta(hours=21)

    def test_window_end_liquidates_at_the_last_close_and_is_recorded(self) -> None:
        result = _run([_flat(60), _flat(61), _flat(62)])
        assert result.forced_liquidation is True
        assert result.fills[-1].reason is FillReason.WINDOW_END_LIQUIDATION

    def test_no_trade_is_carried_past_the_window(self) -> None:
        result = _run([_flat(offset) for offset in range(60, 70)])
        entries = [fill for fill in result.fills if fill.reason is FillReason.ENTRY]
        exits = [fill for fill in result.fills if fill.reason is not FillReason.ENTRY]
        assert len(entries) == len(exits)


class TestCosts:
    def test_commission_is_charged_once_on_each_side(self) -> None:
        costs = fixture_cost_policy().model_copy(
            update={"commission_per_lot_per_side": Decimal("4")}
        )
        result = _run([_flat(60), _m1(61, "1.10400", "1.10500", "1.10400", "1.10450")], costs=costs)
        trade = result.trades[0]
        assert trade.commission == Decimal("0.08")
        assert trade.net_pnl == Decimal("2.92")

    def test_swap_is_charged_once_per_crossed_rollover(self) -> None:
        costs = fixture_cost_policy().model_copy(update={"swap_long_points_per_day": Decimal("-2")})
        # Entry at 01:00 Monday, held past the 21:00 rollover.
        bars = [_flat(offset) for offset in range(60, 60 * 22)]
        result = _run(bars, costs=costs)
        # -2 points x 0.00001 x 1 000 units = -0.02 USD for one rollover.
        assert result.trades[0].swap == Decimal("-0.02")

    def test_stressed_costs_widen_the_spread_and_double_the_slippage(self) -> None:
        stressed = fixture_cost_policy().stressed()
        result = _run([_flat(60), _flat(61)], costs=stressed)
        # ask = 1.10000 + 10 x 1.5 points; slippage = 1 x 2 points.
        assert result.fills[0].price == Decimal("1.10017")

    def test_unsourced_costs_surface_as_an_approximation_flag(self) -> None:
        result = _run([_flat(60), _flat(61)])
        assert ApproximationFlag.ESTIMATED_COST_PROFILE in result.approximation_flags
        assert ApproximationFlag.ASK_DERIVED_FROM_BAR_SPREAD in result.approximation_flags
        assert ApproximationFlag.BAR_LEVEL_DRAWDOWN in result.approximation_flags


class TestAccountCurrency:
    def test_jpy_profit_converts_at_the_contemporaneous_ask(self) -> None:
        definition = _definition().model_copy(update={"symbol": Symbol.USDJPY})
        signal_bars = [
            Bar(
                open_time=START + timedelta(hours=index),
                open=Decimal("150.000"),
                high=Decimal("150.100"),
                low=Decimal("149.900"),
                close=Decimal("150.000"),
                spread_points=SPREAD_POINTS,
            )
            for index in range(40)
        ]
        execution = [
            Bar(
                open_time=START + timedelta(minutes=offset),
                open=Decimal("150.000"),
                high=Decimal("151.500"),
                low=Decimal("150.000"),
                close=Decimal("151.000"),
                spread_points=SPREAD_POINTS,
            )
            for offset in (60, 61)
        ]
        result = simulate(
            definition=definition,
            signal_bars=signal_bars,
            execution_bars=execution,
            contract=USDJPY,
            costs=fixture_cost_policy(),
            sizing=fixture_sizing_policy(),
            window_start=execution[0].open_time,
            window_end=execution[-1].open_time + timedelta(minutes=1),
            signals=[Signal(bar_index=0, direction=Direction.LONG, atr=Decimal("1.000"))],
        )
        # Entry 150.000 + 0.010 spread + 0.001 slippage = 150.011. The target at 153.011
        # is never reached, so the window end liquidates at 151.000 - 0.001 slippage.
        assert result.fills[0].price == Decimal("150.011")
        trade = result.trades[0]
        assert trade.exit_reason is FillReason.WINDOW_END_LIQUIDATION
        assert trade.exit_price == Decimal("150.999")
        # 0.988 JPY x 1 000 units = 988 JPY, converted at the exit bar ask 151.010.
        assert trade.gross_pnl == (Decimal("988") / Decimal("151.010")).quantize(Decimal("0.01"))


class TestCausalityAndDeterminism:
    def test_changing_future_bars_leaves_earlier_fills_unchanged(self) -> None:
        early = [_flat(60), _flat(61), _flat(62)]
        late = [*early, _m1(63, "1.20000", "1.30000", "1.20000", "1.25000")]
        first = _run(early)
        second = _run(late)
        assert first.fills[0] == second.fills[0]

    def test_replaying_identical_inputs_reproduces_trades_within_tolerance(self) -> None:
        bars = [_flat(60), _m1(61, "1.10400", "1.10500", "1.10400", "1.10450")]
        first, second = _run(bars), _run(bars)
        assert first.fills == second.fills
        assert abs(first.final_equity - second.final_equity) <= REPLAY_MONEY_TOLERANCE

    def test_warmup_bars_never_produce_a_trade(self) -> None:
        result = simulate(
            definition=_definition(),
            signal_bars=_signal_bars(),
            execution_bars=[_flat(offset) for offset in range(60, 130)],
            contract=EURUSD,
            costs=fixture_cost_policy(),
            sizing=fixture_sizing_policy(),
            window_start=START + timedelta(minutes=90),
            window_end=START + timedelta(minutes=130),
            signals=[Signal(bar_index=0, direction=Direction.LONG, atr=ATR)],
        )
        assert result.trades == ()


class TestEquity:
    def test_equity_includes_unrealized_pnl_while_positioned(self) -> None:
        result = _run([_flat(60), _m1(61, "1.10100", "1.10150", "1.10100", "1.10120"), _flat(62)])
        mid = result.equity_curve[1]
        assert mid.equity > mid.realized_balance

    def test_insufficient_margin_rejects_the_entry(self) -> None:
        tiny = fixture_sizing_policy().model_copy(update={"initial_balance": Decimal("1")})
        result = simulate(
            definition=_definition(),
            signal_bars=_signal_bars(),
            execution_bars=[_flat(60), _flat(61)],
            contract=EURUSD,
            costs=fixture_cost_policy(),
            sizing=tiny,
            window_start=START + timedelta(minutes=60),
            window_end=START + timedelta(minutes=62),
            signals=[Signal(bar_index=0, direction=Direction.LONG, atr=ATR)],
        )
        assert result.fills == ()
        assert result.rejected_signals[0].reason == "insufficient free margin"

    @pytest.mark.parametrize("volume", [Decimal("0.005"), Decimal("1000")])
    def test_out_of_band_volume_is_rejected_rather_than_rounded(self, volume: Decimal) -> None:
        sizing = fixture_sizing_policy().model_copy(update={"fixed_volume": volume})
        result = simulate(
            definition=_definition(),
            signal_bars=_signal_bars(),
            execution_bars=[_flat(60), _flat(61)],
            contract=EURUSD,
            costs=fixture_cost_policy(),
            sizing=sizing,
            window_start=START + timedelta(minutes=60),
            window_end=START + timedelta(minutes=62),
            signals=[Signal(bar_index=0, direction=Direction.LONG, atr=ATR)],
        )
        assert result.fills == ()
