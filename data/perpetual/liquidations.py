"""
Liquidation Data Processing for SuperDog v0.5

爆倉數據處理 - 監控市場強平事件，識別恐慌情緒

爆倉 (Liquidation) = 強制平倉事件
當交易者保證金不足時，交易所強制平倉以保護系統

爆倉數據用途：
- 市場恐慌指標：大量爆倉表示市場恐慌
- 價格拐點信號：爆倉密集區可能是反轉點
- 流動性評估：爆倉量反映市場流動性

Version: v0.5 Phase B
Author: SuperDog Quant Team
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd

from data.exchanges import BinanceConnector, OKXConnector

logger = logging.getLogger(__name__)


class LiquidationData:
    """爆倉數據處理器

    監控和分析強制平倉事件，生成市場恐慌指標

    Features:
    - 爆倉數據獲取（多交易所）
    - 爆倉密度計算
    - 市場恐慌指數
    - 爆倉聚集區識別
    - 長短邊爆倉比例分析
    """

    def __init__(self, storage_path: Optional[Path] = None):
        """初始化爆倉數據處理器

        Args:
            storage_path: 數據存儲路徑（可選）
        """
        # 設置存儲路徑
        if storage_path is None:
            ssd_path = Path("/Volumes/權志龍的寶藏/SuperDogData/perpetual/liquidations")
            if ssd_path.parent.parent.exists():
                storage_path = ssd_path
            else:
                storage_path = Path.cwd() / "data_storage" / "perpetual" / "liquidations"

        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 交易所連接器
        self.connectors = {"binance": BinanceConnector(), "okx": OKXConnector()}

        # 數據快取
        self._cache: Dict[str, pd.DataFrame] = {}

        logger.info(f"LiquidationData initialized with storage at {self.storage_path}")

    def fetch(
        self,
        symbol: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        exchange: str = "binance",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """獲取爆倉數據

        Args:
            symbol: 交易對（如 'BTCUSDT'）
            start_time: 開始時間（None = 7天前）
            end_time: 結束時間（None = 現在）
            exchange: 交易所名稱
            use_cache: 是否使用快取

        Returns:
            DataFrame with columns:
                - timestamp: 爆倉時間
                - symbol: 交易對
                - side: 方向 (long/short)
                - size: 爆倉數量
                - value: 爆倉價值 (USDT)
                - price: 爆倉價格
                - exchange: 交易所
        """
        # 標準化時間格式
        if start_time is None:
            end_time = datetime.now() if end_time is None else pd.to_datetime(end_time)
            start_time = end_time - timedelta(days=7)
        else:
            start_time = pd.to_datetime(start_time)
            end_time = pd.to_datetime(end_time) if end_time else datetime.now()

        # 檢查交易所
        if exchange not in self.connectors:
            raise ValueError(f"Unsupported exchange: {exchange}")

        # 檢查快取
        cache_key = f"{exchange}_{symbol}_{start_time}_{end_time}"
        if use_cache and cache_key in self._cache:
            logger.info(f"Using cached data for {symbol} on {exchange}")
            return self._cache[cache_key].copy()

        # 從交易所獲取數據
        logger.info(f"Fetching liquidation data for {symbol} on {exchange}")
        connector = self.connectors[exchange]

        try:
            if exchange == "binance":
                # Binance 提供強制平倉訂單流
                df = self._fetch_binance_liquidations(symbol, start_time, end_time)
            elif exchange == "okx":
                # OKX 提供爆倉數據聚合
                df = connector.get_liquidations(symbol, start_time, end_time)
            else:
                df = pd.DataFrame()

            if df.empty:
                logger.warning(f"No liquidation data found for {symbol} on {exchange}")
                return df

            # 添加 exchange 欄位
            df["exchange"] = exchange

            # 快取數據
            if use_cache:
                self._cache[cache_key] = df.copy()

            logger.info(f"Fetched {len(df)} liquidation records for {symbol}")

            return df

        except Exception as e:
            logger.error(f"Failed to fetch liquidation data: {e}")
            return pd.DataFrame()

    def _fetch_binance_liquidations(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> pd.DataFrame:
        """獲取 Binance 爆倉數據

        Binance 提供強制平倉訂單流（實時數據）
        歷史數據需要通過 API 獲取

        API: GET /fapi/v1/forceOrders

        Args:
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間

        Returns:
            DataFrame with liquidation records
        """
        connector = self.connectors["binance"]
        endpoint = "/fapi/v1/forceOrders"

        all_data = []
        current_start = start_time

        while current_start < end_time:
            params = {
                "symbol": symbol.upper(),
                "startTime": int(current_start.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                "limit": 1000,
            }

            try:
                # 使用內部方法訪問 API
                response = connector._make_request(endpoint, params)

                if not response:
                    break

                all_data.extend(response)

                if len(response) < 1000:
                    break

                # 更新下一次請求的開始時間
                last_time = response[-1]["time"]
                current_start = datetime.fromtimestamp(last_time / 1000) + timedelta(milliseconds=1)

                import time

                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Failed to fetch Binance liquidations: {e}")
                break

        if not all_data:
            return pd.DataFrame()

        # 轉換為 DataFrame
        df = pd.DataFrame(all_data)

        # 標準化欄位
        df["timestamp"] = pd.to_datetime(df["time"], unit="ms")
        df["symbol"] = symbol
        df["side"] = df["side"].str.lower()  # BUY -> long, SELL -> short
        df["side"] = df["side"].map({"buy": "long", "sell": "short"})
        df["size"] = df["origQty"].astype(float)
        df["price"] = df["price"].astype(float)
        df["value"] = df["size"] * df["price"]

        # 選擇需要的欄位
        df = df[["timestamp", "symbol", "side", "size", "price", "value"]]
        df = df.sort_values("timestamp").reset_index(drop=True)

        return df

    def calculate_liquidation_density(self, df: pd.DataFrame, window: str = "1H") -> pd.DataFrame:
        """計算爆倉密度

        在指定時間窗口內聚合爆倉數據

        Args:
            df: 爆倉數據
            window: 時間窗口（如 '1H', '4H', '1D'）

        Returns:
            DataFrame with columns:
                - timestamp: 時間窗口開始時間
                - total_liquidations: 總爆倉次數
                - total_value: 總爆倉價值
                - long_liquidations: 多頭爆倉次數
                - short_liquidations: 空頭爆倉次數
                - long_value: 多頭爆倉價值
                - short_value: 空頭爆倉價值
                - dominant_side: 主導方向
        """
        if df.empty:
            return pd.DataFrame()

        df = df.copy()
        df = df.set_index("timestamp")

        # 按時間窗口聚合
        agg_dict = {"value": "sum", "size": "count"}

        # 總體聚合
        total = df.resample(window).agg(agg_dict)
        total = total.rename(columns={"value": "total_value", "size": "total_liquidations"})

        # 多頭爆倉
        long_df = df[df["side"] == "long"]
        long_agg = long_df.resample(window).agg(agg_dict)
        long_agg = long_agg.rename(columns={"value": "long_value", "size": "long_liquidations"})

        # 空頭爆倉
        short_df = df[df["side"] == "short"]
        short_agg = short_df.resample(window).agg(agg_dict)
        short_agg = short_agg.rename(columns={"value": "short_value", "size": "short_liquidations"})

        # 合併
        result = pd.concat([total, long_agg, short_agg], axis=1)
        result = result.fillna(0)

        # 計算主導方向
        result["dominant_side"] = "neutral"
        result.loc[result["long_value"] > result["short_value"] * 1.5, "dominant_side"] = "long"
        result.loc[result["short_value"] > result["long_value"] * 1.5, "dominant_side"] = "short"

        result = result.reset_index()

        logger.info(f"Calculated liquidation density with {len(result)} periods")

        return result

    def calculate_panic_index(self, df: pd.DataFrame, window: int = 24) -> Dict[str, Any]:
        """計算市場恐慌指數

        基於爆倉密度和強度計算恐慌指數（0-100）

        Args:
            df: 爆倉數據
            window: 分析窗口（小時）

        Returns:
            恐慌指數和分析結果
        """
        if df.empty or len(df) < window:
            return {"panic_index": 0, "level": "unknown", "status": "insufficient_data"}

        # 計算密度
        density_df = self.calculate_liquidation_density(df, window="1H")

        if density_df.empty:
            return {"panic_index": 0, "level": "unknown", "status": "no_liquidations"}

        # 取最近的數據
        recent = density_df.tail(window)

        # 計算指標
        total_value = recent["total_value"].sum()
        avg_value = recent["total_value"].mean()
        max_value = recent["total_value"].max()
        current_value = recent["total_value"].iloc[-1]

        # 恐慌指數計算
        # 基於當前爆倉量相對於平均值的倍數
        if avg_value > 0:
            intensity_ratio = current_value / avg_value
        else:
            intensity_ratio = 0

        # 標準化到 0-100
        panic_index = min(100, intensity_ratio * 20)

        # 恐慌等級
        if panic_index < 20:
            level = "calm"
        elif panic_index < 40:
            level = "moderate"
        elif panic_index < 60:
            level = "elevated"
        elif panic_index < 80:
            level = "high"
        else:
            level = "extreme"

        return {
            "panic_index": panic_index,
            "level": level,
            "total_liquidations_24h": total_value,
            "current_liquidations": current_value,
            "avg_liquidations": avg_value,
            "max_liquidations": max_value,
            "intensity_ratio": intensity_ratio,
            "window_hours": window,
        }

    def identify_liquidation_clusters(
        self, df: pd.DataFrame, threshold: float = 1000000  # $1M USDT
    ) -> pd.DataFrame:
        """識別爆倉聚集區

        標記大額爆倉事件（可能是價格拐點）

        Args:
            df: 爆倉數據
            threshold: 爆倉價值閾值（USDT）

        Returns:
            DataFrame with additional columns:
                - is_cluster: 是否為聚集區
                - cluster_type: 聚集類型 (long_squeeze/short_squeeze)
        """
        if df.empty:
            return df

        # 計算密度
        density_df = self.calculate_liquidation_density(df, window="1H")

        # 標記聚集區
        density_df["is_cluster"] = density_df["total_value"] > threshold

        # 聚集類型
        density_df["cluster_type"] = "none"
        density_df.loc[
            (density_df["is_cluster"]) & (density_df["dominant_side"] == "long"), "cluster_type"
        ] = "long_squeeze"
        density_df.loc[
            (density_df["is_cluster"]) & (density_df["dominant_side"] == "short"), "cluster_type"
        ] = "short_squeeze"

        cluster_count = density_df["is_cluster"].sum()
        logger.info(f"Identified {cluster_count} liquidation clusters")

        return density_df

    def save(self, df: pd.DataFrame, symbol: str, exchange: str, format: str = "parquet") -> Path:
        """保存爆倉數據到存儲"""
        if df.empty:
            logger.warning("Empty DataFrame, skipping save")
            return None

        exchange_dir = self.storage_path / exchange
        exchange_dir.mkdir(exist_ok=True)

        start_date = df["timestamp"].min().strftime("%Y%m%d")
        end_date = df["timestamp"].max().strftime("%Y%m%d")
        filename = f"{symbol}_liquidations_{start_date}_{end_date}.{format}"
        filepath = exchange_dir / filename

        if format == "parquet":
            df.to_parquet(filepath, compression="snappy", index=False)
        elif format == "csv":
            df.to_csv(filepath, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Saved liquidation data to {filepath}")

        return filepath

    def load(
        self,
        symbol: str,
        exchange: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """從存儲載入爆倉數據"""
        exchange_dir = self.storage_path / exchange

        if not exchange_dir.exists():
            logger.warning(f"No data found for {exchange}")
            return pd.DataFrame()

        pattern = f"{symbol}_liquidations_*.parquet"
        files = list(exchange_dir.glob(pattern))

        if not files:
            logger.warning(f"No liquidation data files found for {symbol}")
            return pd.DataFrame()

        dfs = []
        for file in files:
            df = pd.read_parquet(file)
            dfs.append(df)

        df = pd.concat(dfs, ignore_index=True)
        df = df.sort_values("timestamp").drop_duplicates("timestamp")

        if start_date:
            df = df[df["timestamp"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["timestamp"] <= pd.to_datetime(end_date)]

        logger.info(f"Loaded {len(df)} liquidation records for {symbol}")

        return df


# 便捷函數
def fetch_liquidations(
    symbol: str,
    start_time: Optional[Union[str, datetime]] = None,
    end_time: Optional[Union[str, datetime]] = None,
    exchange: str = "binance",
) -> pd.DataFrame:
    """便捷函數：獲取爆倉數據

    Example:
        >>> df = fetch_liquidations('BTCUSDT')
        >>> print(f"Total liquidations: {len(df)}")
    """
    liq = LiquidationData()
    return liq.fetch(symbol, start_time, end_time, exchange)


def calculate_panic_index(symbol: str, exchange: str = "binance") -> Dict[str, Any]:
    """便捷函數：計算市場恐慌指數

    Example:
        >>> panic = calculate_panic_index('BTCUSDT')
        >>> print(f"Panic Level: {panic['level']}, Index: {panic['panic_index']:.1f}")
    """
    liq = LiquidationData()
    df = liq.fetch(symbol, exchange=exchange)
    return liq.calculate_panic_index(df)
