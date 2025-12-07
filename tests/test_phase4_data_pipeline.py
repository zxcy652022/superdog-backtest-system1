"""
Phase 4 Data Pipeline Tests

測試 v0.4 數據系統重構的所有組件：
- TimeframeManager
- SymbolManager
- DataPipeline
- OHLCVStorage (v0.4 新增功能)

Version: v0.4
"""

import unittest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# 測試目標模組
from data.timeframe_manager import (
    Timeframe, TimeframeManager, get_timeframe_manager
)
from data.symbol_manager import (
    SymbolManager, SymbolInfo, QuoteAsset, get_symbol_manager,
    validate_symbol, get_top_symbols
)
from data.pipeline import (
    DataPipeline, DataLoadResult, get_pipeline, load_strategy_data
)
from data.storage import OHLCVStorage

# 測試策略
from strategies.simple_sma_v2 import SimpleSMAStrategyV2


class TestTimeframeManager(unittest.TestCase):
    """測試 TimeframeManager"""

    def setUp(self):
        self.manager = TimeframeManager()

    def test_singleton(self):
        """測試單例模式"""
        manager1 = get_timeframe_manager()
        manager2 = get_timeframe_manager()
        self.assertIs(manager1, manager2)

    def test_validate_timeframe(self):
        """測試時間週期驗證"""
        # 有效的時間週期
        self.assertTrue(self.manager.validate_timeframe("1m"))
        self.assertTrue(self.manager.validate_timeframe("1h"))
        self.assertTrue(self.manager.validate_timeframe("1d"))
        self.assertTrue(self.manager.validate_timeframe("1w"))

        # 無效的時間週期
        self.assertFalse(self.manager.validate_timeframe("2m"))
        self.assertFalse(self.manager.validate_timeframe("3h"))
        self.assertFalse(self.manager.validate_timeframe("invalid"))

    def test_format_timeframe(self):
        """測試時間週期格式化"""
        # Test that formatting works correctly
        self.assertEqual(self.manager.format_timeframe(Timeframe.M1), Timeframe.M1)
        self.assertEqual(self.manager.format_timeframe(Timeframe.H1), Timeframe.H1)
        self.assertEqual(self.manager.format_timeframe(Timeframe.D1), Timeframe.D1)

        # Test getting the string value
        self.assertEqual(Timeframe.M1.value, "1m")
        self.assertEqual(Timeframe.H1.value, "1h")
        self.assertEqual(Timeframe.D1.value, "1d")

    def test_to_minutes(self):
        """測試轉換為分鐘"""
        self.assertEqual(self.manager.get_minutes("1m"), 1)
        self.assertEqual(self.manager.get_minutes("5m"), 5)
        self.assertEqual(self.manager.get_minutes("1h"), 60)
        self.assertEqual(self.manager.get_minutes("4h"), 240)
        self.assertEqual(self.manager.get_minutes("1d"), 1440)
        self.assertEqual(self.manager.get_minutes("1w"), 10080)

    def test_to_timedelta(self):
        """測試轉換為 timedelta"""
        self.assertEqual(
            self.manager.get_timedelta("1m"),
            timedelta(minutes=1)
        )
        self.assertEqual(
            self.manager.get_timedelta("1h"),
            timedelta(hours=1)
        )
        self.assertEqual(
            self.manager.get_timedelta("1d"),
            timedelta(days=1)
        )

    def test_compare_timeframes(self):
        """測試時間週期比較"""
        # Compare using get_minutes
        self.assertLess(self.manager.get_minutes("1m"), self.manager.get_minutes("1h"))
        self.assertEqual(self.manager.get_minutes("1h"), self.manager.get_minutes("1h"))
        self.assertGreater(self.manager.get_minutes("1d"), self.manager.get_minutes("1h"))

    def test_resample_ohlcv(self):
        """測試 OHLCV 重採樣"""
        # 創建測試數據（1分鐘數據）
        dates = pd.date_range(start='2023-01-01', periods=60, freq='1min')
        df = pd.DataFrame({
            'open': np.random.randn(60).cumsum() + 100,
            'high': np.random.randn(60).cumsum() + 102,
            'low': np.random.randn(60).cumsum() + 98,
            'close': np.random.randn(60).cumsum() + 100,
            'volume': np.random.randint(1000, 10000, 60)
        }, index=dates)

        # 重採樣為 5 分鐘
        resampled = self.manager.resample_ohlcv(df, "1m", "5m")

        # 驗證結果
        self.assertEqual(len(resampled), 12)  # 60 / 5 = 12
        self.assertIn('open', resampled.columns)
        self.assertIn('high', resampled.columns)
        self.assertIn('low', resampled.columns)
        self.assertIn('close', resampled.columns)
        self.assertIn('volume', resampled.columns)

    def test_get_compatible_timeframes(self):
        """測試獲取兼容的時間週期"""
        compatible = self.manager.get_compatible_timeframes("1m")

        # 1m 應該可以重採樣為 5m, 15m, 30m, 1h, 4h, 1d, 1w
        self.assertIn("5m", compatible)
        self.assertIn("15m", compatible)
        self.assertIn("1h", compatible)
        self.assertIn("1d", compatible)


class TestSymbolManager(unittest.TestCase):
    """測試 SymbolManager"""

    def setUp(self):
        self.manager = SymbolManager()

    def test_singleton(self):
        """測試單例模式"""
        manager1 = get_symbol_manager()
        manager2 = get_symbol_manager()
        self.assertIs(manager1, manager2)

    def test_validate_symbol(self):
        """測試交易對驗證"""
        # 預定義的交易對
        self.assertTrue(self.manager.validate_symbol("BTCUSDT"))
        self.assertTrue(self.manager.validate_symbol("ETHUSDT"))
        self.assertTrue(self.manager.validate_symbol("BNBUSDT"))

        # 有效格式的交易對
        self.assertTrue(self.manager.validate_symbol("NEWUSDT"))

        # 無效的交易對
        self.assertFalse(self.manager.validate_symbol("INVALID"))
        self.assertFalse(self.manager.validate_symbol("ABC"))

    def test_convenience_function(self):
        """測試便捷函數"""
        self.assertTrue(validate_symbol("BTCUSDT"))
        self.assertFalse(validate_symbol("INVALID"))

    def test_get_symbol_info(self):
        """測試獲取交易對信息"""
        info = self.manager.get_symbol_info("BTCUSDT")

        self.assertIsNotNone(info)
        self.assertEqual(info.symbol, "BTCUSDT")
        self.assertEqual(info.base_asset, "BTC")
        self.assertEqual(info.quote_asset, "USDT")
        self.assertEqual(info.market_cap_rank, 1)

    def test_parse_symbol(self):
        """測試交易對解析"""
        base, quote = self.manager.parse_symbol("BTCUSDT")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "USDT")

        base, quote = self.manager.parse_symbol("ETHBTC")
        self.assertEqual(base, "ETH")
        self.assertEqual(quote, "BTC")

    def test_format_symbol(self):
        """測試格式化交易對"""
        symbol = self.manager.format_symbol("BTC", "USDT")
        self.assertEqual(symbol, "BTCUSDT")

    def test_list_symbols(self):
        """測試列出交易對"""
        all_symbols = self.manager.list_symbols()
        self.assertGreater(len(all_symbols), 0)
        self.assertIn("BTCUSDT", all_symbols)

        # 過濾 USDT 交易對
        usdt_symbols = self.manager.list_symbols(quote_asset="USDT")
        self.assertTrue(all(s.endswith("USDT") for s in usdt_symbols))

    def test_get_top_symbols(self):
        """測試獲取前 N 個交易對"""
        top5 = self.manager.get_top_symbols(5, "USDT")

        self.assertEqual(len(top5), 5)
        self.assertEqual(top5[0], "BTCUSDT")  # BTC 應該排第一
        self.assertEqual(top5[1], "ETHUSDT")  # ETH 應該排第二

        # 測試便捷函數
        top10 = get_top_symbols(10)
        self.assertEqual(len(top10), 10)

    def test_is_stablecoin_pair(self):
        """測試穩定幣交易對檢查"""
        self.assertTrue(self.manager.is_stablecoin_pair("BTCUSDT"))
        self.assertTrue(self.manager.is_stablecoin_pair("ETHUSD"))
        self.assertFalse(self.manager.is_stablecoin_pair("ETHBTC"))

    def test_format_price_and_quantity(self):
        """測試價格和數量格式化"""
        info = self.manager.get_symbol_info("BTCUSDT")

        formatted_price = info.format_price(45123.456)
        self.assertEqual(formatted_price, "45123.46")

        formatted_qty = info.format_quantity(0.12345678)
        self.assertEqual(formatted_qty, "0.123457")

    def test_register_custom_symbol(self):
        """測試註冊自定義交易對"""
        custom_info = SymbolInfo(
            symbol="CUSTOMUSDT",
            base_asset="CUSTOM",
            quote_asset="USDT",
            price_precision=4,
            quantity_precision=2
        )

        self.manager.register_symbol(custom_info)

        # 驗證已註冊
        self.assertTrue(self.manager.validate_symbol("CUSTOMUSDT"))

        # 獲取信息
        info = self.manager.get_symbol_info("CUSTOMUSDT")
        self.assertEqual(info.base_asset, "CUSTOM")
        self.assertEqual(info.price_precision, 4)


class TestDataPipeline(unittest.TestCase):
    """測試 DataPipeline"""

    def setUp(self):
        self.pipeline = DataPipeline()
        self.strategy = SimpleSMAStrategyV2()

    def test_singleton(self):
        """測試單例模式"""
        pipeline1 = get_pipeline()
        pipeline2 = get_pipeline()
        self.assertIs(pipeline1, pipeline2)

    def test_validate_inputs(self):
        """測試輸入驗證"""
        # 無效的交易對
        result = self.pipeline.load_strategy_data(
            self.strategy, "INVALID", "1h"
        )
        self.assertFalse(result.success)
        self.assertIn("Invalid symbol", result.error)

        # 無效的時間週期
        result = self.pipeline.load_strategy_data(
            self.strategy, "BTCUSDT", "invalid"
        )
        self.assertFalse(result.success)
        self.assertIn("Invalid timeframe", result.error)

    def test_cache_functionality(self):
        """測試快取功能"""
        # 清除快取
        self.pipeline.clear_cache()

        # 獲取快取統計
        stats = self.pipeline.get_cache_stats()
        self.assertEqual(stats['count'], 0)

    def test_convenience_function(self):
        """測試便捷函數"""
        # 這個函數應該使用全局管道
        # 注意：可能會因為數據文件不存在而失敗，這是預期的
        result = load_strategy_data(self.strategy, "BTCUSDT", "1h")
        self.assertIsInstance(result, DataLoadResult)


class TestOHLCVStorage(unittest.TestCase):
    """測試 OHLCVStorage v0.4 新增功能"""

    def setUp(self):
        self.storage = OHLCVStorage()

    def test_initialization(self):
        """測試初始化"""
        self.assertIsNotNone(self.storage.timeframe_manager)
        self.assertIsNotNone(self.storage.symbol_manager)
        self.assertIsNotNone(self.storage.data_dir)

    def test_list_available_data(self):
        """測試列出可用數據"""
        available = self.storage.list_available_data()

        # available 可能為空（如果沒有數據文件）
        self.assertIsInstance(available, list)

        # 如果有數據，驗證格式
        for item in available:
            self.assertIn('symbol', item)
            self.assertIn('timeframe', item)
            self.assertIn('file_path', item)


class TestDataLoadResult(unittest.TestCase):
    """測試 DataLoadResult"""

    def test_initialization(self):
        """測試初始化"""
        result = DataLoadResult(success=True)
        self.assertTrue(result.success)
        self.assertIsNone(result.data)
        self.assertIsNone(result.error)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.metadata, {})

    def test_with_data(self):
        """測試帶數據的結果"""
        df = pd.DataFrame({'close': [100, 101, 102]})
        result = DataLoadResult(
            success=True,
            data={'ohlcv': df},
            metadata={'rows': 3}
        )

        self.assertTrue(result.success)
        self.assertIn('ohlcv', result.data)
        self.assertEqual(result.metadata['rows'], 3)

    def test_with_error(self):
        """測試帶錯誤的結果"""
        result = DataLoadResult(
            success=False,
            error="File not found"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "File not found")


class TestIntegration(unittest.TestCase):
    """整合測試"""

    def test_timeframe_symbol_integration(self):
        """測試 TimeframeManager 和 SymbolManager 整合"""
        tf_manager = get_timeframe_manager()
        sym_manager = get_symbol_manager()

        # 驗證它們可以一起工作
        valid_tf = tf_manager.validate_timeframe("1h")
        valid_sym = sym_manager.validate_symbol("BTCUSDT")

        self.assertTrue(valid_tf)
        self.assertTrue(valid_sym)

    def test_pipeline_uses_managers(self):
        """測試 DataPipeline 使用管理器"""
        pipeline = get_pipeline()

        # Pipeline 應該有 TimeframeManager 和 SymbolManager
        self.assertIsInstance(
            pipeline.timeframe_manager,
            TimeframeManager
        )
        self.assertIsInstance(
            pipeline.symbol_manager,
            SymbolManager
        )

    def test_storage_uses_managers(self):
        """測試 OHLCVStorage 使用管理器"""
        storage = OHLCVStorage()

        # Storage 應該有 TimeframeManager 和 SymbolManager
        self.assertIsInstance(
            storage.timeframe_manager,
            TimeframeManager
        )
        self.assertIsInstance(
            storage.symbol_manager,
            SymbolManager
        )


def run_tests():
    """運行所有測試"""
    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類
    suite.addTests(loader.loadTestsFromTestCase(TestTimeframeManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSymbolManager))
    suite.addTests(loader.loadTestsFromTestCase(TestDataPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestOHLCVStorage))
    suite.addTests(loader.loadTestsFromTestCase(TestDataLoadResult))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回測試結果
    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
