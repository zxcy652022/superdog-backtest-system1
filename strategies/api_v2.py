"""
策略 API v2.0 別名模組

此模組是 strategies/api.py 的別名，保持向後兼容性。
所有新開發應直接使用 strategies/api.py。

Version: v2.0 (alias)
"""

# 直接從 api.py 重新導出所有內容
from strategies.api import (
    BaseStrategy,
    DataRequirement,
    DataSource,
    ParameterSpec,
    ParameterType,
    bool_param,
    float_param,
    int_param,
    str_param,
)

__all__ = [
    "BaseStrategy",
    "DataRequirement",
    "DataSource",
    "ParameterSpec",
    "ParameterType",
    "bool_param",
    "float_param",
    "int_param",
    "str_param",
]
