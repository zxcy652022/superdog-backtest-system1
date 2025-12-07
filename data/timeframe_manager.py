"""
Timeframe Manager v0.4

多時間週期管理器 - 支援多種時間週期的轉換和驗證

這個模組提供：
- 支援標準時間週期（1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w）
- 時間週期轉換和重採樣
- 數據對齊和時間校正
- 時間週期驗證

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from datetime import timedelta
from enum import Enum
from typing import Dict, List

import pandas as pd


class Timeframe(Enum):
    """標準時間週期枚舉

    支援的時間週期：
    - 分鐘級：1m, 5m, 15m, 30m
    - 小時級：1h, 4h
    - 日級：1d
    - 週級：1w
    """

    M1 = "1m"  # 1 分鐘
    M5 = "5m"  # 5 分鐘
    M15 = "15m"  # 15 分鐘
    M30 = "30m"  # 30 分鐘
    H1 = "1h"  # 1 小時
    H4 = "4h"  # 4 小時
    D1 = "1d"  # 1 天
    W1 = "1w"  # 1 週

    @classmethod
    def is_valid(cls, timeframe: str) -> bool:
        """檢查時間週期是否有效

        Args:
            timeframe: 時間週期字符串

        Returns:
            True 如果有效，否則 False

        Example:
            >>> Timeframe.is_valid("1h")
            True
            >>> Timeframe.is_valid("2h")
            False
        """
        return timeframe in [tf.value for tf in cls]

    @classmethod
    def get_all(cls) -> List[str]:
        """獲取所有支援的時間週期

        Returns:
            時間週期列表

        Example:
            >>> Timeframe.get_all()
            ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        """
        return [tf.value for tf in cls]

    @classmethod
    def from_string(cls, timeframe: str) -> "Timeframe":
        """從字符串創建 Timeframe

        Args:
            timeframe: 時間週期字符串

        Returns:
            Timeframe 枚舉

        Raises:
            ValueError: 無效的時間週期

        Example:
            >>> tf = Timeframe.from_string("1h")
            >>> print(tf.value)
            '1h'
        """
        for tf in cls:
            if tf.value == timeframe:
                return tf

        raise ValueError(
            f"Invalid timeframe '{timeframe}'. " f"Valid options: {', '.join(cls.get_all())}"
        )


class TimeframeManager:
    """時間週期管理器

    管理多種時間週期的轉換、驗證和重採樣

    Example:
        >>> manager = TimeframeManager()
        >>> is_valid = manager.validate_timeframe("1h")
        >>> minutes = manager.get_minutes("1h")
    """

    # 時間週期到分鐘數的映射
    TIMEFRAME_MINUTES = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1w": 10080,
    }

    # pandas 重採樣規則
    RESAMPLE_RULES = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
        "1w": "1W",
    }

    def __init__(self):
        """初始化時間週期管理器"""
        self._cache: Dict[str, pd.DatetimeIndex] = {}

    def validate_timeframe(self, timeframe: str) -> bool:
        """驗證時間週期是否有效

        Args:
            timeframe: 時間週期字符串

        Returns:
            True 如果有效，否則 False

        Example:
            >>> manager = TimeframeManager()
            >>> manager.validate_timeframe("1h")
            True
        """
        return Timeframe.is_valid(timeframe)

    def get_minutes(self, timeframe: str) -> int:
        """獲取時間週期對應的分鐘數

        Args:
            timeframe: 時間週期字符串

        Returns:
            分鐘數

        Raises:
            ValueError: 無效的時間週期

        Example:
            >>> manager = TimeframeManager()
            >>> manager.get_minutes("1h")
            60
        """
        if timeframe not in self.TIMEFRAME_MINUTES:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        return self.TIMEFRAME_MINUTES[timeframe]

    def get_timedelta(self, timeframe: str) -> timedelta:
        """獲取時間週期對應的 timedelta

        Args:
            timeframe: 時間週期字符串

        Returns:
            timedelta 對象

        Example:
            >>> manager = TimeframeManager()
            >>> td = manager.get_timedelta("1h")
            >>> print(td)
            timedelta(hours=1)
        """
        minutes = self.get_minutes(timeframe)
        return timedelta(minutes=minutes)

    def resample_ohlcv(
        self, data: pd.DataFrame, source_timeframe: str, target_timeframe: str
    ) -> pd.DataFrame:
        """重採樣 OHLCV 數據到不同時間週期

        Args:
            data: 原始 OHLCV 數據
            source_timeframe: 源時間週期
            target_timeframe: 目標時間週期

        Returns:
            重採樣後的 OHLCV 數據

        Raises:
            ValueError: 無效的時間週期或數據格式

        Example:
            >>> manager = TimeframeManager()
            >>> data_1h = manager.resample_ohlcv(data_1m, "1m", "1h")

        Note:
            目標時間週期必須大於或等於源時間週期
        """
        # 驗證時間週期
        if not self.validate_timeframe(source_timeframe):
            raise ValueError(f"Invalid source timeframe: {source_timeframe}")

        if not self.validate_timeframe(target_timeframe):
            raise ValueError(f"Invalid target timeframe: {target_timeframe}")

        # 檢查目標時間週期是否大於源時間週期
        source_minutes = self.get_minutes(source_timeframe)
        target_minutes = self.get_minutes(target_timeframe)

        if target_minutes < source_minutes:
            raise ValueError(
                f"Cannot resample from {source_timeframe} to {target_timeframe}: "
                f"target timeframe must be >= source timeframe"
            )

        if target_minutes == source_minutes:
            return data.copy()  # 相同時間週期，返回副本

        # 獲取重採樣規則
        rule = self.RESAMPLE_RULES[target_timeframe]

        # 重採樣
        resampled = data.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )

        # 移除 NaN 行
        resampled = resampled.dropna()

        return resampled

    def align_timeframes(
        self, data1: pd.DataFrame, data2: pd.DataFrame, how: str = "inner"
    ) -> tuple:
        """對齊兩個不同時間週期的數據

        Args:
            data1: 第一個數據集
            data2: 第二個數據集
            how: 對齊方式（'inner', 'outer', 'left', 'right'）

        Returns:
            對齊後的兩個數據集（data1_aligned, data2_aligned）

        Example:
            >>> manager = TimeframeManager()
            >>> data1_aligned, data2_aligned = manager.align_timeframes(
            ...     data_1h, data_4h, how='inner'
            ... )
        """
        # 使用 pandas 的 join 功能對齊索引
        if how == "inner":
            common_index = data1.index.intersection(data2.index)
            return data1.loc[common_index], data2.loc[common_index]

        elif how == "outer":
            all_index = data1.index.union(data2.index).sort_values()
            return (
                data1.reindex(all_index, method="ffill"),
                data2.reindex(all_index, method="ffill"),
            )

        elif how == "left":
            return data1, data2.reindex(data1.index, method="ffill")

        elif how == "right":
            return data1.reindex(data2.index, method="ffill"), data2

        else:
            raise ValueError(f"Invalid 'how' parameter: {how}")

    def get_compatible_timeframes(self, base_timeframe: str) -> List[str]:
        """獲取與基準時間週期兼容的時間週期

        返回可以從基準時間週期重採樣得到的時間週期

        Args:
            base_timeframe: 基準時間週期

        Returns:
            兼容的時間週期列表

        Example:
            >>> manager = TimeframeManager()
            >>> compatible = manager.get_compatible_timeframes("1m")
            >>> print(compatible)
            ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        """
        base_minutes = self.get_minutes(base_timeframe)

        compatible = []
        for tf in Timeframe.get_all():
            tf_minutes = self.get_minutes(tf)
            if tf_minutes >= base_minutes:
                compatible.append(tf)

        return compatible

    def calculate_bar_count(
        self, timeframe: str, start_time: pd.Timestamp, end_time: pd.Timestamp
    ) -> int:
        """計算時間範圍內的 K 線數量

        Args:
            timeframe: 時間週期
            start_time: 開始時間
            end_time: 結束時間

        Returns:
            K 線數量（估算值）

        Example:
            >>> manager = TimeframeManager()
            >>> start = pd.Timestamp("2024-01-01")
            >>> end = pd.Timestamp("2024-01-02")
            >>> count = manager.calculate_bar_count("1h", start, end)
            >>> print(count)
            24
        """
        time_diff = end_time - start_time
        minutes = self.get_minutes(timeframe)

        return int(time_diff.total_seconds() / 60 / minutes)

    def format_timeframe(self, timeframe: str) -> str:
        """格式化時間週期為可讀字符串

        Args:
            timeframe: 時間週期

        Returns:
            格式化的字符串

        Example:
            >>> manager = TimeframeManager()
            >>> manager.format_timeframe("1h")
            '1 Hour'
            >>> manager.format_timeframe("1d")
            '1 Day'
        """
        formats = {
            "1m": "1 Minute",
            "5m": "5 Minutes",
            "15m": "15 Minutes",
            "30m": "30 Minutes",
            "1h": "1 Hour",
            "4h": "4 Hours",
            "1d": "1 Day",
            "1w": "1 Week",
        }

        return formats.get(timeframe, timeframe)


# 全局管理器實例
_global_timeframe_manager = TimeframeManager()


def get_timeframe_manager() -> TimeframeManager:
    """獲取全局時間週期管理器

    Returns:
        全局 TimeframeManager 實例

    Example:
        >>> manager = get_timeframe_manager()
        >>> is_valid = manager.validate_timeframe("1h")
    """
    return _global_timeframe_manager


def validate_timeframe(timeframe: str) -> bool:
    """驗證時間週期的便捷函數

    Args:
        timeframe: 時間週期字符串

    Returns:
        True 如果有效，否則 False

    Example:
        >>> validate_timeframe("1h")
        True
        >>> validate_timeframe("2h")
        False
    """
    return Timeframe.is_valid(timeframe)


def get_all_timeframes() -> List[str]:
    """獲取所有支援的時間週期

    Returns:
        時間週期列表

    Example:
        >>> get_all_timeframes()
        ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
    """
    return Timeframe.get_all()
