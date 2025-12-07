"""
Strategy Registry v2.0

策略註冊器 v2.0 - 自動掃描、動態載入、緩存管理

v2.0 新特性：
- 自動掃描 strategies/ 目錄
- 動態載入策略模組
- 策略實例緩存
- 相依性檢查整合
- 元數據管理整合
- 同時支援 v0.3 和 v2.0 策略

Version: v2.0
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md §3
"""

import os
import sys
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Type, Optional, Union
import warnings

# v0.3 策略基類
from backtest.engine import BaseStrategy as V03BaseStrategy

# v2.0 策略基類
try:
    from strategies.api_v2 import BaseStrategy as V2BaseStrategy
    HAS_V2_API = True
except ImportError:
    V2BaseStrategy = None
    HAS_V2_API = False

# 元數據和相依性檢查
try:
    from strategies.metadata import StrategyMetadata, MetadataManager, get_metadata_manager
    from strategies.dependency_checker import DependencyChecker, check_strategy_dependencies
    HAS_METADATA = True
except ImportError:
    HAS_METADATA = False


class StrategyInfo:
    """策略信息封裝

    封裝策略的完整信息，包括類別、類型、元數據等

    Attributes:
        name: 策略名稱
        strategy_class: 策略類別
        strategy_type: 策略類型（'v0.3' 或 'v2.0'）
        module_path: 模組路徑
        metadata: 策略元數據（可選）
        is_cached: 是否已緩存實例
    """

    def __init__(
        self,
        name: str,
        strategy_class: type,
        strategy_type: str,
        module_path: str,
        metadata: Optional['StrategyMetadata'] = None
    ):
        """初始化策略信息

        Args:
            name: 策略名稱
            strategy_class: 策略類別
            strategy_type: 策略類型
            module_path: 模組路徑
            metadata: 策略元數據（可選）
        """
        self.name = name
        self.strategy_class = strategy_class
        self.strategy_type = strategy_type
        self.module_path = module_path
        self.metadata = metadata
        self.is_cached = False
        self._cached_instance = None

    def get_instance(self, use_cache: bool = True):
        """獲取策略實例

        Args:
            use_cache: 是否使用緩存

        Returns:
            策略實例

        Note:
            對於 v2.0 策略，緩存實例以提高性能
            對於 v0.3 策略，每次創建新實例
        """
        if use_cache and self.is_cached and self._cached_instance is not None:
            return self._cached_instance

        # 創建新實例
        if self.strategy_type == 'v2.0':
            instance = self.strategy_class()
            if use_cache:
                self._cached_instance = instance
                self.is_cached = True
            return instance
        else:
            # v0.3 策略不緩存（需要 broker 和 data 參數）
            return None

    def clear_cache(self):
        """清除緩存的實例"""
        self._cached_instance = None
        self.is_cached = False


class StrategyRegistryV2:
    """策略註冊器 v2.0

    自動掃描、動態載入和管理所有策略

    Example:
        >>> registry = StrategyRegistryV2()
        >>> registry.discover_strategies()
        >>> strategy_cls = registry.get_strategy("simple_sma_v2")
        >>> strategies = registry.list_strategies()
    """

    def __init__(self, strategies_dir: str = "strategies", auto_discover: bool = True):
        """初始化策略註冊器

        Args:
            strategies_dir: 策略目錄路徑
            auto_discover: 是否自動掃描策略
        """
        self.strategies_dir = Path(strategies_dir)
        self._strategies: Dict[str, StrategyInfo] = {}
        self._metadata_manager = get_metadata_manager() if HAS_METADATA else None
        self._dependency_checker = DependencyChecker() if HAS_METADATA else None

        if auto_discover:
            self.discover_strategies()

    def discover_strategies(self, verbose: bool = False) -> int:
        """自動發現並註冊策略

        掃描 strategies/ 目錄，載入所有策略模組

        Args:
            verbose: 是否顯示詳細信息

        Returns:
            發現的策略數量

        Example:
            >>> registry = StrategyRegistryV2(auto_discover=False)
            >>> count = registry.discover_strategies(verbose=True)
            >>> print(f"Found {count} strategies")
        """
        discovered_count = 0

        if verbose:
            print(f"Scanning directory: {self.strategies_dir}")

        # 掃描所有 Python 文件
        for strategy_file in self.strategies_dir.glob("*.py"):
            # 跳過私有文件和特殊文件
            if strategy_file.name.startswith("_"):
                continue

            if strategy_file.name in ["registry.py", "registry_v2.py", "base.py",
                                       "metadata.py", "dependency_checker.py",
                                       "compatibility.py", "indicators.py"]:
                continue

            module_name = strategy_file.stem

            try:
                # 動態載入模組
                module_path = f"strategies.{module_name}"
                spec = importlib.util.spec_from_file_location(module_name, strategy_file)

                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    # 尋找策略類別
                    strategies_found = self._extract_strategies_from_module(
                        module, module_path, verbose
                    )
                    discovered_count += strategies_found

            except Exception as e:
                if verbose:
                    print(f"Warning: Failed to load {strategy_file}: {e}")
                warnings.warn(f"Failed to load strategy from {strategy_file}: {e}")

        if verbose:
            print(f"Discovered {discovered_count} strategies")

        return discovered_count

    def _extract_strategies_from_module(
        self, module, module_path: str, verbose: bool = False
    ) -> int:
        """從模組中提取策略類別

        Args:
            module: 已載入的模組
            module_path: 模組路徑
            verbose: 是否顯示詳細信息

        Returns:
            提取的策略數量
        """
        count = 0

        for name, obj in inspect.getmembers(module, inspect.isclass):
            # 檢查是否為策略類別
            is_v2_strategy = (
                HAS_V2_API and
                V2BaseStrategy and
                issubclass(obj, V2BaseStrategy) and
                obj != V2BaseStrategy
            )

            is_v03_strategy = (
                issubclass(obj, V03BaseStrategy) and
                obj != V03BaseStrategy and
                not is_v2_strategy  # 避免重複
            )

            if is_v2_strategy or is_v03_strategy:
                strategy_type = 'v2.0' if is_v2_strategy else 'v0.3'

                # 生成策略名稱（小寫，去掉 Strategy 後綴）
                strategy_name = name.lower()
                if strategy_name.endswith('strategy'):
                    strategy_name = strategy_name[:-8]  # 移除 'strategy'
                if strategy_name.endswith('strategyv2'):
                    strategy_name = strategy_name[:-10]  # 移除 'strategyv2'

                # 創建策略信息
                strategy_info = StrategyInfo(
                    name=strategy_name,
                    strategy_class=obj,
                    strategy_type=strategy_type,
                    module_path=module_path
                )

                # 嘗試獲取元數據（v2.0 策略）
                if is_v2_strategy and HAS_METADATA:
                    try:
                        instance = obj()
                        # 這裡可以從策略實例提取元數據
                        # 或者策略可以提供 get_metadata() 方法
                    except Exception:
                        pass

                # 註冊策略
                self._strategies[strategy_name] = strategy_info
                count += 1

                if verbose:
                    print(f"  Registered: {strategy_name} ({strategy_type})")

        return count

    def register_strategy(
        self,
        name: str,
        strategy_class: type,
        metadata: Optional['StrategyMetadata'] = None
    ) -> None:
        """手動註冊策略

        Args:
            name: 策略名稱
            strategy_class: 策略類別
            metadata: 策略元數據（可選）

        Raises:
            ValueError: 策略名稱已存在
            TypeError: 策略類別不合法

        Example:
            >>> registry = StrategyRegistryV2()
            >>> registry.register_strategy("my_strategy", MyStrategy)
        """
        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' already registered")

        # 檢查策略類型
        is_v2 = HAS_V2_API and V2BaseStrategy and issubclass(strategy_class, V2BaseStrategy)
        is_v03 = issubclass(strategy_class, V03BaseStrategy)

        if not (is_v2 or is_v03):
            raise TypeError(
                f"{strategy_class.__name__} must inherit from BaseStrategy "
                f"(v0.3 or v2.0)"
            )

        strategy_type = 'v2.0' if is_v2 else 'v0.3'

        strategy_info = StrategyInfo(
            name=name,
            strategy_class=strategy_class,
            strategy_type=strategy_type,
            module_path="manually_registered",
            metadata=metadata
        )

        self._strategies[name] = strategy_info

        # 註冊元數據
        if metadata and self._metadata_manager:
            self._metadata_manager.register(metadata)

    def get_strategy(self, name: str) -> type:
        """獲取策略類別

        Args:
            name: 策略名稱

        Returns:
            策略類別

        Raises:
            KeyError: 策略不存在

        Example:
            >>> registry = StrategyRegistryV2()
            >>> strategy_cls = registry.get_strategy("simple_sma_v2")
        """
        if name not in self._strategies:
            available = ", ".join(sorted(self._strategies.keys()))
            raise KeyError(
                f"Strategy '{name}' not found. "
                f"Available strategies: {available}"
            )

        return self._strategies[name].strategy_class

    def get_strategy_info(self, name: str) -> StrategyInfo:
        """獲取策略完整信息

        Args:
            name: 策略名稱

        Returns:
            策略信息對象

        Raises:
            KeyError: 策略不存在

        Example:
            >>> registry = StrategyRegistryV2()
            >>> info = registry.get_strategy_info("simple_sma_v2")
            >>> print(info.strategy_type)
            'v2.0'
        """
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not found")

        return self._strategies[name]

    def list_strategies(self, filter_type: Optional[str] = None) -> List[str]:
        """列出所有策略名稱

        Args:
            filter_type: 過濾策略類型（'v0.3' 或 'v2.0'）

        Returns:
            策略名稱列表（排序）

        Example:
            >>> registry = StrategyRegistryV2()
            >>> all_strategies = registry.list_strategies()
            >>> v2_strategies = registry.list_strategies(filter_type='v2.0')
        """
        if filter_type:
            filtered = [
                name for name, info in self._strategies.items()
                if info.strategy_type == filter_type
            ]
            return sorted(filtered)

        return sorted(self._strategies.keys())

    def check_dependencies(self, strategy_name: str) -> Optional['DependencyCheckResult']:
        """檢查策略的相依性

        Args:
            strategy_name: 策略名稱

        Returns:
            相依性檢查結果，如果策略不是 v2.0 或檢查器不可用則返回 None

        Example:
            >>> registry = StrategyRegistryV2()
            >>> result = registry.check_dependencies("kawamoku_demo")
            >>> if result and not result.is_satisfied:
            ...     print(result.format_report())
        """
        if not self._dependency_checker:
            return None

        strategy_info = self.get_strategy_info(strategy_name)

        if strategy_info.strategy_type != 'v2.0':
            return None  # v0.3 策略不支援相依性檢查

        # 獲取策略實例
        instance = strategy_info.get_instance(use_cache=True)

        if instance is None:
            return None

        # 執行相依性檢查
        return self._dependency_checker.check_strategy(instance)

    def get_strategies_by_type(self, strategy_type: str) -> Dict[str, StrategyInfo]:
        """按類型獲取策略

        Args:
            strategy_type: 策略類型（'v0.3' 或 'v2.0'）

        Returns:
            策略信息字典

        Example:
            >>> registry = StrategyRegistryV2()
            >>> v2_strategies = registry.get_strategies_by_type('v2.0')
        """
        return {
            name: info for name, info in self._strategies.items()
            if info.strategy_type == strategy_type
        }

    def get_summary(self) -> Dict[str, any]:
        """獲取註冊器摘要

        Returns:
            包含註冊器統計信息的字典

        Example:
            >>> registry = StrategyRegistryV2()
            >>> summary = registry.get_summary()
            >>> print(summary)
            {'total': 3, 'v0.3': 1, 'v2.0': 2}
        """
        v03_count = len(self.list_strategies(filter_type='v0.3'))
        v2_count = len(self.list_strategies(filter_type='v2.0'))

        return {
            'total': len(self._strategies),
            'v0.3': v03_count,
            'v2.0': v2_count,
            'strategies': list(self._strategies.keys())
        }

    def clear_cache(self, strategy_name: Optional[str] = None) -> None:
        """清除策略實例緩存

        Args:
            strategy_name: 策略名稱（如果為 None，清除所有緩存）

        Example:
            >>> registry = StrategyRegistryV2()
            >>> registry.clear_cache("simple_sma_v2")  # 清除特定策略
            >>> registry.clear_cache()  # 清除所有緩存
        """
        if strategy_name:
            if strategy_name in self._strategies:
                self._strategies[strategy_name].clear_cache()
        else:
            for info in self._strategies.values():
                info.clear_cache()


# 全局註冊器實例
_global_registry_v2 = None


def get_registry() -> StrategyRegistryV2:
    """獲取全局策略註冊器實例

    Returns:
        全局 StrategyRegistryV2 實例

    Example:
        >>> registry = get_registry()
        >>> strategies = registry.list_strategies()
    """
    global _global_registry_v2

    if _global_registry_v2 is None:
        _global_registry_v2 = StrategyRegistryV2(auto_discover=True)

    return _global_registry_v2


def reset_registry() -> None:
    """重置全局註冊器（主要用於測試）

    Example:
        >>> reset_registry()
        >>> registry = get_registry()  # 獲取新的實例
    """
    global _global_registry_v2
    _global_registry_v2 = None
