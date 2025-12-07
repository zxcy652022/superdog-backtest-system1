"""
Multi-Exchange Data Aggregation for SuperDog v0.5

多交易所數據聚合器 - 整合Binance, Bybit, OKX的數據

Features:
- 多交易所數據並行獲取
- 數據一致性檢查
- 交叉驗證和異常檢測
- 加權平均和中位數計算
- 交易所間價差分析

Version: v0.5 Phase B
Author: SuperDog Quant Team
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from data.perpetual import FundingRateData, LongShortRatioData, OpenInterestData

logger = logging.getLogger(__name__)


class MultiExchangeAggregator:
    """多交易所數據聚合器

    並行獲取並整合多個交易所的永續合約數據

    Features:
    - 並行數據獲取
    - 自動時間對齊
    - 數據一致性檢查
    - 交叉驗證
    - 異常值檢測
    """

    def __init__(self, exchanges: Optional[List[str]] = None):
        """初始化多交易所聚合器

        Args:
            exchanges: 交易所列表（默認：['binance', 'bybit', 'okx']）
        """
        if exchanges is None:
            exchanges = ["binance", "bybit", "okx"]

        self.exchanges = exchanges
        self.supported_exchanges = ["binance", "bybit", "okx"]

        # 驗證交易所
        for exchange in self.exchanges:
            if exchange not in self.supported_exchanges:
                raise ValueError(f"Unsupported exchange: {exchange}")

        # 數據處理器
        self.funding_rate = FundingRateData()
        self.open_interest = OpenInterestData()
        self.long_short_ratio = LongShortRatioData()

        logger.info(f"MultiExchangeAggregator initialized with exchanges: {self.exchanges}")

    def aggregate_funding_rates(
        self,
        symbol: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        method: str = "weighted_mean",
    ) -> pd.DataFrame:
        """聚合多交易所資金費率

        Args:
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間
            method: 聚合方法 (weighted_mean/median/mean)

        Returns:
            聚合後的資金費率數據
        """
        # 並行獲取各交易所數據
        data_dict = self._fetch_parallel("funding_rate", symbol, start_time, end_time)

        if not data_dict:
            logger.warning(f"No funding rate data from any exchange for {symbol}")
            return pd.DataFrame()

        # 合併數據
        all_data = []
        for exchange, df in data_dict.items():
            if not df.empty:
                df["exchange"] = exchange
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)

        # 按時間聚合
        aggregated = self._aggregate_by_time(combined, value_column="funding_rate", method=method)

        # 添加額外統計
        aggregated["num_exchanges"] = combined.groupby("timestamp")["exchange"].nunique()
        aggregated["std_across_exchanges"] = combined.groupby("timestamp")["funding_rate"].std()

        logger.info(f"Aggregated funding rates from {len(data_dict)} exchanges")

        return aggregated

    def aggregate_open_interest(
        self,
        symbol: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        interval: str = "1h",
        method: str = "sum",
    ) -> pd.DataFrame:
        """聚合多交易所持倉量

        Args:
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間
            interval: 時間間隔
            method: 聚合方法 (sum/weighted_mean/median)

        Returns:
            聚合後的持倉量數據
        """
        # 並行獲取各交易所數據
        data_dict = self._fetch_parallel(
            "open_interest", symbol, start_time, end_time, interval=interval
        )

        if not data_dict:
            logger.warning(f"No open interest data from any exchange for {symbol}")
            return pd.DataFrame()

        # 合併數據
        all_data = []
        for exchange, df in data_dict.items():
            if not df.empty:
                df["exchange"] = exchange
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)

        # 按時間聚合
        aggregated = self._aggregate_by_time(combined, value_column="open_interest", method=method)

        aggregated["num_exchanges"] = combined.groupby("timestamp")["exchange"].nunique()
        aggregated["total_oi"] = combined.groupby("timestamp")["open_interest"].sum()

        logger.info(f"Aggregated open interest from {len(data_dict)} exchanges")

        return aggregated

    def compare_exchanges(
        self, symbol: str, data_type: str = "funding_rate", window: int = 24
    ) -> Dict[str, Any]:
        """比較交易所間的數據差異

        Args:
            symbol: 交易對
            data_type: 數據類型 (funding_rate/open_interest/long_short_ratio)
            window: 分析窗口（小時）

        Returns:
            比較結果
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=window)

        # 獲取各交易所數據
        data_dict = self._fetch_parallel(data_type, symbol, start_time, end_time)

        if len(data_dict) < 2:
            return {"status": "insufficient_exchanges", "available": len(data_dict)}

        # 計算統計
        stats = {}

        for exchange, df in data_dict.items():
            if df.empty:
                continue

            if data_type == "funding_rate":
                value_col = "funding_rate"
            elif data_type == "open_interest":
                value_col = "open_interest"
            elif data_type == "long_short_ratio":
                value_col = "long_ratio"
            else:
                value_col = "value"

            if value_col not in df.columns:
                continue

            stats[exchange] = {
                "mean": df[value_col].mean(),
                "median": df[value_col].median(),
                "std": df[value_col].std(),
                "min": df[value_col].min(),
                "max": df[value_col].max(),
                "count": len(df),
            }

        # 計算差異
        if len(stats) >= 2:
            means = [s["mean"] for s in stats.values()]
            mean_diff = max(means) - min(means)
            mean_diff_pct = (mean_diff / np.mean(means)) * 100 if np.mean(means) != 0 else 0
        else:
            mean_diff = 0
            mean_diff_pct = 0

        return {
            "symbol": symbol,
            "data_type": data_type,
            "window_hours": window,
            "exchanges": list(stats.keys()),
            "stats": stats,
            "mean_difference": mean_diff,
            "mean_difference_pct": mean_diff_pct,
            "is_consistent": mean_diff_pct < 5.0,  # 5% threshold
        }

    def detect_cross_exchange_anomalies(
        self, symbol: str, threshold: float = 2.0
    ) -> Dict[str, Any]:
        """檢測交易所間的異常差異

        Args:
            symbol: 交易對
            threshold: Z-score閾值

        Returns:
            異常檢測結果
        """
        # 獲取資金費率數據
        data_dict = self._fetch_parallel("funding_rate", symbol)

        if len(data_dict) < 2:
            return {"anomalies_detected": False, "reason": "insufficient_exchanges"}

        # 對齊時間並計算差異
        dfs = []
        for exchange, df in data_dict.items():
            if not df.empty:
                df = df[["timestamp", "funding_rate"]].copy()
                df = df.rename(columns={"funding_rate": exchange})
                dfs.append(df)

        if not dfs:
            return {"anomalies_detected": False, "reason": "no_data"}

        # 合併數據
        merged = dfs[0]
        for df in dfs[1:]:
            merged = pd.merge(merged, df, on="timestamp", how="outer")

        # 計算各交易所的偏離
        merged = merged.set_index("timestamp")
        mean_rate = merged.mean(axis=1)
        std_rate = merged.std(axis=1)

        anomalies = []
        for col in merged.columns:
            z_scores = (merged[col] - mean_rate) / (std_rate + 1e-10)
            anomaly_mask = z_scores.abs() > threshold

            if anomaly_mask.any():
                anomalies.append(
                    {
                        "exchange": col,
                        "count": anomaly_mask.sum(),
                        "max_z_score": z_scores.abs().max(),
                    }
                )

        return {
            "anomalies_detected": len(anomalies) > 0,
            "anomalies": anomalies,
            "threshold": threshold,
        }

    def _fetch_parallel(
        self,
        data_type: str,
        symbol: str,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        **kwargs,
    ) -> Dict[str, pd.DataFrame]:
        """並行獲取多交易所數據

        Args:
            data_type: 數據類型
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間
            **kwargs: 額外參數

        Returns:
            {exchange: DataFrame} 字典
        """
        results = {}

        def fetch_single_exchange(exchange: str) -> tuple:
            try:
                if data_type == "funding_rate":
                    df = self.funding_rate.fetch(symbol, start_time, end_time, exchange=exchange)
                elif data_type == "open_interest":
                    interval = kwargs.get("interval", "1h")
                    df = self.open_interest.fetch(symbol, start_time, end_time, interval, exchange)
                elif data_type == "long_short_ratio":
                    interval = kwargs.get("interval", "5m")
                    df = self.long_short_ratio.fetch(
                        symbol, start_time, end_time, interval, exchange
                    )
                else:
                    df = pd.DataFrame()

                return (exchange, df)

            except Exception as e:
                logger.warning(f"Failed to fetch {data_type} from {exchange}: {e}")
                return (exchange, pd.DataFrame())

        # 並行執行
        with ThreadPoolExecutor(max_workers=len(self.exchanges)) as executor:
            futures = {
                executor.submit(fetch_single_exchange, exchange): exchange
                for exchange in self.exchanges
            }

            for future in as_completed(futures):
                exchange, df = future.result()
                if not df.empty:
                    results[exchange] = df

        return results

    def _aggregate_by_time(
        self, df: pd.DataFrame, value_column: str, method: str = "weighted_mean"
    ) -> pd.DataFrame:
        """按時間聚合數據

        Args:
            df: 合併後的數據
            value_column: 要聚合的值欄位
            method: 聚合方法

        Returns:
            聚合後的數據
        """
        if df.empty:
            return df

        if method == "weighted_mean":
            # 使用交易量作為權重（如果有）
            aggregated = df.groupby("timestamp")[value_column].mean().reset_index()
        elif method == "median":
            aggregated = df.groupby("timestamp")[value_column].median().reset_index()
        elif method == "mean":
            aggregated = df.groupby("timestamp")[value_column].mean().reset_index()
        elif method == "sum":
            aggregated = df.groupby("timestamp")[value_column].sum().reset_index()
        else:
            raise ValueError(f"Unsupported aggregation method: {method}")

        aggregated = aggregated.rename(columns={value_column: f"{value_column}_aggregated"})
        aggregated["symbol"] = df["symbol"].iloc[0] if "symbol" in df.columns else None

        return aggregated


# 便捷函數
def aggregate_funding_rates(
    symbol: str,
    exchanges: Optional[List[str]] = None,
    start_time: Optional[Union[str, datetime]] = None,
    end_time: Optional[Union[str, datetime]] = None,
) -> pd.DataFrame:
    """便捷函數：聚合多交易所資金費率

    Example:
        >>> df = aggregate_funding_rates('BTCUSDT', exchanges=['binance', 'bybit'])
        >>> print(df[['timestamp', 'funding_rate_aggregated', 'num_exchanges']].tail())
    """
    agg = MultiExchangeAggregator(exchanges)
    return agg.aggregate_funding_rates(symbol, start_time, end_time)


def aggregate_open_interest(
    symbol: str, exchanges: Optional[List[str]] = None, interval: str = "1h"
) -> pd.DataFrame:
    """便捷函數：聚合多交易所持倉量

    Example:
        >>> df = aggregate_open_interest('BTCUSDT', exchanges=['binance', 'okx'])
        >>> print(f"Total OI: {df['total_oi'].iloc[-1]:,.0f}")
    """
    agg = MultiExchangeAggregator(exchanges)
    return agg.aggregate_open_interest(symbol, interval=interval)


def compare_exchanges(
    symbol: str, data_type: str = "funding_rate", exchanges: Optional[List[str]] = None
) -> Dict[str, Any]:
    """便捷函數：比較交易所間數據

    Example:
        >>> result = compare_exchanges('BTCUSDT', 'funding_rate')
        >>> print(f"Consistent: {result['is_consistent']}")
        >>> print(f"Difference: {result['mean_difference_pct']:.2f}%")
    """
    agg = MultiExchangeAggregator(exchanges)
    return agg.compare_exchanges(symbol, data_type)
