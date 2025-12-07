"""
Fee Models v0.6 Phase 3

手續費計算器 - Maker/Taker費率、VIP等級、精確成本計算

核心功能:
- 現貨/永續合約費率支援
- Maker/Taker 費率區分
- VIP 等級優惠
- 精確交易成本計算

Version: v0.6.0-phase3
Design Reference: docs/specs/v0.6/superdog_v06_execution_model_spec.md
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class InstrumentType(Enum):
    """交易工具類型"""
    SPOT = "spot"           # 現貨
    FUTURES = "futures"     # 永續合約
    OPTIONS = "options"     # 期權（未來支援）


class OrderType(Enum):
    """訂單類型"""
    LIMIT = "limit"         # 限價單 (Maker)
    MARKET = "market"       # 市價單 (Taker)
    STOP_LIMIT = "stop_limit"
    STOP_MARKET = "stop_market"


@dataclass
class FeeStructure:
    """手續費結構定義

    定義不同交易工具和VIP等級的費率結構

    Example:
        >>> fee_structure = FeeStructure()
        >>> fee_structure.spot_maker_fee
        0.001  # 0.1%
    """

    # 現貨交易費率
    spot_maker_fee: float = 0.001      # 0.1% Maker
    spot_taker_fee: float = 0.001      # 0.1% Taker

    # 永續合約費率（Binance標準）
    futures_maker_fee: float = 0.0002  # 0.02% Maker
    futures_taker_fee: float = 0.0004  # 0.04% Taker

    # VIP等級費率（Binance VIP結構）
    vip_levels: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'VIP0': {'maker': 0.0002, 'taker': 0.0004},  # 默認
        'VIP1': {'maker': 0.00016, 'taker': 0.00040},
        'VIP2': {'maker': 0.00014, 'taker': 0.00035},
        'VIP3': {'maker': 0.00012, 'taker': 0.00032},
        'VIP4': {'maker': 0.00010, 'taker': 0.00028},
        'VIP5': {'maker': 0.00008, 'taker': 0.00024},
        'VIP6': {'maker': 0.00006, 'taker': 0.00020},
        'VIP7': {'maker': 0.00004, 'taker': 0.00016},
        'VIP8': {'maker': 0.00002, 'taker': 0.00012},
        'VIP9': {'maker': 0.00000, 'taker': 0.00010},  # Maker 返佣
    })

    # 最小手續費（防止極小訂單）
    min_fee: float = 0.0  # USDT

    def get_fee_rate(
        self,
        instrument_type: InstrumentType,
        order_type: OrderType,
        vip_level: str = 'VIP0'
    ) -> float:
        """獲取費率

        Args:
            instrument_type: 交易工具類型
            order_type: 訂單類型
            vip_level: VIP等級

        Returns:
            float: 費率（小數形式）

        Example:
            >>> structure = FeeStructure()
            >>> structure.get_fee_rate(InstrumentType.FUTURES, OrderType.LIMIT, 'VIP3')
            0.00012
        """
        # VIP等級優先
        if vip_level in self.vip_levels:
            fee_type = 'maker' if order_type == OrderType.LIMIT else 'taker'
            return self.vip_levels[vip_level][fee_type]

        # 默認費率
        if instrument_type == InstrumentType.SPOT:
            return self.spot_maker_fee if order_type == OrderType.LIMIT else self.spot_taker_fee
        else:  # FUTURES
            return self.futures_maker_fee if order_type == OrderType.LIMIT else self.futures_taker_fee


@dataclass
class FeeCost:
    """手續費成本詳情"""
    base_fee: float                # 基礎手續費
    discount: float = 0.0          # 折扣金額
    rebate: float = 0.0            # 返佣金額
    final_fee: float = 0.0         # 最終手續費
    fee_rate: float = 0.0          # 實際費率
    vip_level: str = 'VIP0'        # VIP等級

    def __post_init__(self):
        """計算最終手續費"""
        self.final_fee = max(self.base_fee - self.discount + self.rebate, 0)


class FeeCalculator:
    """手續費計算器

    提供精確的交易手續費計算，支援多種費率結構

    Example:
        >>> calculator = FeeCalculator()
        >>> cost = calculator.calculate_trading_fee(
        ...     order_type=OrderType.LIMIT,
        ...     notional_value=10000,
        ...     instrument_type=InstrumentType.FUTURES
        ... )
        >>> cost.final_fee
        2.0  # $10000 * 0.0002 = $2
    """

    def __init__(
        self,
        fee_structure: Optional[FeeStructure] = None,
        default_vip_level: str = 'VIP0',
        enable_rebates: bool = False
    ):
        """初始化手續費計算器

        Args:
            fee_structure: 費率結構（默認使用標準結構）
            default_vip_level: 默認VIP等級
            enable_rebates: 是否啟用返佣
        """
        self.fee_structure = fee_structure or FeeStructure()
        self.default_vip_level = default_vip_level
        self.enable_rebates = enable_rebates

        # 統計信息
        self.total_fees_paid = 0.0
        self.total_rebates = 0.0
        self.fee_count = 0

    def calculate_trading_fee(
        self,
        order_type: OrderType,
        notional_value: float,
        instrument_type: InstrumentType = InstrumentType.FUTURES,
        vip_level: Optional[str] = None,
        apply_discount: float = 0.0
    ) -> FeeCost:
        """計算交易手續費

        Args:
            order_type: 訂單類型（limit/market）
            notional_value: 名義價值（價格 × 數量）
            instrument_type: 交易工具類型
            vip_level: VIP等級（可選）
            apply_discount: 額外折扣率（0-1）

        Returns:
            FeeCost: 手續費成本詳情

        Example:
            >>> calc = FeeCalculator(default_vip_level='VIP3')
            >>> cost = calc.calculate_trading_fee(
            ...     OrderType.LIMIT,
            ...     10000,
            ...     InstrumentType.FUTURES
            ... )
            >>> cost.final_fee
            1.2  # $10000 * 0.00012
        """
        vip_level = vip_level or self.default_vip_level

        # 獲取費率
        fee_rate = self.fee_structure.get_fee_rate(
            instrument_type,
            order_type,
            vip_level
        )

        # 計算基礎手續費
        base_fee = notional_value * fee_rate

        # 應用折扣
        discount = base_fee * apply_discount if apply_discount > 0 else 0.0

        # 計算返佣（僅 Maker 訂單且 VIP9）
        rebate = 0.0
        if self.enable_rebates and order_type == OrderType.LIMIT and vip_level == 'VIP9':
            # VIP9 Maker 返佣 (負費率)
            rebate = abs(base_fee)  # 返佣等於手續費

        # 應用最小手續費
        final_fee = max(base_fee - discount - rebate, self.fee_structure.min_fee)

        # 更新統計
        self.total_fees_paid += final_fee
        self.total_rebates += rebate
        self.fee_count += 1

        return FeeCost(
            base_fee=base_fee,
            discount=discount,
            rebate=rebate,
            final_fee=final_fee,
            fee_rate=fee_rate,
            vip_level=vip_level
        )

    def calculate_round_trip_fee(
        self,
        notional_value: float,
        instrument_type: InstrumentType = InstrumentType.FUTURES,
        entry_order_type: OrderType = OrderType.LIMIT,
        exit_order_type: OrderType = OrderType.MARKET,
        vip_level: Optional[str] = None
    ) -> float:
        """計算往返手續費（開倉 + 平倉）

        Args:
            notional_value: 名義價值
            instrument_type: 交易工具類型
            entry_order_type: 開倉訂單類型
            exit_order_type: 平倉訂單類型
            vip_level: VIP等級

        Returns:
            float: 總手續費

        Example:
            >>> calc = FeeCalculator()
            >>> total_fee = calc.calculate_round_trip_fee(10000)
            >>> total_fee
            6.0  # (0.0002 + 0.0004) * 10000
        """
        # 開倉手續費
        entry_fee = self.calculate_trading_fee(
            entry_order_type,
            notional_value,
            instrument_type,
            vip_level
        )

        # 平倉手續費
        exit_fee = self.calculate_trading_fee(
            exit_order_type,
            notional_value,
            instrument_type,
            vip_level
        )

        return entry_fee.final_fee + exit_fee.final_fee

    def estimate_daily_fees(
        self,
        daily_volume: float,
        instrument_type: InstrumentType = InstrumentType.FUTURES,
        maker_ratio: float = 0.6,
        vip_level: Optional[str] = None
    ) -> Dict[str, float]:
        """估算每日手續費

        Args:
            daily_volume: 每日交易量
            instrument_type: 交易工具類型
            maker_ratio: Maker訂單比例（0-1）
            vip_level: VIP等級

        Returns:
            Dict: 費用估算詳情
        """
        vip_level = vip_level or self.default_vip_level

        # Maker 和 Taker 交易量
        maker_volume = daily_volume * maker_ratio
        taker_volume = daily_volume * (1 - maker_ratio)

        # 計算費用
        maker_fee_cost = self.calculate_trading_fee(
            OrderType.LIMIT,
            maker_volume,
            instrument_type,
            vip_level
        )

        taker_fee_cost = self.calculate_trading_fee(
            OrderType.MARKET,
            taker_volume,
            instrument_type,
            vip_level
        )

        total_fee = maker_fee_cost.final_fee + taker_fee_cost.final_fee

        return {
            'daily_volume': daily_volume,
            'maker_volume': maker_volume,
            'taker_volume': taker_volume,
            'maker_fee': maker_fee_cost.final_fee,
            'taker_fee': taker_fee_cost.final_fee,
            'total_fee': total_fee,
            'fee_rate': total_fee / daily_volume if daily_volume > 0 else 0,
            'maker_rebate': maker_fee_cost.rebate,
            'vip_level': vip_level
        }

    def get_statistics(self) -> Dict[str, float]:
        """獲取手續費統計信息

        Returns:
            Dict: 統計信息
        """
        return {
            'total_fees_paid': self.total_fees_paid,
            'total_rebates': self.total_rebates,
            'net_fees': self.total_fees_paid - self.total_rebates,
            'fee_count': self.fee_count,
            'avg_fee': self.total_fees_paid / self.fee_count if self.fee_count > 0 else 0
        }

    def reset_statistics(self):
        """重置統計信息"""
        self.total_fees_paid = 0.0
        self.total_rebates = 0.0
        self.fee_count = 0


# ===== 便捷函數 =====

def calculate_simple_fee(
    notional_value: float,
    fee_rate: float = 0.0004
) -> float:
    """簡化的手續費計算

    Args:
        notional_value: 名義價值
        fee_rate: 費率（默認0.04% Taker）

    Returns:
        float: 手續費

    Example:
        >>> calculate_simple_fee(10000)
        4.0
    """
    return notional_value * fee_rate


def get_binance_vip_requirements() -> Dict[str, Dict]:
    """獲取 Binance VIP 等級要求

    Returns:
        Dict: VIP等級要求（30日交易量和BNB持倉）
    """
    return {
        'VIP0': {'volume_30d': 0, 'bnb_balance': 0},
        'VIP1': {'volume_30d': 250, 'bnb_balance': 50},  # $250K, 50 BNB
        'VIP2': {'volume_30d': 2500, 'bnb_balance': 200},
        'VIP3': {'volume_30d': 7500, 'bnb_balance': 500},
        'VIP4': {'volume_30d': 22500, 'bnb_balance': 1000},
        'VIP5': {'volume_30d': 50000, 'bnb_balance': 2000},
        'VIP6': {'volume_30d': 100000, 'bnb_balance': 3500},
        'VIP7': {'volume_30d': 200000, 'bnb_balance': 6000},
        'VIP8': {'volume_30d': 400000, 'bnb_balance': 9000},
        'VIP9': {'volume_30d': 750000, 'bnb_balance': 11000},
    }
