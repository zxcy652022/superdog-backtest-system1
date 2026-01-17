"""
幣哥雙均線策略 - 正確實現版 v2.0

根據原始策略文檔重新實現，**符合 RULES.md 規範**。

=== 策略職責（符合 §2.1-2.2） ===
- 只產生進場信號
- 通過 ExecutionConfig 提供止損/止盈配置
- 引擎負責所有執行邏輯

=== 原始策略核心邏輯 ===

1. 進場方法（2種）：
   A. 均線密集開倉法：
      - 找到均線密集（6條均線纏繞在一起）
      - K 線在均線上方 → 做多
      - K 線在均線下方 → 做空

   B. 第一次回踩 MA20 不破開倉法：
      - 均線密集突破後
      - 等待價格第一次回踩 MA20
      - 回踩不跌破 → 進場

2. 止損/止盈：通過 ExecutionConfig 配置，引擎統一處理

Version: v2.0 (符合 RULES.md 規範)
Author: DDragon
"""

from dataclasses import dataclass
from enum import Enum
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


class EntryMethod(Enum):
    """進場方式"""

    CLUSTER = "cluster"  # 均線密集開倉法
    PULLBACK_MA20 = "pullback_ma20"  # 第一次回踩 MA20 不破


@dataclass
class ClusterInfo:
    """均線密集資訊"""

    start_idx: int
    end_idx: int
    price_level: float  # 均線密集的價格中心
    is_valid: bool = True


class BiGeCorrectStrategy(BaseStrategy):
    """
    幣哥雙均線策略 - 正確實現版

    符合 RULES.md §2.1-2.2：策略只產生信號，執行邏輯由引擎處理。
    """

    @classmethod
    def get_default_parameters(cls):
        """策略參數 - 只影響信號計算"""
        return {
            # === 均線週期 ===
            "ma_periods": [20, 60, 120],  # MA 和 EMA 共用週期
            # === 均線密集判定 ===
            "cluster_spread_pct": 0.05,  # 5% 以內視為密集
            "min_cluster_bars": 3,  # 最少連續 3 根 K 線
            # === 進場過濾 ===
            "min_rr_ratio": 1.5,  # 最低賠率門檻
            # === 方向 ===
            "allow_short": False,  # 只做多
            # === MA20 回踩 ===
            "ma20_pullback_buffer": 0.005,  # MA20 回踩容許 0.5%
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """執行配置 - 告訴引擎如何處理止損/止盈"""
        return ExecutionConfig(
            stop_config=StopConfig(
                type="simple",
                fixed_stop_pct=0.03,  # 3% 止損
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=0.09,  # 9% 止盈（約 1:3 賠率）
            leverage=7.0,
            fee_rate=0.0005,
        )

    def __init__(self, broker, data, **kwargs):
        """初始化"""
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

        # 趨勢追蹤（用於 MA20 回踩進場）
        self.trend_direction: Optional[str] = None  # "up" or "down"
        self.cluster_breakout_idx: Optional[int] = None
        self.first_pullback_done: bool = False

        # 計算指標
        self._calculate_indicators()

    def _calculate_indicators(self):
        """計算所有技術指標"""
        df = self.data
        periods = self.params["ma_periods"]

        # 計算 6 條均線
        for p in periods:
            df[f"ma{p}"] = df["close"].rolling(p).mean()
            df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()

        # 計算均線中心（6 條均線的平均）
        ma_cols = [f"ma{p}" for p in periods] + [f"ema{p}" for p in periods]
        df["ma_center"] = df[ma_cols].mean(axis=1)

        # 計算均線 spread
        def calc_spread(row):
            values = [row[col] for col in ma_cols if pd.notna(row[col])]
            if len(values) < 6:
                return np.nan
            return (max(values) - min(values)) / min(values)

        df["ma_spread"] = df.apply(calc_spread, axis=1)

    def _is_cluster(self, row) -> bool:
        """判斷當前是否為均線密集"""
        spread = row.get("ma_spread")
        if pd.isna(spread):
            return False
        return spread < self.params["cluster_spread_pct"]

    def _get_price_position(self, row) -> str:
        """判斷 K 線相對於均線密集的位置"""
        close = row["close"]
        ma_center = row["ma_center"]

        if pd.isna(ma_center):
            return "unknown"

        if close > ma_center:
            return "above"
        else:
            return "below"

    def on_bar(self, i: int, row: pd.Series):
        """每根 K 線調用 - 只產生進場信號"""
        # 等待足夠的數據
        if i < self.params["ma_periods"][-1]:
            return

        current_time = row.name
        close = row["close"]
        ma_center = row["ma_center"]
        is_cluster = self._is_cluster(row)

        # === 1. 追蹤均線密集狀態 ===
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
                    cluster = ClusterInfo(
                        start_idx=self.current_cluster_start,
                        end_idx=i - 1,
                        price_level=ma_center if pd.notna(ma_center) else close,
                    )
                    self.cluster_history.append(cluster)

                    position = self._get_price_position(row)
                    if position == "above":
                        self.trend_direction = "up"
                        self.cluster_breakout_idx = i
                        self.first_pullback_done = False
                    elif position == "below":
                        self.trend_direction = "down"
                        self.cluster_breakout_idx = i
                        self.first_pullback_done = False

                self.in_cluster = False
                self.bars_in_cluster = 0

        # === 2. 有持倉時不做任何事（引擎處理止損止盈）===
        if self.broker.has_position:
            return

        # === 3. 檢查進場信號 ===

        # 方法 A: 均線密集開倉法
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

        # 方法 B: 第一次回踩 MA20 不破開倉法
        if (
            self.trend_direction == "up"
            and self.cluster_breakout_idx is not None
            and not self.first_pullback_done
            and i > self.cluster_breakout_idx + 3
        ):
            ma20 = row["ma20"]
            if pd.notna(ma20):
                pullback_zone = ma20 * (1 + self.params["ma20_pullback_buffer"])

                if close <= pullback_zone and close > ma20:
                    self.first_pullback_done = True
                    self.broker.buy_all(close, current_time)
                    return

        elif (
            self.trend_direction == "down"
            and self.params["allow_short"]
            and self.cluster_breakout_idx is not None
            and not self.first_pullback_done
            and i > self.cluster_breakout_idx + 3
        ):
            ma20 = row["ma20"]
            if pd.notna(ma20):
                pullback_zone = ma20 * (1 - self.params["ma20_pullback_buffer"])

                if close >= pullback_zone and close < ma20:
                    self.first_pullback_done = True
                    self.broker.short_all(close, current_time)
                    return
