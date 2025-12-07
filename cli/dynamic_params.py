"""
Dynamic CLI Parameter Generator v0.4

動態 CLI 參數生成器 - 根據策略參數規格自動生成 click 選項

這個模組的核心功能：
1. 掃描策略的參數規格（ParameterSpec）
2. 自動生成對應的 click.Option
3. 處理參數類型轉換和驗證
4. 生成友好的幫助信息

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md §CLI 動態參數系統
"""

import click
from typing import Dict, Any, Callable, Optional
from strategies.api_v2 import BaseStrategy, ParameterType, ParameterSpec


class DynamicCLI:
    """動態 CLI 參數生成器

    根據策略的參數規格自動生成 CLI 選項

    Example:
        >>> from strategies.simple_sma_v2 import SimpleSMAStrategyV2
        >>> dynamic_cli = DynamicCLI()
        >>> options = dynamic_cli.generate_strategy_options(SimpleSMAStrategyV2())
        >>> # options 包含了 --short-window 和 --long-window 選項
    """

    def __init__(self):
        """初始化動態 CLI 生成器"""
        pass

    def generate_strategy_options(self, strategy: BaseStrategy) -> Dict[str, Callable]:
        """為指定策略生成 CLI 選項

        Args:
            strategy: 策略實例（BaseStrategy 子類）

        Returns:
            Dict[str, Callable]: 參數名稱對應 click.option 裝飾器

        Example:
            >>> strategy = SimpleSMAStrategyV2()
            >>> options = dynamic_cli.generate_strategy_options(strategy)
            >>> # options = {
            >>> #     'short_window': <click.option decorator>,
            >>> #     'long_window': <click.option decorator>
            >>> # }
        """
        parameters = strategy.get_parameters()
        options = {}

        for param_name, param_spec in parameters.items():
            option_decorator = self._create_option_decorator(param_name, param_spec)
            options[param_name] = option_decorator

        return options

    def _create_option_decorator(self, param_name: str, param_spec: ParameterSpec) -> Callable:
        """創建單個參數的 click.option 裝飾器

        Args:
            param_name: 參數名稱（Python 格式，如 'short_window'）
            param_spec: 參數規格

        Returns:
            click.option 裝飾器

        Note:
            參數名稱轉換規則：
            - Python: short_window → CLI: --short-window
            - 底線轉連字號，保持可讀性
        """
        # 轉換參數名稱：short_window → --short-window
        option_name = f"--{param_name.replace('_', '-')}"

        # 根據參數類型創建不同的選項
        if param_spec.param_type == ParameterType.BOOL:
            # 布林參數使用 flag 形式
            return click.option(
                option_name,
                is_flag=True,
                default=param_spec.default_value,
                help=self._format_help_text(param_spec, param_name)
            )
        else:
            # 其他類型參數
            python_type = self._get_python_type(param_spec.param_type)

            return click.option(
                option_name,
                type=python_type,
                default=param_spec.default_value,
                help=self._format_help_text(param_spec, param_name),
                show_default=True
            )

    def _get_python_type(self, param_type: ParameterType) -> type:
        """獲取 Python 類型對應的 click 類型

        Args:
            param_type: ParameterType 枚舉

        Returns:
            Python 類型（int, float, str）

        Raises:
            ValueError: 未知的參數類型
        """
        type_mapping = {
            ParameterType.INT: int,
            ParameterType.FLOAT: float,
            ParameterType.STR: str,
            ParameterType.BOOL: bool
        }

        if param_type not in type_mapping:
            raise ValueError(f"Unknown parameter type: {param_type}")

        return type_mapping[param_type]

    def _format_help_text(self, param_spec: ParameterSpec, param_name: str) -> str:
        """格式化參數的幫助文本

        Args:
            param_spec: 參數規格
            param_name: 參數名稱

        Returns:
            格式化的幫助文本

        Example:
            >>> _format_help_text(
            ...     ParameterSpec(ParameterType.INT, 20, "SMA週期", 5, 200),
            ...     "sma_period"
            ... )
            "SMA週期 [範圍: 5-200]"
        """
        help_text = param_spec.description

        # 添加範圍信息（數值類型）
        if param_spec.param_type in (ParameterType.INT, ParameterType.FLOAT):
            if param_spec.min_value is not None and param_spec.max_value is not None:
                help_text += f" [範圍: {param_spec.min_value}-{param_spec.max_value}]"
            elif param_spec.min_value is not None:
                help_text += f" [最小值: {param_spec.min_value}]"
            elif param_spec.max_value is not None:
                help_text += f" [最大值: {param_spec.max_value}]"

        # 添加選項信息（字符串類型）
        if param_spec.param_type == ParameterType.STR and param_spec.choices:
            choices_str = ", ".join(param_spec.choices)
            help_text += f" [可選: {choices_str}]"

        return help_text


def create_dynamic_command(strategy_name: str, strategy_class: type) -> click.Command:
    """創建動態策略命令

    為特定策略創建完整的 CLI 命令，包含所有策略參數選項

    Args:
        strategy_name: 策略名稱（用於命令標識）
        strategy_class: 策略類別（BaseStrategy 子類）

    Returns:
        click.Command: 可執行的 CLI 命令

    Example:
        >>> from strategies.simple_sma_v2 import SimpleSMAStrategyV2
        >>> cmd = create_dynamic_command("simple_sma", SimpleSMAStrategyV2)
        >>> # 現在可以執行 cmd(...) 來運行帶策略參數的回測

    Note:
        這個函數通常不直接使用，而是通過 apply_dynamic_options 函數
        來動態添加選項到現有命令。
    """
    # 創建策略實例以獲取參數規格
    strategy_instance = strategy_class()

    # 生成動態選項
    dynamic_cli = DynamicCLI()
    options = dynamic_cli.generate_strategy_options(strategy_instance)

    # 創建命令函數
    @click.command(name=f"run-{strategy_name}")
    @click.option("-m", "--symbol", required=True, help="交易對")
    @click.option("-t", "--timeframe", required=True, help="時間週期")
    @click.option("--cash", default=10000.0, help="初始資金")
    @click.option("--fee", default=0.0005, help="手續費率")
    def dynamic_run(symbol: str, timeframe: str, cash: float, fee: float, **kwargs):
        """動態策略執行命令"""
        # 這裡的 kwargs 包含所有策略特定參數
        click.echo(f"Running {strategy_name} with params: {kwargs}")

        # 實際執行邏輯將在 cli/main.py 中實作
        pass

    # 動態添加策略參數選項
    for param_name, option_decorator in options.items():
        dynamic_run = option_decorator(dynamic_run)

    return dynamic_run


def apply_dynamic_options(command_func: Callable, strategy: BaseStrategy) -> Callable:
    """將動態選項應用到現有命令函數

    這個函數用於在運行時動態添加策略參數選項到 CLI 命令

    Args:
        command_func: 現有的命令函數
        strategy: 策略實例

    Returns:
        添加了動態選項的命令函數

    Example:
        >>> @click.command()
        >>> def run_backtest(symbol, timeframe, **kwargs):
        ...     pass
        >>>
        >>> # 動態添加策略參數
        >>> strategy = SimpleSMAStrategyV2()
        >>> run_backtest = apply_dynamic_options(run_backtest, strategy)
        >>> # 現在 run_backtest 有了 --short-window 和 --long-window 選項

    Note:
        這是推薦的使用方式，允許在運行時根據策略動態調整 CLI 選項
    """
    dynamic_cli = DynamicCLI()
    options = dynamic_cli.generate_strategy_options(strategy)

    # 逆序應用選項（click 裝飾器的順序要求）
    decorated_func = command_func
    for param_name in reversed(list(options.keys())):
        option_decorator = options[param_name]
        decorated_func = option_decorator(decorated_func)

    return decorated_func


def extract_strategy_params(all_kwargs: Dict[str, Any], strategy: BaseStrategy) -> Dict[str, Any]:
    """從 CLI kwargs 中提取策略參數

    Args:
        all_kwargs: CLI 命令接收到的所有參數
        strategy: 策略實例

    Returns:
        僅包含策略參數的字典

    Example:
        >>> all_kwargs = {
        ...     'symbol': 'BTCUSDT',
        ...     'timeframe': '1h',
        ...     'cash': 10000,
        ...     'short_window': 10,
        ...     'long_window': 20
        ... }
        >>> strategy = SimpleSMAStrategyV2()
        >>> strategy_params = extract_strategy_params(all_kwargs, strategy)
        >>> # strategy_params = {'short_window': 10, 'long_window': 20}
    """
    parameter_specs = strategy.get_parameters()
    strategy_param_names = set(parameter_specs.keys())

    # 提取策略參數
    strategy_params = {
        key: value
        for key, value in all_kwargs.items()
        if key in strategy_param_names
    }

    return strategy_params


def validate_and_convert_params(raw_params: Dict[str, Any], strategy: BaseStrategy) -> Dict[str, Any]:
    """驗證並轉換策略參數

    使用策略的 validate_parameters 方法進行驗證和轉換

    Args:
        raw_params: 原始參數字典（從 CLI 獲取）
        strategy: 策略實例

    Returns:
        驗證並轉換後的參數字典

    Raises:
        ValueError: 參數驗證失敗
        TypeError: 參數類型轉換失敗

    Example:
        >>> raw_params = {'short_window': '10', 'long_window': '20'}
        >>> strategy = SimpleSMAStrategyV2()
        >>> validated = validate_and_convert_params(raw_params, strategy)
        >>> # validated = {'short_window': 10, 'long_window': 20}
    """
    try:
        validated_params = strategy.validate_parameters(raw_params)
        return validated_params
    except (ValueError, TypeError) as e:
        raise click.BadParameter(
            f"Parameter validation failed: {e}\n"
            f"Please check parameter values and ranges."
        )


def format_strategy_help(strategy: BaseStrategy) -> str:
    """格式化策略幫助信息

    生成策略的詳細幫助文本，包括參數列表和說明

    Args:
        strategy: 策略實例

    Returns:
        格式化的幫助文本

    Example:
        >>> strategy = SimpleSMAStrategyV2()
        >>> help_text = format_strategy_help(strategy)
        >>> print(help_text)
        Strategy: SimpleSMA
        Version: 2.0
        Author: SuperDog Team
        Description: 簡單均線交叉策略 - 基於雙SMA的趨勢跟隨系統

        Parameters:
          --short-window    短期均線週期 [範圍: 1-50] (default: 10)
          --long-window     長期均線週期 [範圍: 5-200] (default: 20)
    """
    metadata = strategy.get_metadata()
    parameters = strategy.get_parameters()

    help_lines = []

    # 基本信息
    help_lines.append(f"Strategy: {metadata['name']}")
    help_lines.append(f"Version: {metadata['version']}")
    help_lines.append(f"Author: {metadata['author']}")
    if metadata['description']:
        help_lines.append(f"Description: {metadata['description']}")

    help_lines.append("")
    help_lines.append("Parameters:")

    # 參數列表
    for param_name, param_spec in parameters.items():
        option_name = f"--{param_name.replace('_', '-')}"
        dynamic_cli = DynamicCLI()
        help_text = dynamic_cli._format_help_text(param_spec, param_name)

        # 格式化輸出
        help_lines.append(f"  {option_name:<20} {help_text} (default: {param_spec.default_value})")

    # 數據需求
    data_requirements = strategy.get_data_requirements()
    if data_requirements:
        help_lines.append("")
        help_lines.append("Data Requirements:")
        for req in data_requirements:
            required_str = "required" if req.required else "optional"
            help_lines.append(
                f"  - {req.source.value}: {req.lookback_periods} periods ({required_str})"
            )

    return "\n".join(help_lines)
