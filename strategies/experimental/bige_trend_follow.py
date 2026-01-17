"""
幣哥雙均線策略 - 趨勢跟隨版 v2.0

符合 RULES.md 規範：策略只產生信號，引擎處理執行。

設計理念：
- 進場信號：均線密集 + K 線位置
- 追蹤止損：由引擎的 StopManager 處理
- 讓利潤奔跑，截斷虧損

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


@dataclass
class ClusterInfo:
    """均線密集資訊"""

    start_idx: int
    end_idx: int
    price_level: float
    direction: str = "unknown"  # "up" or "down"


class BiGeTrendFollowStrategy(BaseStrategy):
    """
    幣哥雙均線策略 - 趨勢跟隨版

    符合 RULES.md：策略只產生進場信號。
    追蹤止損由引擎的 StopManager 處理。
    """

    @classmethod
    def get_default_parameters(cls):
        return {
            # 均線週期
            "ma_periods": [20, 60, 120],
            # 均線密集判定
            "cluster_spread_pct": 0.05,  # 5%
            "min_cluster_bars": 3,
            # 最低賠率門檻
            "min_rr_ratio": 1.5,
            # 方向
            "allow_short": False,
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """執行配置 - 追蹤止損"""
        return ExecutionConfig(
            stop_config=StopConfig(
                type="confirmed",  # 確認式止損
                confirm_bars=5,
                trailing=True,  # 啟用追蹤
                trailing_ma_key="ma20",  # 追蹤 MA20
                trailing_buffer=0.01,  # 1% 緩衝
                fixed_stop_pct=0.05,  # 最大 5% 止損
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=None,  # 不設固定止盈
            leverage=7.0,
            fee_rate=0.0005,
        )

    def __init__(self, broker, data, **kwargs):
        super().__init__(broker, data)

        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        # 狀態追蹤
        self.cluster_history: List[ClusterInfo] = []
        self.current_cluster_start: Optional[int] = None
        self.in_cluster: bool = False
        self.bars_in_cluster: int = 0

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
        high = row["high"]
        low = row["low"]
        ma_center = row["ma_center"]
        is_cluster = self._is_cluster(row)

        # 更新均線密集狀態
        if is_cluster:
            if not self.in_cluster:
                self.in_cluster = True
                self.current_cluster_start = i
                self.bars_in_cluster = 1
            else:
                self.bars_in_cluster += 1
        else:
            if self.in_cluster:
                if self.bars_in_cluster >= self.params["min_cluster_bars"]:
                    position = self._get_price_position(row)
                    cluster = ClusterInfo(
                        start_idx=self.current_cluster_start,
                        end_idx=i - 1,
                        price_level=ma_center if pd.notna(ma_center) else close,
                        direction="up" if position == "above" else "down",
                    )
                    self.cluster_history.append(cluster)

                self.in_cluster = False
                self.bars_in_cluster = 0

        # 有持倉時不做任何事（引擎處理止損追蹤）
        if self.broker.has_position:
            return

        # 檢查進場信號
        if is_cluster and self.bars_in_cluster >= self.params["min_cluster_bars"]:
            position = self._get_price_position(row)

            if position == "above":
                # K 線在均線上方 → 做多
                self.broker.buy_all(close, current_time)
                return

            elif position == "below" and self.params["allow_short"]:
                # K 線在均線下方 → 做空
                self.broker.short_all(close, current_time)
                return
