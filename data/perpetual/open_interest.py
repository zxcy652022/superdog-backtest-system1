"""
Open Interest Data Processing for SuperDog v0.5

持倉量數據處理層 - 提供高層級的持倉量數據操作介面

Features:
- Multi-exchange open interest data aggregation
- Data normalization and standardization
- Historical data fetching and caching
- Integration with storage layer
- Trend analysis and statistics

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


class OpenInterestData:
    """持倉量數據處理類

    提供持倉量數據的獲取、處理、存儲功能

    Example:
        >>> oi = OpenInterestData()
        >>> df = oi.fetch('BTCUSDT', '2024-01-01', '2024-01-31', interval='1h')
        >>> trend = oi.analyze_trend(df)
        >>> oi.save(df, 'BTCUSDT', 'binance')
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """初始化持倉量數據處理器

        Args:
            storage_path: 數據存儲路徑（默認使用 SSD）
        """
        self.storage_path = storage_path or Path("/Volumes/權志龍的寶藏/SuperDogData/perpetual/open_interest")
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
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        interval: str = '1h',
        exchange: str = 'binance',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """獲取持倉量數據

        Args:
            symbol: 交易對（如 'BTCUSDT'）
            start_time: 開始時間（None = 30天前）
            end_time: 結束時間（None = 現在）
            interval: 時間間隔（5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d）
            exchange: 交易所名稱
            use_cache: 是否使用快取

        Returns:
            DataFrame with columns:
                - timestamp: 時間戳
                - symbol: 交易對
                - open_interest: 持倉量（張數）
                - open_interest_value: 持倉量價值（USDT）
                - exchange: 交易所
                - oi_change: 持倉量變化
                - oi_change_pct: 持倉量變化百分比

        Raises:
            ValueError: 當交易所不支援或參數無效時
        """
        # 標準化時間格式
        if start_time is not None and isinstance(start_time, str):
            start_time = pd.to_datetime(start_time)
        if end_time is not None and isinstance(end_time, str):
            end_time = pd.to_datetime(end_time)

        # 檢查交易所
        if exchange not in self.connectors:
            raise ValueError(f"Unsupported exchange: {exchange}")

        # 檢查快取
        cache_key = f"{exchange}_{symbol}_{interval}_{start_time}_{end_time}"
        if use_cache and cache_key in self._cache:
            logger.info(f"Using cached data for {symbol} on {exchange}")
            return self._cache[cache_key].copy()

        # 從交易所獲取數據
        logger.info(f"Fetching open interest data for {symbol} on {exchange}")
        connector = self.connectors[exchange]

        try:
            df = connector.get_open_interest(
                symbol=symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time
            )

            if df.empty:
                logger.warning(f"No open interest data found for {symbol} on {exchange}")
                return pd.DataFrame()

            # 添加交易所標籤
            df['exchange'] = exchange

            # 計算持倉量變化
            df['oi_change'] = df['open_interest'].diff()
            df['oi_change_pct'] = df['open_interest'].pct_change() * 100

            # 重新排序欄位
            df = df[[
                'timestamp', 'symbol', 'exchange',
                'open_interest', 'open_interest_value',
                'oi_change', 'oi_change_pct'
            ]]

            # 快取數據
            if use_cache:
                self._cache[cache_key] = df.copy()

            logger.info(f"Fetched {len(df)} open interest records for {symbol}")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch open interest data: {e}")
            raise

    def fetch_multiple_exchanges(
        self,
        symbol: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        interval: str = '1h',
        exchanges: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """從多個交易所獲取持倉量數據並合併

        Args:
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間
            interval: 時間間隔
            exchanges: 交易所列表（None = 所有支援的交易所）

        Returns:
            合併的 DataFrame，包含所有交易所的數據
        """
        if exchanges is None:
            exchanges = list(self.connectors.keys())

        all_data = []

        for exchange in exchanges:
            try:
                df = self.fetch(symbol, start_time, end_time, interval, exchange)
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

    def analyze_trend(
        self,
        df: pd.DataFrame,
        window: int = 24
    ) -> Dict[str, Any]:
        """分析持倉量趨勢

        Args:
            df: 持倉量 DataFrame
            window: 滾動窗口大小（默認24，代表24小時）

        Returns:
            趨勢分析結果字典：
                - current_oi: 當前持倉量
                - avg_oi: 平均持倉量
                - max_oi: 最大持倉量
                - min_oi: 最小持倉量
                - trend: 趨勢方向（'increasing', 'decreasing', 'stable'）
                - change_24h: 24小時變化
                - change_24h_pct: 24小時變化百分比
                - volatility: 波動率
        """
        if df.empty:
            return {}

        oi_values = df['open_interest']

        # 基本統計
        current_oi = oi_values.iloc[-1]
        avg_oi = oi_values.mean()
        max_oi = oi_values.max()
        min_oi = oi_values.min()

        # 計算趨勢
        if len(oi_values) >= window:
            recent_avg = oi_values.iloc[-window:].mean()
            previous_avg = oi_values.iloc[-window*2:-window].mean() if len(oi_values) >= window*2 else avg_oi

            if recent_avg > previous_avg * 1.05:
                trend = 'increasing'
            elif recent_avg < previous_avg * 0.95:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'unknown'

        # 24小時變化
        if len(oi_values) >= window:
            change_24h = oi_values.iloc[-1] - oi_values.iloc[-window]
            change_24h_pct = (change_24h / oi_values.iloc[-window]) * 100
        else:
            change_24h = 0
            change_24h_pct = 0

        # 波動率（標準差 / 平均值）
        volatility = (oi_values.std() / avg_oi) * 100 if avg_oi > 0 else 0

        return {
            'current_oi': current_oi,
            'avg_oi': avg_oi,
            'max_oi': max_oi,
            'min_oi': min_oi,
            'trend': trend,
            'change_24h': change_24h,
            'change_24h_pct': change_24h_pct,
            'volatility': volatility
        }

    def calculate_statistics(
        self,
        df: pd.DataFrame,
        window: Optional[int] = None
    ) -> Dict[str, Any]:
        """計算持倉量統計指標

        Args:
            df: 持倉量 DataFrame
            window: 滾動窗口大小（None = 全部數據）

        Returns:
            統計指標字典
        """
        if df.empty:
            return {}

        oi_values = df['open_interest']
        oi_value_usd = df['open_interest_value']

        stats = {
            'mean_oi': oi_values.mean(),
            'median_oi': oi_values.median(),
            'std_oi': oi_values.std(),
            'min_oi': oi_values.min(),
            'max_oi': oi_values.max(),
            'mean_oi_value': oi_value_usd.mean(),
            'total_oi_value': oi_value_usd.iloc[-1] if len(oi_value_usd) > 0 else 0
        }

        # 如果指定窗口，計算滾動統計
        if window is not None:
            stats['rolling_mean'] = oi_values.rolling(window).mean()
            stats['rolling_std'] = oi_values.rolling(window).std()
            stats['rolling_max'] = oi_values.rolling(window).max()
            stats['rolling_min'] = oi_values.rolling(window).min()

        return stats

    def detect_spikes(
        self,
        df: pd.DataFrame,
        threshold: float = 2.0
    ) -> pd.DataFrame:
        """檢測持倉量突增/突減

        Args:
            df: 持倉量 DataFrame
            threshold: 標準差倍數閾值

        Returns:
            包含突增/突減標記的 DataFrame
        """
        df = df.copy()

        # 計算Z-score
        oi_mean = df['open_interest'].mean()
        oi_std = df['open_interest'].std()

        df['z_score'] = (df['open_interest'] - oi_mean) / oi_std if oi_std > 0 else 0

        # 標記突增/突減
        df['is_spike'] = df['z_score'].abs() > threshold
        df['spike_type'] = 'normal'
        df.loc[df['z_score'] > threshold, 'spike_type'] = 'surge'
        df.loc[df['z_score'] < -threshold, 'spike_type'] = 'drop'

        spike_count = df['is_spike'].sum()
        if spike_count > 0:
            logger.warning(f"Detected {spike_count} OI spikes in data")

        return df

    def correlate_with_price(
        self,
        oi_df: pd.DataFrame,
        price_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """計算持倉量與價格的相關性

        Args:
            oi_df: 持倉量 DataFrame
            price_df: 價格 DataFrame（需要有 'close' 欄位）

        Returns:
            相關性分析結果
        """
        # 合併數據
        merged = pd.merge(
            oi_df[['timestamp', 'open_interest']],
            price_df[['timestamp', 'close']],
            on='timestamp',
            how='inner'
        )

        if len(merged) < 2:
            return {'correlation': None, 'error': 'Insufficient data'}

        # 計算相關係數
        correlation = merged['open_interest'].corr(merged['close'])

        # 計算滾動相關性（30期）
        rolling_corr = merged['open_interest'].rolling(30).corr(merged['close'])

        return {
            'correlation': correlation,
            'rolling_correlation': rolling_corr,
            'interpretation': self._interpret_correlation(correlation)
        }

    def _interpret_correlation(self, corr: float) -> str:
        """解釋相關係數"""
        if corr is None or np.isnan(corr):
            return 'unknown'
        elif corr > 0.7:
            return 'strong_positive'
        elif corr > 0.3:
            return 'moderate_positive'
        elif corr > -0.3:
            return 'weak'
        elif corr > -0.7:
            return 'moderate_negative'
        else:
            return 'strong_negative'

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        exchange: str,
        interval: str = '1h',
        format: str = 'parquet'
    ) -> Path:
        """保存持倉量數據到存儲

        Args:
            df: 持倉量 DataFrame
            symbol: 交易對
            exchange: 交易所
            interval: 時間間隔
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
            filename = f"{symbol}_open_interest_{interval}_{start_date}_{end_date}.{format}"
        else:
            filename = f"{symbol}_open_interest_{interval}.{format}"

        file_path = exchange_dir / filename

        # 保存數據
        if format == 'parquet':
            df.to_parquet(file_path, index=False, compression='snappy')
        elif format == 'csv':
            df.to_csv(file_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Saved open interest data to {file_path}")

        return file_path

    def load(
        self,
        symbol: str,
        exchange: str,
        interval: str = '1h',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """從存儲加載持倉量數據

        Args:
            symbol: 交易對
            exchange: 交易所
            interval: 時間間隔
            start_date: 開始日期（可選，格式 'YYYYMMDD'）
            end_date: 結束日期（可選）

        Returns:
            持倉量 DataFrame
        """
        exchange_dir = self.storage_path / exchange

        if not exchange_dir.exists():
            logger.warning(f"No data directory found for {exchange}")
            return pd.DataFrame()

        # 查找匹配的文件
        pattern = f"{symbol}_open_interest_{interval}"
        if start_date and end_date:
            pattern += f"_{start_date}_{end_date}"
        pattern += ".parquet"

        matching_files = list(exchange_dir.glob(pattern))

        if not matching_files:
            # 嘗試通配符模式
            pattern = f"{symbol}_open_interest_{interval}*.parquet"
            matching_files = list(exchange_dir.glob(pattern))

        if not matching_files:
            logger.warning(f"No open interest data found for {symbol} on {exchange}")
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

        logger.info(f"Loaded {len(combined)} open interest records from storage")

        return combined

    def clear_cache(self):
        """清除數據快取"""
        self._cache.clear()
        logger.info("Open interest cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """獲取快取統計信息"""
        total_rows = sum(len(df) for df in self._cache.values())

        return {
            'cached_items': len(self._cache),
            'total_rows': total_rows,
            'cache_keys': list(self._cache.keys())
        }


# 便捷函數
def fetch_open_interest(
    symbol: str,
    start_time: Optional[Union[str, datetime]] = None,
    end_time: Optional[Union[str, datetime]] = None,
    interval: str = '1h',
    exchange: str = 'binance'
) -> pd.DataFrame:
    """便捷函數：獲取持倉量數據

    Example:
        >>> df = fetch_open_interest('BTCUSDT', '2024-01-01', '2024-01-31', interval='1h')
    """
    oi = OpenInterestData()
    return oi.fetch(symbol, start_time, end_time, interval, exchange)


def analyze_oi_trend(
    symbol: str,
    start_time: Optional[Union[str, datetime]] = None,
    end_time: Optional[Union[str, datetime]] = None,
    interval: str = '1h',
    exchange: str = 'binance'
) -> Dict[str, Any]:
    """便捷函數：獲取並分析持倉量趨勢

    Example:
        >>> trend = analyze_oi_trend('BTCUSDT')
        >>> print(f"Trend: {trend['trend']}, 24h change: {trend['change_24h_pct']:.2f}%")
    """
    # 如果沒有指定時間範圍，使用最近 7 天（更穩定）
    if start_time is None and end_time is None:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

    oi = OpenInterestData()
    df = oi.fetch(symbol, start_time, end_time, interval, exchange)
    return oi.analyze_trend(df)
