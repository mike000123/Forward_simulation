from __future__ import annotations

from dataclasses import dataclass

from trading_platform.config import RiskConfig
from trading_platform.strategies.base import Signal


@dataclass
class PortfolioState:
    equity: float
    peak_equity: float
    day_pnl_pct: float


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    allocation_usd: float
    leverage: float


def validate_signal_risk(
    signal: Signal,
    portfolio: PortfolioState,
    risk: RiskConfig,
    requested_leverage: float,
) -> RiskDecision:
    if requested_leverage > risk.max_leverage:
        return RiskDecision(False, f"Requested leverage {requested_leverage} > max {risk.max_leverage}", 0.0, 0.0)

    if signal.stop_loss_pct > risk.hard_stop_loss_pct:
        return RiskDecision(False, "Signal stop-loss exceeds hard stop-loss policy", 0.0, 0.0)

    if signal.take_profit_pct > risk.hard_take_profit_pct:
        return RiskDecision(False, "Signal take-profit exceeds hard take-profit policy", 0.0, 0.0)

    drawdown_pct = max(0.0, (portfolio.peak_equity - portfolio.equity) / max(1e-9, portfolio.peak_equity) * 100)
    if drawdown_pct >= risk.max_drawdown_pct:
        return RiskDecision(False, "Max drawdown breached, trading paused", 0.0, 0.0)

    if portfolio.day_pnl_pct <= -abs(risk.max_daily_loss_pct):
        return RiskDecision(False, "Daily loss limit breached, trading paused", 0.0, 0.0)

    allocation = portfolio.equity * risk.max_capital_per_trade_pct / 100
    return RiskDecision(True, "Approved", allocation, requested_leverage)
