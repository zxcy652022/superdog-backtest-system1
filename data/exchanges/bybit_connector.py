"""
Bybit Exchange Connector for SuperDog v0.5

Bybit 永續合約數據連接器 - 提供資金費率、持倉量、爆倉等數據

API文檔: https://bybit-exchange.github.io/docs/v5/intro
Base URL: https://api.bybit.com

Version: v0.5 Phase B
Author: SuperDog Quant Team
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from .base_connector import ExchangeAPIError, ExchangeConnector

logger = logging.getLogger(__name__)


class BybitAPIError(ExchangeAPIError):
    """Bybit API 專用錯誤類別"""

    pass


class BybitConnector(ExchangeConnector):
    """Bybit 永續合約數據連接器

    支援功能：
    - 資金費率歷史
    - 持倉量數據
    - 多空持倉比
    - 爆倉數據
    - 標記價格

    API特性：
    - Base URL: https://api.bybit.com
    - Rate Limit: 120 requests/minute (public endpoints)
    - 無需API Key用於公開數據
    """

    def __init__(
        self, api_key: Optional[str] = None, secret_key: Optional[str] = None, testnet: bool = False
    ):
        """初始化 Bybit 連接器

        Args:
            api_key: API金鑰（公開端點可選）
            secret_key: API密鑰（公開端點可選）
            testnet: 是否使用測試網
        """
        self.name = "bybit"

        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"

        self.api_key = api_key
        self.secret_key = secret_key

        # 創建會話
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "User-Agent": "SuperDog-Quant-v0.5"}
        )

        # Rate limiting設置
        self.rate_limit = 120  # requests per minute
        self.rate_limit_window = 60  # seconds
        self.request_times: List[float] = []

        logger.info(f"Bybit connector initialized: {self.base_url}")

    def _check_rate_limit(self):
        """檢查並執行速率限制"""
        now = time.time()

        # 清理舊的請求記錄
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit_window]

        # 如果達到限制，等待
        if len(self.request_times) >= self.rate_limit * 0.9:  # 90%閾值
            sleep_time = self.rate_limit_window - (now - self.request_times[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit approaching, sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self.request_times.clear()

        self.request_times.append(now)

    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, method: str = "GET"
    ) -> Dict[str, Any]:
        """執行API請求

        Args:
            endpoint: API端點
            params: 請求參數
            method: HTTP方法

        Returns:
            API響應數據

        Raises:
            BybitAPIError: 當API請求失敗時
        """
        self._check_rate_limit()

        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                response = self.session.get(url, params=params, timeout=30)
            else:
                response = self.session.post(url, json=params, timeout=30)

            response.raise_for_status()
            data = response.json()

            # Bybit API 響應格式: {"retCode": 0, "retMsg": "OK", "result": {...}}
            if data.get("retCode") != 0:
                raise BybitAPIError(f"Bybit API error: {data.get('retMsg', 'Unknown error')}")

            return data.get("result", {})

        except requests.exceptions.RequestException as e:
            raise BybitAPIError(f"Request failed: {e}")
        except Exception as e:
            raise BybitAPIError(f"Unexpected error: {e}")

    def _validate_symbol(self, symbol: str) -> str:
        """驗證並標準化交易對符號

        Bybit格式: BTCUSDT (與Binance相同)
        """
        symbol = symbol.upper().replace("/", "").replace("-", "").replace("_", "")

        if not symbol.endswith("USDT"):
            logger.warning(f"Symbol {symbol} doesn't end with USDT, this might not work on Bybit")

        return symbol

    def get_funding_rate(
        self, symbol: str, start_time: datetime, end_time: datetime, limit: int = 200
    ) -> pd.DataFrame:
        """獲取 Bybit 資金費率歷史數據

        API: GET /v5/market/funding/history

        Args:
            symbol: 交易對（如 'BTCUSDT'）
            start_time: 開始時間
            end_time: 結束時間
            limit: 每次請求數量（最大 200）

        Returns:
            DataFrame with columns:
                timestamp, symbol, funding_rate, mark_price
        """
        symbol = self._validate_symbol(symbol)

        endpoint = "/v5/market/funding/history"
        all_data = []

        current_start = start_time

        while current_start < end_time:
            params = {
                "category": "linear",  # 永續合約
                "symbol": symbol,
                "startTime": int(current_start.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                "limit": min(limit, 200),
            }

            try:
                result = self._make_request(endpoint, params)
                data_list = result.get("list", [])

                if not data_list:
                    break

                all_data.extend(data_list)

                if len(data_list) < limit:
                    break

                # 更新下一次請求的開始時間
                last_time = int(data_list[-1]["fundingRateTimestamp"])
                current_start = datetime.fromtimestamp(last_time / 1000) + timedelta(milliseconds=1)

                time.sleep(0.1)  # 避免請求過快

            except BybitAPIError as e:
                logger.error(f"Failed to fetch funding rate: {e}")
                break

        if not all_data:
            return pd.DataFrame()

        # 轉換為 DataFrame
        df = pd.DataFrame(all_data)

        # 標準化欄位
        df["timestamp"] = pd.to_datetime(df["fundingRateTimestamp"], unit="ms")
        df["funding_rate"] = df["fundingRate"].astype(float)
        df["mark_price"] = df.get("markPrice", pd.Series([None] * len(df))).astype(float)
        df["symbol"] = symbol

        # 選擇需要的欄位
        df = df[["timestamp", "symbol", "funding_rate", "mark_price"]]
        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Fetched {len(df)} funding rate records for {symbol} from Bybit")

        return df

    def get_open_interest(
        self,
        symbol: str,
        interval: str = "5m",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 200,
    ) -> pd.DataFrame:
        """獲取 Bybit 持倉量歷史數據

        API: GET /v5/market/open-interest

        Args:
            symbol: 交易對
            interval: 時間間隔 (5min, 15min, 30min, 1h, 4h, 1d)
            start_time: 開始時間（可選，默認最近 30 天）
            end_time: 結束時間（可選，默認當前時間）
            limit: 每次請求數量（最大 200）

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

        # Bybit 間隔格式映射
        interval_map = {
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
        }

        bybit_interval = interval_map.get(interval, "5min")

        endpoint = "/v5/market/open-interest"
        all_data = []

        current_start = start_time

        while current_start < end_time:
            params = {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": bybit_interval,
                "startTime": int(current_start.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000),
                "limit": min(limit, 200),
            }

            try:
                result = self._make_request(endpoint, params)
                data_list = result.get("list", [])

                if not data_list:
                    break

                all_data.extend(data_list)

                if len(data_list) < limit:
                    break

                # 更新下一次請求的開始時間
                last_time = int(data_list[-1]["timestamp"])
                current_start = datetime.fromtimestamp(last_time / 1000) + timedelta(milliseconds=1)

                time.sleep(0.1)

            except BybitAPIError as e:
                logger.error(f"Failed to fetch open interest: {e}")
                break

        if not all_data:
            return pd.DataFrame()

        # 轉換為 DataFrame
        df = pd.DataFrame(all_data)

        # 標準化欄位
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["open_interest"] = df["openInterest"].astype(float)
        df["open_interest_value"] = df.get("openInterestValue", df["openInterest"]).astype(float)
        df["symbol"] = symbol

        # 選擇需要的欄位
        df = df[["timestamp", "symbol", "open_interest", "open_interest_value"]]
        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Fetched {len(df)} open interest records for {symbol} from Bybit")

        return df

    def get_long_short_ratio(
        self, symbol: str, interval: str = "5m", limit: int = 500
    ) -> pd.DataFrame:
        """獲取 Bybit 多空持倉比數據

        API: GET /v5/market/account-ratio

        Args:
            symbol: 交易對
            interval: 時間間隔 (5min, 15min, 30min, 1h, 4h, 1d)
            limit: 數據數量（最大 500）

        Returns:
            DataFrame with columns:
                timestamp, symbol, long_ratio, short_ratio, long_account_ratio, short_account_ratio
        """
        symbol = self._validate_symbol(symbol)

        # Bybit 間隔格式
        interval_map = {
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
        }

        bybit_interval = interval_map.get(interval, "5min")

        endpoint = "/v5/market/account-ratio"

        params = {
            "category": "linear",
            "symbol": symbol,
            "period": bybit_interval,
            "limit": min(limit, 500),
        }

        try:
            result = self._make_request(endpoint, params)
            data_list = result.get("list", [])

            if not data_list:
                return pd.DataFrame()

            # 轉換為 DataFrame
            df = pd.DataFrame(data_list)

            # 標準化欄位
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["long_ratio"] = df["buyRatio"].astype(float)
            df["short_ratio"] = df["sellRatio"].astype(float)
            df["symbol"] = symbol

            # 選擇需要的欄位
            df = df[["timestamp", "symbol", "long_ratio", "short_ratio"]]
            df = df.sort_values("timestamp").reset_index(drop=True)

            logger.info(f"Fetched {len(df)} long/short ratio records for {symbol} from Bybit")

            return df

        except BybitAPIError as e:
            logger.error(f"Failed to fetch long/short ratio: {e}")
            return pd.DataFrame()

    def get_mark_price(self, symbol: str) -> Optional[float]:
        """獲取 Bybit 當前標記價格

        API: GET /v5/market/tickers

        Args:
            symbol: 交易對

        Returns:
            當前標記價格
        """
        symbol = self._validate_symbol(symbol)

        endpoint = "/v5/market/tickers"

        params = {"category": "linear", "symbol": symbol}

        try:
            result = self._make_request(endpoint, params)
            data_list = result.get("list", [])

            if not data_list:
                return None

            mark_price = float(data_list[0].get("markPrice", 0))

            logger.info(f"Fetched mark price for {symbol} from Bybit: {mark_price}")

            return mark_price

        except BybitAPIError as e:
            logger.error(f"Failed to fetch mark price: {e}")
            return None

    def get_liquidations(
        self, symbol: str, start_time: datetime, end_time: datetime, limit: int = 1000
    ) -> pd.DataFrame:
        """獲取 Bybit 爆倉數據

        注意：Bybit V5 API 沒有直接的爆倉歷史端點
        需要通過 WebSocket 實時訂閱爆倉數據

        這個方法預留用於未來實現 WebSocket 支持

        Args:
            symbol: 交易對
            start_time: 開始時間
            end_time: 結束時間
            limit: 數據數量

        Returns:
            DataFrame (目前返回空)
        """
        logger.warning(
            "Bybit liquidation data requires WebSocket subscription. "
            "Historical liquidation data is not available via REST API."
        )

        return pd.DataFrame()
