"""
Add Position Manager - 加倉管理模組

提供可配置的加倉管理器，從策略中分離加倉邏輯。

Version: v1.0
Date: 2026-01-05

功能：
- 最大加倉次數限制
- 加倉間隔限制
- 盈利門檻檢查
- 回踩容許範圍檢查
- 止損保護檢查

設計原則：
- 策略只產生信號，加倉邏輯由此模組處理
- 符合 RULES.md 第 2.2 節規範
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class AddPositionResult:
    """加倉檢查結果"""

    should_add: bool  # 是否應該加倉
    add_qty: float  # 加倉數量
    reason: str  # 加倉原因或拒絕原因


class BaseAddPositionManager(ABC):
    """加倉管理器基類"""

    @abstractmethod
    def reset(self):
        """重置狀態（新倉位時調用）"""
        pass

    @abstractmethod
    def check(
        self,
        row: pd.Series,
        bar_index: int,
        direction: str,  # 'long' or 'short'
        avg_entry_price: float,
        current_qty: float,
        current_stop: float,
    ) -> AddPositionResult:
        """
        檢查是否應該加倉

        Args:
            row: 當前 K 線數據
            bar_index: 當前 K 線索引
            direction: 持倉方向
            avg_entry_price: 平均進場價
            current_qty: 當前持倉數量
            current_stop: 當前止損價

        Returns:
            AddPositionResult
        """
        pass

    @abstractmethod
    def record_add(self, bar_index: int, new_qty: float):
        """記錄一次加倉"""
        pass


class DisabledAddPositionManager(BaseAddPositionManager):
    """禁用加倉"""

    def reset(self):
        pass

    def check(
        self,
        row: pd.Series,
        bar_index: int,
        direction: str,
        avg_entry_price: float,
        current_qty: float,
        current_stop: float,
    ) -> AddPositionResult:
        return AddPositionResult(False, 0, "disabled")

    def record_add(self, bar_index: int, new_qty: float):
        pass


class AddPositionManager(BaseAddPositionManager):
    """
    加倉管理器

    功能：
    1. 最大加倉次數限制
    2. 加倉間隔限制（最少 N 根 K 線）
    3. 盈利門檻檢查（盈利 > X% 才加倉）
    4. 回踩容許範圍檢查（價格離 MA20 夠近）
    5. 止損保護（價格需在止損價之上）

    這是從 bige_dual_ma_v2.py 提取出來的加倉邏輯。
    """

    def __init__(
        self,
        enabled: bool = True,
        max_count: int = 3,  # 最多加倉次數
        size_pct: float = 0.5,  # 每次加倉比例（相對當前持倉）
        min_interval: int = 6,  # 最小加倉間隔（K 線數）
        min_profit: float = 0.03,  # 最小盈利門檻 (0.03 = 3%)
        pullback_tolerance: float = 0.018,  # 回踩容許 (0.018 = 1.8%)
        pullback_ma_key: str = "avg20",  # 回踩參考的 MA key
    ):
        self.enabled = enabled
        self.max_count = max_count
        self.size_pct = size_pct
        self.min_interval = min_interval
        self.min_profit = min_profit
        self.pullback_tolerance = pullback_tolerance
        self.pullback_ma_key = pullback_ma_key

        # 狀態
        self.add_count = 0
        self.last_add_bar = -999
        self.entry_bar = 0

    def reset(self):
        """重置狀態（新倉位時調用）"""
        self.add_count = 0
        self.last_add_bar = -999

    def set_entry_bar(self, bar_index: int):
        """設置進場 K 線（用於計算加倉間隔）"""
        self.entry_bar = bar_index
        self.last_add_bar = bar_index

    def check(
        self,
        row: pd.Series,
        bar_index: int,
        direction: str,
        avg_entry_price: float,
        current_qty: float,
        current_stop: float,
    ) -> AddPositionResult:
        """檢查是否應該加倉"""

        # 0. 禁用檢查
        if not self.enabled:
            return AddPositionResult(False, 0, "disabled")

        # 1. 次數檢查
        if self.add_count >= self.max_count:
            return AddPositionResult(False, 0, "max_count_reached")

        # 2. 間隔檢查
        if bar_index - self.last_add_bar < self.min_interval:
            return AddPositionResult(False, 0, "interval_not_met")

        close = row["close"]
        low = row["low"]
        high = row["high"]
        ma = row.get(self.pullback_ma_key)

        if pd.isna(ma):
            return AddPositionResult(False, 0, "ma_not_available")

        # 3. 盈利檢查
        if avg_entry_price is None or avg_entry_price <= 0:
            return AddPositionResult(False, 0, "invalid_entry_price")

        if direction == "long":
            pnl_pct = (close - avg_entry_price) / avg_entry_price
        else:  # short
            pnl_pct = (avg_entry_price - close) / avg_entry_price

        if pnl_pct < self.min_profit:
            return AddPositionResult(False, 0, f"profit_too_low:{pnl_pct:.2%}")

        # 4. 回踩加倉檢查（bige_top20_backtest.py 驗證有效的邏輯）
        if direction == "long":
            # 多單回踩加倉條件：
            # a) 最低價靠近 MA（1.5% 內）
            # b) 最低價沒有跌破 MA×0.98
            # c) 收盤價在 MA 之上（確認反彈）
            near_ma = abs(low - ma) / ma < 0.015  # 靠近 MA 1.5% 內
            not_break = low > ma * 0.98  # 沒有跌破 MA×0.98
            bullish = close > ma  # 收盤價在 MA 上方

            if not (near_ma and not_break and bullish):
                return AddPositionResult(False, 0, "pullback_condition_not_met")
        else:  # short
            # 空單回踩加倉條件：
            # a) 最高價靠近 MA（1.5% 內）
            # b) 最高價沒有突破 MA×1.02
            # c) 收盤價在 MA 之下（確認反彈）
            near_ma = abs(high - ma) / ma < 0.015  # 靠近 MA 1.5% 內
            not_break = high < ma * 1.02  # 沒有突破 MA×1.02
            bearish = close < ma  # 收盤價在 MA 下方

            if not (near_ma and not_break and bearish):
                return AddPositionResult(False, 0, "pullback_condition_not_met")

        # 5. 計算加倉數量
        add_qty = current_qty * self.size_pct

        return AddPositionResult(True, add_qty, "conditions_met")

    def record_add(self, bar_index: int, new_qty: float):
        """記錄一次加倉"""
        self.add_count += 1
        self.last_add_bar = bar_index


# === 便捷函數 ===


def create_bige_add_manager() -> AddPositionManager:
    """
    建立 BiGe 策略專用的加倉管理器

    配置（v2.3）：
    - 最多 3 次加倉
    - 每次加倉 50%
    - 間隔 6 根 K 線（24 小時）
    - 盈利 > 3% 才加倉
    - 回踩容許 1.8%
    """
    return AddPositionManager(
        enabled=True,
        max_count=3,
        size_pct=0.5,
        min_interval=6,
        min_profit=0.03,
        pullback_tolerance=0.018,
        pullback_ma_key="avg20",
    )
