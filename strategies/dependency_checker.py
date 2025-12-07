"""
Strategy Dependency Checker v0.4

策略相依性檢查器 - 驗證策略所需的數據源和外部依賴

這個模組提供：
- 數據源可用性檢查
- 參數相容性驗證
- 外部依賴檢查（Python 包、系統資源等）
- 修復建議和錯誤處理

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from strategies.api_v2 import BaseStrategy, DataRequirement, DataSource


@dataclass
class DependencyCheckResult:
    """相依性檢查結果

    Attributes:
        is_satisfied: 是否滿足所有相依性
        missing_data_sources: 缺失的數據源列表
        missing_packages: 缺失的 Python 包列表
        warnings: 警告訊息列表
        errors: 錯誤訊息列表
        suggestions: 修復建議列表

    Example:
        >>> result = DependencyCheckResult(
        ...     is_satisfied=False,
        ...     missing_data_sources=[DataSource.FUNDING],
        ...     suggestions=["Install funding rate data provider"]
        ... )
    """

    is_satisfied: bool = True
    missing_data_sources: List[DataSource] = field(default_factory=list)
    missing_packages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def add_error(self, error: str, suggestion: Optional[str] = None) -> None:
        """添加錯誤訊息

        Args:
            error: 錯誤訊息
            suggestion: 修復建議（可選）
        """
        self.errors.append(error)
        self.is_satisfied = False

        if suggestion:
            self.suggestions.append(suggestion)

    def add_warning(self, warning: str) -> None:
        """添加警告訊息

        Args:
            warning: 警告訊息
        """
        self.warnings.append(warning)

    def format_report(self) -> str:
        """格式化檢查報告

        Returns:
            格式化的報告文本

        Example:
            >>> result = DependencyCheckResult(...)
            >>> print(result.format_report())
            Dependency Check Report
            =======================
            Status: FAILED
            ...
        """
        lines = []
        lines.append("Dependency Check Report")
        lines.append("=" * 60)

        # 狀態
        status = "PASSED" if self.is_satisfied else "FAILED"
        lines.append(f"Status: {status}")
        lines.append("")

        # 錯誤
        if self.errors:
            lines.append("Errors:")
            for i, error in enumerate(self.errors, 1):
                lines.append(f"  {i}. {error}")
            lines.append("")

        # 缺失的數據源
        if self.missing_data_sources:
            lines.append("Missing Data Sources:")
            for source in self.missing_data_sources:
                lines.append(f"  - {source.value}")
            lines.append("")

        # 缺失的 Python 包
        if self.missing_packages:
            lines.append("Missing Python Packages:")
            for package in self.missing_packages:
                lines.append(f"  - {package}")
            lines.append("")

        # 警告
        if self.warnings:
            lines.append("Warnings:")
            for i, warning in enumerate(self.warnings, 1):
                lines.append(f"  {i}. {warning}")
            lines.append("")

        # 建議
        if self.suggestions:
            lines.append("Suggestions:")
            for i, suggestion in enumerate(self.suggestions, 1):
                lines.append(f"  {i}. {suggestion}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)


class DependencyChecker:
    """策略相依性檢查器

    檢查策略所需的所有相依性，包括數據源、Python 包等

    Example:
        >>> checker = DependencyChecker()
        >>> strategy = SimpleSMAStrategyV2()
        >>> result = checker.check_strategy(strategy)
        >>> if not result.is_satisfied:
        ...     print(result.format_report())
    """

    def __init__(self, data_config: Optional[Dict] = None):
        """初始化相依性檢查器

        Args:
            data_config: 數據配置字典（可選）
        """
        self.data_config = data_config or {}
        self._available_data_sources = self._detect_available_data_sources()

    def _detect_available_data_sources(self) -> List[DataSource]:
        """檢測可用的數據源

        Returns:
            可用的數據源列表

        Note:
            v0.4 目前只支援 OHLCV
            v0.5 將支援更多數據源
        """
        available = [DataSource.OHLCV]  # OHLCV 總是可用

        # v0.5: 檢測其他數據源
        # if self._check_funding_data_available():
        #     available.append(DataSource.FUNDING)
        #
        # if self._check_oi_data_available():
        #     available.append(DataSource.OPEN_INTEREST)

        return available

    def check_strategy(self, strategy: BaseStrategy) -> DependencyCheckResult:
        """檢查策略的所有相依性

        Args:
            strategy: 策略實例

        Returns:
            相依性檢查結果

        Example:
            >>> checker = DependencyChecker()
            >>> strategy = KawamokuStrategy()
            >>> result = checker.check_strategy(strategy)
            >>> print(f"Check passed: {result.is_satisfied}")
        """
        result = DependencyCheckResult()

        # 1. 檢查數據源相依性
        self._check_data_sources(strategy, result)

        # 2. 檢查參數相容性
        self._check_parameter_compatibility(strategy, result)

        # 3. 檢查 Python 包相依性
        self._check_python_packages(strategy, result)

        return result

    def _check_data_sources(self, strategy: BaseStrategy, result: DependencyCheckResult) -> None:
        """檢查數據源相依性

        Args:
            strategy: 策略實例
            result: 檢查結果（會被修改）
        """
        requirements = strategy.get_data_requirements()

        for req in requirements:
            if req.source not in self._available_data_sources:
                if req.required:
                    # 必需的數據源缺失 - 錯誤
                    result.missing_data_sources.append(req.source)
                    result.add_error(
                        f"Required data source '{req.source.value}' is not available",
                        self._get_data_source_suggestion(req.source),
                    )
                else:
                    # 可選的數據源缺失 - 警告
                    result.add_warning(
                        f"Optional data source '{req.source.value}' is not available. "
                        f"Strategy will run with reduced functionality."
                    )

    def _check_parameter_compatibility(
        self, strategy: BaseStrategy, result: DependencyCheckResult
    ) -> None:
        """檢查參數相容性

        Args:
            strategy: 策略實例
            result: 檢查結果（會被修改）

        Note:
            檢查參數之間的相容性，例如：
            - short_window 應該小於 long_window
            - 某些參數組合可能不合理
        """
        params = strategy.get_parameters()

        # 檢查常見的參數相容性問題
        if "short_window" in params and "long_window" in params:
            short_default = params["short_window"].default_value
            long_default = params["long_window"].default_value

            if short_default >= long_default:
                result.add_warning(
                    f"Default short_window ({short_default}) >= long_window ({long_default}). "
                    f"This may not be intended."
                )

        # 檢查參數範圍的合理性
        for param_name, param_spec in params.items():
            if param_spec.min_value is not None and param_spec.max_value is not None:
                if param_spec.min_value > param_spec.max_value:
                    result.add_error(
                        f"Parameter '{param_name}' has invalid range: "
                        f"min ({param_spec.min_value}) > max ({param_spec.max_value})"
                    )

            # 檢查預設值是否在範圍內
            try:
                param_spec.validate(param_spec.default_value)
            except (ValueError, TypeError) as e:
                result.add_error(f"Parameter '{param_name}' has invalid default value: {e}")

    def _check_python_packages(self, strategy: BaseStrategy, result: DependencyCheckResult) -> None:
        """檢查 Python 包相依性

        Args:
            strategy: 策略實例
            result: 檢查結果（會被修改）

        Note:
            檢查策略所需的 Python 包是否已安裝
            可以通過策略的 docstring 或特殊屬性聲明相依性
        """
        # 獲取策略的相依性聲明（如果有）
        required_packages = getattr(strategy, "required_packages", [])

        for package_name in required_packages:
            if not self._is_package_installed(package_name):
                result.missing_packages.append(package_name)
                result.add_error(
                    f"Required Python package '{package_name}' is not installed",
                    f"Install it with: pip install {package_name}",
                )

    def _is_package_installed(self, package_name: str) -> bool:
        """檢查 Python 包是否已安裝

        Args:
            package_name: 包名稱

        Returns:
            True 如果已安裝，否則 False
        """
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False

    def _get_data_source_suggestion(self, source: DataSource) -> str:
        """獲取數據源的修復建議

        Args:
            source: 數據源類型

        Returns:
            修復建議字符串
        """
        suggestions = {
            DataSource.OHLCV: "OHLCV data should always be available. Check data configuration.",
            DataSource.FUNDING: (
                "Funding rate data is not yet supported in v0.4. "
                "It will be available in v0.5. "
                "Consider using a strategy that doesn't require funding data, "
                "or wait for v0.5 release."
            ),
            DataSource.OPEN_INTEREST: (
                "Open interest data is not yet supported in v0.4. " "It will be available in v0.5."
            ),
            DataSource.BASIS: (
                "Basis data is not yet supported in v0.4. " "It will be available in v0.5."
            ),
            DataSource.VOLUME_PROFILE: (
                "Volume profile data is not yet supported in v0.4. " "It will be available in v0.5."
            ),
        }

        return suggestions.get(source, f"Configure {source.value} data source.")

    def check_data_availability(
        self, symbol: str, timeframe: str, min_periods: int = 100
    ) -> Tuple[bool, Optional[str]]:
        """檢查特定交易對和時間週期的數據可用性

        Args:
            symbol: 交易對（如 BTCUSDT）
            timeframe: 時間週期（如 1h）
            min_periods: 最小所需數據量

        Returns:
            (是否可用, 錯誤訊息或 None)

        Example:
            >>> checker = DependencyChecker()
            >>> is_available, error = checker.check_data_availability("BTCUSDT", "1h", 200)
            >>> if not is_available:
            ...     print(error)
        """
        # 檢查數據文件是否存在
        data_file = Path(f"data/raw/{symbol}_{timeframe}.csv")

        if not data_file.exists():
            return False, f"Data file not found: {data_file}"

        # 檢查數據量（可選）
        try:
            import pandas as pd

            data = pd.read_csv(data_file)

            if len(data) < min_periods:
                return False, (
                    f"Insufficient data: {len(data)} bars available, " f"but {min_periods} required"
                )

            return True, None

        except Exception as e:
            return False, f"Error reading data file: {e}"

    def get_available_data_sources(self) -> List[DataSource]:
        """獲取可用的數據源列表

        Returns:
            可用的數據源列表

        Example:
            >>> checker = DependencyChecker()
            >>> sources = checker.get_available_data_sources()
            >>> print([s.value for s in sources])
            ['ohlcv']
        """
        return self._available_data_sources.copy()

    def is_data_source_available(self, source: DataSource) -> bool:
        """檢查特定數據源是否可用

        Args:
            source: 數據源類型

        Returns:
            True 如果可用，否則 False

        Example:
            >>> checker = DependencyChecker()
            >>> checker.is_data_source_available(DataSource.OHLCV)
            True
            >>> checker.is_data_source_available(DataSource.FUNDING)
            False
        """
        return source in self._available_data_sources


def check_strategy_dependencies(strategy: BaseStrategy) -> DependencyCheckResult:
    """檢查策略相依性的便捷函數

    Args:
        strategy: 策略實例

    Returns:
        相依性檢查結果

    Example:
        >>> from strategies.kawamoku_demo import KawamokuStrategy
        >>> strategy = KawamokuStrategy()
        >>> result = check_strategy_dependencies(strategy)
        >>> if not result.is_satisfied:
        ...     print(result.format_report())
    """
    checker = DependencyChecker()
    return checker.check_strategy(strategy)
