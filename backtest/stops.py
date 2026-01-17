"""
Stop Manager - 止損管理模組

提供可配置的止損管理器，從策略中分離止損邏輯。

Version: v1.0
Date: 2026-01-05

功能：
- 確認式止損（連續 N 根 K 線觸及才止損）
- 追蹤止損（隨 MA 上移）
- 緊急止損（ATR 倍數保護）

設計原則：
- 策略只產生信號，止損邏輯由此模組處理
- 符合 RULES.md 第 2.2 節規範
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class StopCheckResult:
    """止損檢查結果"""

    should_stop: bool  # 是否應該止損
    stop_price: float  # 止損價格
    reason: str  # 止損原因: 'confirmed', 'emergency', 'trailing'


class BaseStopManager(ABC):
    """止損管理器基類"""

    @abstractmethod
    def reset(self):
        """重置狀態（新倉位時調用）"""
        pass

    @abstractmethod
    def check(
        self,
        row: pd.Series,
        direction: str,  # 'long' or 'short'
        entry_price: float,
        current_stop: float,
    ) -> StopCheckResult:
        """
        檢查是否應該止損

        Args:
            row: 當前 K 線數據（需包含 close, high, low, 及技術指標）
            direction: 持倉方向 'long' 或 'short'
            entry_price: 進場價格
            current_stop: 當前止損價

        Returns:
            StopCheckResult
        """
        pass

    @abstractmethod
    def update_trailing(
        self,
        row: pd.Series,
        direction: str,
        current_stop: float,
    ) -> float:
        """
        更新追蹤止損

        Args:
            row: 當前 K 線數據
            direction: 持倉方向
            current_stop: 當前止損價

        Returns:
            新的止損價（只升不降/只降不升）
        """
        pass


class SimpleStopManager(BaseStopManager):
    """簡單止損管理器 - 觸及即止損"""

    def reset(self):
        pass

    def check(
        self,
        row: pd.Series,
        direction: str,
        entry_price: float,
        current_stop: float,
    ) -> StopCheckResult:
        close = row["close"]
        high = row["high"]
        low = row["low"]

        if direction == "long":
            if low <= current_stop:
                return StopCheckResult(True, current_stop, "simple")
        else:  # short
            if high >= current_stop:
                return StopCheckResult(True, current_stop, "simple")

        return StopCheckResult(False, current_stop, "")

    def update_trailing(
        self,
        row: pd.Series,
        direction: str,
        current_stop: float,
    ) -> float:
        return current_stop


class ConfirmedStopManager(BaseStopManager):
    """
    確認式止損管理器

    功能：
    1. 確認式止損：連續 confirm_bars 根 K 線觸及止損價才執行
    2. 追蹤止損：隨 MA20 上移（trailing_ma_key 指定）
    3. 緊急止損：跌破 MA 超過 emergency_atr_mult × ATR 立即止損

    這是從 bige_dual_ma_v2.py 提取出來的止損邏輯，
    讓策略只負責產生信號，止損由此模組處理。
    """

    def __init__(
        self,
        confirm_bars: int = 10,  # 確認根數
        trailing: bool = True,  # 是否追蹤止損
        trailing_ma_key: str = "avg20",  # 追蹤的 MA key
        trailing_buffer: float = 0.02,  # MA 緩衝 (0.02 = 2%)
        emergency_atr_mult: float = 3.5,  # 緊急止損 ATR 倍數 (0 = 禁用)
        atr_key: str = "atr",  # ATR 欄位名
    ):
        self.confirm_bars = confirm_bars
        self.trailing = trailing
        self.trailing_ma_key = trailing_ma_key
        self.trailing_buffer = trailing_buffer
        self.emergency_atr_mult = emergency_atr_mult
        self.atr_key = atr_key

        # 狀態
        self.below_stop_count = 0

    def reset(self):
        """重置狀態（新倉位時調用）"""
        self.below_stop_count = 0

    def check(
        self,
        row: pd.Series,
        direction: str,
        entry_price: float,
        current_stop: float,
    ) -> StopCheckResult:
        """檢查是否應該止損"""
        close = row["close"]
        high = row["high"]
        low = row["low"]

        # 1. 緊急止損檢查（最高優先級）
        if self.emergency_atr_mult > 0:
            emergency_result = self._check_emergency(row, direction, current_stop)
            if emergency_result.should_stop:
                return emergency_result

        # 2. 確認式止損（最低價觸及止損價 + N 根確認）
        # 這是 bige_top20_backtest.py 驗證有效的邏輯
        if direction == "long":
            # 多單：最低價觸及止損價
            if low <= current_stop:
                self.below_stop_count += 1
                if self.below_stop_count >= self.confirm_bars:
                    return StopCheckResult(True, current_stop, "confirmed")
            else:
                self.below_stop_count = 0
        else:  # short
            # 空單：最高價觸及止損價
            if high >= current_stop:
                self.below_stop_count += 1
                if self.below_stop_count >= self.confirm_bars:
                    return StopCheckResult(True, current_stop, "confirmed")
            else:
                self.below_stop_count = 0

        return StopCheckResult(False, current_stop, "")

    def _check_emergency(
        self,
        row: pd.Series,
        direction: str,
        current_stop: float,
    ) -> StopCheckResult:
        """檢查緊急止損"""
        ma = row.get(self.trailing_ma_key)
        atr = row.get(self.atr_key)
        low = row["low"]
        high = row["high"]

        if pd.isna(ma) or pd.isna(atr) or atr <= 0:
            return StopCheckResult(False, current_stop, "")

        threshold = self.emergency_atr_mult * atr

        if direction == "long":
            # 多單：跌破 MA 超過 threshold
            breach = ma - low
            if breach > 0 and breach > threshold:
                emergency_price = low  # 用最低價作為止損價
                return StopCheckResult(True, emergency_price, "emergency")
        else:  # short
            # 空單：突破 MA 超過 threshold
            breach = high - ma
            if breach > 0 and breach > threshold:
                emergency_price = high
                return StopCheckResult(True, emergency_price, "emergency")

        return StopCheckResult(False, current_stop, "")

    def update_trailing(
        self,
        row: pd.Series,
        direction: str,
        current_stop: float,
    ) -> float:
        """更新追蹤止損"""
        if not self.trailing:
            return current_stop

        ma = row.get(self.trailing_ma_key)
        if pd.isna(ma):
            return current_stop

        if direction == "long":
            # 多單：新止損 = MA × (1 - buffer)，只能上移
            new_stop = ma * (1 - self.trailing_buffer)
            if new_stop > current_stop:
                return new_stop
        else:  # short
            # 空單：新止損 = MA × (1 + buffer)，只能下移
            new_stop = ma * (1 + self.trailing_buffer)
            if new_stop < current_stop:
                return new_stop

        return current_stop


# === 便捷函數 ===


def create_bige_stop_manager() -> ConfirmedStopManager:
    """
    建立 BiGe 策略專用的止損管理器

    配置（v2.1 驗證有效）：
    - 2 根確認（8 小時）
    - 追蹤 avg20（MA20 × 0.98）
    - 2% 緩衝
    - 禁用緊急止損（有效版本不用）
    """
    return ConfirmedStopManager(
        confirm_bars=2,  # v2.1: 2 根確認
        trailing=True,
        trailing_ma_key="avg20",
        trailing_buffer=0.02,
        emergency_atr_mult=0,  # 禁用
    )
