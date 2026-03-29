from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from .base import Signal


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    return 100 - (100 / (1 + rs))


@dataclass
class RsiMeanReversionStrategy:
    rsi_period: int = 14
    rsi_buy_threshold: float = 30.0
    rsi_sell_threshold: float = 70.0
    take_profit_pct: float = 3.0
    stop_loss_pct: float = 2.0
    name: str = "RSI Mean Reversion"

    def parameters(self) -> Dict[str, float]:
        return {
            "rsi_period": self.rsi_period,
            "rsi_buy_threshold": self.rsi_buy_threshold,
            "rsi_sell_threshold": self.rsi_sell_threshold,
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
        }

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> list[Signal]:
        if data.empty:
            return []

        frame = data.copy()
        frame["rsi"] = compute_rsi(frame["close"], self.rsi_period)
        signals: list[Signal] = []

        for _, row in frame.dropna(subset=["rsi"]).iterrows():
            rsi = float(row["rsi"])
            if rsi <= self.rsi_buy_threshold:
                signals.append(
                    Signal(
                        timestamp=row["date"],
                        symbol=symbol,
                        side="buy",
                        confidence=min(1.0, (self.rsi_buy_threshold - rsi) / max(1, self.rsi_buy_threshold)),
                        reason=f"RSI {rsi:.2f} <= buy threshold {self.rsi_buy_threshold}",
                        take_profit_pct=self.take_profit_pct,
                        stop_loss_pct=self.stop_loss_pct,
                    )
                )
            elif rsi >= self.rsi_sell_threshold:
                signals.append(
                    Signal(
                        timestamp=row["date"],
                        symbol=symbol,
                        side="sell",
                        confidence=min(1.0, (rsi - self.rsi_sell_threshold) / max(1, 100 - self.rsi_sell_threshold)),
                        reason=f"RSI {rsi:.2f} >= sell threshold {self.rsi_sell_threshold}",
                        take_profit_pct=self.take_profit_pct,
                        stop_loss_pct=self.stop_loss_pct,
                    )
                )

        return signals
