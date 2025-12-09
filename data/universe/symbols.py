"""
Symbol Manager v0.4

多幣種管理器 - 支援多種加密貨幣交易對的管理和驗證

這個模組提供：
- 支援前20大加密貨幣
- 交易對驗證和格式化
- 幣種元數據（精度、最小單位等）
- 幣種分類和過濾

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class QuoteAsset(Enum):
    """報價資產類型"""

    USDT = "USDT"  # Tether USD
    USD = "USD"  # US Dollar
    BTC = "BTC"  # Bitcoin
    ETH = "ETH"  # Ethereum


@dataclass
class SymbolInfo:
    """交易對信息

    Attributes:
        symbol: 交易對符號（如 BTCUSDT）
        base_asset: 基礎資產（如 BTC）
        quote_asset: 報價資產（如 USDT）
        price_precision: 價格精度（小數位數）
        quantity_precision: 數量精度（小數位數）
        min_notional: 最小名義價值
        is_active: 是否活躍
        market_cap_rank: 市值排名（可選）
    """

    symbol: str
    base_asset: str
    quote_asset: str
    price_precision: int = 2
    quantity_precision: int = 8
    min_notional: float = 10.0
    is_active: bool = True
    market_cap_rank: Optional[int] = None

    def format_price(self, price: float) -> str:
        """格式化價格

        Args:
            price: 價格值

        Returns:
            格式化的價格字符串

        Example:
            >>> info = SymbolInfo("BTCUSDT", "BTC", "USDT", price_precision=2)
            >>> info.format_price(45123.456)
            '45123.46'
        """
        return f"{price:.{self.price_precision}f}"

    def format_quantity(self, quantity: float) -> str:
        """格式化數量

        Args:
            quantity: 數量值

        Returns:
            格式化的數量字符串
        """
        return f"{quantity:.{self.quantity_precision}f}"


class SymbolManager:
    """交易對管理器

    管理加密貨幣交易對的元數據和驗證

    Example:
        >>> manager = SymbolManager()
        >>> is_valid = manager.validate_symbol("BTCUSDT")
        >>> info = manager.get_symbol_info("BTCUSDT")
    """

    # 支援的前20大加密貨幣（按市值）
    TOP_CRYPTOS = [
        "BTC",  # Bitcoin
        "ETH",  # Ethereum
        "BNB",  # Binance Coin
        "SOL",  # Solana
        "XRP",  # Ripple
        "ADA",  # Cardano
        "DOGE",  # Dogecoin
        "AVAX",  # Avalanche
        "DOT",  # Polkadot
        "MATIC",  # Polygon
        "LTC",  # Litecoin
        "LINK",  # Chainlink
        "UNI",  # Uniswap
        "ATOM",  # Cosmos
        "XLM",  # Stellar
        "FIL",  # Filecoin
        "NEAR",  # NEAR Protocol
        "APT",  # Aptos
        "ARB",  # Arbitrum
        "OP",  # Optimism
    ]

    # 預定義的交易對信息
    SYMBOL_INFO = {
        # BTC pairs
        "BTCUSDT": SymbolInfo("BTCUSDT", "BTC", "USDT", 2, 6, 10.0, market_cap_rank=1),
        "BTCUSD": SymbolInfo("BTCUSD", "BTC", "USD", 2, 6, 10.0, market_cap_rank=1),
        # ETH pairs
        "ETHUSDT": SymbolInfo("ETHUSDT", "ETH", "USDT", 2, 5, 10.0, market_cap_rank=2),
        "ETHBTC": SymbolInfo("ETHBTC", "ETH", "BTC", 6, 5, 0.001),
        # BNB pairs
        "BNBUSDT": SymbolInfo("BNBUSDT", "BNB", "USDT", 2, 4, 10.0, market_cap_rank=3),
        # SOL pairs
        "SOLUSDT": SymbolInfo("SOLUSDT", "SOL", "USDT", 3, 3, 10.0, market_cap_rank=4),
        # XRP pairs
        "XRPUSDT": SymbolInfo("XRPUSDT", "XRP", "USDT", 4, 1, 10.0, market_cap_rank=5),
        # ADA pairs
        "ADAUSDT": SymbolInfo("ADAUSDT", "ADA", "USDT", 4, 0, 10.0, market_cap_rank=6),
        # DOGE pairs
        "DOGEUSDT": SymbolInfo("DOGEUSDT", "DOGE", "USDT", 5, 0, 10.0, market_cap_rank=7),
        # AVAX pairs
        "AVAXUSDT": SymbolInfo("AVAXUSDT", "AVAX", "USDT", 3, 2, 10.0, market_cap_rank=8),
        # DOT pairs
        "DOTUSDT": SymbolInfo("DOTUSDT", "DOT", "USDT", 3, 2, 10.0, market_cap_rank=9),
        # MATIC pairs
        "MATICUSDT": SymbolInfo("MATICUSDT", "MATIC", "USDT", 4, 1, 10.0, market_cap_rank=10),
    }

    def __init__(self):
        """初始化交易對管理器"""
        self._custom_symbols: Dict[str, SymbolInfo] = {}

    def validate_symbol(self, symbol: str) -> bool:
        """驗證交易對是否有效

        Args:
            symbol: 交易對符號

        Returns:
            True 如果有效，否則 False

        Example:
            >>> manager = SymbolManager()
            >>> manager.validate_symbol("BTCUSDT")
            True
            >>> manager.validate_symbol("INVALID")
            False
        """
        # 檢查預定義的交易對
        if symbol in self.SYMBOL_INFO:
            return True

        # 檢查自定義交易對
        if symbol in self._custom_symbols:
            return True

        # 嘗試解析交易對格式
        return self._is_valid_format(symbol)

    def _is_valid_format(self, symbol: str) -> bool:
        """檢查交易對格式是否有效

        Args:
            symbol: 交易對符號

        Returns:
            True 如果格式有效
        """
        # 基本格式檢查
        if not symbol or len(symbol) < 6:
            return False

        # 檢查是否以常見報價資產結尾
        for quote in ["USDT", "USD", "BTC", "ETH"]:
            if symbol.endswith(quote):
                return True

        return False

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """獲取交易對信息

        Args:
            symbol: 交易對符號

        Returns:
            SymbolInfo 對象，如果不存在則返回 None

        Example:
            >>> manager = SymbolManager()
            >>> info = manager.get_symbol_info("BTCUSDT")
            >>> print(info.base_asset)
            'BTC'
        """
        # 檢查預定義的交易對
        if symbol in self.SYMBOL_INFO:
            return self.SYMBOL_INFO[symbol]

        # 檢查自定義交易對
        if symbol in self._custom_symbols:
            return self._custom_symbols[symbol]

        # 嘗試創建默認信息
        if self._is_valid_format(symbol):
            return self._create_default_info(symbol)

        return None

    def _create_default_info(self, symbol: str) -> SymbolInfo:
        """創建默認的交易對信息

        Args:
            symbol: 交易對符號

        Returns:
            SymbolInfo 對象
        """
        # 解析基礎資產和報價資產
        for quote in ["USDT", "USD", "BTC", "ETH"]:
            if symbol.endswith(quote):
                base = symbol[: -len(quote)]
                return SymbolInfo(
                    symbol=symbol,
                    base_asset=base,
                    quote_asset=quote,
                    price_precision=4,
                    quantity_precision=4,
                    min_notional=10.0,
                )

        # 默認配置
        return SymbolInfo(
            symbol=symbol,
            base_asset=symbol[:-4] if len(symbol) > 4 else symbol,
            quote_asset=symbol[-4:] if len(symbol) > 4 else "USDT",
            price_precision=4,
            quantity_precision=4,
            min_notional=10.0,
        )

    def register_symbol(self, info: SymbolInfo) -> None:
        """註冊自定義交易對

        Args:
            info: 交易對信息

        Example:
            >>> manager = SymbolManager()
            >>> info = SymbolInfo("CUSTOMUSDT", "CUSTOM", "USDT")
            >>> manager.register_symbol(info)
        """
        self._custom_symbols[info.symbol] = info

    def list_symbols(self, quote_asset: Optional[str] = None) -> List[str]:
        """列出所有支援的交易對

        Args:
            quote_asset: 過濾報價資產（可選）

        Returns:
            交易對列表

        Example:
            >>> manager = SymbolManager()
            >>> usdt_pairs = manager.list_symbols(quote_asset="USDT")
        """
        symbols = list(self.SYMBOL_INFO.keys()) + list(self._custom_symbols.keys())

        if quote_asset:
            symbols = [s for s in symbols if s.endswith(quote_asset)]

        return sorted(symbols)

    def get_top_symbols(self, n: int = 10, quote_asset: str = "USDT") -> List[str]:
        """獲取前 N 個交易對（按市值排名）

        Args:
            n: 返回數量
            quote_asset: 報價資產

        Returns:
            交易對列表

        Example:
            >>> manager = SymbolManager()
            >>> top10 = manager.get_top_symbols(10, "USDT")
        """
        # 獲取有市值排名的交易對
        ranked_symbols = [
            (symbol, info)
            for symbol, info in self.SYMBOL_INFO.items()
            if info.market_cap_rank is not None and info.quote_asset == quote_asset
        ]

        # 按市值排名排序
        ranked_symbols.sort(key=lambda x: x[1].market_cap_rank)

        # 返回前 N 個
        return [symbol for symbol, _ in ranked_symbols[:n]]

    def parse_symbol(self, symbol: str) -> tuple:
        """解析交易對為基礎資產和報價資產

        Args:
            symbol: 交易對符號

        Returns:
            (base_asset, quote_asset) 元組

        Example:
            >>> manager = SymbolManager()
            >>> base, quote = manager.parse_symbol("BTCUSDT")
            >>> print(base, quote)
            'BTC' 'USDT'
        """
        info = self.get_symbol_info(symbol)

        if info:
            return (info.base_asset, info.quote_asset)

        # 默認解析
        for quote in ["USDT", "USD", "BTC", "ETH"]:
            if symbol.endswith(quote):
                return (symbol[: -len(quote)], quote)

        # 無法解析
        return (symbol, "UNKNOWN")

    def format_symbol(self, base: str, quote: str) -> str:
        """格式化基礎資產和報價資產為交易對符號

        Args:
            base: 基礎資產
            quote: 報價資產

        Returns:
            交易對符號

        Example:
            >>> manager = SymbolManager()
            >>> symbol = manager.format_symbol("BTC", "USDT")
            >>> print(symbol)
            'BTCUSDT'
        """
        return f"{base}{quote}"

    def is_stablecoin_pair(self, symbol: str) -> bool:
        """檢查是否為穩定幣交易對

        Args:
            symbol: 交易對符號

        Returns:
            True 如果報價資產為穩定幣

        Example:
            >>> manager = SymbolManager()
            >>> manager.is_stablecoin_pair("BTCUSDT")
            True
            >>> manager.is_stablecoin_pair("ETHBTC")
            False
        """
        stablecoins = ["USDT", "USD", "USDC", "BUSD", "DAI"]

        _, quote = self.parse_symbol(symbol)
        return quote in stablecoins


# 全局管理器實例
_global_symbol_manager = SymbolManager()


def get_symbol_manager() -> SymbolManager:
    """獲取全局交易對管理器

    Returns:
        全局 SymbolManager 實例

    Example:
        >>> manager = get_symbol_manager()
        >>> info = manager.get_symbol_info("BTCUSDT")
    """
    return _global_symbol_manager


def validate_symbol(symbol: str) -> bool:
    """驗證交易對的便捷函數

    Args:
        symbol: 交易對符號

    Returns:
        True 如果有效，否則 False

    Example:
        >>> validate_symbol("BTCUSDT")
        True
    """
    return get_symbol_manager().validate_symbol(symbol)


def get_top_symbols(n: int = 10) -> List[str]:
    """獲取前 N 個 USDT 交易對

    Args:
        n: 返回數量

    Returns:
        交易對列表

    Example:
        >>> get_top_symbols(5)
        ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
    """
    return get_symbol_manager().get_top_symbols(n, "USDT")
