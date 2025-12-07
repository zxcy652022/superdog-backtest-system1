"""
Basis Data Processing for SuperDog v0.5

期現基差數據處理 - 計算永續合約與現貨價格差異

期現基差 (Basis) = 永續合約價格 - 現貨價格
年化基差 = (基差 / 現貨價格) × 365 × 100%

基差用途：
- 套利交易：基差過大時進行期現套利
- 市場情緒：正基差表示看漲，負基差表示看跌
- 價格發現：基差收斂提供交易信號

Version: v0.5 Phase B
Author: SuperDog Quant Team
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List
from pathlib import Path

import pandas as pd
import numpy as np

from data.exchanges import BinanceConnector

logger = logging.getLogger(__name__)


class BasisData:
    """期現基差數據處理器

    計算永續合約與現貨的價格差異（基差），用於套利和情緒分析

    Features:
    - 基差計算（絕對值和百分比）
    - 年化基差計算
    - 基差收斂信號檢測
    - 均值回歸分析
    - 套利機會識別
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None
    ):
        """初始化基差數據處理器

        Args:
            storage_path: 數據存儲路徑（可選）
        """
        # 設置存儲路徑
        if storage_path is None:
            # 優先使用 SSD
            ssd_path = Path('/Volumes/權志龍的寶藏/SuperDogData/perpetual/basis')
            if ssd_path.parent.parent.exists():
                storage_path = ssd_path
            else:
                # 回退到項目目錄
                storage_path = Path.cwd() / 'data_storage' / 'perpetual' / 'basis'

        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 交易所連接器
        self.binance = BinanceConnector()

        # 數據快取
        self._cache: Dict[str, pd.DataFrame] = {}

        logger.info(f"BasisData initialized with storage at {self.storage_path}")

    def calculate_basis(
        self,
        perp_price: Union[pd.Series, float],
        spot_price: Union[pd.Series, float]
    ) -> Union[pd.Series, float]:
        """計算基差

        基差 = 永續價格 - 現貨價格

        Args:
            perp_price: 永續合約價格
            spot_price: 現貨價格

        Returns:
            基差值
        """
        return perp_price - spot_price

    def calculate_basis_percentage(
        self,
        perp_price: Union[pd.Series, float],
        spot_price: Union[pd.Series, float]
    ) -> Union[pd.Series, float]:
        """計算基差百分比

        基差百分比 = (永續價格 - 現貨價格) / 現貨價格 × 100%

        Args:
            perp_price: 永續合約價格
            spot_price: 現貨價格

        Returns:
            基差百分比
        """
        basis = perp_price - spot_price
        return (basis / spot_price) * 100

    def calculate_annualized_basis(
        self,
        perp_price: Union[pd.Series, float],
        spot_price: Union[pd.Series, float]
    ) -> Union[pd.Series, float]:
        """計算年化基差

        年化基差 = (基差百分比) × 365

        Args:
            perp_price: 永續合約價格
            spot_price: 現貨價格

        Returns:
            年化基差百分比
        """
        basis_pct = self.calculate_basis_percentage(perp_price, spot_price)
        return basis_pct * 365

    def fetch_and_calculate(
        self,
        symbol: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        interval: str = '1h',
        exchange: str = 'binance'
    ) -> pd.DataFrame:
        """獲取價格數據並計算基差

        Args:
            symbol: 交易對（如 'BTCUSDT'）
            start_time: 開始時間（None = 7天前）
            end_time: 結束時間（None = 現在）
            interval: 時間間隔
            exchange: 交易所名稱

        Returns:
            DataFrame with columns:
                - timestamp
                - symbol
                - perp_price: 永續合約價格
                - spot_price: 現貨價格
                - basis: 基差（絕對值）
                - basis_pct: 基差百分比
                - annualized_basis: 年化基差
                - exchange
        """
        # 標準化時間
        if start_time is None:
            end_time = datetime.now() if end_time is None else pd.to_datetime(end_time)
            start_time = end_time - timedelta(days=7)
        else:
            start_time = pd.to_datetime(start_time)
            end_time = pd.to_datetime(end_time) if end_time else datetime.now()

        if exchange == 'binance':
            # 獲取永續合約價格（使用標記價格）
            from data.perpetual.funding_rate import FundingRateData
            fr = FundingRateData()
            perp_df = fr.fetch(symbol, start_time, end_time, exchange=exchange)

            if perp_df.empty:
                logger.warning(f"No perpetual price data found for {symbol}")
                return pd.DataFrame()

            # 獲取現貨價格
            # 注意：這裡使用現貨API獲取K線數據
            spot_df = self._fetch_spot_price(symbol, start_time, end_time, interval)

            if spot_df.empty:
                logger.warning(f"No spot price data found for {symbol}")
                return pd.DataFrame()

            # 合併數據（按時間對齊）
            # 使用 merge_asof 進行時間對齊
            df = pd.merge_asof(
                perp_df.sort_values('timestamp'),
                spot_df[['timestamp', 'spot_price']].sort_values('timestamp'),
                on='timestamp',
                direction='nearest',
                tolerance=pd.Timedelta('15min')  # 允許15分鐘誤差
            )

            # 刪除沒有匹配的行
            df = df.dropna(subset=['spot_price'])

            # 重命名永續價格
            df = df.rename(columns={'mark_price': 'perp_price'})

            # 計算基差指標
            df['basis'] = self.calculate_basis(df['perp_price'], df['spot_price'])
            df['basis_pct'] = self.calculate_basis_percentage(df['perp_price'], df['spot_price'])
            df['annualized_basis'] = self.calculate_annualized_basis(df['perp_price'], df['spot_price'])
            df['exchange'] = exchange

            # 選擇需要的欄位
            df = df[[
                'timestamp', 'symbol', 'perp_price', 'spot_price',
                'basis', 'basis_pct', 'annualized_basis', 'exchange'
            ]]

            logger.info(f"Calculated basis for {symbol}: {len(df)} records")

            return df

        else:
            logger.error(f"Unsupported exchange: {exchange}")
            return pd.DataFrame()

    def _fetch_spot_price(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = '1h'
    ) -> pd.DataFrame:
        """獲取現貨價格數據

        使用 Binance Spot API

        Args:
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間
            interval: K線間隔

        Returns:
            DataFrame with columns: timestamp, spot_price
        """
        # Binance Spot API
        spot_url = "https://api.binance.com/api/v3/klines"

        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': int(start_time.timestamp() * 1000),
            'endTime': int(end_time.timestamp() * 1000),
            'limit': 1000
        }

        try:
            import requests
            response = requests.get(spot_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data:
                return pd.DataFrame()

            # Binance K線格式：
            # [時間, 開, 高, 低, 收, 量, 收盤時間, ...]
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['spot_price'] = df['close'].astype(float)

            df = df[['timestamp', 'spot_price']]

            logger.info(f"Fetched {len(df)} spot price records")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch spot price: {e}")
            return pd.DataFrame()

    def analyze_basis_convergence(
        self,
        df: pd.DataFrame,
        window: int = 24
    ) -> Dict[str, Any]:
        """分析基差收斂趨勢

        Args:
            df: 基差數據
            window: 分析窗口（小時）

        Returns:
            分析結果
        """
        if df.empty or len(df) < window:
            return {
                'status': 'insufficient_data',
                'records': len(df),
                'required': window
            }

        recent = df.tail(window)

        # 基差統計
        basis_mean = recent['basis_pct'].mean()
        basis_std = recent['basis_pct'].std()
        current_basis = recent['basis_pct'].iloc[-1]

        # 趨勢分析（線性回歸）
        x = np.arange(len(recent))
        y = recent['basis_pct'].values

        if len(x) > 1 and basis_std > 0:
            # 簡單線性回歸
            slope = np.polyfit(x, y, 1)[0]

            # 判斷趨勢
            if slope < -0.01:
                trend = 'converging'  # 收斂（基差縮小）
            elif slope > 0.01:
                trend = 'diverging'   # 發散（基差擴大）
            else:
                trend = 'stable'
        else:
            slope = 0
            trend = 'stable'

        # Z-score (標準化距離)
        if basis_std > 0:
            z_score = (current_basis - basis_mean) / basis_std
        else:
            z_score = 0

        return {
            'current_basis_pct': current_basis,
            'mean_basis_pct': basis_mean,
            'std_basis_pct': basis_std,
            'trend': trend,
            'slope': slope,
            'z_score': z_score,
            'window_hours': window,
            'is_extreme': abs(z_score) > 2.0
        }

    def identify_arbitrage_opportunities(
        self,
        df: pd.DataFrame,
        threshold: float = 0.5
    ) -> pd.DataFrame:
        """識別套利機會

        當基差超過閾值時，標記為套利機會

        Args:
            df: 基差數據
            threshold: 基差閾值（百分比）

        Returns:
            DataFrame with additional columns:
                - is_arbitrage: 是否為套利機會
                - arbitrage_type: 套利類型 (cash_and_carry / reverse)
        """
        if df.empty:
            return df

        df = df.copy()

        # 標記套利機會
        df['is_arbitrage'] = df['basis_pct'].abs() > threshold

        # 套利類型
        # Cash and Carry: 基差為正，做空永續+做多現貨
        # Reverse: 基差為負，做多永續+做空現貨
        df['arbitrage_type'] = 'none'
        df.loc[df['basis_pct'] > threshold, 'arbitrage_type'] = 'cash_and_carry'
        df.loc[df['basis_pct'] < -threshold, 'arbitrage_type'] = 'reverse'

        # 預期收益（年化）
        df['expected_return_pct'] = df['annualized_basis'].abs()

        arbitrage_count = df['is_arbitrage'].sum()
        logger.info(f"Identified {arbitrage_count} arbitrage opportunities")

        return df

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        exchange: str,
        format: str = 'parquet'
    ) -> Path:
        """保存基差數據到存儲

        Args:
            df: 基差數據
            symbol: 交易對
            exchange: 交易所
            format: 存儲格式（parquet/csv）

        Returns:
            保存的文件路徑
        """
        if df.empty:
            logger.warning("Empty DataFrame, skipping save")
            return None

        # 創建交易所目錄
        exchange_dir = self.storage_path / exchange
        exchange_dir.mkdir(exist_ok=True)

        # 生成文件名
        start_date = df['timestamp'].min().strftime('%Y%m%d')
        end_date = df['timestamp'].max().strftime('%Y%m%d')
        filename = f"{symbol}_basis_{start_date}_{end_date}.{format}"
        filepath = exchange_dir / filename

        # 保存
        if format == 'parquet':
            df.to_parquet(filepath, compression='snappy', index=False)
        elif format == 'csv':
            df.to_csv(filepath, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Saved basis data to {filepath}")

        return filepath

    def load(
        self,
        symbol: str,
        exchange: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """從存儲載入基差數據

        Args:
            symbol: 交易對
            exchange: 交易所
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）

        Returns:
            基差數據
        """
        exchange_dir = self.storage_path / exchange

        if not exchange_dir.exists():
            logger.warning(f"No data found for {exchange}")
            return pd.DataFrame()

        # 查找匹配的文件
        pattern = f"{symbol}_basis_*.parquet"
        files = list(exchange_dir.glob(pattern))

        if not files:
            logger.warning(f"No basis data files found for {symbol}")
            return pd.DataFrame()

        # 載入所有匹配的文件
        dfs = []
        for file in files:
            df = pd.read_parquet(file)
            dfs.append(df)

        df = pd.concat(dfs, ignore_index=True)
        df = df.sort_values('timestamp').drop_duplicates('timestamp')

        # 篩選日期範圍
        if start_date:
            df = df[df['timestamp'] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df['timestamp'] <= pd.to_datetime(end_date)]

        logger.info(f"Loaded {len(df)} basis records for {symbol}")

        return df


# 便捷函數
def calculate_basis(
    symbol: str,
    start_time: Optional[Union[str, datetime]] = None,
    end_time: Optional[Union[str, datetime]] = None,
    exchange: str = 'binance'
) -> pd.DataFrame:
    """便捷函數：計算期現基差

    Example:
        >>> df = calculate_basis('BTCUSDT')
        >>> print(df[['timestamp', 'basis_pct', 'annualized_basis']].tail())
    """
    basis = BasisData()
    return basis.fetch_and_calculate(symbol, start_time, end_time, exchange=exchange)


def find_arbitrage_opportunities(
    symbol: str,
    threshold: float = 0.5,
    exchange: str = 'binance'
) -> pd.DataFrame:
    """便捷函數：尋找套利機會

    Example:
        >>> opportunities = find_arbitrage_opportunities('BTCUSDT', threshold=0.3)
        >>> arb = opportunities[opportunities['is_arbitrage']]
        >>> print(f"Found {len(arb)} arbitrage opportunities")
    """
    basis = BasisData()
    df = basis.fetch_and_calculate(symbol, exchange=exchange)
    return basis.identify_arbitrage_opportunities(df, threshold)
