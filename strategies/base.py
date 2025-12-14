"""
策略基類 v1.0

提供可優化參數定義標準和輔助方法

核心功能：
- OPTIMIZABLE_PARAMS 類變數定義
- 參數類型驗證
- 參數空間生成（用於優化器）
- 與現有 BaseStrategy 兼容

Version: v1.0
Design Reference: docs/v1.0/DESIGN.md
"""

import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ParamType(Enum):
    """參數類型"""

    INT = "int"  # 整數
    FLOAT = "float"  # 浮點數
    CHOICE = "choice"  # 選擇型
    BOOL = "bool"  # 布林值


class ParamCategory(Enum):
    """參數類別"""

    SIGNAL = "signal"  # 信號參數 - 影響進出場判斷
    EXECUTION = "execution"  # 執行參數 - 影響倉位和出場


@dataclass
class ParamSpec:
    """參數規格定義"""

    name: str
    param_type: ParamType
    default: Any
    description: str
    category: ParamCategory = ParamCategory.SIGNAL

    # 數值型參數的範圍
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    step: Optional[float] = None

    # 選擇型參數的選項
    choices: Optional[List[Any]] = None

    def validate(self, value: Any) -> bool:
        """驗證參數值是否有效"""
        if self.param_type == ParamType.INT:
            if not isinstance(value, int):
                return False
            if self.range_min is not None and value < self.range_min:
                return False
            if self.range_max is not None and value > self.range_max:
                return False
            return True

        elif self.param_type == ParamType.FLOAT:
            if not isinstance(value, (int, float)):
                return False
            if self.range_min is not None and value < self.range_min:
                return False
            if self.range_max is not None and value > self.range_max:
                return False
            return True

        elif self.param_type == ParamType.CHOICE:
            return value in (self.choices or [])

        elif self.param_type == ParamType.BOOL:
            return isinstance(value, bool)

        return False

    def get_search_space(self) -> List[Any]:
        """生成搜索空間（用於網格搜索）"""
        if self.param_type == ParamType.INT:
            if self.range_min is None or self.range_max is None:
                return [self.default]
            step = int(self.step) if self.step else 1
            return list(range(int(self.range_min), int(self.range_max) + 1, step))

        elif self.param_type == ParamType.FLOAT:
            if self.range_min is None or self.range_max is None:
                return [self.default]
            step = self.step or 0.1
            values = []
            current = self.range_min
            while current <= self.range_max:
                values.append(round(current, 6))
                current += step
            return values

        elif self.param_type == ParamType.CHOICE:
            return self.choices or [self.default]

        elif self.param_type == ParamType.BOOL:
            return [True, False]

        return [self.default]


# ===== 便捷函數：建立參數規格 =====


def int_param(
    default: int,
    description: str,
    range_min: Optional[int] = None,
    range_max: Optional[int] = None,
    step: int = 1,
    category: ParamCategory = ParamCategory.SIGNAL,
) -> Dict[str, Any]:
    """建立整數參數定義"""
    return {
        "type": "int",
        "default": default,
        "description": description,
        "range": [range_min, range_max] if range_min is not None else None,
        "step": step,
        "category": category.value,
    }


def float_param(
    default: float,
    description: str,
    range_min: Optional[float] = None,
    range_max: Optional[float] = None,
    step: float = 0.01,
    category: ParamCategory = ParamCategory.SIGNAL,
) -> Dict[str, Any]:
    """建立浮點數參數定義"""
    return {
        "type": "float",
        "default": default,
        "description": description,
        "range": [range_min, range_max] if range_min is not None else None,
        "step": step,
        "category": category.value,
    }


def choice_param(
    default: Any,
    choices: List[Any],
    description: str,
    category: ParamCategory = ParamCategory.SIGNAL,
) -> Dict[str, Any]:
    """建立選擇型參數定義"""
    return {
        "type": "choice",
        "default": default,
        "choices": choices,
        "description": description,
        "category": category.value,
    }


def bool_param(
    default: bool,
    description: str,
    category: ParamCategory = ParamCategory.SIGNAL,
) -> Dict[str, Any]:
    """建立布林值參數定義"""
    return {
        "type": "bool",
        "default": default,
        "description": description,
        "category": category.value,
    }


class OptimizableStrategyMixin:
    """可優化策略混入類

    提供參數優化相關的輔助方法
    策略類繼承此 Mixin 即可獲得優化功能

    使用方式：
        class MyStrategy(BaseStrategy, OptimizableStrategyMixin):
            OPTIMIZABLE_PARAMS = {
                "ma_short": int_param(20, "短均線", 10, 30, 5),
                ...
            }
    """

    # 子類必須定義這個類變數
    OPTIMIZABLE_PARAMS: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_optimizable_params(cls) -> Dict[str, Dict[str, Any]]:
        """獲取可優化參數定義"""
        return cls.OPTIMIZABLE_PARAMS

    @classmethod
    def get_default_params(cls) -> Dict[str, Any]:
        """獲取所有參數的默認值"""
        defaults = {}
        for name, spec in cls.OPTIMIZABLE_PARAMS.items():
            defaults[name] = spec.get("default")
        return defaults

    @classmethod
    def get_param_search_space(
        cls, param_names: Optional[List[str]] = None
    ) -> Dict[str, List[Any]]:
        """獲取參數搜索空間

        Args:
            param_names: 要獲取的參數名列表，None 表示全部

        Returns:
            Dict[str, List[Any]]: 參數名 -> 可能值列表
        """
        search_space = {}
        params = cls.OPTIMIZABLE_PARAMS

        if param_names is None:
            param_names = list(params.keys())

        for name in param_names:
            if name not in params:
                continue

            spec = params[name]
            param_type = spec.get("type", "float")
            default = spec.get("default")

            if param_type == "int":
                range_spec = spec.get("range")
                if range_spec:
                    step = spec.get("step", 1)
                    search_space[name] = list(
                        range(int(range_spec[0]), int(range_spec[1]) + 1, int(step))
                    )
                else:
                    search_space[name] = [default]

            elif param_type == "float":
                range_spec = spec.get("range")
                if range_spec:
                    step = spec.get("step", 0.01)
                    values = []
                    current = range_spec[0]
                    while current <= range_spec[1]:
                        values.append(round(current, 6))
                        current += step
                    search_space[name] = values
                else:
                    search_space[name] = [default]

            elif param_type == "choice":
                search_space[name] = spec.get("choices", [default])

            elif param_type == "bool":
                search_space[name] = [True, False]

            else:
                search_space[name] = [default]

        return search_space

    @classmethod
    def generate_param_combinations(
        cls,
        param_names: Optional[List[str]] = None,
        max_combinations: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """生成所有參數組合

        Args:
            param_names: 要組合的參數名列表
            max_combinations: 最大組合數（超過則隨機採樣）

        Returns:
            List[Dict[str, Any]]: 參數組合列表
        """
        import random

        search_space = cls.get_param_search_space(param_names)

        if not search_space:
            return [cls.get_default_params()]

        # 計算總組合數
        total = 1
        for values in search_space.values():
            total *= len(values)

        # 生成所有組合
        param_names_ordered = list(search_space.keys())
        values_lists = [search_space[name] for name in param_names_ordered]

        combinations = []
        for combo in itertools.product(*values_lists):
            params = dict(zip(param_names_ordered, combo))
            # 補充未在搜索空間中的參數使用默認值
            defaults = cls.get_default_params()
            for name, default in defaults.items():
                if name not in params:
                    params[name] = default
            combinations.append(params)

        # 如果超過限制，隨機採樣
        if max_combinations and len(combinations) > max_combinations:
            combinations = random.sample(combinations, max_combinations)

        return combinations

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> Dict[str, str]:
        """驗證參數值

        Args:
            params: 要驗證的參數字典

        Returns:
            Dict[str, str]: 錯誤參數名 -> 錯誤訊息
        """
        errors = {}

        for name, value in params.items():
            if name not in cls.OPTIMIZABLE_PARAMS:
                continue

            spec = cls.OPTIMIZABLE_PARAMS[name]
            param_type = spec.get("type", "float")
            range_spec = spec.get("range")
            choices = spec.get("choices")

            if param_type == "int":
                if not isinstance(value, int):
                    errors[name] = f"Expected int, got {type(value).__name__}"
                elif range_spec:
                    if value < range_spec[0] or value > range_spec[1]:
                        errors[name] = f"Value {value} out of range {range_spec}"

            elif param_type == "float":
                if not isinstance(value, (int, float)):
                    errors[name] = f"Expected float, got {type(value).__name__}"
                elif range_spec:
                    if value < range_spec[0] or value > range_spec[1]:
                        errors[name] = f"Value {value} out of range {range_spec}"

            elif param_type == "choice":
                if choices and value not in choices:
                    errors[name] = f"Value {value} not in choices {choices}"

            elif param_type == "bool":
                if not isinstance(value, bool):
                    errors[name] = f"Expected bool, got {type(value).__name__}"

        return errors

    @classmethod
    def get_params_summary(cls) -> str:
        """生成參數摘要文字"""
        lines = []
        lines.append(f"=== {cls.__name__} 可優化參數 ===\n")

        # 按類別分組
        signal_params = []
        execution_params = []

        for name, spec in cls.OPTIMIZABLE_PARAMS.items():
            category = spec.get("category", "signal")
            if category == "signal":
                signal_params.append((name, spec))
            else:
                execution_params.append((name, spec))

        if signal_params:
            lines.append("【信號參數】")
            for name, spec in signal_params:
                lines.append(cls._format_param_line(name, spec))
            lines.append("")

        if execution_params:
            lines.append("【執行參數】")
            for name, spec in execution_params:
                lines.append(cls._format_param_line(name, spec))

        return "\n".join(lines)

    @classmethod
    def _format_param_line(cls, name: str, spec: Dict[str, Any]) -> str:
        """格式化單個參數行"""
        param_type = spec.get("type", "float")
        default = spec.get("default")
        description = spec.get("description", "")

        if param_type in ("int", "float"):
            range_spec = spec.get("range")
            if range_spec:
                return f"  {name}: {default} ({range_spec[0]}~{range_spec[1]}) - {description}"
            else:
                return f"  {name}: {default} - {description}"
        elif param_type == "choice":
            choices = spec.get("choices", [])
            return f"  {name}: {default} {choices} - {description}"
        elif param_type == "bool":
            return f"  {name}: {default} (True/False) - {description}"
        else:
            return f"  {name}: {default} - {description}"


# ===== 輔助函數 =====


def get_strategy_params(strategy_cls) -> Dict[str, Dict[str, Any]]:
    """獲取策略的可優化參數

    支援有 OPTIMIZABLE_PARAMS 的新策略和
    有 get_default_parameters() 的舊策略

    Args:
        strategy_cls: 策略類

    Returns:
        Dict[str, Dict[str, Any]]: 參數定義
    """
    # 優先使用新的 OPTIMIZABLE_PARAMS
    if hasattr(strategy_cls, "OPTIMIZABLE_PARAMS"):
        return strategy_cls.OPTIMIZABLE_PARAMS

    # 回退到舊的 get_default_parameters
    if hasattr(strategy_cls, "get_default_parameters"):
        defaults = strategy_cls.get_default_parameters()
        # 將簡單的默認值轉換為參數規格
        params = {}
        for name, default in defaults.items():
            if isinstance(default, int):
                params[name] = {
                    "type": "int",
                    "default": default,
                    "description": name,
                    "category": "signal",
                }
            elif isinstance(default, float):
                params[name] = {
                    "type": "float",
                    "default": default,
                    "description": name,
                    "category": "signal",
                }
            elif isinstance(default, bool):
                params[name] = {
                    "type": "bool",
                    "default": default,
                    "description": name,
                    "category": "signal",
                }
            elif isinstance(default, str):
                params[name] = {
                    "type": "choice",
                    "default": default,
                    "choices": [default],
                    "description": name,
                    "category": "signal",
                }
            else:
                params[name] = {
                    "type": "float",
                    "default": default,
                    "description": name,
                    "category": "signal",
                }
        return params

    return {}


def count_param_combinations(params: Dict[str, Dict[str, Any]]) -> int:
    """計算參數組合總數

    Args:
        params: OPTIMIZABLE_PARAMS 格式的參數定義

    Returns:
        int: 總組合數
    """
    total = 1

    for name, spec in params.items():
        param_type = spec.get("type", "float")
        range_spec = spec.get("range")
        choices = spec.get("choices")
        step = spec.get("step", 1)

        if param_type in ("int", "float"):
            if range_spec:
                if param_type == "int":
                    count = len(range(int(range_spec[0]), int(range_spec[1]) + 1, int(step)))
                else:
                    count = int((range_spec[1] - range_spec[0]) / step) + 1
                total *= count
        elif param_type == "choice":
            if choices:
                total *= len(choices)
        elif param_type == "bool":
            total *= 2

    return total
