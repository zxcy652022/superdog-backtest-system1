"""
Simple SMA Strategy v0.1

簡單的移動平均線策略，用於測試回測引擎。

策略邏輯：
- 收盤價 > SMA20 且無持倉 → 全倉買入
- 收盤價 < SMA20 且有持倉 → 全倉賣出
"""

import pandas as pd

from backtest.engine import BaseStrategy


class SimpleSMAStrategy(BaseStrategy):
    """簡單 SMA 策略"""

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
        每根 K 線執行一次

        Args:
            i: 當前索引
            row: 當前 K 線數據
        """
        # 前 N 根 K 線 SMA 尚未計算完成，跳過
        if i < self.sma_period - 1:
            return

        current_price = row["close"]
        current_time = row.name  # DataFrame 的 index
        current_sma = self.sma.iloc[i]

        # 策略邏輯
        if pd.notna(current_sma):
            # 做多訊號：價格突破 SMA 向上
            if current_price > current_sma and not self.broker.has_position:
                self.broker.buy_all(price=current_price, time=current_time)

            # 平倉訊號：價格跌破 SMA 向下
            elif current_price < current_sma and self.broker.has_position:
                self.broker.sell_all(price=current_price, time=current_time)
