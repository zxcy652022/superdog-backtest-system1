"""
Symbol Mapper v0.7

符號映射器 - 處理不同交易所的符號格式轉換

功能:
- 自動處理 BTC/USDT ↔ BTCUSDT 轉換
- 支援多交易所符號格式（Binance、Bybit、OKX）
- 符號驗證和標準化

Version: v0.7
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ExchangeFormat(Enum):
    """交易所符號格式"""

    BINANCE = "binance"  # BTCUSDT
    BYBIT = "bybit"  # BTCUSDT
    OKX = "okx"  # BTC-USDT-SWAP
    CCXT = "ccxt"  # BTC/USDT


@dataclass
class ParsedSymbol:
    """解析後的符號結構"""

    base: str  # 基礎貨幣 (BTC)
    quote: str  # 報價貨幣 (USDT)
    original: str  # 原始符號
    is_perpetual: bool = False  # 是否永續合約


class SymbolMapper:
    """符號映射器

    Example:
        >>> mapper = SymbolMapper()
        >>> mapper.to_binance("BTC/USDT")
        'BTCUSDT'
        >>> mapper.to_ccxt("BTCUSDT")
        'BTC/USDT'
        >>> mapper.parse("BTC-USDT-SWAP")
        ParsedSymbol(base='BTC', quote='USDT', original='BTC-USDT-SWAP', is_perpetual=True)
    """

    # 常見報價貨幣
    QUOTE_CURRENCIES = ["USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB"]

    # 穩定幣列表
    STABLECOINS = ["USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "FDUSD"]

    # 槓桿代幣後綴
    LEVERAGED_SUFFIXES = ["UP", "DOWN", "BULL", "BEAR", "3L", "3S", "2L", "2S"]

    def __init__(self):
        """初始化符號映射器"""
        pass

    def parse(self, symbol: str) -> Optional[ParsedSymbol]:
        """解析符號"""
        if not symbol:
            return None

        symbol = symbol.strip().upper()
        original = symbol

        # 處理 OKX 格式: BTC-USDT-SWAP
        if "-SWAP" in symbol:
            symbol = symbol.replace("-SWAP", "")
            is_perpetual = True
        else:
            is_perpetual = False

        # 處理 CCXT 格式: BTC/USDT
        if "/" in symbol:
            parts = symbol.split("/")
            if len(parts) == 2:
                return ParsedSymbol(
                    base=parts[0],
                    quote=parts[1],
                    original=original,
                    is_perpetual=is_perpetual,
                )

        # 處理 OKX 格式: BTC-USDT
        if "-" in symbol:
            parts = symbol.split("-")
            if len(parts) >= 2:
                return ParsedSymbol(
                    base=parts[0],
                    quote=parts[1],
                    original=original,
                    is_perpetual=is_perpetual,
                )

        # 處理 Binance 格式: BTCUSDT
        base, quote = self._split_binance_symbol(symbol)
        if base and quote:
            return ParsedSymbol(
                base=base, quote=quote, original=original, is_perpetual=is_perpetual
            )

        logger.warning(f"無法解析符號: {original}")
        return None

    def _split_binance_symbol(self, symbol: str) -> Tuple[Optional[str], Optional[str]]:
        """拆分 Binance 格式的符號"""
        for quote in self.QUOTE_CURRENCIES:
            if symbol.endswith(quote):
                base = symbol[: -len(quote)]
                if base:
                    return base, quote
        return None, None

    def to_binance(self, symbol: str) -> Optional[str]:
        """轉換為 Binance 格式"""
        parsed = self.parse(symbol)
        if parsed:
            return f"{parsed.base}{parsed.quote}"
        return None

    def to_ccxt(self, symbol: str) -> Optional[str]:
        """轉換為 CCXT 格式"""
        parsed = self.parse(symbol)
        if parsed:
            return f"{parsed.base}/{parsed.quote}"
        return None

    def to_okx(self, symbol: str, perpetual: bool = False) -> Optional[str]:
        """轉換為 OKX 格式"""
        parsed = self.parse(symbol)
        if parsed:
            base = f"{parsed.base}-{parsed.quote}"
            if perpetual:
                return f"{base}-SWAP"
            return base
        return None

    def is_stablecoin(self, symbol: str) -> bool:
        """檢查是否為穩定幣交易對"""
        parsed = self.parse(symbol)
        if parsed:
            return parsed.base in self.STABLECOINS
        return False

    def is_leveraged_token(self, symbol: str) -> bool:
        """檢查是否為槓桿代幣"""
        parsed = self.parse(symbol)
        if parsed:
            base = parsed.base
            for suffix in self.LEVERAGED_SUFFIXES:
                if base.endswith(suffix):
                    return True
        return False

    def validate(self, symbol: str) -> bool:
        """驗證符號是否有效"""
        return self.parse(symbol) is not None

    def get_base(self, symbol: str) -> Optional[str]:
        """獲取基礎貨幣"""
        parsed = self.parse(symbol)
        return parsed.base if parsed else None

    def get_quote(self, symbol: str) -> Optional[str]:
        """獲取報價貨幣"""
        parsed = self.parse(symbol)
        return parsed.quote if parsed else None


# ===== 便捷函數 =====


def normalize_symbol(symbol: str, target_format: str = "binance") -> Optional[str]:
    """標準化符號格式"""
    mapper = SymbolMapper()

    if target_format == "binance":
        return mapper.to_binance(symbol)
    elif target_format == "ccxt":
        return mapper.to_ccxt(symbol)
    elif target_format == "okx":
        return mapper.to_okx(symbol)
    else:
        raise ValueError(f"不支援的格式: {target_format}")


def is_valid_trading_pair(symbol: str) -> bool:
    """檢查是否為有效的交易對"""
    mapper = SymbolMapper()
    return mapper.validate(symbol)
