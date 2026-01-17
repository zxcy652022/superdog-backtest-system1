"""
幣哥策略 - 純進場邏輯測試版

目的：驗證進場邏輯是否有效，是否有盈利空間

進場邏輯：
1. 均線密集發生（6 條均線收斂）
2. 確認密集前的價格走勢：
   - 做多：價格向上突破，站在均線密集區之上
   - 做空：價格向下跌破，在均線密集區之下
3. 止損：密集前的支撐/壓力位

測試方式：
- 1x 槓桿（無槓桿）
- 不設固定止盈
- 出場條件：反向信號 或 固定持有天數

Version: v1.0 (進場測試版)
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


@dataclass
class ClusterEvent:
    """均線密集事件"""

    bar_idx: int  # 密集開始的 K 線索引
    end_idx: int  # 密集結束的 K 線索引
    center_price: float  # 密集區中心價格
    pre_trend: str  # 密集前趨勢: "up", "down", "none"
    support: Optional[float]  # 密集前的支撐位
    resistance: Optional[float]  # 密集前的壓力位


class BiGeEntryTestStrategy(BaseStrategy):
    """
    幣哥進場邏輯測試策略

    核心：驗證均線密集 + 突破方向的進場邏輯是否有效
    """

    @classmethod
    def get_default_parameters(cls):
        return {
            # 均線週期
            "ma_periods": [20, 60, 120],
            # 均線密集判定
            "cluster_spread_pct": 0.03,  # 3% 視為密集
            "min_cluster_bars": 3,  # 至少連續 3 根
            # 趨勢判定（密集前）
            "trend_lookback": 20,  # 往前看 20 根判斷趨勢
            "trend_threshold": 0.03,  # 3% 漲跌幅視為有趨勢
            # 方向
            "allow_long": True,
            "allow_short": True,
            # 出場（測試用）
            "max_hold_bars": 50,  # 最多持有 50 根 K 線
            "exit_on_reverse_signal": True,  # 反向信號出場
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """1x 槓桿，寬鬆止損（測試用）"""
        return ExecutionConfig(
            stop_config=StopConfig(
                type="simple",
                fixed_stop_pct=0.10,  # 10% 寬鬆止損（讓交易有空間發展）
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=None,  # 不設止盈
            leverage=1.0,  # 無槓桿
            fee_rate=0.0005,
        )

    def __init__(self, broker, data, **kwargs):
        super().__init__(broker, data)

        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        # 狀態追蹤
        self.in_cluster = False
        self.cluster_start_idx: Optional[int] = None
        self.bars_in_cluster = 0
        self.cluster_history: List[ClusterEvent] = []

        # 持倉追蹤
        self.entry_bar: Optional[int] = None
        self.entry_direction: Optional[str] = None

        # 計算指標
        self._calculate_indicators()

    def _calculate_indicators(self):
        """計算技術指標"""
        df = self.data
        periods = self.params["ma_periods"]

        # 6 條均線
        for p in periods:
            df[f"ma{p}"] = df["close"].rolling(p).mean()
            df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()

        # 均線中心
        ma_cols = [f"ma{p}" for p in periods] + [f"ema{p}" for p in periods]
        df["ma_center"] = df[ma_cols].mean(axis=1)

        # 均線 spread（判斷是否密集）
        def calc_spread(row):
            values = [row[col] for col in ma_cols if pd.notna(row[col])]
            if len(values) < 6:
                return np.nan
            return (max(values) - min(values)) / min(values)

        df["ma_spread"] = df.apply(calc_spread, axis=1)

        # 支撐壓力（用 swing high/low）
        lookback = self.params["trend_lookback"]
        df["swing_low"] = df["low"].rolling(lookback).min()
        df["swing_high"] = df["high"].rolling(lookback).max()

    def _is_cluster(self, row) -> bool:
        """判斷是否均線密集"""
        spread = row.get("ma_spread")
        if pd.isna(spread):
            return False
        return spread < self.params["cluster_spread_pct"]

    def _get_pre_trend(self, current_idx: int) -> str:
        """
        判斷密集發生前的趨勢

        Returns:
            "up": 向上突破
            "down": 向下跌破
            "none": 無明顯趨勢
        """
        lookback = self.params["trend_lookback"]
        threshold = self.params["trend_threshold"]

        if current_idx < lookback:
            return "none"

        # 密集前的價格區間
        start_idx = max(0, current_idx - lookback)
        start_price = self.data.iloc[start_idx]["close"]
        end_price = self.data.iloc[current_idx]["close"]

        change_pct = (end_price - start_price) / start_price

        if change_pct > threshold:
            return "up"
        elif change_pct < -threshold:
            return "down"
        else:
            return "none"

    def _get_price_position(self, row) -> str:
        """價格相對於均線中心的位置"""
        close = row["close"]
        ma_center = row["ma_center"]
        if pd.isna(ma_center):
            return "unknown"
        return "above" if close > ma_center else "below"

    def _record_cluster(self, end_idx: int, row: pd.Series):
        """記錄一個完整的均線密集事件"""
        pre_trend = self._get_pre_trend(self.cluster_start_idx)

        cluster = ClusterEvent(
            bar_idx=self.cluster_start_idx,
            end_idx=end_idx,
            center_price=row["ma_center"] if pd.notna(row["ma_center"]) else row["close"],
            pre_trend=pre_trend,
            support=row.get("swing_low"),
            resistance=row.get("swing_high"),
        )
        self.cluster_history.append(cluster)
        return cluster

    def on_bar(self, i: int, row: pd.Series):
        """每根 K 線調用"""
        if i < self.params["ma_periods"][-1]:
            return

        current_time = row.name
        close = row["close"]
        is_cluster = self._is_cluster(row)

        # === 1. 追蹤均線密集狀態 ===
        cluster_just_ended = False
        current_cluster: Optional[ClusterEvent] = None

        if is_cluster:
            if not self.in_cluster:
                # 進入新密集
                self.in_cluster = True
                self.cluster_start_idx = i
                self.bars_in_cluster = 1
            else:
                self.bars_in_cluster += 1
        else:
            if self.in_cluster:
                # 密集結束
                if self.bars_in_cluster >= self.params["min_cluster_bars"]:
                    current_cluster = self._record_cluster(i - 1, row)
                    cluster_just_ended = True

                self.in_cluster = False
                self.bars_in_cluster = 0
                self.cluster_start_idx = None

        # === 2. 有持倉：檢查出場條件 ===
        if self.broker.has_position:
            should_exit = False

            # 條件1：持有超過最大天數
            if self.entry_bar is not None:
                bars_held = i - self.entry_bar
                if bars_held >= self.params["max_hold_bars"]:
                    should_exit = True

            # 條件2：反向信號
            if self.params["exit_on_reverse_signal"] and cluster_just_ended:
                if current_cluster:
                    price_pos = self._get_price_position(row)

                    # 持多單，出現做空信號
                    if (
                        self.entry_direction == "long"
                        and current_cluster.pre_trend == "down"
                        and price_pos == "below"
                    ):
                        should_exit = True

                    # 持空單，出現做多信號
                    if (
                        self.entry_direction == "short"
                        and current_cluster.pre_trend == "up"
                        and price_pos == "above"
                    ):
                        should_exit = True

            if should_exit:
                # sell_all 同時處理平多和平空
                self.broker.sell_all(close, current_time)
                self.entry_bar = None
                self.entry_direction = None

            return  # 有持倉就不進場

        # === 3. 檢查進場條件 ===
        if cluster_just_ended and current_cluster:
            price_pos = self._get_price_position(row)

            # 做多條件：
            # - 密集前趨勢向上（突破壓力）
            # - 價格站在均線密集區之上
            if (
                self.params["allow_long"]
                and current_cluster.pre_trend == "up"
                and price_pos == "above"
            ):
                self.broker.buy_all(close, current_time)
                self.entry_bar = i
                self.entry_direction = "long"
                return

            # 做空條件：
            # - 密集前趨勢向下（跌破支撐）
            # - 價格在均線密集區之下
            if (
                self.params["allow_short"]
                and current_cluster.pre_trend == "down"
                and price_pos == "below"
            ):
                self.broker.short_all(close, current_time)
                self.entry_bar = i
                self.entry_direction = "short"
                return
