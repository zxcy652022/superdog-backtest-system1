"""
Universe Manager v0.6

幣種宇宙核心管理器 - 自動分類和管理加密貨幣宇宙

核心功能:
- 構建幣種宇宙（計算屬性、執行分類）
- 加載歷史宇宙快照
- 匯出宇宙配置文件（YAML/JSON）
- 管理宇宙元數據

Version: v0.6 Phase 1
Design Reference: docs/specs/v0.6/superdog_v06_universe_manager_spec.md
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from data.universe_calculator import UniverseCalculator, calculate_all_metrics

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SymbolMetadata:
    """幣種元數據結構"""

    symbol: str
    volume_30d_usd: float  # 30日平均成交額
    volume_7d_usd: float  # 7日平均成交額
    history_days: int  # 上市天數
    market_cap_rank: Optional[int]  # 市值排名
    oi_avg_usd: float  # 平均持倉量
    oi_trend: float  # 持倉量趨勢(-1到1)
    has_perpetual: bool  # 是否有永續合約
    is_stablecoin: bool  # 是否穩定幣
    is_defi: bool  # 是否DeFi代幣
    is_layer1: bool  # 是否Layer1
    is_meme: bool  # 是否Meme幣
    classification: str  # 分類結果
    last_updated: str  # 最後更新時間

    def to_dict(self) -> Dict:
        """轉換為字典"""
        return asdict(self)


@dataclass
class UniverseSnapshot:
    """宇宙快照數據結構"""

    date: str
    symbols: Dict[str, SymbolMetadata]
    classification: Dict[str, List[str]]
    statistics: Dict[str, int]

    def to_dict(self) -> Dict:
        """轉換為字典（用於序列化）"""
        return {
            "date": self.date,
            "symbols": {k: v.to_dict() for k, v in self.symbols.items()},
            "classification": self.classification,
            "statistics": self.statistics,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "UniverseSnapshot":
        """從字典創建快照"""
        symbols = {k: SymbolMetadata(**v) for k, v in data["symbols"].items()}

        return cls(
            date=data["date"],
            symbols=symbols,
            classification=data["classification"],
            statistics=data["statistics"],
        )


class ClassificationRules:
    """幣種分類規則

    根據成交額和市值進行四級分類:
    - large_cap: 大盤幣
    - mid_cap: 中盤幣
    - small_cap: 小盤幣
    - micro_cap: 微盤幣
    """

    @staticmethod
    def classify_by_market_cap(metadata: SymbolMetadata) -> str:
        """基於市值和成交額的分類

        分類標準:
        1. large_cap: 30日平均成交額 > $1B 或 市值排名 <= 10
        2. mid_cap: 30日平均成交額 > $100M 或 市值排名 <= 50
        3. small_cap: 30日平均成交額 > $10M 或 市值排名 <= 200
        4. micro_cap: 其他

        Args:
            metadata: 幣種元數據

        Returns:
            str: 分類結果 ('large_cap', 'mid_cap', 'small_cap', 'micro_cap')
        """
        volume_30d = metadata.volume_30d_usd
        rank = metadata.market_cap_rank or 9999

        # Large Cap: 頂級幣種
        if volume_30d > 1_000_000_000 or rank <= 10:
            return "large_cap"

        # Mid Cap: 中等市值
        elif volume_30d > 100_000_000 or rank <= 50:
            return "mid_cap"

        # Small Cap: 小市值但有流動性
        elif volume_30d > 10_000_000 or rank <= 200:
            return "small_cap"

        # Micro Cap: 微小市值
        else:
            return "micro_cap"

    @staticmethod
    def apply_filters(
        metadata: SymbolMetadata,
        exclude_stablecoins: bool = True,
        min_history_days: int = 90,
        min_volume: float = 1_000_000,
    ) -> bool:
        """應用篩選規則

        Args:
            metadata: 幣種元數據
            exclude_stablecoins: 是否排除穩定幣
            min_history_days: 最小上市天數
            min_volume: 最小30日平均成交額

        Returns:
            bool: 是否通過篩選
        """
        # 排除穩定幣
        if exclude_stablecoins and metadata.is_stablecoin:
            return False

        # 上市天數過短
        if metadata.history_days < min_history_days:
            return False

        # 成交額過低
        if metadata.volume_30d_usd < min_volume:
            return False

        return True


class UniverseManager:
    """幣種宇宙核心管理器

    Example:
        >>> manager = UniverseManager()
        >>> universe = manager.build_universe(['BTCUSDT', 'ETHUSDT'])
        >>> print(universe.statistics)
        >>> manager.save_universe(universe)
    """

    def __init__(self, data_dir: Optional[str] = None, universe_dir: Optional[str] = None):
        """初始化管理器

        Args:
            data_dir: OHLCV數據目錄
            universe_dir: 宇宙數據目錄
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "raw"
        if universe_dir is None:
            universe_dir = Path(__file__).parent / "universe"

        self.data_dir = Path(data_dir)
        self.universe_dir = Path(universe_dir)
        self.calculator = UniverseCalculator(data_dir)

        # 確保目錄存在
        self.universe_dir.mkdir(parents=True, exist_ok=True)
        (self.universe_dir / "metadata").mkdir(exist_ok=True)
        (self.universe_dir / "snapshots").mkdir(exist_ok=True)
        (self.universe_dir / "configs").mkdir(exist_ok=True)

    def build_universe(
        self,
        symbols: Optional[List[str]] = None,
        date_str: Optional[str] = None,
        exclude_stablecoins: bool = True,
        min_history_days: int = 90,
        min_volume: float = 1_000_000,
        parallel: bool = True,
        max_workers: int = 10,
    ) -> UniverseSnapshot:
        """構建幣種宇宙

        Args:
            symbols: 幣種列表，None則自動發現
            date_str: 快照日期，None則使用今天
            exclude_stablecoins: 是否排除穩定幣
            min_history_days: 最小上市天數
            min_volume: 最小30日平均成交額
            parallel: 是否並行計算
            max_workers: 並行線程數

        Returns:
            UniverseSnapshot: 宇宙快照

        Example:
            >>> universe = manager.build_universe(
            ...     symbols=['BTCUSDT', 'ETHUSDT'],
            ...     exclude_stablecoins=True,
            ...     min_history_days=90
            ... )
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"開始構建宇宙 (日期: {date_str})")

        # 獲取幣種列表
        if symbols is None:
            symbols = self._discover_symbols()

        logger.info(f"找到 {len(symbols)} 個幣種")

        # 計算幣種屬性（並行或串行）
        if parallel:
            all_metadata = self._calculate_parallel(symbols, max_workers)
        else:
            all_metadata = self._calculate_sequential(symbols)

        logger.info(f"成功計算 {len(all_metadata)} 個幣種的屬性")

        # 應用篩選規則
        filtered_metadata = {}
        for symbol, metadata in all_metadata.items():
            if ClassificationRules.apply_filters(
                metadata,
                exclude_stablecoins=exclude_stablecoins,
                min_history_days=min_history_days,
                min_volume=min_volume,
            ):
                filtered_metadata[symbol] = metadata

        logger.info(f"篩選後剩餘 {len(filtered_metadata)} 個幣種")

        # 執行分類
        classification = self._classify_symbols(filtered_metadata)

        # 計算統計數據
        statistics = self._calculate_statistics(classification)

        # 創建快照
        snapshot = UniverseSnapshot(
            date=date_str,
            symbols=filtered_metadata,
            classification=classification,
            statistics=statistics,
        )

        logger.info("宇宙構建完成")
        logger.info(f"分類統計: {statistics}")

        return snapshot

    def save_universe(self, snapshot: UniverseSnapshot, filename: Optional[str] = None) -> str:
        """保存宇宙快照

        Args:
            snapshot: 宇宙快照
            filename: 文件名，None則自動生成

        Returns:
            str: 保存的文件路徑
        """
        if filename is None:
            filename = f"universe_{snapshot.date}.json"

        file_path = self.universe_dir / "snapshots" / filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"宇宙快照已保存到: {file_path}")
        return str(file_path)

    def load_universe(self, date_str: str) -> UniverseSnapshot:
        """加載歷史宇宙快照

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)

        Returns:
            UniverseSnapshot: 宇宙快照

        Raises:
            FileNotFoundError: 找不到快照文件
        """
        filename = f"universe_{date_str}.json"
        file_path = self.universe_dir / "snapshots" / filename

        if not file_path.exists():
            raise FileNotFoundError(f"找不到快照文件: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        snapshot = UniverseSnapshot.from_dict(data)
        logger.info(f"已加載快照: {date_str}")

        return snapshot

    def export_config(
        self,
        snapshot: UniverseSnapshot,
        universe_type: str = "large_cap",
        top_n: Optional[int] = None,
        format: str = "yaml",
        filename: Optional[str] = None,
    ) -> str:
        """匯出宇宙配置文件

        Args:
            snapshot: 宇宙快照
            universe_type: 宇宙類型 ('large_cap', 'mid_cap', 'small_cap', 'micro_cap')
            top_n: 只取前N個（按成交額排序），None則全部
            format: 輸出格式 ('yaml' or 'json')
            filename: 文件名，None則自動生成

        Returns:
            str: 配置文件路徑
        """
        # 獲取指定分類的幣種
        symbols = snapshot.classification.get(universe_type, [])

        if not symbols:
            logger.warning(f"沒有找到 {universe_type} 分類的幣種")
            return ""

        # 按成交額排序
        sorted_symbols = sorted(
            symbols, key=lambda s: snapshot.symbols[s].volume_30d_usd, reverse=True
        )

        # 取前N個
        if top_n:
            sorted_symbols = sorted_symbols[:top_n]

        # 構建配置
        config = {
            "universe_type": universe_type,
            "date": snapshot.date,
            "total_symbols": len(sorted_symbols),
            "symbols": sorted_symbols,
            "metadata": {symbol: snapshot.symbols[symbol].to_dict() for symbol in sorted_symbols},
        }

        # 生成文件名
        if filename is None:
            count_str = f"_top{top_n}" if top_n else ""
            filename = f"{universe_type}{count_str}_{snapshot.date}.{format}"

        file_path = self.universe_dir / "configs" / filename

        # 保存文件
        with open(file_path, "w", encoding="utf-8") as f:
            if format == "yaml":
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            else:
                json.dump(config, f, indent=2, ensure_ascii=False)

        logger.info(f"配置文件已匯出到: {file_path}")
        return str(file_path)

    def get_available_dates(self) -> List[str]:
        """獲取可用的快照日期列表

        Returns:
            List[str]: 日期列表
        """
        snapshots_dir = self.universe_dir / "snapshots"
        dates = []

        for file in snapshots_dir.glob("universe_*.json"):
            # Extract date from filename: universe_2024-12-07.json
            date_str = file.stem.replace("universe_", "")
            dates.append(date_str)

        return sorted(dates, reverse=True)

    # ===== 私有方法 =====

    def _discover_symbols(self) -> List[str]:
        """自動發現可用的幣種

        Returns:
            List[str]: 幣種列表
        """
        symbols = set()

        # 從data/raw目錄掃描CSV文件
        for file in self.data_dir.glob("*_1d.csv"):
            # 提取幣種: BTCUSDT_1d.csv -> BTCUSDT
            symbol = file.stem.replace("_1d", "")
            symbols.add(symbol)

        return sorted(list(symbols))

    def _calculate_parallel(
        self, symbols: List[str], max_workers: int
    ) -> Dict[str, SymbolMetadata]:
        """並行計算幣種屬性

        Args:
            symbols: 幣種列表
            max_workers: 最大線程數

        Returns:
            Dict[str, SymbolMetadata]: 幣種元數據字典
        """
        all_metadata = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任務
            future_to_symbol = {
                executor.submit(self._calculate_symbol_metadata, symbol): symbol
                for symbol in symbols
            }

            # 收集結果
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    metadata = future.result()
                    if metadata:
                        all_metadata[symbol] = metadata
                except Exception as e:
                    logger.warning(f"計算 {symbol} 失敗: {e}")

        return all_metadata

    def _calculate_sequential(self, symbols: List[str]) -> Dict[str, SymbolMetadata]:
        """串行計算幣種屬性

        Args:
            symbols: 幣種列表

        Returns:
            Dict[str, SymbolMetadata]: 幣種元數據字典
        """
        all_metadata = {}

        for i, symbol in enumerate(symbols, 1):
            try:
                logger.info(f"計算 [{i}/{len(symbols)}] {symbol}")
                metadata = self._calculate_symbol_metadata(symbol)
                if metadata:
                    all_metadata[symbol] = metadata
            except Exception as e:
                logger.warning(f"計算 {symbol} 失敗: {e}")

        return all_metadata

    def _calculate_symbol_metadata(self, symbol: str) -> Optional[SymbolMetadata]:
        """計算單個幣種的元數據

        Args:
            symbol: 幣種符號

        Returns:
            Optional[SymbolMetadata]: 元數據對象，失敗則返回None
        """
        try:
            metrics = calculate_all_metrics(symbol, days=30, calculator=self.calculator)

            if "error" in metrics:
                return None

            # 執行分類（臨時，稍後會批量重新分類）
            temp_metadata = SymbolMetadata(
                symbol=symbol,
                volume_30d_usd=metrics["volume_30d_avg"],
                volume_7d_usd=metrics["volume_7d_avg"],
                history_days=metrics["history_days"],
                market_cap_rank=metrics["market_cap_rank"],
                oi_avg_usd=metrics["oi_avg_usd"],
                oi_trend=metrics["oi_trend"],
                has_perpetual=metrics["has_perpetual"],
                is_stablecoin=metrics["is_stablecoin"],
                is_defi=metrics["is_defi"],
                is_layer1=metrics["is_layer1"],
                is_meme=metrics["is_meme"],
                classification="",  # 暫時為空
                last_updated=metrics["last_updated"],
            )

            # 分類
            classification = ClassificationRules.classify_by_market_cap(temp_metadata)
            temp_metadata.classification = classification

            return temp_metadata

        except Exception as e:
            logger.error(f"計算 {symbol} 元數據失敗: {e}")
            return None

    def _classify_symbols(self, metadata_dict: Dict[str, SymbolMetadata]) -> Dict[str, List[str]]:
        """將幣種分類

        Args:
            metadata_dict: 元數據字典

        Returns:
            Dict[str, List[str]]: 分類結果 {classification: [symbols]}
        """
        classification = {"large_cap": [], "mid_cap": [], "small_cap": [], "micro_cap": []}

        for symbol, metadata in metadata_dict.items():
            cat = metadata.classification
            if cat in classification:
                classification[cat].append(symbol)

        return classification

    def _calculate_statistics(self, classification: Dict[str, List[str]]) -> Dict[str, int]:
        """計算統計數據

        Args:
            classification: 分類結果

        Returns:
            Dict[str, int]: 統計數據
        """
        total = sum(len(symbols) for symbols in classification.values())

        return {
            "total": total,
            "large_cap": len(classification.get("large_cap", [])),
            "mid_cap": len(classification.get("mid_cap", [])),
            "small_cap": len(classification.get("small_cap", [])),
            "micro_cap": len(classification.get("micro_cap", [])),
        }


# ===== 便捷函數 =====


def get_universe_manager(
    data_dir: Optional[str] = None, universe_dir: Optional[str] = None
) -> UniverseManager:
    """獲取宇宙管理器實例

    便捷函數，用於快速創建管理器

    Args:
        data_dir: 數據目錄
        universe_dir: 宇宙目錄

    Returns:
        UniverseManager: 管理器實例
    """
    return UniverseManager(data_dir=data_dir, universe_dir=universe_dir)
