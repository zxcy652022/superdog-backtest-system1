"""
Slippage Models v0.6 Phase 3

滑價模型 - 自適應滑價、市場影響、訂單大小影響

核心功能:
- 固定滑價模型
- 自適應滑價模型（基於訂單大小、波動率）
- 分級滑價（依據幣種分類）
- 市場影響建模

Version: v0.6.0-phase3
Design Reference: docs/specs/v0.6/superdog_v06_execution_model_spec.md
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum
import numpy as np

from .fee_models import OrderType


class SlippageModelType(Enum):
    """滑價模型類型"""
    FIXED = "fixed"               # 固定滑價
    ADAPTIVE = "adaptive"         # 自適應滑價
    VOLUME_WEIGHTED = "volume_weighted"  # 成交量加權
    VOLATILITY_ADJUSTED = "volatility_adjusted"  # 波動率調整


class SymbolTier(Enum):
    """幣種分級（對應 Universe Manager）"""
    LARGE_CAP = "large_cap"       # 大盤
    MID_CAP = "mid_cap"           # 中盤
    SMALL_CAP = "small_cap"       # 小盤
    MICRO_CAP = "micro_cap"       # 微盤


@dataclass
class SlippageConfig:
    """滑價配置

    定義不同幣種級別的基礎滑價參數
    """

    # 基礎滑價（依幣種分級）
    base_slippage: Dict[str, float] = None

    # 最大滑價限制
    max_slippage: float = 0.01  # 1%

    # 訂單大小閾值（相對於平均成交量）
    small_order_threshold: float = 0.01    # 1%
    medium_order_threshold: float = 0.05   # 5%
    large_order_threshold: float = 0.10    # 10%

    # 波動率影響係數
    volatility_multiplier: float = 2.0

    def __post_init__(self):
        """初始化默認基礎滑價"""
        if self.base_slippage is None:
            # Binance 實際觀察的滑價水平（bps）
            self.base_slippage = {
                SymbolTier.LARGE_CAP.value: 0.0001,    # 0.01% - BTC, ETH
                SymbolTier.MID_CAP.value: 0.0003,      # 0.03% - Top 50
                SymbolTier.SMALL_CAP.value: 0.0008,    # 0.08% - Top 200
                SymbolTier.MICRO_CAP.value: 0.002,     # 0.2%  - 其他
            }


@dataclass
class SlippageResult:
    """滑價計算結果"""
    slippage_rate: float           # 滑價率
    slippage_cost: float           # 滑價成本（絕對值）
    base_slippage: float           # 基礎滑價
    size_impact: float             # 訂單大小影響
    volatility_impact: float       # 波動率影響
    model_type: str                # 使用的模型類型


class SlippageModel:
    """滑價影響模型

    提供多種滑價計算方法，從簡單固定滑價到複雜的自適應模型

    Example:
        >>> model = SlippageModel(model_type=SlippageModelType.ADAPTIVE)
        >>> result = model.calculate_slippage(
        ...     order_size=1000,
        ...     order_value=50000,
        ...     avg_volume_24h=10000000,
        ...     volatility=0.02,
        ...     symbol_tier=SymbolTier.LARGE_CAP,
        ...     order_type=OrderType.MARKET
        ... )
        >>> result.slippage_rate
        0.00012  # 0.012%
    """

    def __init__(
        self,
        model_type: SlippageModelType = SlippageModelType.ADAPTIVE,
        config: Optional[SlippageConfig] = None
    ):
        """初始化滑價模型

        Args:
            model_type: 滑價模型類型
            config: 滑價配置（可選）
        """
        self.model_type = model_type
        self.config = config or SlippageConfig()

        # 統計信息
        self.total_slippage_cost = 0.0
        self.slippage_count = 0

    def calculate_slippage(
        self,
        order_size: float,
        order_value: float,
        avg_volume_24h: float,
        volatility: float,
        symbol_tier: SymbolTier,
        order_type: OrderType = OrderType.MARKET,
        market_condition: str = 'normal'
    ) -> SlippageResult:
        """計算訂單滑價

        Args:
            order_size: 訂單數量
            order_value: 訂單價值（USDT）
            avg_volume_24h: 24小時平均成交量
            volatility: 波動率（標準差/均值）
            symbol_tier: 幣種分級
            order_type: 訂單類型
            market_condition: 市場狀況（normal/volatile/illiquid）

        Returns:
            SlippageResult: 滑價計算結果

        Example:
            >>> model = SlippageModel()
            >>> result = model.calculate_slippage(
            ...     order_size=1.0,
            ...     order_value=50000,
            ...     avg_volume_24h=1000000,
            ...     volatility=0.02,
            ...     symbol_tier=SymbolTier.LARGE_CAP,
            ...     order_type=OrderType.MARKET
            ... )
        """
        # 限價單假設無滑價（等待成交）
        if order_type == OrderType.LIMIT:
            return SlippageResult(
                slippage_rate=0.0,
                slippage_cost=0.0,
                base_slippage=0.0,
                size_impact=0.0,
                volatility_impact=0.0,
                model_type=self.model_type.value
            )

        # 根據模型類型計算滑價
        if self.model_type == SlippageModelType.FIXED:
            slippage_rate = self._calculate_fixed_slippage(symbol_tier)
        elif self.model_type == SlippageModelType.ADAPTIVE:
            slippage_rate = self._calculate_adaptive_slippage(
                order_value, avg_volume_24h, volatility, symbol_tier, market_condition
            )
        elif self.model_type == SlippageModelType.VOLUME_WEIGHTED:
            slippage_rate = self._calculate_volume_weighted_slippage(
                order_value, avg_volume_24h, symbol_tier
            )
        else:  # VOLATILITY_ADJUSTED
            slippage_rate = self._calculate_volatility_adjusted_slippage(
                volatility, symbol_tier
            )

        # 計算滑價成本
        slippage_cost = order_value * slippage_rate

        # 更新統計
        self.total_slippage_cost += slippage_cost
        self.slippage_count += 1

        # 提取詳細信息
        base_slip = self.config.base_slippage.get(symbol_tier.value, 0.001)
        volume_ratio = order_value / avg_volume_24h if avg_volume_24h > 0 else 0
        size_impact = self._calculate_size_impact(volume_ratio)
        volatility_impact = volatility * self.config.volatility_multiplier

        return SlippageResult(
            slippage_rate=min(slippage_rate, self.config.max_slippage),
            slippage_cost=slippage_cost,
            base_slippage=base_slip,
            size_impact=size_impact,
            volatility_impact=volatility_impact,
            model_type=self.model_type.value
        )

    def _calculate_fixed_slippage(self, symbol_tier: SymbolTier) -> float:
        """固定滑價模型

        最簡單的模型，僅基於幣種分級

        Args:
            symbol_tier: 幣種分級

        Returns:
            float: 滑價率
        """
        return self.config.base_slippage.get(symbol_tier.value, 0.001)

    def _calculate_adaptive_slippage(
        self,
        order_value: float,
        avg_volume: float,
        volatility: float,
        symbol_tier: SymbolTier,
        market_condition: str
    ) -> float:
        """自適應滑價模型

        基於訂單大小、波動率和市場狀況的智能滑價計算

        Args:
            order_value: 訂單價值
            avg_volume: 平均成交量
            volatility: 波動率
            symbol_tier: 幣種分級
            market_condition: 市場狀況

        Returns:
            float: 滑價率
        """
        # 基礎滑價
        base_slip = self.config.base_slippage.get(symbol_tier.value, 0.001)

        # 計算成交量比例
        volume_ratio = order_value / avg_volume if avg_volume > 0 else 1.0

        # 訂單大小影響
        size_impact = self._calculate_size_impact(volume_ratio)

        # 波動率影響
        volatility_multiplier = 1 + min(volatility * self.config.volatility_multiplier, 1.0)

        # 市場狀況調整
        market_multiplier = {
            'normal': 1.0,
            'volatile': 1.5,
            'illiquid': 2.0,
            'flash_crash': 3.0
        }.get(market_condition, 1.0)

        # 綜合滑價
        total_slippage = (base_slip + size_impact) * volatility_multiplier * market_multiplier

        return min(total_slippage, self.config.max_slippage)

    def _calculate_size_impact(self, volume_ratio: float) -> float:
        """計算訂單大小影響

        使用分段函數模擬市場影響

        Args:
            volume_ratio: 訂單價值/平均成交量比例

        Returns:
            float: 大小影響率
        """
        if volume_ratio < self.config.small_order_threshold:
            # 小訂單: 線性影響
            return volume_ratio * 0.05
        elif volume_ratio < self.config.medium_order_threshold:
            # 中等訂單: 加速影響
            base = self.config.small_order_threshold * 0.05
            excess = volume_ratio - self.config.small_order_threshold
            return base + excess * 0.1
        else:
            # 大訂單: 平方根影響（市場影響模型）
            base = self.config.small_order_threshold * 0.05 + \
                   (self.config.medium_order_threshold - self.config.small_order_threshold) * 0.1
            excess = volume_ratio - self.config.medium_order_threshold
            return base + np.sqrt(excess) * 0.15

    def _calculate_volume_weighted_slippage(
        self,
        order_value: float,
        avg_volume: float,
        symbol_tier: SymbolTier
    ) -> float:
        """成交量加權滑價模型

        主要基於訂單相對於市場成交量的大小

        Args:
            order_value: 訂單價值
            avg_volume: 平均成交量
            symbol_tier: 幣種分級

        Returns:
            float: 滑價率
        """
        base_slip = self.config.base_slippage.get(symbol_tier.value, 0.001)
        volume_ratio = order_value / avg_volume if avg_volume > 0 else 1.0

        # 純粹基於成交量比例
        if volume_ratio < 0.01:
            return base_slip
        elif volume_ratio < 0.05:
            return base_slip * (1 + volume_ratio * 10)
        else:
            return base_slip * (1 + np.log(volume_ratio * 20))

    def _calculate_volatility_adjusted_slippage(
        self,
        volatility: float,
        symbol_tier: SymbolTier
    ) -> float:
        """波動率調整滑價模型

        主要基於市場波動率

        Args:
            volatility: 波動率
            symbol_tier: 幣種分級

        Returns:
            float: 滑價率
        """
        base_slip = self.config.base_slippage.get(symbol_tier.value, 0.001)

        # 波動率倍數（指數關係）
        vol_multiplier = np.exp(volatility * 3) if volatility > 0 else 1.0

        return base_slip * min(vol_multiplier, 5.0)  # 最大5倍

    def estimate_execution_price(
        self,
        reference_price: float,
        slippage_result: SlippageResult,
        side: str  # 'buy' or 'sell'
    ) -> float:
        """估算實際成交價格

        Args:
            reference_price: 參考價格（市價）
            slippage_result: 滑價計算結果
            side: 交易方向

        Returns:
            float: 預估成交價格

        Example:
            >>> model = SlippageModel()
            >>> slip_result = model.calculate_slippage(...)
            >>> execution_price = model.estimate_execution_price(
            ...     50000, slip_result, 'buy'
            ... )
            >>> execution_price
            50006.0  # 50000 * (1 + 0.00012)
        """
        if side == 'buy':
            # 買入: 價格更高（不利）
            return reference_price * (1 + slippage_result.slippage_rate)
        else:  # sell
            # 賣出: 價格更低（不利）
            return reference_price * (1 - slippage_result.slippage_rate)

    def get_statistics(self) -> Dict[str, float]:
        """獲取滑價統計信息

        Returns:
            Dict: 統計信息
        """
        return {
            'total_slippage_cost': self.total_slippage_cost,
            'slippage_count': self.slippage_count,
            'avg_slippage_cost': (
                self.total_slippage_cost / self.slippage_count
                if self.slippage_count > 0 else 0
            )
        }

    def reset_statistics(self):
        """重置統計信息"""
        self.total_slippage_cost = 0.0
        self.slippage_count = 0


# ===== 便捷函數 =====

def calculate_simple_slippage(
    order_value: float,
    slippage_rate: float = 0.0005
) -> float:
    """簡化的滑價計算

    Args:
        order_value: 訂單價值
        slippage_rate: 滑價率（默認0.05%）

    Returns:
        float: 滑價成本

    Example:
        >>> calculate_simple_slippage(10000)
        5.0
    """
    return order_value * slippage_rate


def get_recommended_model_for_strategy(
    trading_frequency: str,
    avg_order_size_ratio: float
) -> SlippageModelType:
    """根據策略特性推薦滑價模型

    Args:
        trading_frequency: 交易頻率（'high'/'medium'/'low'）
        avg_order_size_ratio: 平均訂單大小比例

    Returns:
        SlippageModelType: 推薦的滑價模型

    Example:
        >>> model_type = get_recommended_model_for_strategy('high', 0.001)
        >>> model_type
        SlippageModelType.FIXED
    """
    if trading_frequency == 'high' and avg_order_size_ratio < 0.01:
        # 高頻小單: 使用固定滑價
        return SlippageModelType.FIXED
    elif avg_order_size_ratio > 0.05:
        # 大訂單: 使用自適應模型
        return SlippageModelType.ADAPTIVE
    else:
        # 一般情況: 成交量加權
        return SlippageModelType.VOLUME_WEIGHTED
