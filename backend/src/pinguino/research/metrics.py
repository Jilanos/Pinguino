"""Metrics computed from a simulated window.

Ratios that are mathematically undefined stay ``None`` with a stated reason; they never
become infinity, and a window with no trade is reported as such rather than as a zero.
Drawdown is measured on M1-close and fill-time equity, which is not a tick-level maximum.
"""

from __future__ import annotations

from decimal import Decimal

from pinguino.domain.enums import WindowKind
from pinguino.domain.results import WindowMetrics
from pinguino.engine.simulator import SimulationResult
from pinguino.research.windows import ResolvedWindow


def window_metrics(
    result: SimulationResult,
    window: ResolvedWindow,
    *,
    initial_balance: Decimal,
    units_per_lot: Decimal,
) -> WindowMetrics:
    trades = result.trades
    reasons: list[str] = []

    net_return = (
        (result.final_equity - initial_balance) / initial_balance
        if result.equity_curve
        else Decimal(0)
    )
    if not result.equity_curve:
        reasons.append("no equity observation was produced in this window")

    wins = [trade for trade in trades if trade.net_pnl > 0]
    losses = [trade for trade in trades if trade.net_pnl < 0]
    gross_profit = sum((trade.net_pnl for trade in wins), Decimal(0))
    gross_loss = -sum((trade.net_pnl for trade in losses), Decimal(0))

    if not trades:
        win_rate: Decimal | None = None
        profit_factor: Decimal | None = None
        reasons.append("no trade was taken in this window")
    else:
        win_rate = Decimal(len(wins)) / Decimal(len(trades))
        if gross_loss == 0:
            profit_factor = None
            reasons.append("profit factor is undefined without a losing trade")
        else:
            profit_factor = gross_profit / gross_loss

    span = Decimal(int((window.end - window.start).total_seconds()))
    exposure_seconds = sum(
        (Decimal(int((trade.closed_at - trade.opened_at).total_seconds())) for trade in trades),
        Decimal(0),
    )
    exposure = min(exposure_seconds / span, Decimal(1)) if span > 0 else Decimal(0)

    return WindowMetrics(
        window=window.kind if window.kind is not WindowKind.WARMUP else WindowKind.TRAINING,
        start=window.start,
        end=window.end,
        net_return=net_return,
        max_drawdown=max_drawdown(result),
        trade_count=len(trades),
        win_rate=win_rate,
        profit_factor=profit_factor,
        exposure_fraction=exposure,
        turnover=sum(
            (trade.entry_price * trade.volume * units_per_lot for trade in trades),
            Decimal(0),
        ),
        commission_cost=sum((trade.commission for trade in trades), Decimal(0)),
        spread_cost=sum((trade.spread_cost for trade in trades), Decimal(0)),
        swap_cost=sum((trade.swap for trade in trades), Decimal(0)),
        slippage_cost=sum((trade.slippage_cost for trade in trades), Decimal(0)),
        ambiguity_count=result.ambiguity_count,
        undefined_reasons=tuple(reasons),
    )


def max_drawdown(result: SimulationResult) -> Decimal:
    """Largest peak-to-trough fall of observed equity, as a fraction of the peak."""
    peak: Decimal | None = None
    worst = Decimal(0)
    for observation in result.equity_curve:
        if peak is None or observation.equity > peak:
            peak = observation.equity
        if peak and peak > 0:
            fall = (peak - observation.equity) / peak
            worst = max(worst, fall)
    return worst
