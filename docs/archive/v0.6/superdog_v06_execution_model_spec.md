# SuperDog v0.6 真實執行模型技術規格
**Realistic Execution Model Technical Specification**

---

## 💰 系統概述

真實執行模型旨在提供接近實盤交易的回測精度，通過模擬真實交易成本、滑價影響、資金費用和強平風險，讓回測結果更貼近實際交易表現。

### 核心目標
- **真實成本模擬**: Maker/Taker費率、滑價影響
- **永續合約特性**: Funding費用、強平風險
- **風險控制**: 保證金管理、槓桿限制
- **精確建模**: 基於真實市場數據的模型參數

---

## 🏗️ 架構設計

### 模組結構
```
execution_engine/
├── execution_model.py          # 核心執行模型
├── fee_models.py              # 手續費模型
├── slippage_models.py         # 滑價模型
├── funding_models.py          # 資金費用模型
├── liquidation_models.py      # 強平風險模型
└── market_impact.py           # 市場影響模型

risk_management/
├── margin_calculator.py       # 保證金計算
├── leverage_manager.py        # 槓桿管理
└── position_sizer.py          # 倉位計算
```

### 執行流程
```
交易信號 → 訂單生成 → 成本計算 → 風險檢查 → 執行確認 → 持倉更新
    ↓         ↓         ↓         ↓         ↓         ↓
  策略信號   訂單類型   手續費+滑價  保證金檢查  實際成交   資金費用
```

---

## 💸 手續費模型

### 基礎費率結構
```python
@dataclass
class FeeStructure:
    """手續費結構定義"""

    # 現貨交易費率
    spot_maker_fee: float = 0.001      # 0.1% Maker
    spot_taker_fee: float = 0.001      # 0.1% Taker

    # 永續合約費率
    futures_maker_fee: float = 0.0002  # 0.02% Maker
    futures_taker_fee: float = 0.0004  # 0.04% Taker

    # VIP等級費率
    vip_levels: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'VIP1': {'maker': 0.00015, 'taker': 0.00035},
        'VIP2': {'maker': 0.00010, 'taker': 0.00030},
        'VIP3': {'maker': 0.00005, 'taker': 0.00025},
    })

class FeeCalculator:
    """手續費計算器"""

    def calculate_trading_fee(self, order_type: str, notional_value: float,
                             instrument_type: str = 'futures') -> float:
        """計算交易手續費"""

        # 基礎費率
        if instrument_type == 'spot':
            base_rate = (self.fee_structure.spot_maker_fee if order_type == 'limit'
                        else self.fee_structure.spot_taker_fee)
        else:  # futures
            base_rate = (self.fee_structure.futures_maker_fee if order_type == 'limit'
                        else self.fee_structure.futures_taker_fee)

        return notional_value * base_rate
```

---

## 📊 滑價模型

### 多層滑價計算
```python
class SlippageModel:
    """滑價影響模型"""

    def __init__(self, model_type: str = 'adaptive'):
        self.model_type = model_type

        # 基礎滑價參數
        self.base_slippage = {
            'large_cap': 0.0001,    # 大盤股基礎滑價 0.01%
            'mid_cap': 0.0003,      # 中盤股 0.03%
            'small_cap': 0.0008,    # 小盤股 0.08%
            'micro_cap': 0.002,     # 微盤股 0.2%
        }

    def calculate_slippage(self, order_size: float, avg_volume: float,
                          volatility: float, symbol_tier: str,
                          order_type: str = 'market') -> float:
        """計算訂單滑價"""

        if order_type == 'limit':
            return 0  # 限價單假設無滑價

        # 基礎滑價
        base_slip = self.base_slippage.get(symbol_tier, 0.001)

        # 根據模型類型計算
        if self.model_type == 'adaptive':
            return self._adaptive_slippage(order_size, avg_volume, volatility, base_slip)
        else:
            return base_slip

    def _adaptive_slippage(self, order_size: float, avg_volume: float,
                          volatility: float, base_slip: float) -> float:
        """自適應滑價模型"""

        volume_ratio = order_size / avg_volume

        # 基於訂單大小的影響
        if volume_ratio < 0.01:  # <1% 平均成交量
            size_impact = volume_ratio * 0.05
        elif volume_ratio < 0.05:  # 1-5% 平均成交量
            size_impact = 0.0005 + (volume_ratio - 0.01) * 0.1
        else:  # >5% 平均成交量
            size_impact = 0.0045 + np.sqrt(volume_ratio - 0.05) * 0.15

        # 波動率調整
        volatility_multiplier = 1 + min(volatility * 2, 1)

        total_slippage = (base_slip + size_impact) * volatility_multiplier
        return min(total_slippage, 0.01)  # 最大1%滑價
```

---

## 💰 資金費用模型

### Funding費用計算
```python
class FundingModel:
    """永續合約資金費用模型"""

    def __init__(self, funding_interval_hours: int = 8):
        self.funding_interval_hours = funding_interval_hours
        self.funding_times_utc = [0, 8, 16]  # Binance funding時間

    def calculate_funding_cost(self, position, funding_rate_data: pd.DataFrame) -> float:
        """計算持倉期間的總資金費用"""

        total_funding = 0.0
        current_time = position.entry_time

        while current_time < position.exit_time:
            # 找到下一個funding時間
            next_funding_time = self._get_next_funding_time(current_time)

            if next_funding_time <= position.exit_time:
                # 獲取該時點的funding rate
                funding_rate = self._get_funding_rate_at_time(
                    funding_rate_data, next_funding_time
                )

                # 計算funding cost
                position_value = position.size * self._get_price_at_time(next_funding_time)
                direction = 1 if position.side == 'long' else -1

                funding_cost = position_value * funding_rate * direction
                total_funding += funding_cost

                current_time = next_funding_time
            else:
                break

        return total_funding
```

---

## ⚠️ 強平風險模型

### 保證金與強平計算
```python
class LiquidationModel:
    """強平風險模型"""

    def __init__(self, initial_margin_rate: float = 0.1,
                 maintenance_margin_rate: float = 0.05):
        self.initial_margin_rate = initial_margin_rate
        self.maintenance_margin_rate = maintenance_margin_rate

    def calculate_liquidation_price(self, position) -> float:
        """計算強平價格"""

        if position.side == 'long':
            # 多頭強平價格
            liquidation_price = position.entry_price * (
                1 - self.maintenance_margin_rate + 0.0008  # 加上手續費估算
            )
        else:  # short
            # 空頭強平價格
            liquidation_price = position.entry_price * (
                1 + self.maintenance_margin_rate + 0.0008
            )

        return liquidation_price

    def check_liquidation_risk(self, position, current_price: float,
                              account_balance: float) -> Dict:
        """檢查強平風險"""

        # 計算未實現盈虧
        if position.side == 'long':
            unrealized_pnl = (current_price - position.entry_price) * position.size
        else:
            unrealized_pnl = (position.entry_price - current_price) * position.size

        # 計算保證金比率
        position_value = position.size * current_price
        available_margin = account_balance + unrealized_pnl
        margin_ratio = available_margin / position_value

        # 強平價格
        liquidation_price = self.calculate_liquidation_price(position)

        # 風險等級評估
        if margin_ratio < 0.02:
            risk_level = 'CRITICAL'
        elif margin_ratio < 0.05:
            risk_level = 'HIGH'
        elif margin_ratio < 0.1:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'

        return {
            'risk_level': risk_level,
            'margin_ratio': margin_ratio,
            'liquidation_price': liquidation_price,
            'is_liquidated': margin_ratio <= 0,
            'unrealized_pnl': unrealized_pnl
        }
```

---

## 🎯 執行模型整合

### 核心執行引擎
```python
class RealisticExecutionEngine:
    """真實執行模型引擎"""

    def __init__(self, config: ExecutionConfig):
        self.config = config
        self.fee_calculator = FeeCalculator(config.fee_structure)
        self.slippage_model = SlippageModel(config.slippage_model_type)
        self.funding_model = FundingModel(config.funding_interval_hours)
        self.liquidation_model = LiquidationModel()

    def execute_trade(self, signal: TradeSignal, market_data: MarketData,
                     account: Account) -> TradeExecution:
        """執行交易信號"""

        # 1. 生成訂單
        order = self._create_order(signal, account)

        # 2. 計算交易成本
        trading_costs = self._calculate_total_costs(order, market_data)

        # 3. 風險檢查
        risk_check = self._perform_risk_checks(order, account)
        if not risk_check.approved:
            return TradeExecution(status='rejected', reason=risk_check.reason)

        # 4. 執行訂單
        execution_result = self._execute_order(order, market_data, trading_costs)

        # 5. 更新賬戶狀態
        self._update_account(account, execution_result)

        return execution_result

    def _calculate_total_costs(self, order: Order, market_data: MarketData) -> TradingCosts:
        """計算總交易成本"""

        # 手續費
        trading_fee = self.fee_calculator.calculate_trading_fee(
            order.type, order.notional_value, order.instrument_type
        )

        # 滑價成本
        slippage_cost = 0
        if order.type == 'market':
            slippage_rate = self.slippage_model.calculate_slippage(
                order.size, market_data.avg_volume, market_data.volatility,
                market_data.symbol_tier, order.type
            )
            slippage_cost = order.notional_value * slippage_rate

        return TradingCosts(
            trading_fee=trading_fee,
            slippage_cost=slippage_cost,
            total_cost=trading_fee + slippage_cost
        )

@dataclass
class ExecutionConfig:
    """執行配置"""

    fee_structure: FeeStructure = field(default_factory=FeeStructure)
    slippage_model_type: str = 'adaptive'
    funding_interval_hours: int = 8
    apply_funding_costs: bool = True
    enable_liquidation_simulation: bool = True
    max_leverage: float = 20
    max_order_value: float = 1000000

@dataclass
class TradingCosts:
    """交易成本結構"""

    trading_fee: float
    slippage_cost: float
    total_cost: float
```

---

## 🔧 CLI整合

### 命令接口
```python
@click.group(name='execution')
def execution_commands():
    """真實執行模型命令"""
    pass

@execution_commands.command()
@click.option('--config', type=click.Path(exists=True), help='執行配置文件')
def simulate(config):
    """模擬真實執行成本"""
    pass

@execution_commands.command()
@click.argument('strategy')
@click.option('--execution-model', default='realistic', help='執行模型類型')
def backtest(strategy, execution_model):
    """使用真實執行模型進行回測"""
    pass
```

---

## 📊 驗證與監控

### 模型驗證
```python
class ModelValidation:
    """模型驗證器"""

    def validate_slippage_model(self, historical_executions: pd.DataFrame,
                               model_predictions: pd.DataFrame) -> Dict:
        """驗證滑價模型準確性"""

        prediction_error = abs(historical_executions['actual_slippage'] -
                              model_predictions['predicted_slippage'])

        mae = prediction_error.mean()
        correlation = historical_executions['actual_slippage'].corr(
            model_predictions['predicted_slippage']
        )

        return {
            'mae_bps': mae * 10000,
            'correlation': correlation,
            'accuracy_within_10bps': (prediction_error < 0.001).mean()
        }
```

這個技術規格為SuperDog v0.6提供了完整的真實執行模型設計，確保回測結果更接近實盤交易表現。
