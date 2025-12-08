"""
Symbol Mapper 測試

測試符號映射器的各種功能
"""

import pytest

from data.downloaders.symbol_mapper import (SymbolMapper,
                                            is_valid_trading_pair,
                                            normalize_symbol)


class TestSymbolMapper:
    """SymbolMapper 測試類"""

    @pytest.fixture
    def mapper(self):
        """創建 SymbolMapper 實例"""
        return SymbolMapper()

    # ===== parse 測試 =====

    def test_parse_binance_format(self, mapper):
        """測試解析 Binance 格式"""
        result = mapper.parse("BTCUSDT")
        assert result is not None
        assert result.base == "BTC"
        assert result.quote == "USDT"
        assert result.is_perpetual is False

    def test_parse_ccxt_format(self, mapper):
        """測試解析 CCXT 格式"""
        result = mapper.parse("BTC/USDT")
        assert result is not None
        assert result.base == "BTC"
        assert result.quote == "USDT"

    def test_parse_okx_format(self, mapper):
        """測試解析 OKX 格式"""
        result = mapper.parse("BTC-USDT")
        assert result is not None
        assert result.base == "BTC"
        assert result.quote == "USDT"

    def test_parse_okx_perpetual(self, mapper):
        """測試解析 OKX 永續合約格式"""
        result = mapper.parse("BTC-USDT-SWAP")
        assert result is not None
        assert result.base == "BTC"
        assert result.quote == "USDT"
        assert result.is_perpetual is True

    def test_parse_lowercase(self, mapper):
        """測試解析小寫符號"""
        result = mapper.parse("btcusdt")
        assert result is not None
        assert result.base == "BTC"
        assert result.quote == "USDT"

    def test_parse_with_spaces(self, mapper):
        """測試解析帶空格的符號"""
        result = mapper.parse("  BTCUSDT  ")
        assert result is not None
        assert result.base == "BTC"

    def test_parse_empty_string(self, mapper):
        """測試解析空字符串"""
        result = mapper.parse("")
        assert result is None

    def test_parse_invalid_symbol(self, mapper):
        """測試解析無效符號"""
        result = mapper.parse("INVALID")
        assert result is None

    # ===== 轉換測試 =====

    def test_to_binance_from_ccxt(self, mapper):
        """測試 CCXT 轉 Binance"""
        result = mapper.to_binance("BTC/USDT")
        assert result == "BTCUSDT"

    def test_to_binance_from_okx(self, mapper):
        """測試 OKX 轉 Binance"""
        result = mapper.to_binance("BTC-USDT")
        assert result == "BTCUSDT"

    def test_to_ccxt_from_binance(self, mapper):
        """測試 Binance 轉 CCXT"""
        result = mapper.to_ccxt("BTCUSDT")
        assert result == "BTC/USDT"

    def test_to_okx_from_binance(self, mapper):
        """測試 Binance 轉 OKX"""
        result = mapper.to_okx("BTCUSDT")
        assert result == "BTC-USDT"

    def test_to_okx_perpetual(self, mapper):
        """測試轉換為 OKX 永續合約格式"""
        result = mapper.to_okx("BTCUSDT", perpetual=True)
        assert result == "BTC-USDT-SWAP"

    # ===== 檢查方法測試 =====

    def test_is_stablecoin_true(self, mapper):
        """測試穩定幣檢測 - 是"""
        assert mapper.is_stablecoin("USDCUSDT") is True
        assert mapper.is_stablecoin("BUSDUSDT") is True

    def test_is_stablecoin_false(self, mapper):
        """測試穩定幣檢測 - 否"""
        assert mapper.is_stablecoin("BTCUSDT") is False
        assert mapper.is_stablecoin("ETHUSDT") is False

    def test_is_leveraged_token_true(self, mapper):
        """測試槓桿代幣檢測 - 是"""
        assert mapper.is_leveraged_token("BTCUPUSDT") is True
        assert mapper.is_leveraged_token("ETHDOWNUSDT") is True
        assert mapper.is_leveraged_token("BTC3LUSDT") is True

    def test_is_leveraged_token_false(self, mapper):
        """測試槓桿代幣檢測 - 否"""
        assert mapper.is_leveraged_token("BTCUSDT") is False
        assert mapper.is_leveraged_token("ETHUSDT") is False

    def test_validate_valid_symbol(self, mapper):
        """測試驗證有效符號"""
        assert mapper.validate("BTCUSDT") is True
        assert mapper.validate("BTC/USDT") is True
        assert mapper.validate("BTC-USDT") is True

    def test_validate_invalid_symbol(self, mapper):
        """測試驗證無效符號"""
        assert mapper.validate("INVALID") is False
        assert mapper.validate("") is False

    def test_get_base(self, mapper):
        """測試獲取基礎貨幣"""
        assert mapper.get_base("BTCUSDT") == "BTC"
        assert mapper.get_base("ETHUSDT") == "ETH"

    def test_get_quote(self, mapper):
        """測試獲取報價貨幣"""
        assert mapper.get_quote("BTCUSDT") == "USDT"
        assert mapper.get_quote("BTCBUSD") == "BUSD"


class TestConvenienceFunctions:
    """便捷函數測試"""

    def test_normalize_symbol_binance(self):
        """測試標準化為 Binance 格式"""
        result = normalize_symbol("BTC/USDT", "binance")
        assert result == "BTCUSDT"

    def test_normalize_symbol_ccxt(self):
        """測試標準化為 CCXT 格式"""
        result = normalize_symbol("BTCUSDT", "ccxt")
        assert result == "BTC/USDT"

    def test_normalize_symbol_okx(self):
        """測試標準化為 OKX 格式"""
        result = normalize_symbol("BTCUSDT", "okx")
        assert result == "BTC-USDT"

    def test_normalize_symbol_invalid_format(self):
        """測試無效格式"""
        with pytest.raises(ValueError):
            normalize_symbol("BTCUSDT", "invalid")

    def test_is_valid_trading_pair_true(self):
        """測試有效交易對"""
        assert is_valid_trading_pair("BTCUSDT") is True
        assert is_valid_trading_pair("BTC/USDT") is True

    def test_is_valid_trading_pair_false(self):
        """測試無效交易對"""
        assert is_valid_trading_pair("INVALID") is False
