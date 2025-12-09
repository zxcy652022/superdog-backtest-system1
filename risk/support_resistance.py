"""
Support/Resistance Detector v0.6 Phase 4

支撐壓力位檢測 - 技術分析 + 永續數據增強

核心功能:
- 基於價格行為的支撐壓力檢測
- 前高前低識別
- 強度評分（交易量、觸碰次數）
- 永續數據增強（資金費率、持倉量）

Version: v0.6.0-phase4
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


class SRType(Enum):
    """支撐壓力類型"""

    SUPPORT = "support"  # 支撐位
    RESISTANCE = "resistance"  # 壓力位
    BOTH = "both"  # 雙向（支撐轉壓力或壓力轉支撐）


@dataclass
class SRLevel:
    """支撐壓力位"""

    price: float  # 價格水平
    sr_type: SRType  # 類型
    strength: float  # 強度 (0-1)
    touches: int  # 觸碰次數
    last_touch_idx: int  # 最後觸碰位置
    volume_score: float = 0.0  # 成交量得分
    oi_score: float = 0.0  # 持倉量得分
    funding_score: float = 0.0  # 資金費率得分


class SupportResistanceDetector:
    """支撐壓力位檢測器

    使用多種方法檢測關鍵價格水平

    Example:
        >>> detector = SupportResistanceDetector()
        >>> levels = detector.detect(ohlcv_data)
        >>> for level in levels:
        ...     print(f"{level.sr_type.value}: {level.price:.2f} (強度: {level.strength:.2f})")
    """

    def __init__(
        self,
        lookback_period: int = 100,
        min_touches: int = 2,
        price_tolerance: float = 0.002,  # 0.2%
        min_strength: float = 0.3,
    ):
        """初始化檢測器

        Args:
            lookback_period: 回看週期
            min_touches: 最小觸碰次數
            price_tolerance: 價格容差（用於合併相近水平）
            min_strength: 最小強度閾值
        """
        self.lookback_period = lookback_period
        self.min_touches = min_touches
        self.price_tolerance = price_tolerance
        self.min_strength = min_strength

    def detect(
        self,
        ohlcv: pd.DataFrame,
        include_volume: bool = True,
        oi_data: Optional[pd.DataFrame] = None,
        funding_data: Optional[pd.DataFrame] = None,
    ) -> List[SRLevel]:
        """檢測支撐壓力位

        Args:
            ohlcv: OHLCV數據
            include_volume: 是否考慮成交量
            oi_data: 持倉量數據（可選）
            funding_data: 資金費率數據（可選）

        Returns:
            List[SRLevel]: 支撐壓力位列表
        """
        if len(ohlcv) < self.lookback_period:
            return []

        # 1. 檢測局部極值
        highs, lows = self._find_local_extrema(ohlcv)

        # 2. 聚類相近價格水平
        resistance_levels = self._cluster_levels(highs, ohlcv, SRType.RESISTANCE)
        support_levels = self._cluster_levels(lows, ohlcv, SRType.SUPPORT)

        all_levels = resistance_levels + support_levels

        # 3. 計算基礎強度
        for level in all_levels:
            level.strength = self._calculate_strength(level, ohlcv)

        # 4. 成交量增強
        if include_volume and "volume" in ohlcv.columns:
            for level in all_levels:
                level.volume_score = self._calculate_volume_score(level, ohlcv)

        # 5. 永續數據增強
        if oi_data is not None:
            for level in all_levels:
                level.oi_score = self._calculate_oi_score(level, ohlcv, oi_data)

        if funding_data is not None:
            for level in all_levels:
                level.funding_score = self._calculate_funding_score(level, funding_data)

        # 6. 綜合強度調整
        for level in all_levels:
            level.strength = self._综合_strength(level)

        # 7. 過濾弱水平
        filtered_levels = [
            level
            for level in all_levels
            if level.strength >= self.min_strength and level.touches >= self.min_touches
        ]

        # 8. 按強度排序
        filtered_levels.sort(key=lambda x: x.strength, reverse=True)

        return filtered_levels

    def _find_local_extrema(
        self, ohlcv: pd.DataFrame, order: int = 5
    ) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """找出局部極值（高點和低點）

        Args:
            ohlcv: OHLCV數據
            order: 局部極值的階數

        Returns:
            Tuple: (高點列表, 低點列表)
        """
        highs = []
        lows = []

        high_prices = ohlcv["high"].values
        low_prices = ohlcv["low"].values

        for i in range(order, len(ohlcv) - order):
            # 檢查局部高點
            if all(high_prices[i] >= high_prices[i - order : i]) and all(
                high_prices[i] >= high_prices[i + 1 : i + order + 1]
            ):
                highs.append((i, high_prices[i]))

            # 檢查局部低點
            if all(low_prices[i] <= low_prices[i - order : i]) and all(
                low_prices[i] <= low_prices[i + 1 : i + order + 1]
            ):
                lows.append((i, low_prices[i]))

        return highs, lows

    def _cluster_levels(
        self, extrema: List[Tuple[int, float]], ohlcv: pd.DataFrame, sr_type: SRType
    ) -> List[SRLevel]:
        """聚類相近的價格水平

        Args:
            extrema: 極值列表 [(index, price), ...]
            ohlcv: OHLCV數據
            sr_type: 支撐/壓力類型

        Returns:
            List[SRLevel]: 聚類後的水平列表
        """
        if not extrema:
            return []

        # 按價格排序
        extrema_sorted = sorted(extrema, key=lambda x: x[1])

        clusters = []
        current_cluster = [extrema_sorted[0]]

        for i in range(1, len(extrema_sorted)):
            idx, price = extrema_sorted[i]
            prev_idx, prev_price = current_cluster[-1]

            # 檢查是否在容差範圍內
            if abs(price - prev_price) / prev_price <= self.price_tolerance:
                current_cluster.append((idx, price))
            else:
                # 創建新簇
                clusters.append(current_cluster)
                current_cluster = [(idx, price)]

        clusters.append(current_cluster)

        # 為每個簇創建 SRLevel
        levels = []
        for cluster in clusters:
            # 計算簇的平均價格
            avg_price = np.mean([price for _, price in cluster])
            touches = len(cluster)
            last_touch_idx = max(idx for idx, _ in cluster)

            level = SRLevel(
                price=avg_price,
                sr_type=sr_type,
                strength=0.0,  # 後續計算
                touches=touches,
                last_touch_idx=last_touch_idx,
            )
            levels.append(level)

        return levels

    def _calculate_strength(self, level: SRLevel, ohlcv: pd.DataFrame) -> float:
        """計算基礎強度

        基於觸碰次數、最近性、價格反彈幅度

        Args:
            level: 支撐壓力位
            ohlcv: OHLCV數據

        Returns:
            float: 強度分數 (0-1)
        """
        # 觸碰次數得分（歸一化）
        touch_score = min(level.touches / 5, 1.0) * 0.4

        # 最近性得分（越近越重要）
        recency = (len(ohlcv) - level.last_touch_idx) / len(ohlcv)
        recency_score = (1 - recency) * 0.3

        # 反彈強度得分
        bounce_score = self._calculate_bounce_strength(level, ohlcv) * 0.3

        return touch_score + recency_score + bounce_score

    def _calculate_bounce_strength(
        self, level: SRLevel, ohlcv: pd.DataFrame, window: int = 5
    ) -> float:
        """計算價格反彈強度

        Args:
            level: 支撐壓力位
            ohlcv: OHLCV數據
            window: 反彈檢測窗口

        Returns:
            float: 反彈強度 (0-1)
        """
        idx = level.last_touch_idx
        if idx + window >= len(ohlcv):
            return 0.0

        price_at_touch = ohlcv["close"].iloc[idx]
        prices_after = ohlcv["close"].iloc[idx + 1 : idx + window + 1]

        if len(prices_after) == 0:
            return 0.0

        if level.sr_type == SRType.SUPPORT:
            # 支撐位：向上反彈
            max_bounce = prices_after.max() - price_at_touch
            bounce_pct = max_bounce / price_at_touch
        else:
            # 壓力位：向下反彈
            max_bounce = price_at_touch - prices_after.min()
            bounce_pct = max_bounce / price_at_touch

        # 歸一化（假設5%為強反彈）
        return min(bounce_pct / 0.05, 1.0)

    def _calculate_volume_score(self, level: SRLevel, ohlcv: pd.DataFrame) -> float:
        """計算成交量得分

        Args:
            level: 支撐壓力位
            ohlcv: OHLCV數據

        Returns:
            float: 成交量得分 (0-1)
        """
        idx = level.last_touch_idx
        if "volume" not in ohlcv.columns:
            return 0.0

        volume_at_touch = ohlcv["volume"].iloc[idx]
        avg_volume = ohlcv["volume"].mean()

        if avg_volume == 0:
            return 0.0

        # 相對成交量
        volume_ratio = volume_at_touch / avg_volume

        # 歸一化（假設2倍平均成交量為高）
        return min(volume_ratio / 2.0, 1.0)

    def _calculate_oi_score(
        self, level: SRLevel, ohlcv: pd.DataFrame, oi_data: pd.DataFrame
    ) -> float:
        """計算持倉量得分

        Args:
            level: 支撐壓力位
            ohlcv: OHLCV數據
            oi_data: 持倉量數據

        Returns:
            float: 持倉量得分 (0-1)
        """
        # 簡化實現：檢查該價格區間的持倉量變化
        try:
            idx = level.last_touch_idx
            timestamp = ohlcv.index[idx]

            # 找到最接近的持倉量數據
            oi_at_time = oi_data.loc[oi_data.index <= timestamp].iloc[-1]["open_interest"]
            avg_oi = oi_data["open_interest"].mean()

            if avg_oi == 0:
                return 0.0

            oi_ratio = oi_at_time / avg_oi
            return min(oi_ratio / 1.5, 1.0)

        except Exception:
            return 0.0

    def _calculate_funding_score(self, level: SRLevel, funding_data: pd.DataFrame) -> float:
        """計算資金費率得分

        高資金費率可能預示壓力位；負資金費率可能預示支撐位

        Args:
            level: 支撐壓力位
            funding_data: 資金費率數據

        Returns:
            float: 資金費率得分 (0-1)
        """
        try:
            avg_funding = funding_data["funding_rate"].mean()

            if level.sr_type == SRType.RESISTANCE and avg_funding > 0.0001:
                # 正費率強化壓力位
                return min(avg_funding / 0.0003, 1.0)
            elif level.sr_type == SRType.SUPPORT and avg_funding < -0.0001:
                # 負費率強化支撐位
                return min(abs(avg_funding) / 0.0003, 1.0)

            return 0.0
        except Exception:
            return 0.0

    def _综合_strength(self, level: SRLevel) -> float:
        """綜合計算最終強度

        整合基礎強度和各項增強得分

        Args:
            level: 支撐壓力位

        Returns:
            float: 最終強度 (0-1)
        """
        base_weight = 0.5
        volume_weight = 0.2
        oi_weight = 0.2
        funding_weight = 0.1

        final_strength = (
            level.strength * base_weight
            + level.volume_score * volume_weight
            + level.oi_score * oi_weight
            + level.funding_score * funding_weight
        )

        return min(final_strength, 1.0)

    def get_nearest_support(self, current_price: float, levels: List[SRLevel]) -> Optional[SRLevel]:
        """獲取最近的支撐位

        Args:
            current_price: 當前價格
            levels: 支撐壓力位列表

        Returns:
            Optional[SRLevel]: 最近的支撐位
        """
        supports = [
            level
            for level in levels
            if level.sr_type in [SRType.SUPPORT, SRType.BOTH] and level.price < current_price
        ]

        if not supports:
            return None

        return max(supports, key=lambda x: x.price)

    def get_nearest_resistance(
        self, current_price: float, levels: List[SRLevel]
    ) -> Optional[SRLevel]:
        """獲取最近的壓力位

        Args:
            current_price: 當前價格
            levels: 支撐壓力位列表

        Returns:
            Optional[SRLevel]: 最近的壓力位
        """
        resistances = [
            level
            for level in levels
            if level.sr_type in [SRType.RESISTANCE, SRType.BOTH] and level.price > current_price
        ]

        if not resistances:
            return None

        return min(resistances, key=lambda x: x.price)


# ===== 便捷函數 =====


def detect_support_resistance(ohlcv: pd.DataFrame, **kwargs) -> List[SRLevel]:
    """快速檢測支撐壓力位

    Args:
        ohlcv: OHLCV數據
        **kwargs: 傳遞給 SupportResistanceDetector 的參數

    Returns:
        List[SRLevel]: 支撐壓力位列表

    Example:
        >>> levels = detect_support_resistance(ohlcv_data)
        >>> print(f"找到 {len(levels)} 個關鍵水平")
    """
    detector = SupportResistanceDetector(**kwargs)
    return detector.detect(ohlcv)
