"""
Long/Short Ratio Data Processing for SuperDog v0.5

多空持倉比數據處理 - 市場情緒的逆向指標

多空比 = 多頭持倉 / 空頭持倉

多空比用途：
- 逆向情緒指標：極端多空比可能預示反轉
- 趨勢確認：多空比與價格趨勢的一致性
- 群眾心理：識別市場過度樂觀或悲觀

Version: v0.5 Phase B
Author: SuperDog Quant Team
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List
from pathlib import Path

import pandas as pd
import numpy as np

from data.exchanges import BinanceConnector, BybitConnector, OKXConnector

logger = logging.getLogger(__name__)


class LongShortRatioData:
    """多空持倉比數據處理器

    獲取並分析多空持倉比例，生成逆向情緒指標

    Features:
    - 多空比數據獲取（多交易所）
    - 賬戶多空比 vs 持倉量多空比
    - 極端值檢測
    - 逆向信號生成
    - 多空分歧分析
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None
    ):
        """初始化多空比數據處理器

        Args:
            storage_path: 數據存儲路徑（可選）
        """
        # 設置存儲路徑
        if storage_path is None:
            ssd_path = Path('/Volumes/權志龍的寶藏/SuperDogData/perpetual/long_short_ratio')
            if ssd_path.parent.parent.exists():
                storage_path = ssd_path
            else:
                storage_path = Path.cwd() / 'data_storage' / 'perpetual' / 'long_short_ratio'

        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 交易所連接器
        self.connectors = {
            'binance': BinanceConnector(),
            'bybit': BybitConnector(),
            'okx': OKXConnector()
        }

        # 數據快取
        self._cache: Dict[str, pd.DataFrame] = {}

        logger.info(f"LongShortRatioData initialized with storage at {self.storage_path}")

    def fetch(
        self,
        symbol: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        interval: str = '5m',
        exchange: str = 'binance',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """獲取多空持倉比數據

        Args:
            symbol: 交易對（如 'BTCUSDT'）
            start_time: 開始時間（None = 7天前）
            end_time: 結束時間（None = 現在）
            interval: 時間間隔（5m, 15m, 30m, 1h, 4h, 1d）
            exchange: 交易所名稱
            use_cache: 是否使用快取

        Returns:
            DataFrame with columns:
                - timestamp: 時間戳
                - symbol: 交易對
                - long_ratio: 多頭比例
                - short_ratio: 空頭比例
                - long_short_ratio: 多空比值 (long/short)
                - exchange: 交易所
        """
        # 標準化時間格式
        if start_time is not None:
            start_time = pd.to_datetime(start_time)
        if end_time is not None:
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
        logger.info(f"Fetching long/short ratio for {symbol} on {exchange}")
        connector = self.connectors[exchange]

        try:
            df = connector.get_long_short_ratio(symbol, interval=interval)

            if df.empty:
                logger.warning(f"No long/short ratio data found for {symbol} on {exchange}")
                return df

            # 計算多空比值
            df['long_short_ratio'] = df['long_ratio'] / (df['short_ratio'] + 1e-10)  # 避免除零

            # 添加 exchange 欄位
            df['exchange'] = exchange

            # 篩選時間範圍
            if start_time is not None:
                df = df[df['timestamp'] >= start_time]
            if end_time is not None:
                df = df[df['timestamp'] <= end_time]

            # 快取數據
            if use_cache:
                self._cache[cache_key] = df.copy()

            logger.info(f"Fetched {len(df)} long/short ratio records for {symbol}")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch long/short ratio: {e}")
            return pd.DataFrame()

    def detect_extreme_ratios(
        self,
        df: pd.DataFrame,
        threshold_long: float = 0.70,
        threshold_short: float = 0.30
    ) -> pd.DataFrame:
        """檢測極端多空比

        極端值可能預示市場即將反轉

        Args:
            df: 多空比數據
            threshold_long: 多頭極端閾值（如 0.70 = 70%多頭）
            threshold_short: 空頭極端閾值（如 0.30 = 30%多頭）

        Returns:
            DataFrame with additional columns:
                - is_extreme: 是否為極端值
                - extreme_type: 極端類型 (extreme_bullish/extreme_bearish)
                - reversal_signal: 反轉信號 (bearish_reversal/bullish_reversal)
        """
        if df.empty:
            return df

        df = df.copy()

        # 標記極端值
        df['is_extreme'] = False
        df['extreme_type'] = 'neutral'
        df['reversal_signal'] = 'none'

        # 極端看多（逆向看空信號）
        extreme_bullish = df['long_ratio'] > threshold_long
        df.loc[extreme_bullish, 'is_extreme'] = True
        df.loc[extreme_bullish, 'extreme_type'] = 'extreme_bullish'
        df.loc[extreme_bullish, 'reversal_signal'] = 'bearish_reversal'  # 逆向信號

        # 極端看空（逆向看多信號）
        extreme_bearish = df['long_ratio'] < threshold_short
        df.loc[extreme_bearish, 'is_extreme'] = True
        df.loc[extreme_bearish, 'extreme_type'] = 'extreme_bearish'
        df.loc[extreme_bearish, 'reversal_signal'] = 'bullish_reversal'  # 逆向信號

        extreme_count = df['is_extreme'].sum()
        logger.info(f"Detected {extreme_count} extreme long/short ratios")

        return df

    def calculate_sentiment_index(
        self,
        df: pd.DataFrame,
        window: int = 24
    ) -> Dict[str, Any]:
        """計算市場情緒指數

        基於多空比計算情緒指數（-100 到 +100）

        Args:
            df: 多空比數據
            window: 分析窗口（小時）

        Returns:
            情緒指數和分析結果
        """
        if df.empty or len(df) < window:
            return {
                'sentiment_index': 0,
                'sentiment': 'unknown',
                'status': 'insufficient_data'
            }

        recent = df.tail(window)

        # 當前多空比
        current_long_ratio = recent['long_ratio'].iloc[-1]
        current_ratio = recent['long_short_ratio'].iloc[-1]

        # 平均多空比
        avg_long_ratio = recent['long_ratio'].mean()
        avg_ratio = recent['long_short_ratio'].mean()

        # 情緒指數：將多頭比例映射到 -100 ~ +100
        # 50% 多頭 = 0（中性）
        # 100% 多頭 = +100（極度看多）
        # 0% 多頭 = -100（極度看空）
        sentiment_index = (current_long_ratio - 0.5) * 200

        # 情緒分類
        if sentiment_index > 40:
            sentiment = 'extreme_bullish'
            contrarian_signal = 'consider_short'  # 逆向信號
        elif sentiment_index > 20:
            sentiment = 'bullish'
            contrarian_signal = 'watch_for_reversal'
        elif sentiment_index > -20:
            sentiment = 'neutral'
            contrarian_signal = 'no_signal'
        elif sentiment_index > -40:
            sentiment = 'bearish'
            contrarian_signal = 'watch_for_reversal'
        else:
            sentiment = 'extreme_bearish'
            contrarian_signal = 'consider_long'  # 逆向信號

        return {
            'sentiment_index': sentiment_index,
            'sentiment': sentiment,
            'contrarian_signal': contrarian_signal,
            'current_long_ratio': current_long_ratio,
            'current_long_short_ratio': current_ratio,
            'avg_long_ratio': avg_long_ratio,
            'avg_long_short_ratio': avg_ratio,
            'window_hours': window
        }

    def analyze_divergence(
        self,
        ratio_df: pd.DataFrame,
        price_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """分析多空比與價格的背離

        背離可能是趨勢反轉的信號

        Args:
            ratio_df: 多空比數據
            price_df: 價格數據

        Returns:
            背離分析結果
        """
        if ratio_df.empty or price_df.empty:
            return {
                'divergence': False,
                'type': 'none',
                'status': 'insufficient_data'
            }

        # 合併數據
        merged = pd.merge_asof(
            ratio_df.sort_values('timestamp'),
            price_df[['timestamp', 'close']].sort_values('timestamp'),
            on='timestamp',
            direction='nearest',
            tolerance=pd.Timedelta('15min')
        )

        if merged.empty or len(merged) < 20:
            return {
                'divergence': False,
                'type': 'none',
                'status': 'insufficient_data'
            }

        # 計算趨勢（簡單斜率）
        recent = merged.tail(20)

        # 價格趨勢
        price_slope = np.polyfit(range(len(recent)), recent['close'].values, 1)[0]
        price_trend = 'up' if price_slope > 0 else 'down'

        # 多空比趨勢
        ratio_slope = np.polyfit(range(len(recent)), recent['long_ratio'].values, 1)[0]
        ratio_trend = 'increasing' if ratio_slope > 0 else 'decreasing'

        # 檢測背離
        # 看漲背離：價格下跌 + 多頭增加
        bullish_divergence = (price_trend == 'down') and (ratio_trend == 'increasing')

        # 看跌背離：價格上漲 + 空頭增加
        bearish_divergence = (price_trend == 'up') and (ratio_trend == 'decreasing')

        if bullish_divergence:
            divergence_type = 'bullish'
            signal = 'potential_bottom'
        elif bearish_divergence:
            divergence_type = 'bearish'
            signal = 'potential_top'
        else:
            divergence_type = 'none'
            signal = 'no_divergence'

        return {
            'divergence': bullish_divergence or bearish_divergence,
            'type': divergence_type,
            'signal': signal,
            'price_trend': price_trend,
            'ratio_trend': ratio_trend,
            'price_slope': price_slope,
            'ratio_slope': ratio_slope
        }

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        exchange: str,
        format: str = 'parquet'
    ) -> Path:
        """保存多空比數據到存儲"""
        if df.empty:
            logger.warning("Empty DataFrame, skipping save")
            return None

        exchange_dir = self.storage_path / exchange
        exchange_dir.mkdir(exist_ok=True)

        start_date = df['timestamp'].min().strftime('%Y%m%d')
        end_date = df['timestamp'].max().strftime('%Y%m%d')
        filename = f"{symbol}_long_short_ratio_{start_date}_{end_date}.{format}"
        filepath = exchange_dir / filename

        if format == 'parquet':
            df.to_parquet(filepath, compression='snappy', index=False)
        elif format == 'csv':
            df.to_csv(filepath, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Saved long/short ratio data to {filepath}")

        return filepath

    def load(
        self,
        symbol: str,
        exchange: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """從存儲載入多空比數據"""
        exchange_dir = self.storage_path / exchange

        if not exchange_dir.exists():
            logger.warning(f"No data found for {exchange}")
            return pd.DataFrame()

        pattern = f"{symbol}_long_short_ratio_*.parquet"
        files = list(exchange_dir.glob(pattern))

        if not files:
            logger.warning(f"No long/short ratio data files found for {symbol}")
            return pd.DataFrame()

        dfs = []
        for file in files:
            df = pd.read_parquet(file)
            dfs.append(df)

        df = pd.concat(dfs, ignore_index=True)
        df = df.sort_values('timestamp').drop_duplicates('timestamp')

        if start_date:
            df = df[df['timestamp'] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df['timestamp'] <= pd.to_datetime(end_date)]

        logger.info(f"Loaded {len(df)} long/short ratio records for {symbol}")

        return df


# 便捷函數
def fetch_long_short_ratio(
    symbol: str,
    interval: str = '5m',
    exchange: str = 'binance'
) -> pd.DataFrame:
    """便捷函數：獲取多空持倉比

    Example:
        >>> df = fetch_long_short_ratio('BTCUSDT')
        >>> print(f"Current long ratio: {df['long_ratio'].iloc[-1]:.2%}")
    """
    lsr = LongShortRatioData()
    return lsr.fetch(symbol, interval=interval, exchange=exchange)


def calculate_sentiment(
    symbol: str,
    exchange: str = 'binance'
) -> Dict[str, Any]:
    """便捷函數：計算市場情緒指數

    Example:
        >>> sentiment = calculate_sentiment('BTCUSDT')
        >>> print(f"Sentiment: {sentiment['sentiment']}")
        >>> print(f"Contrarian Signal: {sentiment['contrarian_signal']}")
    """
    lsr = LongShortRatioData()
    df = lsr.fetch(symbol, exchange=exchange)
    return lsr.calculate_sentiment_index(df)
