"""
Strategy Compatibility Layer v0.4

v0.3 策略兼容層 - 確保舊版策略能在新框架中運行

這個模組提供包裝器和轉換器，使得：
1. v0.3 的舊版策略（基於 on_bar）可以在 v0.4 框架中運行
2. v0.4 的新版策略（基於 compute_signals）可以在舊版引擎中運行

設計原則：
- 100% 向後兼容 v0.3 策略
- 無需修改現有策略代碼
- 透明的接口轉換
- 性能損耗最小化

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from typing import Dict, List, Any, Optional
import pandas as pd
from backtest.engine import BaseStrategy as V03BaseStrategy
from backtest.broker import SimulatedBroker
from strategies.api_v2 import (
    BaseStrategy as V2BaseStrategy,
    ParameterSpec,
    DataRequirement,
    DataSource,
    ParameterType
)


class V03StrategyWrapper(V2BaseStrategy):
    """v0.3 策略包裝器

    將 v0.3 的舊版策略包裝成 v2.0 API 兼容的策略

    這個包裝器讓舊版策略（使用 on_bar 接口）可以在新框架中運行，
    而無需修改原有策略代碼。

    Example:
        >>> # v0.3 舊版策略
        >>> from strategies.simple_sma import SimpleSMAStrategy
        >>>
        >>> # 包裝成 v2.0 API
        >>> wrapped_strategy = V03StrategyWrapper(
        ...     v03_strategy_class=SimpleSMAStrategy,
        ...     strategy_params={'sma_period': 20}
        ... )
        >>>
        >>> # 現在可以使用 v2.0 API
        >>> signals = wrapped_strategy.compute_signals(data, params)
    """

    def __init__(self, v03_strategy_class: type, strategy_params: Optional[Dict[str, Any]] = None):
        """初始化包裝器

        Args:
            v03_strategy_class: v0.3 策略類別（繼承自 backtest.engine.BaseStrategy）
            strategy_params: 策略構造參數（傳遞給 v0.3 策略的 __init__）

        Example:
            >>> wrapper = V03StrategyWrapper(
            ...     SimpleSMAStrategy,
            ...     {'sma_period': 20}
            ... )
        """
        super().__init__()
        self.v03_strategy_class = v03_strategy_class
        self.strategy_params = strategy_params or {}

        # 從 v0.3 策略提取元數據
        self.name = v03_strategy_class.__name__
        self.version = "0.3 (wrapped)"
        self.author = "Unknown"
        self.description = f"v0.3 策略包裝: {v03_strategy_class.__name__}"

    def get_parameters(self) -> Dict[str, ParameterSpec]:
        """返回策略參數規格

        v0.3 策略沒有標準參數規格，這裡基於構造參數推斷

        Returns:
            推斷的參數規格（基本類型檢測）
        """
        # v0.3 策略沒有聲明參數，返回空字典
        # 或者基於 strategy_params 推斷基本規格
        inferred_params = {}

        for param_name, param_value in self.strategy_params.items():
            # 簡單類型推斷
            if isinstance(param_value, int):
                param_type = ParameterType.INT
            elif isinstance(param_value, float):
                param_type = ParameterType.FLOAT
            elif isinstance(param_value, bool):
                param_type = ParameterType.BOOL
            elif isinstance(param_value, str):
                param_type = ParameterType.STR
            else:
                param_type = ParameterType.STR  # 預設為字符串

            inferred_params[param_name] = ParameterSpec(
                param_type=param_type,
                default_value=param_value,
                description=f"v0.3 策略參數: {param_name}"
            )

        return inferred_params

    def get_data_requirements(self) -> List[DataRequirement]:
        """聲明數據需求

        v0.3 策略默認需要 OHLCV 數據

        Returns:
            默認的 OHLCV 數據需求
        """
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=200,  # 保守估計
                required=True
            )
        ]

    def compute_signals(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> pd.Series:
        """計算交易信號

        通過模擬 v0.3 的 on_bar 調用來生成信號

        Args:
            data: 數據字典（至少包含 'ohlcv'）
            params: 參數字典

        Returns:
            交易信號序列

        Note:
            這個方法通過創建臨時 broker 並模擬 on_bar 調用來獲取信號。
            性能可能不如原生 v2.0 策略，但確保了完全兼容。
        """
        if 'ohlcv' not in data:
            raise ValueError("Missing required data source: ohlcv")

        ohlcv = data['ohlcv']

        # 創建臨時 broker 用於捕獲交易信號
        broker = _SignalCaptureBroker(initial_cash=10000, fee_rate=0.0)

        # 合併構造參數和運行時參數
        merged_params = {**self.strategy_params, **params}

        # 實例化 v0.3 策略
        try:
            v03_strategy = self.v03_strategy_class(
                broker=broker,
                data=ohlcv,
                **merged_params
            )
        except TypeError:
            # 如果參數不匹配，嘗試只傳遞 broker 和 data
            v03_strategy = self.v03_strategy_class(
                broker=broker,
                data=ohlcv
            )

        # 模擬 on_bar 調用，捕獲信號
        signals = pd.Series(0, index=ohlcv.index)

        for i, (timestamp, row) in enumerate(ohlcv.iterrows()):
            # 重置信號捕獲器
            broker.reset_signal()

            # 調用策略的 on_bar
            v03_strategy.on_bar(i, row)

            # 記錄信號
            if broker.last_signal == 'buy':
                signals.iloc[i] = 1
            elif broker.last_signal == 'sell':
                signals.iloc[i] = -1
            else:
                signals.iloc[i] = 0

        return signals


class _SignalCaptureBroker:
    """信號捕獲器（內部使用）

    模擬 SimulatedBroker 接口，但只記錄信號而不實際交易

    這個類用於 V03StrategyWrapper 中，通過捕獲 buy/sell 調用
    來推斷策略的交易信號。
    """

    def __init__(self, initial_cash: float, fee_rate: float):
        """初始化信號捕獲器

        Args:
            initial_cash: 初始資金
            fee_rate: 手續費率
        """
        self.cash = initial_cash
        self.fee_rate = fee_rate
        self.position_qty = 0.0
        self.position_entry_price = 0.0
        self.has_position = False
        self.last_signal = None  # 'buy', 'sell', or None

    def buy_all(self, price: float, time):
        """記錄買入信號"""
        self.last_signal = 'buy'
        return True

    def sell_all(self, price: float, time):
        """記錄賣出信號"""
        self.last_signal = 'sell'
        return True

    def buy(self, size: float, price: float, time, leverage: float = 1.0):
        """記錄買入信號"""
        self.last_signal = 'buy'
        return True

    def sell(self, size: float, price: float, time):
        """記錄賣出信號"""
        self.last_signal = 'sell'
        return True

    def get_current_equity(self, price: float) -> float:
        """返回當前權益"""
        return self.cash

    def reset_signal(self):
        """重置信號"""
        self.last_signal = None


class V2toV03Adapter:
    """v2.0 策略適配器（可選）

    將 v2.0 策略適配為 v0.3 接口，使其可以在舊版引擎中運行

    Note:
        這個適配器主要用於測試和過渡期。
        推薦直接使用 v2.0 API 和新版引擎。

    Example:
        >>> # v2.0 新版策略
        >>> from strategies.simple_sma_v2 import SimpleSMAStrategyV2
        >>>
        >>> # 適配為 v0.3 接口
        >>> v03_strategy = V2toV03Adapter.adapt(
        ...     v2_strategy=SimpleSMAStrategyV2(),
        ...     broker=broker,
        ...     data=ohlcv,
        ...     params={'short_window': 10, 'long_window': 20}
        ... )
        >>>
        >>> # 可以使用 v0.3 的 on_bar 接口
        >>> for i, row in enumerate(ohlcv.itertuples()):
        ...     v03_strategy.on_bar(i, row)
    """

    @staticmethod
    def adapt(v2_strategy: V2BaseStrategy,
              broker: SimulatedBroker,
              data: pd.DataFrame,
              params: Optional[Dict[str, Any]] = None) -> V03BaseStrategy:
        """適配 v2.0 策略為 v0.3 接口

        Args:
            v2_strategy: v2.0 策略實例
            broker: v0.3 broker 實例
            data: OHLCV 數據
            params: 策略參數（可選）

        Returns:
            適配後的 v0.3 策略實例

        Example:
            >>> v2_strategy = SimpleSMAStrategyV2()
            >>> v03_strategy = V2toV03Adapter.adapt(
            ...     v2_strategy, broker, data, {'short_window': 10}
            ... )
        """
        # 驗證並規範化參數
        if params is None:
            params = {}

        validated_params = v2_strategy.validate_parameters(params)

        # 預計算信號（v2.0 策略是批量計算）
        data_dict = {'ohlcv': data}
        signals = v2_strategy.compute_signals(data_dict, validated_params)

        # 創建適配器實例
        adapted_strategy = _V2StrategyAdapter(broker, data, signals)

        return adapted_strategy


class _V2StrategyAdapter(V03BaseStrategy):
    """v2.0 策略適配器實現（內部使用）

    實現 v0.3 的 on_bar 接口，基於預計算的信號執行交易
    """

    def __init__(self, broker: SimulatedBroker, data: pd.DataFrame, signals: pd.Series):
        """初始化適配器

        Args:
            broker: v0.3 broker 實例
            data: OHLCV 數據
            signals: 預計算的信號序列
        """
        super().__init__(broker, data)
        self.signals = signals
        self.prev_signal = 0

    def on_bar(self, i: int, row: pd.Series):
        """實作 v0.3 的 on_bar 接口

        基於預計算的信號執行交易

        Args:
            i: 當前索引
            row: 當前 K 線數據
        """
        # 獲取當前信號
        current_signal = self.signals.iloc[i] if i < len(self.signals) else 0

        current_price = row['close']
        current_time = row.name

        # 信號變化時執行交易
        if current_signal == 1 and self.prev_signal != 1:
            # 買入信號
            if not self.broker.has_position:
                self.broker.buy_all(price=current_price, time=current_time)
        elif current_signal == -1 and self.prev_signal != -1:
            # 賣出信號
            if self.broker.has_position:
                self.broker.sell_all(price=current_price, time=current_time)

        self.prev_signal = current_signal


# 便捷函數

def wrap_v03_strategy(strategy_class: type, **strategy_params) -> V03StrategyWrapper:
    """快速包裝 v0.3 策略

    Args:
        strategy_class: v0.3 策略類別
        **strategy_params: 策略構造參數

    Returns:
        包裝後的 v2.0 兼容策略

    Example:
        >>> from strategies.simple_sma import SimpleSMAStrategy
        >>> wrapped = wrap_v03_strategy(SimpleSMAStrategy, sma_period=20)
    """
    return V03StrategyWrapper(strategy_class, strategy_params)
