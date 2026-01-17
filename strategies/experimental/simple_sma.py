"""
Simple SMA Strategy v0.2

簡單的移動平均線策略，用於測試回測引擎。

符合 RULES.md 規範：策略只產生信號。

策略邏輯：
- 收盤價 > SMA20 → 做多信號
- 做多後由引擎處理止損止盈

Version: v0.2 (符合規範版)
"""

import pandas as pd

from backtest.engine import BaseStrategy
from backtest.strategy_config import (
    AddPositionConfig,
    ExecutionConfig,
    PositionSizingConfig,
    StopConfig,
)


class SimpleSMAStrategy(BaseStrategy):
    """簡單 SMA 策略 - 符合規範"""

    @classmethod
    def get_default_parameters(cls):
        return {
            "sma_period": 20,
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """執行配置"""
        return ExecutionConfig(
            stop_config=StopConfig(
                type="simple",
                fixed_stop_pct=0.05,  # 5% 止損
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=0.10,  # 10% 止盈
            leverage=1.0,
            fee_rate=0.0005,
        )

    def __init__(self, broker, data, sma_period: int = 20):
        """
        初始化策略

        Args:
            broker: 模擬交易所
            data: OHLCV 數據
            sma_period: SMA 週期（預設 20）
        """
        super().__init__(broker, data)
        self.sma_period = sma_period

        # 預先計算 SMA
        self.sma = self.data["close"].rolling(window=self.sma_period).mean()

    def on_bar(self, i: int, row: pd.Series):
        """
        每根 K 線執行一次 - 只產生進場信號

        Args:
            i: 當前索引
            row: 當前 K 線數據
        """
        # 前 N 根 K 線 SMA 尚未計算完成，跳過
        if i < self.sma_period - 1:
            return

        current_price = row["close"]
        current_time = row.name
        current_sma = self.sma.iloc[i]

        # 有持倉時不做任何事（引擎處理止損止盈）
        if self.broker.has_position:
            return

        # 進場信號：價格突破 SMA 向上
        if pd.notna(current_sma) and current_price > current_sma:
            self.broker.buy_all(price=current_price, time=current_time)
