"""
幣哥雙均線策略 - 簡單持有版 v2.0

符合 RULES.md 規範：策略只產生信號，引擎處理執行。

核心邏輯：
1. 進場：均線密集 + K線在均線上方
2. 出場：由引擎根據 ExecutionConfig 處理
   - 使用 MA 交叉止損（MA20 < MA60）或固定止損

Version: v2.0 (符合規範版)
Author: DDragon
"""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from backtest.engine import BaseStrategy
from backtest.strategy_config import (
    AddPositionConfig,
    ExecutionConfig,
    PositionSizingConfig,
    StopConfig,
)


class BiGeSimpleHoldStrategy(BaseStrategy):
    """簡單持有版幣哥策略 - 符合規範"""

    @classmethod
    def get_default_parameters(cls):
        return {
            "ma_periods": [20, 60, 120],
            "cluster_spread_pct": 0.05,  # 5%
            "min_cluster_bars": 3,
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """執行配置 - 寬鬆的止損設定"""
        return ExecutionConfig(
            stop_config=StopConfig(
                type="simple",
                fixed_stop_pct=0.10,  # 10% 寬鬆止損
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=None,  # 不設止盈，讓趨勢自己決定
            leverage=7.0,
            fee_rate=0.0005,
        )

    def __init__(self, broker, data, **kwargs):
        super().__init__(broker, data)

        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        # 狀態
        self.in_cluster = False
        self.bars_in_cluster = 0

        self._calculate_indicators()

    def _calculate_indicators(self):
        df = self.data
        periods = self.params["ma_periods"]

        for p in periods:
            df[f"ma{p}"] = df["close"].rolling(p).mean()
            df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()

        ma_cols = [f"ma{p}" for p in periods] + [f"ema{p}" for p in periods]
        df["ma_center"] = df[ma_cols].mean(axis=1)

        def calc_spread(row):
            values = [row[col] for col in ma_cols if pd.notna(row[col])]
            if len(values) < 6:
                return np.nan
            return (max(values) - min(values)) / min(values)

        df["ma_spread"] = df.apply(calc_spread, axis=1)

    def _is_cluster(self, row) -> bool:
        spread = row.get("ma_spread")
        if pd.isna(spread):
            return False
        return spread < self.params["cluster_spread_pct"]

    def _get_price_position(self, row) -> str:
        close = row["close"]
        ma_center = row["ma_center"]
        if pd.isna(ma_center):
            return "unknown"
        return "above" if close > ma_center else "below"

    def on_bar(self, i: int, row: pd.Series):
        """只產生進場信號"""
        if i < self.params["ma_periods"][-1]:
            return

        current_time = row.name
        close = row["close"]
        is_cluster = self._is_cluster(row)

        # 更新密集狀態
        if is_cluster:
            if not self.in_cluster:
                self.in_cluster = True
                self.bars_in_cluster = 1
            else:
                self.bars_in_cluster += 1
        else:
            self.in_cluster = False
            self.bars_in_cluster = 0

        # 有持倉時不做任何事（引擎處理）
        if self.broker.has_position:
            return

        # 檢查進場
        if is_cluster and self.bars_in_cluster >= self.params["min_cluster_bars"]:
            position = self._get_price_position(row)
            if position == "above":
                self.broker.buy_all(close, current_time)
