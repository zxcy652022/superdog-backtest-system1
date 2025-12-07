"""
Simple SMA Strategy v2.0

基於 Strategy API v2.0 重構的簡單移動平均線策略

策略邏輯：
- 短期均線 > 長期均線 → 買入信號
- 短期均線 < 長期均線 → 賣出信號

Version: v2.0
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from typing import Dict, List, Any
import pandas as pd
from strategies.api_v2 import (
    BaseStrategy,
    ParameterSpec,
    DataRequirement,
    DataSource,
    int_param
)


class SimpleSMAStrategyV2(BaseStrategy):
    """簡單 SMA 策略 - Strategy API v2.0 版本

    使用雙均線交叉系統產生交易信號

    參數：
        short_window: 短期均線週期（預設 10）
        long_window: 長期均線週期（預設 20）

    信號邏輯：
        - signal = 1: 短均線 > 長均線（做多）
        - signal = -1: 短均線 < 長均線（做空/平倉）
        - signal = 0: 其他情況（持有）
    """

    def __init__(self):
        """初始化策略"""
        super().__init__()
        self.name = "SimpleSMA"
        self.version = "2.0"
        self.author = "SuperDog Team"
        self.description = "簡單均線交叉策略 - 基於雙SMA的趨勢跟隨系統"

    def get_parameters(self) -> Dict[str, ParameterSpec]:
        """返回策略參數規格

        Returns:
            參數規格字典：
                - short_window: 短期均線週期 (1-50, 預設 10)
                - long_window: 長期均線週期 (5-200, 預設 20)
        """
        return {
            'short_window': int_param(
                default=10,
                description="短期均線週期",
                min_val=1,
                max_val=50
            ),
            'long_window': int_param(
                default=20,
                description="長期均線週期",
                min_val=5,
                max_val=200
            )
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        """聲明數據需求

        Returns:
            數據需求列表：
                - OHLCV: 需要至少 200 根 K 線（確保長均線可計算）
        """
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=200,  # 確保長均線有足夠數據
                required=True
            )
        ]

    def compute_signals(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> pd.Series:
        """計算交易信號

        Args:
            data: 包含 'ohlcv' 的數據字典
            params: 包含 'short_window' 和 'long_window' 的參數字典

        Returns:
            pd.Series: 交易信號序列 (1=買入, -1=賣出, 0=持有)

        Raises:
            ValueError: 數據不足或參數無效
        """
        # 驗證數據
        if 'ohlcv' not in data:
            raise ValueError("Missing required data source: ohlcv")

        ohlcv = data['ohlcv']
        if len(ohlcv) < params['long_window']:
            raise ValueError(
                f"Insufficient data: need at least {params['long_window']} bars, "
                f"got {len(ohlcv)}"
            )

        # 計算均線
        close_prices = ohlcv['close']
        short_ma = close_prices.rolling(window=params['short_window']).mean()
        long_ma = close_prices.rolling(window=params['long_window']).mean()

        # 生成信號
        signals = pd.Series(0, index=close_prices.index)

        # 買入信號：短均線突破長均線向上
        signals[short_ma > long_ma] = 1

        # 賣出信號：短均線跌破長均線向下
        signals[short_ma < long_ma] = -1

        return signals


# 為了向後兼容，保留舊版類名的別名
SimpleSMA = SimpleSMAStrategyV2
