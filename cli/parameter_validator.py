"""
CLI Parameter Validator v0.4

CLI 參數驗證器 - 提供友好的參數驗證和錯誤處理

這個模組提供：
1. 參數類型檢查和轉換
2. 範圍驗證
3. 相依性檢查
4. 友好的錯誤訊息和修復建議

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

import click
from typing import Dict, Any, List, Optional
from strategies.api_v2 import BaseStrategy, ParameterSpec, ParameterType


class ParameterValidator:
    """CLI 參數驗證器

    提供參數驗證、類型轉換和友好的錯誤訊息

    Example:
        >>> validator = ParameterValidator()
        >>> strategy = SimpleSMAStrategyV2()
        >>> params = {'short_window': '10', 'long_window': '20'}
        >>> validated = validator.validate(params, strategy)
    """

    def __init__(self, verbose: bool = False):
        """初始化驗證器

        Args:
            verbose: 是否顯示詳細驗證信息
        """
        self.verbose = verbose
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, params: Dict[str, Any], strategy: BaseStrategy) -> Dict[str, Any]:
        """驗證並轉換參數

        Args:
            params: 原始參數字典
            strategy: 策略實例

        Returns:
            驗證並轉換後的參數字典

        Raises:
            click.BadParameter: 參數驗證失敗
        """
        self.errors.clear()
        self.warnings.clear()

        parameter_specs = strategy.get_parameters()
        validated_params = {}

        # 1. 檢查並驗證提供的參數
        for param_name, param_value in params.items():
            if param_name not in parameter_specs:
                self.warnings.append(
                    f"Unknown parameter '{param_name}' will be ignored"
                )
                continue

            param_spec = parameter_specs[param_name]

            try:
                validated_value = self._validate_single_param(
                    param_name, param_value, param_spec
                )
                validated_params[param_name] = validated_value
            except (ValueError, TypeError) as e:
                self.errors.append(
                    self._format_param_error(param_name, param_value, param_spec, str(e))
                )

        # 2. 添加缺失參數的預設值
        for param_name, param_spec in parameter_specs.items():
            if param_name not in validated_params:
                validated_params[param_name] = param_spec.default_value
                if self.verbose:
                    self.warnings.append(
                        f"Using default value for '{param_name}': {param_spec.default_value}"
                    )

        # 3. 相依性檢查
        self._check_dependencies(validated_params, strategy)

        # 4. 報告錯誤
        if self.errors:
            error_message = self._format_error_report()
            raise click.BadParameter(error_message)

        # 5. 報告警告
        if self.warnings and self.verbose:
            for warning in self.warnings:
                click.echo(f"Warning: {warning}", err=True)

        return validated_params

    def _validate_single_param(
        self, param_name: str, param_value: Any, param_spec: ParameterSpec
    ) -> Any:
        """驗證單個參數

        Args:
            param_name: 參數名稱
            param_value: 參數值
            param_spec: 參數規格

        Returns:
            驗證並轉換後的值

        Raises:
            ValueError: 參數值不符合規格
            TypeError: 參數類型無法轉換
        """
        # 使用 ParameterSpec 的驗證方法
        validated_value = param_spec.validate(param_value)

        if self.verbose:
            click.echo(
                f"  ✓ {param_name}: {param_value} → {validated_value} "
                f"({param_spec.param_type.value})",
                err=True
            )

        return validated_value

    def _format_param_error(
        self, param_name: str, param_value: Any, param_spec: ParameterSpec, error: str
    ) -> str:
        """格式化參數錯誤訊息

        Args:
            param_name: 參數名稱
            param_value: 參數值
            param_spec: 參數規格
            error: 錯誤訊息

        Returns:
            格式化的錯誤訊息，包含修復建議
        """
        error_msg = f"Parameter '{param_name}': {error}"

        # 添加修復建議
        suggestions = self._get_suggestions(param_name, param_value, param_spec)
        if suggestions:
            error_msg += f"\n  Suggestion: {suggestions}"

        return error_msg

    def _get_suggestions(
        self, param_name: str, param_value: Any, param_spec: ParameterSpec
    ) -> Optional[str]:
        """獲取參數修復建議

        Args:
            param_name: 參數名稱
            param_value: 參數值
            param_spec: 參數規格

        Returns:
            修復建議字符串，如果沒有建議則返回 None
        """
        # 範圍錯誤建議
        if param_spec.param_type in (ParameterType.INT, ParameterType.FLOAT):
            try:
                numeric_value = float(param_value)

                if param_spec.min_value is not None and numeric_value < param_spec.min_value:
                    return (
                        f"Value {numeric_value} is below minimum {param_spec.min_value}. "
                        f"Try a value >= {param_spec.min_value}"
                    )

                if param_spec.max_value is not None and numeric_value > param_spec.max_value:
                    return (
                        f"Value {numeric_value} exceeds maximum {param_spec.max_value}. "
                        f"Try a value <= {param_spec.max_value}"
                    )
            except (ValueError, TypeError):
                return (
                    f"Cannot convert '{param_value}' to {param_spec.param_type.value}. "
                    f"Expected a number."
                )

        # 選項錯誤建議
        if param_spec.param_type == ParameterType.STR and param_spec.choices:
            if param_value not in param_spec.choices:
                choices_str = ", ".join(f"'{c}'" for c in param_spec.choices)
                return f"Value must be one of: {choices_str}"

        # 布林值錯誤建議
        if param_spec.param_type == ParameterType.BOOL:
            return "Expected a boolean value (true/false, yes/no, 1/0)"

        return None

    def _check_dependencies(self, params: Dict[str, Any], strategy: BaseStrategy) -> None:
        """檢查參數相依性

        Args:
            params: 驗證後的參數字典
            strategy: 策略實例

        Note:
            這個方法檢查參數之間的邏輯關係，例如：
            - short_window 應該小於 long_window
            - 某些參數組合可能無效
        """
        # 通用檢查：如果策略有 short_window 和 long_window，確保 short < long
        if 'short_window' in params and 'long_window' in params:
            if params['short_window'] >= params['long_window']:
                self.errors.append(
                    f"Parameter dependency error: 'short_window' ({params['short_window']}) "
                    f"must be less than 'long_window' ({params['long_window']})"
                )

        # 策略特定的相依性檢查可以在這裡添加
        # 例如：如果啟用了某個功能，則必須提供相關參數
        # if params.get('enable_volume_filter') and not params.get('volume_threshold'):
        #     self.errors.append("...")

    def _format_error_report(self) -> str:
        """格式化錯誤報告

        Returns:
            格式化的錯誤報告字符串
        """
        report_lines = ["Parameter validation failed:"]
        report_lines.append("")

        for i, error in enumerate(self.errors, 1):
            report_lines.append(f"{i}. {error}")

        report_lines.append("")
        report_lines.append("Please fix the above errors and try again.")

        return "\n".join(report_lines)


class BacktestConfigValidator:
    """回測配置驗證器

    驗證回測的完整配置，包括：
    - 基本參數（symbol, timeframe, cash 等）
    - 策略參數
    - 數據可用性

    Example:
        >>> validator = BacktestConfigValidator()
        >>> config = {
        ...     'symbol': 'BTCUSDT',
        ...     'timeframe': '1h',
        ...     'cash': 10000,
        ...     'strategy_params': {'short_window': 10}
        ... }
        >>> validator.validate_config(config, strategy)
    """

    def __init__(self, verbose: bool = False):
        """初始化配置驗證器

        Args:
            verbose: 是否顯示詳細驗證信息
        """
        self.verbose = verbose
        self.param_validator = ParameterValidator(verbose=verbose)

    def validate_config(
        self, config: Dict[str, Any], strategy: BaseStrategy
    ) -> Dict[str, Any]:
        """驗證完整的回測配置

        Args:
            config: 配置字典，包含所有回測參數
            strategy: 策略實例

        Returns:
            驗證後的配置字典

        Raises:
            click.BadParameter: 配置驗證失敗
        """
        validated_config = {}

        # 1. 驗證必需的基本參數
        required_params = ['symbol', 'timeframe']
        for param in required_params:
            if param not in config:
                raise click.BadParameter(f"Missing required parameter: {param}")
            validated_config[param] = config[param]

        # 2. 驗證可選的基本參數
        optional_params = {
            'cash': 10000.0,
            'fee': 0.0005,
            'leverage': 1.0,
            'stop_loss': None,
            'take_profit': None
        }

        for param, default_value in optional_params.items():
            validated_config[param] = config.get(param, default_value)

        # 3. 驗證數值範圍
        self._validate_numeric_ranges(validated_config)

        # 4. 驗證策略參數
        strategy_params = config.get('strategy_params', {})
        validated_strategy_params = self.param_validator.validate(
            strategy_params, strategy
        )
        validated_config['strategy_params'] = validated_strategy_params

        # 5. 驗證時間週期格式
        self._validate_timeframe(validated_config['timeframe'])

        # 6. 驗證交易對格式
        self._validate_symbol(validated_config['symbol'])

        return validated_config

    def _validate_numeric_ranges(self, config: Dict[str, Any]) -> None:
        """驗證數值參數的範圍

        Args:
            config: 配置字典

        Raises:
            click.BadParameter: 數值超出範圍
        """
        # 初始資金
        if config['cash'] <= 0:
            raise click.BadParameter(
                f"Initial cash must be positive, got {config['cash']}"
            )

        # 手續費率
        if not (0 <= config['fee'] < 1):
            raise click.BadParameter(
                f"Fee rate must be in [0, 1), got {config['fee']}"
            )

        # 槓桿倍數
        if not (1 <= config['leverage'] <= 100):
            raise click.BadParameter(
                f"Leverage must be in [1, 100], got {config['leverage']}"
            )

        # 停損停利
        if config['stop_loss'] is not None:
            if not (0 < config['stop_loss'] < 1):
                raise click.BadParameter(
                    f"Stop loss must be in (0, 1), got {config['stop_loss']}"
                )

        if config['take_profit'] is not None:
            if not (0 < config['take_profit'] < 10):
                raise click.BadParameter(
                    f"Take profit must be in (0, 10), got {config['take_profit']}"
                )

    def _validate_timeframe(self, timeframe: str) -> None:
        """驗證時間週期格式

        Args:
            timeframe: 時間週期字符串

        Raises:
            click.BadParameter: 時間週期格式無效
        """
        valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']

        if timeframe not in valid_timeframes:
            valid_str = ", ".join(valid_timeframes)
            raise click.BadParameter(
                f"Invalid timeframe '{timeframe}'. "
                f"Valid options: {valid_str}"
            )

    def _validate_symbol(self, symbol: str) -> None:
        """驗證交易對格式

        Args:
            symbol: 交易對字符串

        Raises:
            click.BadParameter: 交易對格式無效
        """
        # 基本格式檢查
        if not symbol or len(symbol) < 6:
            raise click.BadParameter(
                f"Invalid symbol '{symbol}'. "
                f"Expected format: BTCUSDT, ETHUSDT, etc."
            )

        # 檢查是否以 USDT 或 USD 結尾（常見格式）
        if not (symbol.endswith('USDT') or symbol.endswith('USD') or symbol.endswith('BTC')):
            # 警告但不報錯
            if self.verbose:
                click.echo(
                    f"Warning: Symbol '{symbol}' has unusual format. "
                    f"Expected to end with USDT, USD, or BTC",
                    err=True
                )


def validate_strategy_params_cli(
    ctx: click.Context, param: click.Parameter, value: Any
) -> Any:
    """Click 參數驗證回調函數

    用於 click.option 的 callback 參數

    Args:
        ctx: Click 上下文
        param: Click 參數
        value: 參數值

    Returns:
        驗證後的值

    Example:
        >>> @click.option('--period', callback=validate_strategy_params_cli)
        >>> def my_command(period):
        ...     pass
    """
    # 這是一個通用的回調函數，可以根據需要擴展
    # 目前主要驗證由 ParameterValidator 處理
    return value
