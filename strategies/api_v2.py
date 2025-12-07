"""
Strategy API v2.0 - 核心接口定義

基於技術規格 docs/specs/planned/v0.4_strategy_api_spec.md
實作標準化策略接口與參數系統

Version: v2.0
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd


class ParameterType(Enum):
    """參數類型枚舉

    定義策略參數支援的數據類型
    """
    FLOAT = "float"
    INT = "int"
    STR = "str"
    BOOL = "bool"


@dataclass
class ParameterSpec:
    """參數規格定義

    定義策略參數的完整規格，包括類型、預設值、描述、驗證範圍等

    Attributes:
        param_type: 參數類型（ParameterType 枚舉）
        default_value: 預設值
        description: 參數描述（用於 CLI 幫助信息）
        min_value: 最小值限制（可選，用於數值類型）
        max_value: 最大值限制（可選，用於數值類型）
        choices: 可選值列表（可選，用於字符串類型）

    Example:
        >>> ParameterSpec(
        ...     param_type=ParameterType.INT,
        ...     default_value=20,
        ...     description="SMA週期",
        ...     min_value=5,
        ...     max_value=200
        ... )
    """
    param_type: ParameterType
    default_value: Any
    description: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[List[str]] = None

    def validate(self, value: Any) -> Any:
        """驗證並轉換參數值

        Args:
            value: 待驗證的參數值

        Returns:
            驗證並轉換後的值

        Raises:
            ValueError: 參數值不符合規格要求
            TypeError: 參數類型無法轉換

        Example:
            >>> spec = ParameterSpec(ParameterType.INT, 10, "週期", min_value=5, max_value=50)
            >>> spec.validate(20)
            20
            >>> spec.validate(100)
            ValueError: Value 100 exceeds max_value 50
        """
        # 類型轉換
        try:
            if self.param_type == ParameterType.FLOAT:
                converted_value = float(value)
            elif self.param_type == ParameterType.INT:
                converted_value = int(value)
            elif self.param_type == ParameterType.STR:
                converted_value = str(value)
            elif self.param_type == ParameterType.BOOL:
                # 處理布林值的多種表示形式
                if isinstance(value, bool):
                    converted_value = value
                elif isinstance(value, str):
                    if value.lower() in ('true', 't', 'yes', 'y', '1'):
                        converted_value = True
                    elif value.lower() in ('false', 'f', 'no', 'n', '0'):
                        converted_value = False
                    else:
                        raise TypeError(f"Cannot convert '{value}' to bool")
                else:
                    converted_value = bool(value)
            else:
                raise TypeError(f"Unknown parameter type: {self.param_type}")
        except (ValueError, TypeError) as e:
            raise TypeError(
                f"Cannot convert value '{value}' to {self.param_type.value}: {e}"
            )

        # 範圍驗證（數值類型）
        if self.param_type in (ParameterType.FLOAT, ParameterType.INT):
            if self.min_value is not None and converted_value < self.min_value:
                raise ValueError(
                    f"Value {converted_value} is below min_value {self.min_value}"
                )
            if self.max_value is not None and converted_value > self.max_value:
                raise ValueError(
                    f"Value {converted_value} exceeds max_value {self.max_value}"
                )

        # 選項驗證（字符串類型）
        if self.param_type == ParameterType.STR and self.choices is not None:
            if converted_value not in self.choices:
                raise ValueError(
                    f"Value '{converted_value}' not in allowed choices: {self.choices}"
                )

        return converted_value


class DataSource(Enum):
    """數據源類型

    定義策略可用的數據源類型

    Note:
        v0.4 僅支援 OHLCV
        v0.5 將支援 FUNDING, OPEN_INTEREST, BASIS, VOLUME_PROFILE
    """
    OHLCV = "ohlcv"           # 基礎K線數據（v0.4 支援）
    FUNDING = "funding"       # 資金費率（v0.5 規劃）
    OPEN_INTEREST = "oi"      # 持倉量（v0.5 規劃）
    BASIS = "basis"           # 基差數據（v0.5 規劃）
    VOLUME_PROFILE = "vp"     # 成交量分佈（v0.5 規劃）


@dataclass
class DataRequirement:
    """數據需求定義

    定義策略所需的數據源及其配置

    Attributes:
        source: 數據源類型
        timeframe: 特定時間週期需求（可選，默認使用回測的時間週期）
        lookback_periods: 回望期數（用於計算指標所需的最小數據量）
        required: 是否為必需數據（True=缺少時報錯，False=缺少時跳過）

    Example:
        >>> DataRequirement(
        ...     source=DataSource.OHLCV,
        ...     lookback_periods=200,
        ...     required=True
        ... )
    """
    source: DataSource
    timeframe: Optional[str] = None  # 特定時間週期需求
    lookback_periods: int = 100      # 回望期數
    required: bool = True            # 是否必需


class BaseStrategy(ABC):
    """策略基底類別 v2.0

    所有策略必須繼承此類別並實作抽象方法

    v2.0 新增特性：
    - 參數規格聲明（get_parameters）
    - 數據需求聲明（get_data_requirements）
    - 信號計算接口（compute_signals）
    - 策略元數據（get_metadata）

    向後兼容：
    - 保留 v0.3 的 on_bar 接口（通過 compatibility 層支援）

    Example:
        >>> class MyStrategy(BaseStrategy):
        ...     def get_parameters(self):
        ...         return {
        ...             'period': ParameterSpec(ParameterType.INT, 20, "週期", 5, 200)
        ...         }
        ...
        ...     def get_data_requirements(self):
        ...         return [DataRequirement(DataSource.OHLCV, lookback_periods=200)]
        ...
        ...     def compute_signals(self, data, params):
        ...         # 計算交易信號邏輯
        ...         pass
    """

    def __init__(self):
        """初始化策略基本信息"""
        self.name = self.__class__.__name__
        self.version = "1.0"
        self.author = "Unknown"
        self.description = ""

    @abstractmethod
    def get_parameters(self) -> Dict[str, ParameterSpec]:
        """返回策略參數規格

        定義策略所需的所有參數及其規格
        CLI 將根據此規格自動生成命令選項

        Returns:
            Dict[str, ParameterSpec]: 參數名稱對應參數規格

        Example:
            >>> def get_parameters(self):
            ...     return {
            ...         'sma_short': ParameterSpec(
            ...             ParameterType.INT, 10, "短均線週期", 5, 50
            ...         ),
            ...         'sma_long': ParameterSpec(
            ...             ParameterType.INT, 20, "長均線週期", 10, 100
            ...         ),
            ...         'stop_loss': ParameterSpec(
            ...             ParameterType.FLOAT, 0.02, "停損比例", 0.01, 0.1
            ...         )
            ...     }
        """
        pass

    @abstractmethod
    def get_data_requirements(self) -> List[DataRequirement]:
        """聲明數據需求

        定義策略所需的所有數據源
        數據管道將根據此聲明自動載入數據

        Returns:
            List[DataRequirement]: 策略所需的數據源列表

        Example:
            >>> def get_data_requirements(self):
            ...     return [
            ...         DataRequirement(DataSource.OHLCV, lookback_periods=200),
            ...         DataRequirement(DataSource.FUNDING, required=False)
            ...     ]
        """
        pass

    @abstractmethod
    def compute_signals(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> pd.Series:
        """計算交易信號

        基於提供的數據和參數計算交易信號

        Args:
            data: 策略所需的所有數據，key 為數據源名稱（如 'ohlcv'）
            params: 策略參數字典，key 為參數名稱，value 為參數值

        Returns:
            pd.Series: 交易信號序列，index 為時間戳
                      值為：1 = 買入（做多），-1 = 賣出（做空），0 = 持有/無信號

        Raises:
            ValueError: 數據不足或參數無效

        Example:
            >>> def compute_signals(self, data, params):
            ...     ohlcv = data['ohlcv']
            ...     close = ohlcv['close']
            ...
            ...     sma_short = close.rolling(params['sma_short']).mean()
            ...     sma_long = close.rolling(params['sma_long']).mean()
            ...
            ...     signals = pd.Series(0, index=close.index)
            ...     signals[sma_short > sma_long] = 1   # 買入信號
            ...     signals[sma_short < sma_long] = -1  # 賣出信號
            ...
            ...     return signals

        Note:
            data 的格式：
            {
                'ohlcv': DataFrame with columns ['open', 'high', 'low', 'close', 'volume'],
                'funding': DataFrame with funding rate data (if requested),
                ...
            }

            返回的 signals Series 必須與 data['ohlcv'] 的 index 對齊
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """獲取策略元數據

        返回策略的描述性信息，用於策略列表、文檔生成等

        Returns:
            Dict[str, Any]: 策略元數據字典

        Example:
            >>> strategy = MyStrategy()
            >>> metadata = strategy.get_metadata()
            >>> print(metadata)
            {
                'name': 'MyStrategy',
                'version': '1.0',
                'author': 'Unknown',
                'description': '',
                'parameters': ['sma_short', 'sma_long', 'stop_loss'],
                'data_sources': ['ohlcv']
            }
        """
        return {
            'name': self.name,
            'version': self.version,
            'author': self.author,
            'description': self.description,
            'parameters': list(self.get_parameters().keys()),
            'data_sources': [req.source.value for req in self.get_data_requirements()]
        }

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """驗證並規範化參數

        檢查參數是否符合規格，並進行類型轉換

        Args:
            params: 待驗證的參數字典

        Returns:
            Dict[str, Any]: 驗證並轉換後的參數字典

        Raises:
            ValueError: 參數不符合規格

        Example:
            >>> strategy = MyStrategy()
            >>> validated = strategy.validate_parameters({'period': '20'})
            >>> print(validated)
            {'period': 20}
        """
        parameter_specs = self.get_parameters()
        validated_params = {}

        for param_name, param_spec in parameter_specs.items():
            if param_name in params:
                # 驗證並轉換提供的參數值
                validated_params[param_name] = param_spec.validate(params[param_name])
            else:
                # 使用預設值
                validated_params[param_name] = param_spec.default_value

        # 檢查是否有未定義的參數
        undefined_params = set(params.keys()) - set(parameter_specs.keys())
        if undefined_params:
            import warnings
            warnings.warn(
                f"Undefined parameters will be ignored: {undefined_params}"
            )

        return validated_params


# 輔助函數：快速創建參數規格

def float_param(default: float, description: str,
                min_val: Optional[float] = None,
                max_val: Optional[float] = None) -> ParameterSpec:
    """快速創建浮點數參數規格

    Args:
        default: 預設值
        description: 參數描述
        min_val: 最小值（可選）
        max_val: 最大值（可選）

    Returns:
        ParameterSpec: 浮點數參數規格

    Example:
        >>> float_param(0.02, "停損比例", 0.01, 0.1)
    """
    return ParameterSpec(ParameterType.FLOAT, default, description, min_val, max_val)


def int_param(default: int, description: str,
              min_val: Optional[int] = None,
              max_val: Optional[int] = None) -> ParameterSpec:
    """快速創建整數參數規格

    Args:
        default: 預設值
        description: 參數描述
        min_val: 最小值（可選）
        max_val: 最大值（可選）

    Returns:
        ParameterSpec: 整數參數規格

    Example:
        >>> int_param(20, "SMA週期", 5, 200)
    """
    return ParameterSpec(ParameterType.INT, default, description, min_val, max_val)


def str_param(default: str, description: str,
              choices: Optional[List[str]] = None) -> ParameterSpec:
    """快速創建字符串參數規格

    Args:
        default: 預設值
        description: 參數描述
        choices: 可選值列表（可選）

    Returns:
        ParameterSpec: 字符串參數規格

    Example:
        >>> str_param("buy", "信號類型", ["buy", "sell", "both"])
    """
    return ParameterSpec(ParameterType.STR, default, description, choices=choices)


def bool_param(default: bool, description: str) -> ParameterSpec:
    """快速創建布林參數規格

    Args:
        default: 預設值
        description: 參數描述

    Returns:
        ParameterSpec: 布林參數規格

    Example:
        >>> bool_param(True, "啟用成交量過濾")
    """
    return ParameterSpec(ParameterType.BOOL, default, description)
