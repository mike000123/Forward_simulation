from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class Mode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


@dataclass
class StrategyConfig:
    name: str = "RSI Mean Reversion"
    params: Dict[str, Any] = field(
        default_factory=lambda: {
            "rsi_period": 14,
            "rsi_buy_threshold": 30.0,
            "rsi_sell_threshold": 70.0,
            "take_profit_pct": 3.0,
            "stop_loss_pct": 2.0,
        }
    )


@dataclass
class RiskConfig:
    starting_capital: float = 10_000.0
    max_capital_per_trade_pct: float = 20.0
    max_daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 20.0
    max_leverage: float = 5.0
    hard_stop_loss_pct: float = 6.0
    hard_take_profit_pct: float = 20.0


@dataclass
class AppConfig:
    mode: Mode = Mode.PAPER
    ticker: str = "AAPL"
    interval: str = "1h"
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    theme: str = "Dark Pro"
    require_live_confirmation: bool = True
