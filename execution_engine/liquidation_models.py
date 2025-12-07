"""
Liquidation Models v0.6 Phase 3

強平風險模型 - 保證金計算、強平價格、風險評估

核心功能:
- 強平價格計算
- 保證金比率監控
- 風險等級評估
- 槓桿限制檢查

Version: v0.6.0-phase3
Design Reference: docs/specs/v0.6/superdog_v06_execution_model_spec.md
"""

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum


class RiskLevel(Enum):
    """風險等級"""
    SAFE = "safe"           # 安全
    LOW = "low"            # 低風險
    MEDIUM = "medium"      # 中等風險
    HIGH = "high"          # 高風險
    CRITICAL = "critical"  # 極危險
    LIQUIDATED = "liquidated"  # 已強平


@dataclass
class MarginConfig:
    """保證金配置

    定義不同槓桿等級的保證金要求
    """

    # 初始保證金率（開倉所需）
    initial_margin_rate: float = 0.1  # 10% (10x槓桿)

    # 維持保證金率（強平觸發）
    maintenance_margin_rate: float = 0.05  # 5%

    # 最大槓桿倍數
    max_leverage: float = 20

    # 槓桿檔位（Binance風格）
    leverage_tiers: Dict[float, Dict[str, float]] = None

    def __post_init__(self):
        """初始化槓桿檔位"""
        if self.leverage_tiers is None:
            # Binance USDT永續合約槓桿檔位
            self.leverage_tiers = {
                # leverage: {maintenance_margin_rate, max_notional}
                125: {'mmr': 0.004, 'max_notional': 50000},      # 0.4%
                100: {'mmr': 0.005, 'max_notional': 250000},     # 0.5%
                50:  {'mmr': 0.01, 'max_notional': 1000000},     # 1%
                20:  {'mmr': 0.025, 'max_notional': 5000000},    # 2.5%
                10:  {'mmr': 0.05, 'max_notional': 20000000},    # 5%
                5:   {'mmr': 0.10, 'max_notional': 50000000},    # 10%
                4:   {'mmr': 0.125, 'max_notional': 100000000},  # 12.5%
                3:   {'mmr': 0.15, 'max_notional': 200000000},   # 15%
                2:   {'mmr': 0.25, 'max_notional': 300000000},   # 25%
                1:   {'mmr': 0.5, 'max_notional': 500000000},    # 50%
            }

    def get_maintenance_margin_rate(self, leverage: float, notional_value: float) -> float:
        """根據槓桿和名義價值獲取維持保證金率

        Args:
            leverage: 槓桿倍數
            notional_value: 名義價值

        Returns:
            float: 維持保證金率
        """
        # 找到適用的檔位
        for lev in sorted(self.leverage_tiers.keys(), reverse=True):
            if leverage >= lev:
                tier = self.leverage_tiers[lev]
                if notional_value <= tier['max_notional']:
                    return tier['mmr']

        # 默認使用配置的維持保證金率
        return self.maintenance_margin_rate


@dataclass
class LiquidationResult:
    """強平風險評估結果"""
    risk_level: RiskLevel          # 風險等級
    margin_ratio: float            # 保證金比率
    liquidation_price: float       # 強平價格
    distance_to_liquidation: float # 距離強平的價格距離（%）
    is_liquidated: bool            # 是否已強平
    unrealized_pnl: float          # 未實現盈虧
    available_margin: float        # 可用保證金
    required_margin: float         # 所需保證金


class LiquidationModel:
    """強平風險模型

    計算強平價格和評估強平風險

    Example:
        >>> model = LiquidationModel()
        >>> result = model.check_liquidation_risk(
        ...     position_size=1.0,
        ...     position_side='long',
        ...     entry_price=50000,
        ...     current_price=48000,
        ...     account_balance=10000,
        ...     leverage=10
        ... )
        >>> result.risk_level
        RiskLevel.HIGH
    """

    def __init__(self, config: Optional[MarginConfig] = None):
        """初始化強平模型

        Args:
            config: 保證金配置（可選）
        """
        self.config = config or MarginConfig()

        # 統計信息
        self.liquidation_count = 0
        self.total_liquidation_loss = 0.0

    def calculate_liquidation_price(
        self,
        position_size: float,
        position_side: str,
        entry_price: float,
        leverage: float,
        account_balance: float,
        maintenance_margin_rate: Optional[float] = None
    ) -> float:
        """計算強平價格

        Args:
            position_size: 持倉數量
            position_side: 持倉方向 ('long'/'short')
            entry_price: 開倉價格
            leverage: 槓桿倍數
            account_balance: 賬戶餘額
            maintenance_margin_rate: 維持保證金率（可選）

        Returns:
            float: 強平價格

        Example:
            >>> model = LiquidationModel()
            >>> liq_price = model.calculate_liquidation_price(
            ...     position_size=1.0,
            ...     position_side='long',
            ...     entry_price=50000,
            ...     leverage=10,
            ...     account_balance=5000
            ... )
            >>> liq_price
            47500.0  # 大約
        """
        # 獲取維持保證金率
        if maintenance_margin_rate is None:
            notional_value = position_size * entry_price
            maintenance_margin_rate = self.config.get_maintenance_margin_rate(
                leverage, notional_value
            )

        # 計算初始保證金
        initial_margin = (position_size * entry_price) / leverage

        # 強平價格公式
        if position_side == 'long':
            # Long 強平價格
            # liquidation_price = entry_price * (1 - (account_balance - maintenance_margin) / position_value)
            # 簡化公式：
            liquidation_price = entry_price * (
                1 - (account_balance / (position_size * entry_price)) + maintenance_margin_rate
            )
        else:  # short
            # Short 強平價格
            liquidation_price = entry_price * (
                1 + (account_balance / (position_size * entry_price)) - maintenance_margin_rate
            )

        return max(liquidation_price, 0.0)

    def check_liquidation_risk(
        self,
        position_size: float,
        position_side: str,
        entry_price: float,
        current_price: float,
        account_balance: float,
        leverage: float,
        maintenance_margin_rate: Optional[float] = None
    ) -> LiquidationResult:
        """檢查強平風險

        Args:
            position_size: 持倉數量
            position_side: 持倉方向
            entry_price: 開倉價格
            current_price: 當前價格
            account_balance: 賬戶餘額
            leverage: 槓桿倍數
            maintenance_margin_rate: 維持保證金率（可選）

        Returns:
            LiquidationResult: 風險評估結果

        Example:
            >>> model = LiquidationModel()
            >>> result = model.check_liquidation_risk(
            ...     position_size=1.0,
            ...     position_side='long',
            ...     entry_price=50000,
            ...     current_price=49000,
            ...     account_balance=5000,
            ...     leverage=10
            ... )
        """
        # 計算未實現盈虧
        if position_side == 'long':
            unrealized_pnl = (current_price - entry_price) * position_size
        else:  # short
            unrealized_pnl = (entry_price - current_price) * position_size

        # 計算持倉價值
        position_value = position_size * current_price

        # 獲取維持保證金率
        if maintenance_margin_rate is None:
            maintenance_margin_rate = self.config.get_maintenance_margin_rate(
                leverage, position_value
            )

        # 計算所需保證金
        required_margin = position_value * maintenance_margin_rate

        # 計算可用保證金
        available_margin = account_balance + unrealized_pnl

        # 計算保證金比率
        margin_ratio = available_margin / position_value if position_value > 0 else 0

        # 計算強平價格
        liquidation_price = self.calculate_liquidation_price(
            position_size, position_side, entry_price,
            leverage, account_balance, maintenance_margin_rate
        )

        # 計算距離強平的距離
        if position_side == 'long':
            distance_pct = (current_price - liquidation_price) / current_price
        else:
            distance_pct = (liquidation_price - current_price) / current_price

        # 判斷是否已強平
        is_liquidated = margin_ratio <= maintenance_margin_rate

        # 評估風險等級
        risk_level = self._assess_risk_level(margin_ratio, maintenance_margin_rate)

        # 記錄強平事件
        if is_liquidated:
            self.liquidation_count += 1
            self.total_liquidation_loss += abs(available_margin)

        return LiquidationResult(
            risk_level=risk_level,
            margin_ratio=margin_ratio,
            liquidation_price=liquidation_price,
            distance_to_liquidation=distance_pct,
            is_liquidated=is_liquidated,
            unrealized_pnl=unrealized_pnl,
            available_margin=available_margin,
            required_margin=required_margin
        )

    def _assess_risk_level(
        self,
        margin_ratio: float,
        maintenance_margin_rate: float
    ) -> RiskLevel:
        """評估風險等級

        Args:
            margin_ratio: 保證金比率
            maintenance_margin_rate: 維持保證金率

        Returns:
            RiskLevel: 風險等級
        """
        if margin_ratio <= 0:
            return RiskLevel.LIQUIDATED
        elif margin_ratio <= maintenance_margin_rate:
            return RiskLevel.CRITICAL
        elif margin_ratio <= maintenance_margin_rate * 1.5:
            return RiskLevel.HIGH
        elif margin_ratio <= maintenance_margin_rate * 2.0:
            return RiskLevel.MEDIUM
        elif margin_ratio <= maintenance_margin_rate * 3.0:
            return RiskLevel.LOW
        else:
            return RiskLevel.SAFE

    def calculate_max_position_size(
        self,
        account_balance: float,
        entry_price: float,
        leverage: float,
        risk_pct: float = 0.02
    ) -> Dict[str, float]:
        """計算最大安全倉位

        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            leverage: 槓桿倍數
            risk_pct: 風險百分比（默認2%）

        Returns:
            Dict: 倉位計算結果
        """
        # 最大可用資金（考慮風險）
        max_risk_capital = account_balance * risk_pct

        # 計算最大名義價值
        max_notional = account_balance * leverage

        # 計算最大倉位
        max_position_size = max_notional / entry_price

        # 考慮風險的推薦倉位
        recommended_position_size = (max_risk_capital * leverage) / entry_price

        return {
            'max_position_size': max_position_size,
            'recommended_position_size': recommended_position_size,
            'max_notional': max_notional,
            'max_risk_capital': max_risk_capital,
            'leverage': leverage
        }

    def simulate_price_movement(
        self,
        position_size: float,
        position_side: str,
        entry_price: float,
        account_balance: float,
        leverage: float,
        price_change_pct: float
    ) -> LiquidationResult:
        """模擬價格變動後的風險狀態

        Args:
            position_size: 持倉數量
            position_side: 持倉方向
            entry_price: 開倉價格
            account_balance: 賬戶餘額
            leverage: 槓桿倍數
            price_change_pct: 價格變動百分比（如 -0.05 表示下跌5%）

        Returns:
            LiquidationResult: 風險評估結果
        """
        # 計算新價格
        new_price = entry_price * (1 + price_change_pct)

        return self.check_liquidation_risk(
            position_size, position_side, entry_price,
            new_price, account_balance, leverage
        )

    def get_safe_leverage(
        self,
        max_expected_drawdown: float
    ) -> float:
        """根據預期最大回撤推薦安全槓桿

        Args:
            max_expected_drawdown: 預期最大回撤（如 0.20 表示20%）

        Returns:
            float: 推薦的安全槓桿倍數

        Example:
            >>> model = LiquidationModel()
            >>> safe_lev = model.get_safe_leverage(0.15)  # 15% 回撤
            >>> safe_lev
            5.0  # 推薦5倍槓桿
        """
        # 保守估計：槓桿 ≈ 1 / (回撤 * 安全係數)
        safety_factor = 1.5  # 安全係數
        recommended_leverage = 1 / (max_expected_drawdown * safety_factor)

        # 限制在合理範圍
        return min(recommended_leverage, self.config.max_leverage)

    def get_statistics(self) -> Dict[str, float]:
        """獲取強平統計信息

        Returns:
            Dict: 統計信息
        """
        return {
            'liquidation_count': self.liquidation_count,
            'total_liquidation_loss': self.total_liquidation_loss,
            'avg_liquidation_loss': (
                self.total_liquidation_loss / self.liquidation_count
                if self.liquidation_count > 0 else 0
            )
        }

    def reset_statistics(self):
        """重置統計信息"""
        self.liquidation_count = 0
        self.total_liquidation_loss = 0.0


# ===== 便捷函數 =====

def calculate_simple_liquidation_price(
    entry_price: float,
    leverage: float,
    position_side: str,
    maintenance_margin_rate: float = 0.05
) -> float:
    """簡化的強平價格計算

    Args:
        entry_price: 開倉價格
        leverage: 槓桿倍數
        position_side: 持倉方向
        maintenance_margin_rate: 維持保證金率

    Returns:
        float: 強平價格

    Example:
        >>> liq_price = calculate_simple_liquidation_price(50000, 10, 'long')
        >>> liq_price
        47500.0
    """
    # 簡化公式（假設全倉模式）
    if position_side == 'long':
        return entry_price * (1 - 1/leverage + maintenance_margin_rate)
    else:  # short
        return entry_price * (1 + 1/leverage - maintenance_margin_rate)


def get_leverage_recommendations() -> Dict[str, Dict]:
    """獲取不同風險偏好的槓桿建議

    Returns:
        Dict: 槓桿建議
    """
    return {
        'conservative': {
            'max_leverage': 3,
            'recommended_leverage': 2,
            'description': '保守型：適合新手，低風險'
        },
        'moderate': {
            'max_leverage': 5,
            'recommended_leverage': 3,
            'description': '穩健型：平衡風險與收益'
        },
        'aggressive': {
            'max_leverage': 10,
            'recommended_leverage': 5,
            'description': '進取型：追求高收益，承受高風險'
        },
        'professional': {
            'max_leverage': 20,
            'recommended_leverage': 10,
            'description': '專業型：經驗豐富的交易者'
        }
    }
