"""
Base Exchange Connector for SuperDog v0.5

交易所連接器基底類別 - 定義統一的數據獲取接口

Version: v0.5
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd


class ExchangeAPIError(Exception):
    """交易所 API 錯誤基底類別"""

    pass


class DataFormatError(Exception):
    """數據格式錯誤"""

    pass


class ExchangeConnector(ABC):
    """交易所連接器基底類別

    所有交易所連接器必須實作此接口，確保數據格式統一

    Example:
        >>> class MyExchangeConnector(ExchangeConnector):
        ...     def get_funding_rate(self, symbol, start_time, end_time):
        ...         # 實作具體邏輯
        ...         pass
    """

    def __init__(self, name: str):
        """初始化連接器

        Args:
            name: 交易所名稱（如 'binance', 'bybit', 'okx'）
        """
        self.name = name
        self.base_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.secret_key: Optional[str] = None

    @abstractmethod
    def get_funding_rate(
        self, symbol: str, start_time: datetime, end_time: datetime, limit: int = 1000
    ) -> pd.DataFrame:
        """獲取資金費率歷史數據

        Args:
            symbol: 交易對符號（如 'BTCUSDT'）
            start_time: 開始時間
            end_time: 結束時間
            limit: 每次請求的最大數據量

        Returns:
            DataFrame with columns:
                - timestamp: pd.Timestamp
                - symbol: str
                - funding_rate: float
                - predicted_rate: float (optional)
                - mark_price: float (optional)
                - index_price: float (optional)
                - funding_time: pd.Timestamp

        Raises:
            APIError: 當 API 請求失敗時
            DataFormatError: 當數據格式異常時
        """
        pass

    @abstractmethod
    def get_open_interest(
        self,
        symbol: str,
        interval: str = "5m",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """獲取持倉量歷史數據

        Args:
            symbol: 交易對符號
            interval: 時間間隔（'5m', '15m', '30m', '1h', '4h', '1d'）
            start_time: 開始時間（可選）
            end_time: 結束時間（可選）
            limit: 每次請求的最大數據量

        Returns:
            DataFrame with columns:
                - timestamp: pd.Timestamp
                - symbol: str
                - open_interest: float
                - open_interest_value: float
                - change_24h: float (optional)
                - change_percentage: float (optional)
        """
        pass

    def get_mark_price(self, symbol: str) -> Dict[str, Any]:
        """獲取當前標記價格（可選實作）

        Args:
            symbol: 交易對符號

        Returns:
            字典包含：mark_price, index_price, funding_rate等
        """
        raise NotImplementedError(f"{self.name} does not implement get_mark_price")

    def get_liquidations(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> pd.DataFrame:
        """獲取爆倉數據（可選實作）

        Args:
            symbol: 交易對符號
            start_time: 開始時間
            end_time: 結束時間

        Returns:
            DataFrame with columns:
                - timestamp: pd.Timestamp
                - symbol: str
                - side: str ('long' or 'short')
                - size: float
                - price: float
                - value: float
        """
        raise NotImplementedError(f"{self.name} does not implement get_liquidations")

    def get_long_short_ratio(
        self, symbol: str, interval: str = "5m", limit: int = 500
    ) -> pd.DataFrame:
        """獲取多空持倉比（可選實作）

        Args:
            symbol: 交易對符號
            interval: 時間間隔
            limit: 數據量

        Returns:
            DataFrame with columns:
                - timestamp: pd.Timestamp
                - symbol: str
                - long_account_ratio: float
                - short_account_ratio: float
                - long_position_ratio: float
                - short_position_ratio: float
        """
        raise NotImplementedError(f"{self.name} does not implement get_long_short_ratio")

    def _handle_api_error(self, response: Any, endpoint: str) -> None:
        """處理 API 錯誤（由子類實作具體邏輯）

        Args:
            response: API 響應
            endpoint: API 端點

        Raises:
            APIError: 當 API 返回錯誤時
        """
        pass

    def _validate_symbol(self, symbol: str) -> str:
        """驗證和標準化交易對符號

        Args:
            symbol: 原始交易對符號

        Returns:
            標準化的交易對符號
        """
        # 基本驗證：轉換為大寫
        return symbol.upper()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
