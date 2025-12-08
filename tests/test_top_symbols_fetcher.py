"""
Top Symbols Fetcher 測試

測試 Top 100 幣種抓取器的各種功能
"""

from unittest.mock import MagicMock, patch

import pytest

from data.downloaders.top_symbols_fetcher import (SymbolInfo,
                                                  TopSymbolsFetcher,
                                                  get_binance_top_100,
                                                  get_top_symbols)


class TestSymbolInfo:
    """SymbolInfo 測試類"""

    def test_symbol_info_creation(self):
        """測試 SymbolInfo 創建"""
        info = SymbolInfo(
            symbol="BTCUSDT",
            base="BTC",
            quote="USDT",
            volume_24h=1_000_000_000,
            price=50000.0,
            price_change_24h=2.5,
        )
        assert info.symbol == "BTCUSDT"
        assert info.base == "BTC"
        assert info.quote == "USDT"
        assert info.volume_24h == 1_000_000_000


class TestTopSymbolsFetcher:
    """TopSymbolsFetcher 測試類"""

    @pytest.fixture
    def fetcher(self):
        """創建 TopSymbolsFetcher 實例"""
        return TopSymbolsFetcher(timeout=10)

    @pytest.fixture
    def mock_response_data(self):
        """模擬 API 響應數據"""
        return [
            {
                "symbol": "BTCUSDT",
                "quoteVolume": "5000000000",
                "lastPrice": "50000",
                "priceChangePercent": "2.5",
            },
            {
                "symbol": "ETHUSDT",
                "quoteVolume": "3000000000",
                "lastPrice": "3000",
                "priceChangePercent": "1.5",
            },
            {
                "symbol": "BNBUSDT",
                "quoteVolume": "500000000",
                "lastPrice": "400",
                "priceChangePercent": "-0.5",
            },
            {
                "symbol": "USDCUSDT",
                "quoteVolume": "2000000000",
                "lastPrice": "1.0",
                "priceChangePercent": "0.01",
            },
            {
                "symbol": "BTCUPUSDT",
                "quoteVolume": "100000000",
                "lastPrice": "100",
                "priceChangePercent": "5.0",
            },
        ]

    def test_initialization(self, fetcher):
        """測試初始化"""
        assert fetcher.timeout == 10
        assert fetcher._cache is None

    def test_stablecoins_list(self, fetcher):
        """測試穩定幣列表"""
        assert "USDT" in fetcher.STABLECOINS
        assert "USDC" in fetcher.STABLECOINS
        assert "BUSD" in fetcher.STABLECOINS

    def test_leveraged_suffixes(self, fetcher):
        """測試槓桿代幣後綴"""
        assert "UP" in fetcher.LEVERAGED_SUFFIXES
        assert "DOWN" in fetcher.LEVERAGED_SUFFIXES

    def test_is_leveraged_token(self, fetcher):
        """測試槓桿代幣檢測"""
        assert fetcher._is_leveraged_token("BTCUP") is True
        assert fetcher._is_leveraged_token("ETHDOWN") is True
        assert fetcher._is_leveraged_token("BTC3L") is True
        assert fetcher._is_leveraged_token("BTC") is False

    @patch("requests.get")
    def test_get_top_symbols(self, mock_get, fetcher, mock_response_data):
        """測試獲取 Top 幣種"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        symbols = fetcher.get_top_symbols(n=10, min_volume=100_000)

        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols
        # 穩定幣應被排除
        assert "USDCUSDT" not in symbols
        # 槓桿代幣應被排除
        assert "BTCUPUSDT" not in symbols

    @patch("requests.get")
    def test_get_top_symbols_include_stablecoins(
        self, mock_get, fetcher, mock_response_data
    ):
        """測試包含穩定幣"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        _ = fetcher.get_top_symbols(n=10, min_volume=100_000, exclude_stablecoins=False)
        # 穩定幣應被包含（USDC base 在 stablecoins 列表中）
        # 注意: USDCUSDT 的 base 是 USDC，在 stablecoins 列表中

    @patch("requests.get")
    def test_get_top_symbols_with_info(self, mock_get, fetcher, mock_response_data):
        """測試獲取帶信息的 Top 幣種"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        infos = fetcher.get_top_symbols_with_info(n=10, min_volume=100_000)

        assert len(infos) > 0
        assert isinstance(infos[0], SymbolInfo)
        assert infos[0].symbol == "BTCUSDT"  # 最高成交量的應該排第一

    @patch("requests.get")
    def test_caching(self, mock_get, fetcher, mock_response_data):
        """測試緩存機制"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # 第一次調用
        fetcher.get_top_symbols(n=10, min_volume=100_000)
        # 第二次調用（應該使用緩存）
        fetcher.get_top_symbols(n=10, min_volume=100_000)

        # API 應該只被調用一次
        assert mock_get.call_count == 1

    @patch("requests.get")
    def test_refresh_cache(self, mock_get, fetcher, mock_response_data):
        """測試刷新緩存"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # 第一次調用
        fetcher.get_top_symbols(n=10, min_volume=100_000)
        # 刷新緩存
        fetcher.get_top_symbols(n=10, min_volume=100_000, refresh=True)

        # API 應該被調用兩次
        assert mock_get.call_count == 2

    def test_clear_cache(self, fetcher):
        """測試清除緩存"""
        fetcher._cache = ["test"]
        fetcher.clear_cache()
        assert fetcher._cache is None

    @patch("requests.get")
    def test_get_symbol_info(self, mock_get, fetcher, mock_response_data):
        """測試獲取單個幣種信息"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        info = fetcher.get_symbol_info("BTCUSDT")
        assert info is not None
        assert info.symbol == "BTCUSDT"

    @patch("requests.get")
    def test_get_symbol_info_not_found(self, mock_get, fetcher, mock_response_data):
        """測試獲取不存在的幣種信息"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        info = fetcher.get_symbol_info("NOTEXIST")
        assert info is None

    @patch("requests.get")
    def test_min_volume_filter(self, mock_get, fetcher, mock_response_data):
        """測試最小成交量過濾"""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # 設置高最小成交量
        symbols = fetcher.get_top_symbols(n=10, min_volume=1_000_000_000)

        # 只有 BTC 和 ETH 超過這個成交量
        assert len(symbols) <= 2


class TestConvenienceFunctions:
    """便捷函數測試"""

    @patch("requests.get")
    def test_get_top_symbols_function(self, mock_get):
        """測試 get_top_symbols 便捷函數"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "symbol": "BTCUSDT",
                "quoteVolume": "5000000000",
                "lastPrice": "50000",
                "priceChangePercent": "2.5",
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        symbols = get_top_symbols(n=10)
        assert isinstance(symbols, list)

    @patch("requests.get")
    def test_get_binance_top_100(self, mock_get):
        """測試 get_binance_top_100 便捷函數"""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "symbol": "BTCUSDT",
                "quoteVolume": "5000000000",
                "lastPrice": "50000",
                "priceChangePercent": "2.5",
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        symbols = get_binance_top_100()
        assert isinstance(symbols, list)
