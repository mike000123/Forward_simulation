from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from trading_platform.config import AppConfig
from trading_platform.execution.router import OrderRouter
from trading_platform.risk.controls import PortfolioState, validate_signal_risk
from trading_platform.state.storage import append_records, ensure_storage, log_event, save_config_snapshot
from trading_platform.strategies.base import Signal
from trading_platform.strategies.rsi_strategy import RsiMeanReversionStrategy


@dataclass
class EngineResult:
    signals: list[Signal]
    orders: list[dict]
    blocked: list[dict]


class TradingEngine:
    def __init__(self, config: AppConfig, storage_root: str = "storage") -> None:
        self.config = config
        self.storage = ensure_storage(storage_root)

    def _build_strategy(self):
        if self.config.strategy.name.lower().startswith("rsi"):
            return RsiMeanReversionStrategy(**self.config.strategy.params)
        raise ValueError(f"Unsupported strategy: {self.config.strategy.name}")

    def run(self, data: pd.DataFrame, live_armed: bool = False) -> EngineResult:
        if data.empty:
            return EngineResult([], [], [])

        strategy = self._build_strategy()
        router = OrderRouter(mode=self.config.mode, live_armed=live_armed)
        latest_price = float(data.iloc[-1]["close"])
        signals = strategy.generate_signals(data, symbol=self.config.ticker)

        portfolio = PortfolioState(
            equity=self.config.risk.starting_capital,
            peak_equity=self.config.risk.starting_capital,
            day_pnl_pct=0.0,
        )

        order_records: list[dict] = []
        blocked_records: list[dict] = []

        for signal in signals[-25:]:
            risk = validate_signal_risk(signal, portfolio, self.config.risk, requested_leverage=1.0)
            order_result = router.route(signal, latest_price=latest_price, risk=risk)
            if order_result.accepted:
                record = {
                    "timestamp": signal.timestamp,
                    "symbol": signal.symbol,
                    "side": signal.side,
                    "order_id": order_result.order_id,
                    "mode": order_result.mode,
                    "reason": signal.reason,
                    "details": order_result.details,
                }
                order_records.append(record)
                log_event(self.storage, "order_submitted", record)
            else:
                blocked = {
                    "timestamp": signal.timestamp,
                    "symbol": signal.symbol,
                    "side": signal.side,
                    "mode": order_result.mode,
                    "risk_reason": order_result.details.get("error", "blocked"),
                }
                blocked_records.append(blocked)
                log_event(self.storage, "order_blocked", blocked)

        append_records(
            self.storage.signals_file,
            [
                {
                    "timestamp": s.timestamp,
                    "symbol": s.symbol,
                    "side": s.side,
                    "confidence": s.confidence,
                    "reason": s.reason,
                    "take_profit_pct": s.take_profit_pct,
                    "stop_loss_pct": s.stop_loss_pct,
                }
                for s in signals
            ],
        )
        append_records(self.storage.orders_file, order_records)
        save_config_snapshot(self.storage, "last_run", asdict(self.config))

        return EngineResult(signals=signals, orders=order_records, blocked=blocked_records)
              
