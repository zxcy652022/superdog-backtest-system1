"""
Data Pipeline v0.4

統一數據管道系統 - 根據策略需求載入和管理數據

這個模組提供：
- 根據策略的 DataRequirement 自動載入數據
- 多時間週期數據載入和對齊
- 多交易對數據載入
- 數據快取機制
- 與 SSD 環境無縫整合

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import logging

from strategies.api_v2 import BaseStrategy, DataSource, DataRequirement
from data.timeframe_manager import TimeframeManager, Timeframe
from data.symbol_manager import SymbolManager
from data_config import config

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class DataLoadResult:
    """數據載入結果

    Attributes:
        success: 是否成功載入
        data: 載入的數據（如果成功）
        error: 錯誤訊息（如果失敗）
        warnings: 警告訊息列表
        metadata: 數據元數據（行數、時間範圍等）

    Example:
        >>> result = DataLoadResult(
        ...     success=True,
        ...     data={'ohlcv': df},
        ...     metadata={'rows': 1000, 'start': '2023-01-01'}
        ... )
    """
    success: bool
    data: Optional[Dict[str, pd.DataFrame]] = None
    error: Optional[str] = None
    warnings: List[str] = None
    metadata: Optional[Dict[str, any]] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}


class DataPipeline:
    """數據管道系統

    根據策略需求自動載入和準備數據

    Features:
    - 自動根據策略的 DataRequirement 載入數據
    - 支援多時間週期數據重採樣和對齊
    - 數據快取機制（減少重複載入）
    - 與 SSD 環境整合
    - 數據驗證和清理

    Example:
        >>> pipeline = DataPipeline()
        >>> strategy = SimpleSMAStrategyV2()
        >>> result = pipeline.load_strategy_data(strategy, "BTCUSDT", "1h")
        >>> if result.success:
        ...     data = result.data
        ...     signals = strategy.compute_signals(data, params)
    """

    def __init__(self, data_dir: Optional[Path] = None, enable_cache: bool = True):
        """初始化數據管道

        Args:
            data_dir: 數據目錄路徑（默認使用 SSD 配置）
            enable_cache: 是否啟用數據快取
        """
        self.data_dir = data_dir or config.data_root
        self.enable_cache = enable_cache

        # 初始化管理器
        self.timeframe_manager = TimeframeManager()
        self.symbol_manager = SymbolManager()

        # 數據快取
        self._cache: Dict[str, pd.DataFrame] = {}

        logger.info(f"DataPipeline initialized with data_dir: {self.data_dir}")

    def load_strategy_data(
        self,
        strategy: BaseStrategy,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> DataLoadResult:
        """載入策略所需的所有數據

        根據策略的 get_data_requirements() 自動載入對應數據

        Args:
            strategy: 策略實例
            symbol: 交易對（如 BTCUSDT）
            timeframe: 時間週期（如 1h）
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）

        Returns:
            DataLoadResult 包含載入的數據或錯誤訊息

        Example:
            >>> pipeline = DataPipeline()
            >>> strategy = KawamokuStrategy()
            >>> result = pipeline.load_strategy_data(strategy, "BTCUSDT", "1h")
            >>> if result.success:
            ...     print(f"Loaded {result.metadata['rows']} bars")
        """
        result = DataLoadResult(success=True)

        # 1. 驗證交易對
        if not self.symbol_manager.validate_symbol(symbol):
            result.success = False
            result.error = f"Invalid symbol: {symbol}"
            return result

        # 2. 驗證時間週期
        if not self.timeframe_manager.validate_timeframe(timeframe):
            result.success = False
            result.error = f"Invalid timeframe: {timeframe}"
            return result

        # 3. 獲取策略的數據需求
        requirements = strategy.get_data_requirements()

        # 4. 載入各類數據
        loaded_data = {}

        for req in requirements:
            try:
                if req.source == DataSource.OHLCV:
                    # 載入 OHLCV 數據
                    data = self._load_ohlcv(
                        symbol, timeframe, req.timeframes, start_date, end_date
                    )

                    if data is not None:
                        loaded_data['ohlcv'] = data
                    elif req.required:
                        result.success = False
                        result.error = f"Required OHLCV data not found for {symbol}"
                        return result
                    else:
                        result.warnings.append(
                            f"Optional OHLCV data not found for {symbol}"
                        )

                elif req.source == DataSource.FUNDING:
                    # v0.4: Funding 數據尚未支援
                    if req.required:
                        result.success = False
                        result.error = "Funding rate data not supported in v0.4"
                        return result
                    else:
                        result.warnings.append(
                            "Funding rate data not available in v0.4 (coming in v0.5)"
                        )

                elif req.source == DataSource.OPEN_INTEREST:
                    # v0.4: OI 數據尚未支援
                    if req.required:
                        result.success = False
                        result.error = "Open interest data not supported in v0.4"
                        return result
                    else:
                        result.warnings.append(
                            "Open interest data not available in v0.4 (coming in v0.5)"
                        )

                else:
                    # 其他數據源
                    if req.required:
                        result.success = False
                        result.error = f"Data source {req.source.value} not supported"
                        return result

            except Exception as e:
                logger.error(f"Error loading data for {req.source.value}: {e}")
                if req.required:
                    result.success = False
                    result.error = f"Error loading {req.source.value}: {str(e)}"
                    return result
                else:
                    result.warnings.append(f"Error loading optional {req.source.value}: {str(e)}")

        # 5. 驗證數據完整性
        if not loaded_data:
            result.success = False
            result.error = "No data loaded"
            return result

        # 6. 添加元數據
        if 'ohlcv' in loaded_data:
            df = loaded_data['ohlcv']
            result.metadata = {
                'rows': len(df),
                'start_date': df.index[0].strftime('%Y-%m-%d') if len(df) > 0 else None,
                'end_date': df.index[-1].strftime('%Y-%m-%d') if len(df) > 0 else None,
                'symbol': symbol,
                'timeframe': timeframe
            }

        result.data = loaded_data

        logger.info(
            f"Successfully loaded data for {symbol} ({timeframe}): "
            f"{result.metadata.get('rows', 0)} bars"
        )

        return result

    def _load_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        required_timeframes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """載入 OHLCV 數據

        Args:
            symbol: 交易對
            timeframe: 主要時間週期
            required_timeframes: 需要的其他時間週期（可選）
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）

        Returns:
            OHLCV DataFrame 或 None
        """
        # 1. 檢查快取
        cache_key = f"{symbol}_{timeframe}"
        if self.enable_cache and cache_key in self._cache:
            logger.debug(f"Loading {cache_key} from cache")
            df = self._cache[cache_key]
        else:
            # 2. 從文件載入
            df = self._load_ohlcv_from_file(symbol, timeframe)

            if df is None:
                return None

            # 3. 存入快取
            if self.enable_cache:
                self._cache[cache_key] = df

        # 4. 過濾日期範圍
        if start_date:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df.index <= pd.Timestamp(end_date)]

        # 5. 數據驗證
        df = self._validate_ohlcv(df)

        return df

    def _load_ohlcv_from_file(
        self, symbol: str, timeframe: str
    ) -> Optional[pd.DataFrame]:
        """從文件載入 OHLCV 數據

        Args:
            symbol: 交易對
            timeframe: 時間週期

        Returns:
            OHLCV DataFrame 或 None
        """
        # 構建文件路徑（兼容 SSD 環境）
        # 檢查歷史數據目錄（binance）
        file_path = self.data_dir / "historical" / "binance" / f"{symbol}_{timeframe}.csv"

        # 如果不存在，嘗試 raw 目錄（向後兼容）
        if not file_path.exists():
            file_path = self.data_dir / "raw" / f"{symbol}_{timeframe}.csv"

        if not file_path.exists():
            logger.warning(f"Data file not found: {file_path}")
            return None

        try:
            # 載入數據
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)

            # 確保列名正確
            expected_columns = ['open', 'high', 'low', 'close', 'volume']
            df.columns = df.columns.str.lower()

            if not all(col in df.columns for col in expected_columns):
                logger.error(f"Missing required columns in {file_path}")
                return None

            # 只保留需要的列
            df = df[expected_columns]

            logger.debug(f"Loaded {len(df)} bars from {file_path}")
            return df

        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None

    def _validate_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """驗證和清理 OHLCV 數據

        Args:
            df: OHLCV DataFrame

        Returns:
            清理後的 DataFrame
        """
        # 1. 刪除重複的索引
        df = df[~df.index.duplicated(keep='first')]

        # 2. 排序
        df = df.sort_index()

        # 3. 刪除 NaN 值
        initial_rows = len(df)
        df = df.dropna()

        if len(df) < initial_rows:
            logger.warning(f"Dropped {initial_rows - len(df)} rows with NaN values")

        # 4. 驗證價格邏輯（high >= low, close 在 [low, high] 之間）
        invalid_mask = (df['high'] < df['low']) | (df['close'] > df['high']) | (df['close'] < df['low'])

        if invalid_mask.any():
            logger.warning(f"Found {invalid_mask.sum()} rows with invalid price relationships")
            df = df[~invalid_mask]

        # 5. 刪除零價格或負價格
        invalid_price_mask = (df['close'] <= 0) | (df['open'] <= 0)

        if invalid_price_mask.any():
            logger.warning(f"Found {invalid_price_mask.sum()} rows with invalid prices")
            df = df[~invalid_price_mask]

        return df

    def load_multiple_symbols(
        self,
        strategy: BaseStrategy,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, DataLoadResult]:
        """載入多個交易對的數據

        Args:
            strategy: 策略實例
            symbols: 交易對列表
            timeframe: 時間週期
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）

        Returns:
            字典，鍵為交易對，值為 DataLoadResult

        Example:
            >>> pipeline = DataPipeline()
            >>> strategy = SimpleSMAStrategyV2()
            >>> symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            >>> results = pipeline.load_multiple_symbols(strategy, symbols, "1h")
            >>> for symbol, result in results.items():
            ...     if result.success:
            ...         print(f"{symbol}: {result.metadata['rows']} bars")
        """
        results = {}

        for symbol in symbols:
            results[symbol] = self.load_strategy_data(
                strategy, symbol, timeframe, start_date, end_date
            )

        # 統計
        successful = sum(1 for r in results.values() if r.success)
        logger.info(
            f"Loaded data for {successful}/{len(symbols)} symbols successfully"
        )

        return results

    def clear_cache(self) -> None:
        """清除數據快取

        Example:
            >>> pipeline = DataPipeline()
            >>> pipeline.clear_cache()
        """
        self._cache.clear()
        logger.info("Data cache cleared")

    def get_cache_stats(self) -> Dict[str, any]:
        """獲取快取統計信息

        Returns:
            快取統計字典

        Example:
            >>> pipeline = DataPipeline()
            >>> stats = pipeline.get_cache_stats()
            >>> print(f"Cached items: {stats['count']}")
        """
        total_memory = sum(
            df.memory_usage(deep=True).sum()
            for df in self._cache.values()
        )

        return {
            'count': len(self._cache),
            'keys': list(self._cache.keys()),
            'memory_mb': total_memory / 1024 / 1024
        }

    def preload_data(
        self,
        symbols: List[str],
        timeframes: List[str]
    ) -> Tuple[int, int]:
        """預載入數據到快取

        Args:
            symbols: 交易對列表
            timeframes: 時間週期列表

        Returns:
            (成功數量, 失敗數量)

        Example:
            >>> pipeline = DataPipeline()
            >>> symbols = ["BTCUSDT", "ETHUSDT"]
            >>> timeframes = ["1h", "4h"]
            >>> success, failed = pipeline.preload_data(symbols, timeframes)
            >>> print(f"Preloaded: {success} successful, {failed} failed")
        """
        if not self.enable_cache:
            logger.warning("Cache is disabled, preload_data has no effect")
            return 0, 0

        success = 0
        failed = 0

        for symbol in symbols:
            for timeframe in timeframes:
                df = self._load_ohlcv(symbol, timeframe)

                if df is not None:
                    success += 1
                else:
                    failed += 1

        logger.info(f"Preloaded {success} datasets, {failed} failed")
        return success, failed


# 全局管道實例
_global_pipeline = DataPipeline()


def get_pipeline() -> DataPipeline:
    """獲取全局數據管道實例

    Returns:
        全局 DataPipeline 實例

    Example:
        >>> pipeline = get_pipeline()
        >>> result = pipeline.load_strategy_data(strategy, "BTCUSDT", "1h")
    """
    return _global_pipeline


def load_strategy_data(
    strategy: BaseStrategy,
    symbol: str,
    timeframe: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> DataLoadResult:
    """載入策略數據的便捷函數

    Args:
        strategy: 策略實例
        symbol: 交易對
        timeframe: 時間週期
        start_date: 開始日期（可選）
        end_date: 結束日期（可選）

    Returns:
        DataLoadResult

    Example:
        >>> from strategies.simple_sma_v2 import SimpleSMAStrategyV2
        >>> strategy = SimpleSMAStrategyV2()
        >>> result = load_strategy_data(strategy, "BTCUSDT", "1h")
        >>> if result.success:
        ...     data = result.data
    """
    return get_pipeline().load_strategy_data(
        strategy, symbol, timeframe, start_date, end_date
    )
