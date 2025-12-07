"""
Strategy Metadata Management v0.4

策略元數據管理 - 提供策略的描述性信息和版本控制

這個模組管理策略的元數據，包括：
- 基本信息（名稱、版本、作者）
- 分類和標籤
- 創建和修改時間
- 性能指標（可選）
- 使用範例和文檔

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class StrategyCategory(Enum):
    """策略分類"""
    TREND_FOLLOWING = "trend_following"      # 趨勢跟隨
    MEAN_REVERSION = "mean_reversion"        # 均值回歸
    MOMENTUM = "momentum"                     # 動量策略
    ARBITRAGE = "arbitrage"                   # 套利策略
    MULTI_FACTOR = "multi_factor"             # 多因子策略
    MACHINE_LEARNING = "machine_learning"     # 機器學習
    OTHER = "other"                           # 其他


class StrategyComplexity(Enum):
    """策略複雜度"""
    SIMPLE = "simple"       # 簡單策略（1-3 個參數）
    MODERATE = "moderate"   # 中等策略（4-8 個參數）
    COMPLEX = "complex"     # 複雜策略（9+ 個參數）


class StrategyStatus(Enum):
    """策略狀態"""
    DEVELOPMENT = "development"   # 開發中
    TESTING = "testing"           # 測試中
    STABLE = "stable"             # 穩定版
    DEPRECATED = "deprecated"     # 已棄用


@dataclass
class StrategyMetadata:
    """策略元數據

    包含策略的所有描述性信息和元數據

    Attributes:
        name: 策略名稱
        version: 策略版本（語義版本號）
        author: 作者名稱
        description: 策略描述
        category: 策略分類
        complexity: 策略複雜度
        status: 策略狀態
        tags: 標籤列表
        created_at: 創建時間
        updated_at: 更新時間
        min_capital: 最小建議資金
        recommended_timeframes: 推薦時間週期
        recommended_symbols: 推薦交易對
        performance_metrics: 性能指標（可選）
        documentation_url: 文檔連結（可選）
        example_config: 使用範例配置

    Example:
        >>> metadata = StrategyMetadata(
        ...     name="SimpleSMA",
        ...     version="2.0.0",
        ...     author="SuperDog Team",
        ...     description="簡單均線交叉策略",
        ...     category=StrategyCategory.TREND_FOLLOWING,
        ...     tags=["sma", "crossover", "beginner"]
        ... )
    """
    name: str
    version: str
    author: str
    description: str
    category: StrategyCategory = StrategyCategory.OTHER
    complexity: StrategyComplexity = StrategyComplexity.MODERATE
    status: StrategyStatus = StrategyStatus.DEVELOPMENT
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    min_capital: Optional[float] = None
    recommended_timeframes: List[str] = field(default_factory=list)
    recommended_symbols: List[str] = field(default_factory=list)
    performance_metrics: Optional[Dict[str, float]] = None
    documentation_url: Optional[str] = None
    example_config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式

        Returns:
            包含所有元數據的字典

        Example:
            >>> metadata = StrategyMetadata(...)
            >>> data = metadata.to_dict()
            >>> print(data['name'])
            'SimpleSMA'
        """
        return {
            'name': self.name,
            'version': self.version,
            'author': self.author,
            'description': self.description,
            'category': self.category.value,
            'complexity': self.complexity.value,
            'status': self.status.value,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'min_capital': self.min_capital,
            'recommended_timeframes': self.recommended_timeframes,
            'recommended_symbols': self.recommended_symbols,
            'performance_metrics': self.performance_metrics,
            'documentation_url': self.documentation_url,
            'example_config': self.example_config
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategyMetadata':
        """從字典創建元數據實例

        Args:
            data: 包含元數據的字典

        Returns:
            StrategyMetadata 實例

        Example:
            >>> data = {'name': 'SimpleSMA', 'version': '2.0', ...}
            >>> metadata = StrategyMetadata.from_dict(data)
        """
        # 轉換枚舉值
        if 'category' in data and isinstance(data['category'], str):
            data['category'] = StrategyCategory(data['category'])

        if 'complexity' in data and isinstance(data['complexity'], str):
            data['complexity'] = StrategyComplexity(data['complexity'])

        if 'status' in data and isinstance(data['status'], str):
            data['status'] = StrategyStatus(data['status'])

        # 轉換日期時間
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])

        if 'updated_at' in data and isinstance(data['updated_at'], str):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])

        return cls(**data)

    def is_production_ready(self) -> bool:
        """檢查策略是否可用於生產環境

        Returns:
            True 如果策略狀態為 STABLE，否則 False

        Example:
            >>> metadata = StrategyMetadata(..., status=StrategyStatus.STABLE)
            >>> metadata.is_production_ready()
            True
        """
        return self.status == StrategyStatus.STABLE

    def is_deprecated(self) -> bool:
        """檢查策略是否已棄用

        Returns:
            True 如果策略狀態為 DEPRECATED，否則 False
        """
        return self.status == StrategyStatus.DEPRECATED

    def get_complexity_level(self) -> str:
        """獲取複雜度級別描述

        Returns:
            複雜度級別的可讀描述

        Example:
            >>> metadata = StrategyMetadata(..., complexity=StrategyComplexity.SIMPLE)
            >>> metadata.get_complexity_level()
            '簡單 (1-3 個參數)'
        """
        complexity_descriptions = {
            StrategyComplexity.SIMPLE: "簡單 (1-3 個參數)",
            StrategyComplexity.MODERATE: "中等 (4-8 個參數)",
            StrategyComplexity.COMPLEX: "複雜 (9+ 個參數)"
        }
        return complexity_descriptions.get(self.complexity, "未知")

    def format_info(self, include_performance: bool = False) -> str:
        """格式化元數據為可讀文本

        Args:
            include_performance: 是否包含性能指標

        Returns:
            格式化的元數據文本

        Example:
            >>> metadata = StrategyMetadata(...)
            >>> print(metadata.format_info())
            Strategy: SimpleSMA
            Version: 2.0.0
            Author: SuperDog Team
            ...
        """
        lines = []

        # 基本信息
        lines.append(f"Strategy: {self.name}")
        lines.append(f"Version: {self.version}")
        lines.append(f"Author: {self.author}")
        lines.append(f"Description: {self.description}")
        lines.append(f"Category: {self.category.value.replace('_', ' ').title()}")
        lines.append(f"Complexity: {self.get_complexity_level()}")
        lines.append(f"Status: {self.status.value.title()}")

        # 標籤
        if self.tags:
            lines.append(f"Tags: {', '.join(self.tags)}")

        # 推薦配置
        if self.min_capital:
            lines.append(f"Minimum Capital: ${self.min_capital:,.2f}")

        if self.recommended_timeframes:
            lines.append(f"Recommended Timeframes: {', '.join(self.recommended_timeframes)}")

        if self.recommended_symbols:
            lines.append(f"Recommended Symbols: {', '.join(self.recommended_symbols)}")

        # 性能指標
        if include_performance and self.performance_metrics:
            lines.append("\nPerformance Metrics:")
            for metric, value in self.performance_metrics.items():
                lines.append(f"  {metric}: {value}")

        # 文檔連結
        if self.documentation_url:
            lines.append(f"\nDocumentation: {self.documentation_url}")

        # 使用範例
        if self.example_config:
            lines.append("\nExample Configuration:")
            for key, value in self.example_config.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)


class MetadataManager:
    """元數據管理器

    管理所有策略的元數據，提供查詢和過濾功能

    Example:
        >>> manager = MetadataManager()
        >>> manager.register(metadata)
        >>> stable_strategies = manager.get_by_status(StrategyStatus.STABLE)
    """

    def __init__(self):
        """初始化元數據管理器"""
        self._metadata: Dict[str, StrategyMetadata] = {}

    def register(self, metadata: StrategyMetadata) -> None:
        """註冊策略元數據

        Args:
            metadata: 策略元數據

        Example:
            >>> manager = MetadataManager()
            >>> metadata = StrategyMetadata(name="SimpleSMA", ...)
            >>> manager.register(metadata)
        """
        self._metadata[metadata.name] = metadata

    def get(self, name: str) -> Optional[StrategyMetadata]:
        """獲取策略元數據

        Args:
            name: 策略名稱

        Returns:
            策略元數據，如果不存在則返回 None

        Example:
            >>> manager = MetadataManager()
            >>> metadata = manager.get("SimpleSMA")
        """
        return self._metadata.get(name)

    def get_all(self) -> Dict[str, StrategyMetadata]:
        """獲取所有策略元數據

        Returns:
            所有策略元數據的字典

        Example:
            >>> manager = MetadataManager()
            >>> all_metadata = manager.get_all()
        """
        return self._metadata.copy()

    def get_by_category(self, category: StrategyCategory) -> List[StrategyMetadata]:
        """按分類獲取策略

        Args:
            category: 策略分類

        Returns:
            該分類下的所有策略元數據

        Example:
            >>> manager = MetadataManager()
            >>> trend_strategies = manager.get_by_category(StrategyCategory.TREND_FOLLOWING)
        """
        return [
            metadata for metadata in self._metadata.values()
            if metadata.category == category
        ]

    def get_by_status(self, status: StrategyStatus) -> List[StrategyMetadata]:
        """按狀態獲取策略

        Args:
            status: 策略狀態

        Returns:
            該狀態下的所有策略元數據

        Example:
            >>> manager = MetadataManager()
            >>> stable_strategies = manager.get_by_status(StrategyStatus.STABLE)
        """
        return [
            metadata for metadata in self._metadata.values()
            if metadata.status == status
        ]

    def get_by_tag(self, tag: str) -> List[StrategyMetadata]:
        """按標籤獲取策略

        Args:
            tag: 標籤名稱

        Returns:
            包含該標籤的所有策略元數據

        Example:
            >>> manager = MetadataManager()
            >>> beginner_strategies = manager.get_by_tag("beginner")
        """
        return [
            metadata for metadata in self._metadata.values()
            if tag in metadata.tags
        ]

    def get_production_ready(self) -> List[StrategyMetadata]:
        """獲取所有生產就緒的策略

        Returns:
            所有狀態為 STABLE 的策略元數據

        Example:
            >>> manager = MetadataManager()
            >>> production_strategies = manager.get_production_ready()
        """
        return self.get_by_status(StrategyStatus.STABLE)

    def search(self, query: str) -> List[StrategyMetadata]:
        """搜索策略

        在策略名稱、描述和標籤中搜索

        Args:
            query: 搜索關鍵字

        Returns:
            匹配的策略元數據列表

        Example:
            >>> manager = MetadataManager()
            >>> results = manager.search("sma")
        """
        query_lower = query.lower()
        results = []

        for metadata in self._metadata.values():
            # 搜索名稱
            if query_lower in metadata.name.lower():
                results.append(metadata)
                continue

            # 搜索描述
            if query_lower in metadata.description.lower():
                results.append(metadata)
                continue

            # 搜索標籤
            if any(query_lower in tag.lower() for tag in metadata.tags):
                results.append(metadata)
                continue

        return results

    def count(self) -> int:
        """獲取策略總數

        Returns:
            已註冊的策略數量

        Example:
            >>> manager = MetadataManager()
            >>> total = manager.count()
        """
        return len(self._metadata)

    def get_categories_summary(self) -> Dict[str, int]:
        """獲取分類摘要

        Returns:
            每個分類的策略數量

        Example:
            >>> manager = MetadataManager()
            >>> summary = manager.get_categories_summary()
            >>> print(summary)
            {'trend_following': 2, 'mean_reversion': 1, ...}
        """
        summary = {}
        for metadata in self._metadata.values():
            category_name = metadata.category.value
            summary[category_name] = summary.get(category_name, 0) + 1
        return summary


# 全局元數據管理器實例
_global_metadata_manager = MetadataManager()


def get_metadata_manager() -> MetadataManager:
    """獲取全局元數據管理器

    Returns:
        全局 MetadataManager 實例

    Example:
        >>> manager = get_metadata_manager()
        >>> metadata = manager.get("SimpleSMA")
    """
    return _global_metadata_manager
