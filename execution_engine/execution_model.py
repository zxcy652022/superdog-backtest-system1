"""
Realistic Execution Engine v0.6 Phase 3

真實執行模型核心引擎 - 整合所有成本模型

核心功能:
- 整合手續費、滑價、資金費用、強平風險
- 真實交易成本計算
- 風險檢查和驗證
- 執行結果追蹤

Version: v0.6.0-phase3
Design Reference: docs/specs/v0.6/superdog_v06_execution_model_spec.md
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime

from .fee_models import FeeCalculator, FeeStructure, FeeCost, InstrumentType, OrderType
from .slippage_models import SlippageModel, SlippageConfig, SlippageResult, SymbolTier, SlippageModelType
from .funding_models import FundingModel, FundingConfig, FundingResult
from .liquidation_models import LiquidationModel, MarginConfig, LiquidationResult, RiskLevel


@dataclass
class ExecutionConfig:
    """執行模型配置

    Example:
        >>> config = ExecutionConfig(
        ...     enable_fees=True,
        ...     enable_slippage=True,
        ...     enable_funding=True,
        ...     enable_liquidation_check=True
        ... )
    """

    # 啟用各項功能
    enable_fees: bool = True
    enable_slippage: bool = True
    enable_funding: bool = True
    enable_liquidation_check: bool = True

    # 子模型配置
    fee_structure: FeeStructure = field(default_factory=FeeStructure)
    slippage_config: SlippageConfig = field(default_factory=SlippageConfig)
    funding_config: FundingConfig = field(default_factory=FundingConfig)
    margin_config: MarginConfig = field(default_factory=MarginConfig)

    # 執行參數
    slippage_model_type: SlippageModelType = SlippageModelType.ADAPTIVE
    default_vip_level: str = 'VIP0'
    max_leverage: float = 20
    max_order_value: float = 1000000  # USD


@dataclass
class TradeExecution:
    """交易執行結果"""
    # 基本信息
    symbol: str
    side: str  # 'buy'/'sell'
    size: float
    price: float
    timestamp: datetime

    # 成本明細
    fee_cost: FeeCost
    slippage_result: Optional[SlippageResult] = None
    funding_result: Optional[FundingResult] = None
    liquidation_result: Optional[LiquidationResult] = None

    # 總成本
    total_cost: float = 0.0
    execution_price: float = 0.0  # 實際成交價格

    # 狀態
    status: str = 'executed'  # 'executed'/'rejected'/'liquidated'
    reason: str = ''

    def __post_init__(self):
        """計算總成本和實際成交價格"""
        self.total_cost = self.fee_cost.final_fee

        if self.slippage_result:
            self.total_cost += self.slippage_result.slippage_cost

        # 計算實際成交價格（包含滑價）
        if self.slippage_result:
            slippage_rate = self.slippage_result.slippage_rate
            if self.side == 'buy':
                self.execution_price = self.price * (1 + slippage_rate)
            else:
                self.execution_price = self.price * (1 - slippage_rate)
        else:
            self.execution_price = self.price


class RealisticExecutionEngine:
    """真實執行模型引擎

    整合所有成本模型，提供接近實盤的回測執行

    Example:
        >>> engine = RealisticExecutionEngine()
        >>> execution = engine.execute_trade(
        ...     symbol='BTCUSDT',
        ...     side='buy',
        ...     size=1.0,
        ...     price=50000,
        ...     order_type=OrderType.MARKET,
        ...     account_balance=10000,
        ...     leverage=10
        ... )
        >>> execution.total_cost
        26.0  # 手續費 + 滑價
    """

    def __init__(self, config: Optional[ExecutionConfig] = None):
        """初始化執行引擎

        Args:
            config: 執行配置（可選）
        """
        self.config = config or ExecutionConfig()

        # 初始化各個模型
        self.fee_calculator = FeeCalculator(
            self.config.fee_structure,
            self.config.default_vip_level
        )

        self.slippage_model = SlippageModel(
            self.config.slippage_model_type,
            self.config.slippage_config
        )

        self.funding_model = FundingModel(self.config.funding_config)
        self.liquidation_model = LiquidationModel(self.config.margin_config)

        # 統計信息
        self.total_executions = 0
        self.total_trading_cost = 0.0
        self.total_slippage_cost = 0.0
        self.total_funding_cost = 0.0

    def execute_trade(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        order_type: OrderType = OrderType.MARKET,
        instrument_type: InstrumentType = InstrumentType.FUTURES,
        symbol_tier: SymbolTier = SymbolTier.LARGE_CAP,
        avg_volume_24h: float = 1000000,
        volatility: float = 0.02,
        account_balance: Optional[float] = None,
        leverage: float = 1.0,
        vip_level: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> TradeExecution:
        """執行交易

        Args:
            symbol: 交易對
            side: 交易方向 ('buy'/'sell')
            size: 數量
            price: 價格
            order_type: 訂單類型
            instrument_type: 交易工具類型
            symbol_tier: 幣種分級
            avg_volume_24h: 24h平均成交量
            volatility: 波動率
            account_balance: 賬戶餘額（用於風險檢查）
            leverage: 槓桿倍數
            vip_level: VIP等級
            timestamp: 時間戳

        Returns:
            TradeExecution: 執行結果
        """
        timestamp = timestamp or datetime.now()
        order_value = size * price

        # 1. 計算手續費
        fee_cost = self.fee_calculator.calculate_trading_fee(
            order_type,
            order_value,
            instrument_type,
            vip_level
        ) if self.config.enable_fees else FeeCost(base_fee=0, final_fee=0)

        # 2. 計算滑價
        slippage_result = None
        if self.config.enable_slippage:
            slippage_result = self.slippage_model.calculate_slippage(
                size,
                order_value,
                avg_volume_24h,
                volatility,
                symbol_tier,
                order_type
            )

        # 3. 風險檢查（如果提供了賬戶餘額）
        liquidation_result = None
        if self.config.enable_liquidation_check and account_balance is not None and leverage > 1:
            liquidation_result = self.liquidation_model.check_liquidation_risk(
                position_size=size,
                position_side=side,
                entry_price=price,
                current_price=price,
                account_balance=account_balance,
                leverage=leverage
            )

            # 如果風險過高，拒絕執行
            if liquidation_result.risk_level in [RiskLevel.CRITICAL, RiskLevel.LIQUIDATED]:
                return TradeExecution(
                    symbol=symbol,
                    side=side,
                    size=size,
                    price=price,
                    timestamp=timestamp,
                    fee_cost=fee_cost,
                    slippage_result=slippage_result,
                    liquidation_result=liquidation_result,
                    status='rejected',
                    reason=f'High liquidation risk: {liquidation_result.risk_level.value}'
                )

        # 4. 創建執行結果
        execution = TradeExecution(
            symbol=symbol,
            side=side,
            size=size,
            price=price,
            timestamp=timestamp,
            fee_cost=fee_cost,
            slippage_result=slippage_result,
            liquidation_result=liquidation_result
        )

        # 5. 更新統計
        self.total_executions += 1
        self.total_trading_cost += execution.total_cost
        if slippage_result:
            self.total_slippage_cost += slippage_result.slippage_cost

        return execution

    def calculate_position_funding(
        self,
        position_size: float,
        position_side: str,
        entry_time: datetime,
        exit_time: datetime,
        entry_price: float,
        funding_rate_data: Optional = None
    ) -> FundingResult:
        """計算持倉的 Funding 費用

        Args:
            position_size: 持倉數量
            position_side: 持倉方向
            entry_time: 開倉時間
            exit_time: 平倉時間
            entry_price: 開倉價格
            funding_rate_data: Funding Rate 數據

        Returns:
            FundingResult: Funding 費用結果
        """
        if not self.config.enable_funding:
            return FundingResult(
                total_funding_cost=0,
                num_funding_events=0,
                avg_funding_rate=0,
                funding_events=[]
            )

        result = self.funding_model.calculate_funding_cost(
            position_size,
            position_side,
            entry_time,
            exit_time,
            entry_price,
            funding_rate_data
        )

        self.total_funding_cost += result.total_funding_cost
        return result

    def get_execution_summary(self) -> Dict:
        """獲取執行摘要統計

        Returns:
            Dict: 統計信息
        """
        return {
            'total_executions': self.total_executions,
            'total_trading_cost': self.total_trading_cost,
            'total_slippage_cost': self.total_slippage_cost,
            'total_funding_cost': self.total_funding_cost,
            'avg_cost_per_trade': (
                self.total_trading_cost / self.total_executions
                if self.total_executions > 0 else 0
            ),
            'fee_stats': self.fee_calculator.get_statistics(),
            'slippage_stats': self.slippage_model.get_statistics(),
            'funding_stats': self.funding_model.get_statistics(),
            'liquidation_stats': self.liquidation_model.get_statistics()
        }

    def reset_statistics(self):
        """重置所有統計信息"""
        self.total_executions = 0
        self.total_trading_cost = 0.0
        self.total_slippage_cost = 0.0
        self.total_funding_cost = 0.0

        self.fee_calculator.reset_statistics()
        self.slippage_model.reset_statistics()
        self.funding_model.reset_statistics()
        self.liquidation_model.reset_statistics()


# ===== 便捷函數 =====

def create_default_engine() -> RealisticExecutionEngine:
    """創建默認配置的執行引擎

    Returns:
        RealisticExecutionEngine: 執行引擎實例
    """
    return RealisticExecutionEngine()


def create_conservative_engine() -> RealisticExecutionEngine:
    """創建保守配置的執行引擎（更高的成本估算）

    Returns:
        RealisticExecutionEngine: 執行引擎實例
    """
    config = ExecutionConfig(
        slippage_model_type=SlippageModelType.ADAPTIVE,
        max_leverage=5
    )
    return RealisticExecutionEngine(config)
