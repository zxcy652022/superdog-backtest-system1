"""
Top Symbols Fetcher v0.7

Top 100 幣種抓取器 - 從 Binance API 獲取熱門幣種

功能:
- 從 Binance API 動態獲取 Top 100 幣種
- 智能過濾（排除穩定幣、槓桿代幣）
- 最低成交量過濾

Version: v0.7
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import requests

from data.downloaders.symbol_mapper import SymbolMapper

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """幣種信息"""

    symbol: str
    base: str
    quote: str
    volume_24h: float
    price: float
    price_change_24h: float


class TopSymbolsFetcher:
    """Top 100 幣種抓取器"""

    BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"

    STABLECOINS = {"USDC", "BUSD", "DAI", "TUSD", "USDP", "FDUSD", "USDT", "EUR", "GBP"}

    LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR", "3L", "3S", "2L", "2S")

    def __init__(self, timeout: int = 30):
        """初始化抓取器"""
        self.timeout = timeout
        self.mapper = SymbolMapper()
        self._cache: Optional[List[SymbolInfo]] = None

    def get_top_symbols(
        self,
        n: int = 100,
        quote: str = "USDT",
        min_volume: float = 1_000_000,
        exclude_stablecoins: bool = True,
        exclude_leveraged: bool = True,
        refresh: bool = False,
    ) -> List[str]:
        """獲取 Top N 幣種"""
        all_symbols = self._fetch_all_symbols(refresh=refresh)

        filtered = []
        for info in all_symbols:
            if info.quote != quote:
                continue
            if exclude_stablecoins and info.base in self.STABLECOINS:
                continue
            if exclude_leveraged and self._is_leveraged_token(info.base):
                continue
            if info.volume_24h < min_volume:
                continue
            filtered.append(info)

        filtered.sort(key=lambda x: x.volume_24h, reverse=True)

        return [info.symbol for info in filtered[:n]]

    def get_top_symbols_with_info(
        self,
        n: int = 100,
        quote: str = "USDT",
        min_volume: float = 1_000_000,
        exclude_stablecoins: bool = True,
        exclude_leveraged: bool = True,
    ) -> List[SymbolInfo]:
        """獲取 Top N 幣種（包含詳細信息）"""
        all_symbols = self._fetch_all_symbols()

        filtered = []
        for info in all_symbols:
            if info.quote != quote:
                continue
            if exclude_stablecoins and info.base in self.STABLECOINS:
                continue
            if exclude_leveraged and self._is_leveraged_token(info.base):
                continue
            if info.volume_24h < min_volume:
                continue
            filtered.append(info)

        filtered.sort(key=lambda x: x.volume_24h, reverse=True)
        return filtered[:n]

    def _fetch_all_symbols(self, refresh: bool = False) -> List[SymbolInfo]:
        """獲取所有幣種信息"""
        if self._cache and not refresh:
            return self._cache

        logger.info("正在從 Binance API 獲取 24h ticker 數據...")

        try:
            response = requests.get(self.BINANCE_TICKER_URL, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"API 請求失敗: {e}")
            raise

        symbols = []
        for item in data:
            try:
                symbol = item["symbol"]
                parsed = self.mapper.parse(symbol)
                if not parsed:
                    continue

                volume_quote = float(item["quoteVolume"])
                price = float(item["lastPrice"])
                price_change = float(item["priceChangePercent"])

                info = SymbolInfo(
                    symbol=symbol,
                    base=parsed.base,
                    quote=parsed.quote,
                    volume_24h=volume_quote,
                    price=price,
                    price_change_24h=price_change,
                )
                symbols.append(info)
            except (KeyError, ValueError) as e:
                logger.debug(f"解析 {item.get('symbol', 'unknown')} 失敗: {e}")
                continue

        logger.info(f"獲取到 {len(symbols)} 個幣種")
        self._cache = symbols
        return symbols

    def _is_leveraged_token(self, base: str) -> bool:
        """檢查是否為槓桿代幣"""
        for suffix in self.LEVERAGED_SUFFIXES:
            if base.endswith(suffix):
                return True
        return False

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """獲取單個幣種信息"""
        all_symbols = self._fetch_all_symbols()
        binance_symbol = self.mapper.to_binance(symbol)

        for info in all_symbols:
            if info.symbol == binance_symbol:
                return info
        return None

    def clear_cache(self):
        """清除緩存"""
        self._cache = None
        logger.info("緩存已清除")


# ===== 便捷函數 =====


def get_top_symbols(
    n: int = 100,
    quote: str = "USDT",
    min_volume: float = 1_000_000,
) -> List[str]:
    """獲取 Top N 幣種（便捷函數）"""
    fetcher = TopSymbolsFetcher()
    return fetcher.get_top_symbols(n=n, quote=quote, min_volume=min_volume)


def get_binance_top_100() -> List[str]:
    """獲取 Binance Top 100 USDT 幣種"""
    return get_top_symbols(n=100, quote="USDT", min_volume=1_000_000)
