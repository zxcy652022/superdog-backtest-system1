"""
Funding Rate Data Processing for SuperDog v0.5

資金費率數據處理層 - 提供高層級的資金費率數據操作介面

Features:
- Multi-exchange funding rate data aggregation
- Data normalization and standardization
- Historical data fetching and caching
- Integration with storage layer
- Data validation and quality checks

Version: v0.5
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import logging

from data.exchanges.base_connector import ExchangeConnector
from data.exchanges.binance_connector import BinanceConnector

logger = logging.getLogger(__name__)


class FundingRateData:
    """資金費率數據處理類

    提供資金費率數據的獲取、處理、存儲功能

    Example:
        >>> fr = FundingRateData()
        >>> df = fr.fetch('BTCUSDT', '2024-01-01', '2024-01-31', exchange='binance')
        >>> stats = fr.calculate_statistics(df)
        >>> fr.save(df, 'BTCUSDT', 'binance')
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """初始化資金費率數據處理器

        Args:
            storage_path: 數據存儲路徑（默認使用 SSD）
        """
        self.storage_path = storage_path or Path("/Volumes/權志龍的寶藏/SuperDogData/perpetual/funding_rate")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 初始化交易所連接器
        self.connectors: Dict[str, ExchangeConnector] = {
            'binance': BinanceConnector()
        }

        # 數據快取
        self._cache: Dict[str, pd.DataFrame] = {}

    def fetch(
        self,
        symbol: str,
        start_time: Union[str, datetime],
        end_time: Union[str, datetime],
        exchange: str = 'binance',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """獲取資金費率數據

        Args:
            symbol: 交易對（如 'BTCUSDT'）
            start_time: 開始時間
            end_time: 結束時間
            exchange: 交易所名稱
            use_cache: 是否使用快取

        Returns:
            DataFrame with columns:
                - timestamp: 時間戳
                - symbol: 交易對
                - funding_rate: 資金費率
                - mark_price: 標記價格
                - exchange: 交易所
                - annual_rate: 年化費率（計算欄位）

        Raises:
            ValueError: 當交易所不支援或參數無效時
        """
        # 標準化時間格式
        if isinstance(start_time, str):
            start_time = pd.to_datetime(start_time)
        if isinstance(end_time, str):
            end_time = pd.to_datetime(end_time)

        # 檢查交易所
        if exchange not in self.connectors:
            raise ValueError(f"Unsupported exchange: {exchange}")

        # 檢查快取
        cache_key = f"{exchange}_{symbol}_{start_time}_{end_time}"
        if use_cache and cache_key in self._cache:
            logger.info(f"Using cached data for {symbol} on {exchange}")
            return self._cache[cache_key].copy()

        # 從交易所獲取數據
        logger.info(f"Fetching funding rate data for {symbol} on {exchange}")
        connector = self.connectors[exchange]

        try:
            df = connector.get_funding_rate(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time
            )

            if df.empty:
                logger.warning(f"No funding rate data found for {symbol} on {exchange}")
                return pd.DataFrame()

            # 添加交易所標籤
            df['exchange'] = exchange

            # 計算年化費率（資金費率每8小時結算一次，年化 = rate * 3 * 365）
            df['annual_rate'] = df['funding_rate'] * 3 * 365

            # 重新排序欄位
            df = df[[
                'timestamp', 'symbol', 'exchange',
                'funding_rate', 'annual_rate', 'mark_price'
            ]]

            # 快取數據
            if use_cache:
                self._cache[cache_key] = df.copy()

            logger.info(f"Fetched {len(df)} funding rate records for {symbol}")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch funding rate data: {e}")
            raise

    def fetch_multiple_exchanges(
        self,
        symbol: str,
        start_time: Union[str, datetime],
        end_time: Union[str, datetime],
        exchanges: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """從多個交易所獲取資金費率數據並合併

        Args:
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間
            exchanges: 交易所列表（None = 所有支援的交易所）

        Returns:
            合併的 DataFrame，包含所有交易所的數據
        """
        if exchanges is None:
            exchanges = list(self.connectors.keys())

        all_data = []

        for exchange in exchanges:
            try:
                df = self.fetch(symbol, start_time, end_time, exchange)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.warning(f"Failed to fetch from {exchange}: {e}")
                continue

        if not all_data:
            return pd.DataFrame()

        # 合併所有數據
        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values(['timestamp', 'exchange']).reset_index(drop=True)

        logger.info(f"Fetched {len(combined)} total records from {len(all_data)} exchanges")

        return combined

    def calculate_statistics(
        self,
        df: pd.DataFrame,
        window: Optional[int] = None
    ) -> Dict[str, Any]:
        """計算資金費率統計指標

        Args:
            df: 資金費率 DataFrame
            window: 滾動窗口大小（None = 全部數據）

        Returns:
            統計指標字典：
                - mean: 平均費率
                - median: 中位數
                - std: 標準差
                - min: 最小值
                - max: 最大值
                - positive_ratio: 正費率比例
                - negative_ratio: 負費率比例
                - extreme_count: 極端費率次數 (|rate| > 0.1%)
                - avg_annual_rate: 平均年化費率
        """
        if df.empty:
            return {}

        rates = df['funding_rate']

        stats = {
            'mean': rates.mean(),
            'median': rates.median(),
            'std': rates.std(),
            'min': rates.min(),
            'max': rates.max(),
            'positive_ratio': (rates > 0).sum() / len(rates),
            'negative_ratio': (rates < 0).sum() / len(rates),
            'extreme_count': (rates.abs() > 0.001).sum(),  # |rate| > 0.1%
            'avg_annual_rate': df['annual_rate'].mean()
        }

        # 如果指定窗口，計算滾動統計
        if window is not None:
            stats['rolling_mean'] = rates.rolling(window).mean()
            stats['rolling_std'] = rates.rolling(window).std()

        return stats

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        threshold: float = 0.005  # 0.5%
    ) -> pd.DataFrame:
        """檢測資金費率異常值

        Args:
            df: 資金費率 DataFrame
            threshold: 異常閾值（絕對值）

        Returns:
            包含異常標記的 DataFrame，新增欄位：
                - is_anomaly: 是否為異常值
                - anomaly_type: 異常類型（extreme_positive/extreme_negative）
        """
        df = df.copy()

        # 標記異常值
        df['is_anomaly'] = df['funding_rate'].abs() > threshold

        # 分類異常類型
        df['anomaly_type'] = 'normal'
        df.loc[df['funding_rate'] > threshold, 'anomaly_type'] = 'extreme_positive'
        df.loc[df['funding_rate'] < -threshold, 'anomaly_type'] = 'extreme_negative'

        anomaly_count = df['is_anomaly'].sum()
        if anomaly_count > 0:
            logger.warning(f"Detected {anomaly_count} anomalies in funding rate data")

        return df

    def resample(
        self,
        df: pd.DataFrame,
        freq: str = 'D'
    ) -> pd.DataFrame:
        """重採樣資金費率數據

        Args:
            df: 資金費率 DataFrame
            freq: 重採樣頻率（'D'=日, 'W'=週, 'M'=月）

        Returns:
            重採樣後的 DataFrame
        """
        if df.empty:
            return df

        # 設置時間索引
        df = df.set_index('timestamp')

        # 重採樣（使用平均值）
        resampled = df.groupby(['symbol', 'exchange']).resample(freq).agg({
            'funding_rate': 'mean',
            'annual_rate': 'mean',
            'mark_price': 'mean'
        }).reset_index()

        return resampled

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        exchange: str,
        format: str = 'parquet'
    ) -> Path:
        """保存資金費率數據到存儲

        Args:
            df: 資金費率 DataFrame
            symbol: 交易對
            exchange: 交易所
            format: 存儲格式（'parquet' 或 'csv'）

        Returns:
            保存的文件路徑
        """
        # 創建存儲目錄
        exchange_dir = self.storage_path / exchange
        exchange_dir.mkdir(exist_ok=True)

        # 生成文件名（包含時間範圍）
        if not df.empty:
            start_date = df['timestamp'].min().strftime('%Y%m%d')
            end_date = df['timestamp'].max().strftime('%Y%m%d')
            filename = f"{symbol}_funding_rate_{start_date}_{end_date}.{format}"
        else:
            filename = f"{symbol}_funding_rate.{format}"

        file_path = exchange_dir / filename

        # 保存數據
        if format == 'parquet':
            df.to_parquet(file_path, index=False, compression='snappy')
        elif format == 'csv':
            df.to_csv(file_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Saved funding rate data to {file_path}")

        return file_path

    def load(
        self,
        symbol: str,
        exchange: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """從存儲加載資金費率數據

        Args:
            symbol: 交易對
            exchange: 交易所
            start_date: 開始日期（可選，格式 'YYYYMMDD'）
            end_date: 結束日期（可選）

        Returns:
            資金費率 DataFrame
        """
        exchange_dir = self.storage_path / exchange

        if not exchange_dir.exists():
            logger.warning(f"No data directory found for {exchange}")
            return pd.DataFrame()

        # 查找匹配的文件
        pattern = f"{symbol}_funding_rate"
        if start_date and end_date:
            pattern += f"_{start_date}_{end_date}"
        pattern += ".parquet"

        matching_files = list(exchange_dir.glob(pattern))

        if not matching_files:
            # 嘗試通配符模式
            pattern = f"{symbol}_funding_rate*.parquet"
            matching_files = list(exchange_dir.glob(pattern))

        if not matching_files:
            logger.warning(f"No funding rate data found for {symbol} on {exchange}")
            return pd.DataFrame()

        # 加載並合併所有匹配的文件
        all_data = []
        for file_path in matching_files:
            df = pd.read_parquet(file_path)
            all_data.append(df)

        combined = pd.concat(all_data, ignore_index=True)
        combined = combined.sort_values('timestamp').reset_index(drop=True)

        # 如果指定了日期範圍，過濾數據
        if start_date or end_date:
            if start_date:
                start_dt = pd.to_datetime(start_date)
                combined = combined[combined['timestamp'] >= start_dt]
            if end_date:
                end_dt = pd.to_datetime(end_date)
                combined = combined[combined['timestamp'] <= end_dt]

        logger.info(f"Loaded {len(combined)} funding rate records from storage")

        return combined

    def get_latest(
        self,
        symbol: str,
        exchange: str = 'binance'
    ) -> Dict[str, Any]:
        """獲取最新的資金費率

        Args:
            symbol: 交易對
            exchange: 交易所

        Returns:
            最新資金費率信息字典
        """
        connector = self.connectors.get(exchange)
        if not connector:
            raise ValueError(f"Unsupported exchange: {exchange}")

        # 獲取當前標記價格和資金費率
        mark_data = connector.get_mark_price(symbol)

        result = {
            'symbol': symbol,
            'exchange': exchange,
            'funding_rate': mark_data.get('funding_rate', 0),
            'annual_rate': mark_data.get('funding_rate', 0) * 3 * 365,
            'mark_price': mark_data.get('mark_price', 0),
            'next_funding_time': mark_data.get('next_funding_time'),
            'timestamp': mark_data.get('timestamp', datetime.now())
        }

        return result

    def clear_cache(self):
        """清除數據快取"""
        self._cache.clear()
        logger.info("Funding rate cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """獲取快取統計信息"""
        total_rows = sum(len(df) for df in self._cache.values())

        return {
            'cached_items': len(self._cache),
            'total_rows': total_rows,
            'cache_keys': list(self._cache.keys())
        }


# 便捷函數
def fetch_funding_rate(
    symbol: str,
    start_time: Union[str, datetime],
    end_time: Union[str, datetime],
    exchange: str = 'binance'
) -> pd.DataFrame:
    """便捷函數：獲取資金費率數據

    Example:
        >>> df = fetch_funding_rate('BTCUSDT', '2024-01-01', '2024-01-31')
    """
    fr = FundingRateData()
    return fr.fetch(symbol, start_time, end_time, exchange)


def get_latest_funding_rate(
    symbol: str,
    exchange: str = 'binance'
) -> Dict[str, Any]:
    """便捷函數：獲取最新資金費率

    Example:
        >>> latest = get_latest_funding_rate('BTCUSDT')
        >>> print(f"Current rate: {latest['funding_rate']:.4%}")
    """
    fr = FundingRateData()
    return fr.get_latest(symbol, exchange)
