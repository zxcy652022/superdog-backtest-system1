"""
Data Pipeline v0.5

統一數據管道系統 - 根據策略需求載入和管理數據

這個模組提供：
- 根據策略的 DataRequirement 自動載入數據
- 多時間週期數據載入和對齊
- 多交易對數據載入
- 數據快取機制
- 與 SSD 環境無縫整合
- v0.5: 支援資金費率和持倉量數據

Version: v0.5 (upgraded from v0.4)
Design Reference: docs/specs/planned/v0.5_perpetual_data_ecosystem_spec.md
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

# v0.5: Import perpetual data modules
from data.perpetual import FundingRateData, OpenInterestData
from data.quality import DataQualityController

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

        # v0.5 Phase A: 初始化永續數據處理器
        self.funding_rate_data = FundingRateData()
        self.open_interest_data = OpenInterestData()

        # v0.5 Phase B: 初始化新增數據處理器
        from data.perpetual import BasisData, LiquidationData, LongShortRatioData
        self.basis_data = BasisData()
        self.liquidation_data = LiquidationData()
        self.long_short_ratio_data = LongShortRatioData()

        # v0.5: 初始化數據品質控制器
        self.quality_controller = DataQualityController(strict_mode=False)

        # 數據快取
        self._cache: Dict[str, pd.DataFrame] = {}

        logger.info(f"DataPipeline v0.5 initialized with data_dir: {self.data_dir}")

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

                elif req.source == DataSource.FUNDING_RATE:
                    # v0.5 Phase A: 載入資金費率數據
                    data = self._load_funding_rate(
                        symbol, timeframe, start_date, end_date
                    )

                    if data is not None:
                        # 數據品質檢查
                        quality_result = self.quality_controller.check_funding_rate(data)
                        if not quality_result.passed:
                            logger.warning(f"Funding rate quality check failed: {quality_result.get_summary()}")

                        loaded_data['funding_rate'] = data
                    elif req.required:
                        result.success = False
                        result.error = f"Required funding rate data not found for {symbol}"
                        return result
                    else:
                        result.warnings.append(
                            f"Optional funding rate data not found for {symbol}"
                        )

                elif req.source == DataSource.OPEN_INTEREST:
                    # v0.5 Phase A: 載入持倉量數據
                    data = self._load_open_interest(
                        symbol, timeframe, start_date, end_date
                    )

                    if data is not None:
                        # 數據品質檢查
                        quality_result = self.quality_controller.check_open_interest(data)
                        if not quality_result.passed:
                            logger.warning(f"Open interest quality check failed: {quality_result.get_summary()}")

                        loaded_data['open_interest'] = data
                    elif req.required:
                        result.success = False
                        result.error = f"Required open interest data not found for {symbol}"
                        return result
                    else:
                        result.warnings.append(
                            f"Optional open interest data not found for {symbol}"
                        )

                elif req.source == DataSource.BASIS:
                    # v0.5 Phase B: 載入期現基差數據
                    data = self._load_basis(
                        symbol, timeframe, start_date, end_date
                    )

                    if data is not None:
                        loaded_data['basis'] = data
                    elif req.required:
                        result.success = False
                        result.error = f"Required basis data not found for {symbol}"
                        return result
                    else:
                        result.warnings.append(
                            f"Optional basis data not found for {symbol}"
                        )

                elif req.source == DataSource.LIQUIDATIONS:
                    # v0.5 Phase B: 載入爆倉數據
                    data = self._load_liquidations(
                        symbol, timeframe, start_date, end_date
                    )

                    if data is not None:
                        loaded_data['liquidations'] = data
                    elif req.required:
                        result.success = False
                        result.error = f"Required liquidations data not found for {symbol}"
                        return result
                    else:
                        result.warnings.append(
                            f"Optional liquidations data not found for {symbol}"
                        )

                elif req.source == DataSource.LONG_SHORT_RATIO:
                    # v0.5 Phase B: 載入多空持倉比數據
                    data = self._load_long_short_ratio(
                        symbol, timeframe, start_date, end_date
                    )

                    if data is not None:
                        loaded_data['long_short_ratio'] = data
                    elif req.required:
                        result.success = False
                        result.error = f"Required long/short ratio data not found for {symbol}"
                        return result
                    else:
                        result.warnings.append(
                            f"Optional long/short ratio data not found for {symbol}"
                        )

                else:
                    # 未支援的數據源
                    if req.required:
                        result.success = False
                        result.error = f"Data source {req.source.value} not supported yet"
                        return result
                    else:
                        result.warnings.append(
                            f"Data source {req.source.value} not supported yet, skipping"
                        )

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
        # v0.5: 使用數據品質控制器
        quality_result = self.quality_controller.check_ohlcv(df)

        if not quality_result.passed:
            logger.warning(f"OHLCV quality check failed: {quality_result.get_summary()}")
            # 自動清理數據
            df = self.quality_controller.clean_ohlcv(df, auto_fix=True)
            logger.info(f"OHLCV data cleaned, {len(df)} rows remaining")

        return df

    def _load_funding_rate(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """載入資金費率數據

        Args:
            symbol: 交易對
            timeframe: 時間週期（用於確定時間範圍）
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            資金費率 DataFrame 或 None
        """
        try:
            # 優先從存儲載入
            df = self.funding_rate_data.load(symbol, 'binance', start_date, end_date)

            # 如果存儲中沒有，嘗試從 API 獲取
            if df.empty and start_date and end_date:
                logger.info(f"Fetching funding rate data from API for {symbol}")
                df = self.funding_rate_data.fetch(
                    symbol, start_date, end_date, exchange='binance'
                )

                # 保存到存儲
                if not df.empty:
                    self.funding_rate_data.save(df, symbol, 'binance')

            return df if not df.empty else None

        except Exception as e:
            logger.error(f"Error loading funding rate data: {e}")
            return None

    def _load_open_interest(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """載入持倉量數據

        Args:
            symbol: 交易對
            timeframe: 時間週期
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            持倉量 DataFrame 或 None
        """
        try:
            # 優先從存儲載入
            df = self.open_interest_data.load(symbol, 'binance', timeframe, start_date, end_date)

            # 如果存儲中沒有，嘗試從 API 獲取
            if df.empty and start_date and end_date:
                logger.info(f"Fetching open interest data from API for {symbol}")
                df = self.open_interest_data.fetch(
                    symbol, start_date, end_date, interval=timeframe, exchange='binance'
                )

                # 保存到存儲
                if not df.empty:
                    self.open_interest_data.save(df, symbol, 'binance', interval=timeframe)

            return df if not df.empty else None

        except Exception as e:
            logger.error(f"Error loading open interest data: {e}")
            return None

    def _load_basis(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """載入期現基差數據 (v0.5 Phase B)

        Args:
            symbol: 交易對
            timeframe: 時間週期
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            基差 DataFrame 或 None
        """
        try:
            # 優先從存儲載入
            df = self.basis_data.load(symbol, 'binance', start_date, end_date)

            # 如果存儲中沒有，嘗試從 API 計算
            if df.empty and start_date and end_date:
                logger.info(f"Calculating basis data from API for {symbol}")
                df = self.basis_data.fetch_and_calculate(
                    symbol, start_date, end_date, interval=timeframe, exchange='binance'
                )

                # 保存到存儲
                if not df.empty:
                    self.basis_data.save(df, symbol, 'binance')

            return df if not df.empty else None

        except Exception as e:
            logger.error(f"Error loading basis data: {e}")
            return None

    def _load_liquidations(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """載入爆倉數據 (v0.5 Phase B)

        Args:
            symbol: 交易對
            timeframe: 時間週期
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            爆倉 DataFrame 或 None
        """
        try:
            # 優先從存儲載入
            df = self.liquidation_data.load(symbol, 'binance', start_date, end_date)

            # 如果存儲中沒有，嘗試從 API 獲取
            if df.empty and start_date and end_date:
                logger.info(f"Fetching liquidation data from API for {symbol}")
                df = self.liquidation_data.fetch(
                    symbol, start_date, end_date, exchange='binance'
                )

                # 保存到存儲
                if not df.empty:
                    self.liquidation_data.save(df, symbol, 'binance')

            return df if not df.empty else None

        except Exception as e:
            logger.error(f"Error loading liquidation data: {e}")
            return None

    def _load_long_short_ratio(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """載入多空持倉比數據 (v0.5 Phase B)

        Args:
            symbol: 交易對
            timeframe: 時間週期
            start_date: 開始日期
            end_date: 結束日期

        Returns:
            多空比 DataFrame 或 None
        """
        try:
            # 優先從存儲載入
            df = self.long_short_ratio_data.load(symbol, 'binance', start_date, end_date)

            # 如果存儲中沒有，嘗試從 API 獲取
            if df.empty and start_date and end_date:
                logger.info(f"Fetching long/short ratio data from API for {symbol}")
                df = self.long_short_ratio_data.fetch(
                    symbol, start_date, end_date, interval=timeframe, exchange='binance'
                )

                # 保存到存儲
                if not df.empty:
                    self.long_short_ratio_data.save(df, symbol, 'binance')

            return df if not df.empty else None

        except Exception as e:
            logger.error(f"Error loading long/short ratio data: {e}")
            return None

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
