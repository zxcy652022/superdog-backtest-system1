"""
Market Classifier v1.0

行情分類器 - 識別市場狀態（牛市/熊市/震盪/高波動）

核心功能：
- 單一時間點行情分類
- 時間範圍行情統計
- 按行情類型分割數據
- 支援多種分類方法

Version: v1.0
Design Reference: docs/v1.0/DESIGN.md
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class MarketRegime(Enum):
    """行情類型"""

    BULL = "bull"  # 牛市：明確上升趨勢
    BEAR = "bear"  # 熊市：明確下降趨勢
    SIDEWAYS = "sideways"  # 震盪：無明確趨勢
    HIGH_VOL = "high_vol"  # 高波動：波動率異常高


@dataclass
class RegimeStats:
    """行情統計"""

    regime: MarketRegime
    count: int  # 該行情的 K 線數
    ratio: float  # 佔比
    avg_return: float  # 該行情下的平均收益
    volatility: float  # 該行情下的波動率


class MarketClassifier:
    """行情分類器

    使用均線和波動率判斷市場狀態

    分類邏輯：
    1. 牛市：MA20 > MA60 > MA120，且 MA20 斜率 > 0
    2. 熊市：MA20 < MA60 < MA120，且 MA20 斜率 < 0
    3. 高波動：ATR > 1.5x 平均 ATR
    4. 震盪：不符合以上任何條件

    Example:
        >>> classifier = MarketClassifier()
        >>> df["regime"] = classifier.classify_series(df)
        >>> stats = classifier.get_regime_stats(df)
    """

    def __init__(
        self,
        ma_short: int = 20,
        ma_mid: int = 60,
        ma_long: int = 120,
        atr_period: int = 14,
        vol_threshold: float = 1.5,
        trend_slope_period: int = 5,
    ):
        """初始化分類器

        Args:
            ma_short: 短期均線週期
            ma_mid: 中期均線週期
            ma_long: 長期均線週期
            atr_period: ATR 計算週期
            vol_threshold: 高波動閾值（相對平均 ATR 的倍數）
            trend_slope_period: 趨勢斜率計算週期
        """
        self.ma_short = ma_short
        self.ma_mid = ma_mid
        self.ma_long = ma_long
        self.atr_period = atr_period
        self.vol_threshold = vol_threshold
        self.trend_slope_period = trend_slope_period

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算分類所需指標

        Args:
            df: OHLCV DataFrame

        Returns:
            pd.DataFrame: 附加指標的 DataFrame
        """
        result = df.copy()

        # 均線
        result["ma_short"] = result["close"].rolling(self.ma_short).mean()
        result["ma_mid"] = result["close"].rolling(self.ma_mid).mean()
        result["ma_long"] = result["close"].rolling(self.ma_long).mean()

        # MA 斜率
        result["ma_slope"] = result["ma_short"].diff(self.trend_slope_period)

        # ATR
        high = result["high"]
        low = result["low"]
        close = result["close"]

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        result["atr"] = tr.rolling(self.atr_period).mean()
        result["atr_avg"] = result["atr"].rolling(50).mean()  # 長期平均 ATR

        # 收益率
        result["returns"] = result["close"].pct_change()

        return result

    def classify_row(self, row: pd.Series) -> MarketRegime:
        """分類單一時間點

        Args:
            row: 包含指標的 Series

        Returns:
            MarketRegime: 行情類型
        """
        # 檢查數據是否完整
        required = ["ma_short", "ma_mid", "ma_long", "ma_slope", "atr", "atr_avg"]
        if any(pd.isna(row.get(col)) for col in required):
            return MarketRegime.SIDEWAYS

        # 1. 檢查高波動
        if row["atr"] > row["atr_avg"] * self.vol_threshold:
            return MarketRegime.HIGH_VOL

        # 2. 檢查牛市
        ma_bull = row["ma_short"] > row["ma_mid"] > row["ma_long"]
        slope_bull = row["ma_slope"] > 0

        if ma_bull and slope_bull:
            return MarketRegime.BULL

        # 3. 檢查熊市
        ma_bear = row["ma_short"] < row["ma_mid"] < row["ma_long"]
        slope_bear = row["ma_slope"] < 0

        if ma_bear and slope_bear:
            return MarketRegime.BEAR

        # 4. 其他為震盪
        return MarketRegime.SIDEWAYS

    def classify_series(self, df: pd.DataFrame) -> pd.Series:
        """分類整個時間序列

        Args:
            df: OHLCV DataFrame

        Returns:
            pd.Series: 每個時間點的行情類型
        """
        df_with_indicators = self._calculate_indicators(df)
        regimes = df_with_indicators.apply(self.classify_row, axis=1)
        return regimes

    def classify_period(
        self,
        df: pd.DataFrame,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[MarketRegime, float]:
        """分類時間範圍內各行情佔比

        Args:
            df: OHLCV DataFrame
            start: 開始日期（可選）
            end: 結束日期（可選）

        Returns:
            Dict[MarketRegime, float]: 各行情佔比
        """
        # 篩選時間範圍
        data = df.copy()
        if start:
            data = data[data.index >= start]
        if end:
            data = data[data.index <= end]

        if data.empty:
            return {regime: 0.0 for regime in MarketRegime}

        # 分類
        regimes = self.classify_series(data)

        # 計算佔比
        counts = regimes.value_counts()
        total = len(regimes)

        result = {}
        for regime in MarketRegime:
            count = counts.get(regime, 0)
            result[regime] = count / total if total > 0 else 0.0

        return result

    def get_regime_stats(self, df: pd.DataFrame) -> List[RegimeStats]:
        """獲取各行情的統計信息

        Args:
            df: OHLCV DataFrame

        Returns:
            List[RegimeStats]: 各行情的統計
        """
        df_with_indicators = self._calculate_indicators(df)
        regimes = self.classify_series(df)

        df_with_indicators["regime"] = regimes

        stats = []
        total_rows = len(df_with_indicators)

        for regime in MarketRegime:
            subset = df_with_indicators[df_with_indicators["regime"] == regime]

            if subset.empty:
                stats.append(
                    RegimeStats(
                        regime=regime,
                        count=0,
                        ratio=0.0,
                        avg_return=0.0,
                        volatility=0.0,
                    )
                )
            else:
                stats.append(
                    RegimeStats(
                        regime=regime,
                        count=len(subset),
                        ratio=len(subset) / total_rows,
                        avg_return=subset["returns"].mean() if "returns" in subset else 0.0,
                        volatility=subset["returns"].std() if "returns" in subset else 0.0,
                    )
                )

        return stats

    def split_by_regime(self, df: pd.DataFrame) -> Dict[MarketRegime, pd.DataFrame]:
        """按行情類型分割數據

        Args:
            df: OHLCV DataFrame

        Returns:
            Dict[MarketRegime, pd.DataFrame]: 分割後的數據
        """
        df_with_indicators = self._calculate_indicators(df)
        regimes = self.classify_series(df)
        df_with_indicators["regime"] = regimes

        result = {}
        for regime in MarketRegime:
            subset = df_with_indicators[df_with_indicators["regime"] == regime]
            if not subset.empty:
                result[regime] = subset.drop(columns=["regime"])

        return result

    def find_regime_periods(
        self,
        df: pd.DataFrame,
        regime: MarketRegime,
        min_length: int = 10,
    ) -> List[Tuple[str, str]]:
        """找出特定行情的連續時間段

        Args:
            df: OHLCV DataFrame
            regime: 要找的行情類型
            min_length: 最小連續長度（K 線數）

        Returns:
            List[Tuple[str, str]]: (開始, 結束) 時間對列表
        """
        regimes = self.classify_series(df)
        regimes = regimes.reset_index()
        regimes.columns = ["time", "regime"]

        periods = []
        start_idx = None
        count = 0

        for i, row in regimes.iterrows():
            if row["regime"] == regime:
                if start_idx is None:
                    start_idx = i
                count += 1
            else:
                if start_idx is not None and count >= min_length:
                    end_idx = i - 1
                    periods.append(
                        (
                            str(regimes.loc[start_idx, "time"]),
                            str(regimes.loc[end_idx, "time"]),
                        )
                    )
                start_idx = None
                count = 0

        # 處理結尾
        if start_idx is not None and count >= min_length:
            end_idx = len(regimes) - 1
            periods.append(
                (
                    str(regimes.loc[start_idx, "time"]),
                    str(regimes.loc[end_idx, "time"]),
                )
            )

        return periods


# ===== 便捷函數 =====


def classify_market(
    df: pd.DataFrame,
    method: str = "ma",
) -> pd.Series:
    """分類行情的便捷函數

    Args:
        df: OHLCV DataFrame
        method: 分類方法（目前只支援 "ma"）

    Returns:
        pd.Series: 行情分類結果

    Example:
        >>> df["regime"] = classify_market(df)
    """
    classifier = MarketClassifier()
    return classifier.classify_series(df)


def get_regime_summary(df: pd.DataFrame) -> str:
    """生成行情分類摘要

    Args:
        df: OHLCV DataFrame

    Returns:
        str: 行情摘要文字
    """
    classifier = MarketClassifier()
    stats = classifier.get_regime_stats(df)

    lines = ["=== 行情分類摘要 ===", ""]
    lines.append(f"{'行情類型':<10} | {'佔比':>8} | {'平均收益':>10} | {'波動率':>8}")
    lines.append("-" * 45)

    for s in stats:
        lines.append(
            f"{s.regime.value:<10} | {s.ratio:>7.1%} | "
            f"{s.avg_return:>+9.4%} | {s.volatility:>7.4%}"
        )

    return "\n".join(lines)
