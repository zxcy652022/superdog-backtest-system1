"""
Binance Perpetual Futures Connector for SuperDog v0.5

Binance 永續合約數據連接器 - 實作資金費率、持倉量等數據獲取

API 文檔: https://binance-docs.github.io/apidocs/futures/en/

Version: v0.5
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from .base_connector import ExchangeConnector

logger = logging.getLogger(__name__)


class BinanceAPIError(Exception):
    """Binance API 錯誤"""

    pass


class BinanceConnector(ExchangeConnector):
    """Binance 永續合約數據連接器

    特性：
    - 無需 API Key 即可獲取公開數據
    - 支援資金費率、持倉量、多空比等數據
    - 自動處理 API 限流和重試
    - 數據格式標準化

    Example:
        >>> connector = BinanceConnector()
        >>> funding = connector.get_funding_rate('BTCUSDT', start_time, end_time)
        >>> oi = connector.get_open_interest('BTCUSDT', interval='5m')
    """

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        """初始化 Binance 連接器

        Args:
            api_key: API 密鑰（可選，公開數據不需要）
            secret_key: API 密鑰（可選）
        """
        super().__init__(name="binance")
        self.base_url = "https://fapi.binance.com"  # Futures API
        self.api_key = api_key
        self.secret_key = secret_key
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SuperDog/0.5", "Accept": "application/json"})

        # API 限流控制
        self.request_count = 0
        self.last_request_time = time.time()
        self.rate_limit_interval = 60  # 秒
        self.max_requests_per_interval = 1200  # Binance 限制

    def get_funding_rate(
        self, symbol: str, start_time: datetime, end_time: datetime, limit: int = 1000
    ) -> pd.DataFrame:
        """獲取 Binance 資金費率歷史數據

        API: GET /fapi/v1/fundingRate
        權重: 1
        限制: 最多返回 1000 條記錄

        Args:
            symbol: 交易對（如 'BTCUSDT'）
            start_time: 開始時間
            end_time: 結束時間
            limit: 每次請求數量（最大 1000）

        Returns:
            DataFrame with columns:
                timestamp, symbol, funding_rate, funding_time, mark_price
        """
        symbol = self._validate_symbol(symbol)

        endpoint = "/fapi/v1/fundingRate"
        all_data = []

        # Binance 資金費率每 8 小時結算一次
        # 計算需要的請求次數
        time_diff = (end_time - start_time).total_seconds() / 3600
        estimated_records = int(time_diff / 8)  # 每 8 小時一條記錄

        current_start = start_time

        while current_start < end_time:
            params = {
                "symbol": symbol,
                "startTime": int(current_start.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                "limit": min(limit, 1000),
            }

            try:
                response = self._make_request(endpoint, params)

                if not response:
                    break

                all_data.extend(response)

                # 如果返回的數據量小於 limit，說明已經獲取完所有數據
                if len(response) < limit:
                    break

                # 更新 current_start 為最後一條記錄的時間 + 1ms
                last_time = response[-1]["fundingTime"]
                current_start = datetime.fromtimestamp(last_time / 1000) + timedelta(milliseconds=1)

                # 避免過於頻繁的請求
                time.sleep(0.1)

            except BinanceAPIError as e:
                logger.error(f"Failed to fetch funding rate: {e}")
                break

        if not all_data:
            return pd.DataFrame()

        # 轉換為 DataFrame
        df = pd.DataFrame(all_data)

        # 標準化欄位
        df["timestamp"] = pd.to_datetime(df["fundingTime"], unit="ms")
        df["funding_rate"] = df["fundingRate"].astype(float)
        df["mark_price"] = df.get("markPrice", pd.Series([None] * len(df))).astype(float)
        df["symbol"] = symbol

        # 選擇需要的欄位
        df = df[["timestamp", "symbol", "funding_rate", "mark_price"]]
        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Fetched {len(df)} funding rate records for {symbol}")

        return df

    def get_open_interest(
        self,
        symbol: str,
        interval: str = "5m",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """獲取 Binance 持倉量歷史數據

        API: GET /futures/data/openInterestHist
        權重: 1
        間隔: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d

        Args:
            symbol: 交易對
            interval: 時間間隔
            start_time: 開始時間（可選，默認最近 30 天）
            end_time: 結束時間（可選，默認當前時間）
            limit: 每次請求數量（最大 500）

        Returns:
            DataFrame with columns:
                timestamp, symbol, open_interest, open_interest_value
        """
        symbol = self._validate_symbol(symbol)

        # 默認時間範圍
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=30)

        endpoint = "/futures/data/openInterestHist"
        all_data = []

        current_start = start_time

        while current_start < end_time:
            params = {"symbol": symbol, "period": interval, "limit": min(limit, 500)}

            # 添加時間參數（注意：這個 API 只支持 startTime 和 endTime，不支持分頁）
            if start_time:
                params["startTime"] = int(current_start.timestamp() * 1000)
            if end_time:
                params["endTime"] = int(end_time.timestamp() * 1000)

            try:
                response = self._make_request(endpoint, params)

                if not response:
                    break

                all_data.extend(response)

                if len(response) < limit:
                    break

                # 更新 current_start
                last_time = response[-1]["timestamp"]
                current_start = datetime.fromtimestamp(last_time / 1000) + timedelta(milliseconds=1)

                time.sleep(0.1)

            except BinanceAPIError as e:
                logger.error(f"Failed to fetch open interest: {e}")
                break

        if not all_data:
            return pd.DataFrame()

        # 轉換為 DataFrame
        df = pd.DataFrame(all_data)

        # 標準化欄位
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["open_interest"] = df["sumOpenInterest"].astype(float)
        df["open_interest_value"] = df["sumOpenInterestValue"].astype(float)
        df["symbol"] = symbol

        # 選擇需要的欄位
        df = df[["timestamp", "symbol", "open_interest", "open_interest_value"]]
        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Fetched {len(df)} open interest records for {symbol}")

        return df

    def get_long_short_ratio(
        self, symbol: str, interval: str = "5m", limit: int = 500
    ) -> pd.DataFrame:
        """獲取 Binance 多空持倉比數據

        API: GET /futures/data/globalLongShortAccountRatio
        權重: 1

        Args:
            symbol: 交易對
            interval: 時間間隔（5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d）
            limit: 數據量（最大 500）

        Returns:
            DataFrame with columns:
                timestamp, symbol, long_account_ratio, short_account_ratio
        """
        symbol = self._validate_symbol(symbol)

        endpoint = "/futures/data/globalLongShortAccountRatio"
        params = {"symbol": symbol, "period": interval, "limit": min(limit, 500)}

        try:
            response = self._make_request(endpoint, params)

            if not response:
                return pd.DataFrame()

            # 轉換為 DataFrame
            df = pd.DataFrame(response)

            # 標準化欄位
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["long_account_ratio"] = df["longAccount"].astype(float)
            df["short_account_ratio"] = df["shortAccount"].astype(float)
            df["symbol"] = symbol

            # 計算持倉比例
            total = df["long_account_ratio"] + df["short_account_ratio"]
            df["long_position_ratio"] = df["long_account_ratio"] / total
            df["short_position_ratio"] = df["short_account_ratio"] / total

            # 選擇需要的欄位
            df = df[
                [
                    "timestamp",
                    "symbol",
                    "long_account_ratio",
                    "short_account_ratio",
                    "long_position_ratio",
                    "short_position_ratio",
                ]
            ]
            df = df.sort_values("timestamp").reset_index(drop=True)

            logger.info(f"Fetched {len(df)} long/short ratio records for {symbol}")

            return df

        except BinanceAPIError as e:
            logger.error(f"Failed to fetch long/short ratio: {e}")
            return pd.DataFrame()

    def get_mark_price(self, symbol: str) -> Dict[str, Any]:
        """獲取當前標記價格

        API: GET /fapi/v1/premiumIndex
        權重: 1

        Args:
            symbol: 交易對

        Returns:
            字典包含：mark_price, index_price, funding_rate, next_funding_time
        """
        symbol = self._validate_symbol(symbol)

        endpoint = "/fapi/v1/premiumIndex"
        params = {"symbol": symbol}

        try:
            response = self._make_request(endpoint, params)

            return {
                "symbol": symbol,
                "mark_price": float(response.get("markPrice", 0)),
                "index_price": float(response.get("indexPrice", 0)),
                "funding_rate": float(response.get("lastFundingRate", 0)),
                "next_funding_time": datetime.fromtimestamp(
                    int(response.get("nextFundingTime", 0)) / 1000
                ),
                "timestamp": datetime.now(),
            }

        except BinanceAPIError as e:
            logger.error(f"Failed to fetch mark price: {e}")
            return {}

    def _make_request(
        self, endpoint: str, params: Optional[Dict] = None, method: str = "GET"
    ) -> Any:
        """發送 API 請求

        Args:
            endpoint: API 端點
            params: 請求參數
            method: HTTP 方法

        Returns:
            API 響應數據

        Raises:
            BinanceAPIError: 當請求失敗時
        """
        # 限流檢查
        self._check_rate_limit()

        url = self.base_url + endpoint

        try:
            if method == "GET":
                response = self.session.get(url, params=params, timeout=30)
            else:
                response = self.session.post(url, params=params, timeout=30)

            response.raise_for_status()

            # 更新請求計數
            self.request_count += 1

            data = response.json()

            # 檢查 Binance API 錯誤
            if isinstance(data, dict) and "code" in data:
                raise BinanceAPIError(
                    f"API Error {data['code']}: {data.get('msg', 'Unknown error')}"
                )

            return data

        except requests.exceptions.RequestException as e:
            raise BinanceAPIError(f"Request failed: {e}")

    def _check_rate_limit(self):
        """檢查並控制 API 請求頻率"""
        current_time = time.time()
        time_since_last_reset = current_time - self.last_request_time

        # 如果超過限流時間間隔，重置計數
        if time_since_last_reset >= self.rate_limit_interval:
            self.request_count = 0
            self.last_request_time = current_time

        # 如果接近限制，等待
        if self.request_count >= self.max_requests_per_interval * 0.9:
            sleep_time = self.rate_limit_interval - time_since_last_reset
            if sleep_time > 0:
                logger.warning(f"Rate limit approaching, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self.request_count = 0
                self.last_request_time = time.time()
