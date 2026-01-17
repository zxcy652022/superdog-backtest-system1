"""
MACD 短線策略 v2.0 - BaseStrategy 兼容版

基於原始 macd_scalping.py，重構為符合 BaseStrategy 接口。
可以使用統一的 run_backtest 引擎執行回測。

特點:
- 基於 MACD 黃金/死亡交叉信號
- 固定止損止盈 (不依賴信號出場)
- 適合 15 分鐘時間框架

Version: v2.0
"""

from typing import Optional

import numpy as np
import pandas as pd

from backtest.engine import BaseStrategy
from backtest.strategy_config import (
    AddPositionConfig,
    ExecutionConfig,
    PositionSizingConfig,
    StopConfig,
)


class MACDScalpingStrategyV2(BaseStrategy):
    """MACD 短線策略 - BaseStrategy 兼容版"""

    @classmethod
    def get_default_parameters(cls):
        return {
            # MACD 參數
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            # 止損止盈
            "stop_loss_pct": 0.008,  # 0.8%
            "take_profit_pct": 0.024,  # 2.4% (1:3 風報比)
            # 方向
            "allow_short": True,
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """提供執行配置"""
        params = cls.get_default_parameters()
        return ExecutionConfig(
            stop_config=StopConfig(
                type="simple",
                fixed_stop_pct=params["stop_loss_pct"],
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=params["take_profit_pct"],
            leverage=20.0,  # 推薦 20x
            fee_rate=0.0004,
        )

    def __init__(self, broker, data, **kwargs):
        super().__init__(broker, data)

        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        self._calculate_indicators()

    def _calculate_indicators(self):
        """計算 MACD 指標"""
        df = self.data
        close = df["close"]

        fast = self.params["fast_period"]
        slow = self.params["slow_period"]
        signal = self.params["signal_period"]

        # EMA 計算
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()

        # MACD 線 = 快 EMA - 慢 EMA
        df["macd"] = ema_fast - ema_slow

        # 信號線 = MACD 的 EMA
        df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()

        # MACD 柱狀圖
        df["macd_hist"] = df["macd"] - df["macd_signal"]

    def _check_entry_signal(self, row, prev_row) -> Optional[str]:
        """檢查進場信號

        Returns:
            "long", "short", 或 None
        """
        macd = row.get("macd")
        signal = row.get("macd_signal")
        prev_macd = prev_row.get("macd")
        prev_signal = prev_row.get("macd_signal")

        if pd.isna(macd) or pd.isna(signal) or pd.isna(prev_macd) or pd.isna(prev_signal):
            return None

        above_signal = macd > signal
        prev_below_signal = prev_macd < prev_signal

        # 黃金交叉: 前一根在下，當前在上 → 做多
        if above_signal and prev_below_signal:
            return "long"

        below_signal = macd < signal
        prev_above_signal = prev_macd > prev_signal

        # 死亡交叉: 前一根在上，當前在下 → 做空
        if below_signal and prev_above_signal and self.params["allow_short"]:
            return "short"

        return None

    def on_bar(self, i: int, row: pd.Series):
        if i < self.params["slow_period"] + self.params["signal_period"]:
            return

        current_time = row.name
        close = row["close"]

        # 有持倉時不進場（止損止盈由引擎處理）
        if self.broker.has_position:
            return

        # 檢查進場信號
        prev_row = self.data.iloc[i - 1]
        signal = self._check_entry_signal(row, prev_row)

        if signal == "long":
            self.broker.buy_all(close, current_time)
        elif signal == "short":
            self.broker.short_all(close, current_time)


# 推薦配置常數（從原版繼承）
RECOMMENDED_CONFIG = {
    "timeframe": "15m",
    "fast_period": 12,
    "slow_period": 26,
    "signal_period": 9,
    "stop_loss_pct": 0.008,  # 0.8%
    "take_profit_pct": 0.024,  # 2.4%
    "leverage": 20,
}

# 適合的幣種
RECOMMENDED_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LTCUSDT",
    "OPUSDT",
    "SOLUSDT",
    "XRPUSDT",
]
