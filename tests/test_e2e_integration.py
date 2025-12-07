"""
End-to-End Integration Tests for SuperDog v0.4

測試完整的策略執行流程：
1. 策略創建和參數驗證
2. 數據載入（多時間週期、多交易對）
3. 策略執行和信號生成
4. 回測引擎整合
5. 結果生成和驗證

Version: v0.4
"""

import unittest

import numpy as np
import pandas as pd

from cli.dynamic_params import DynamicCLI
from data.pipeline import DataPipeline, get_pipeline
from data.storage import OHLCVStorage
from data.symbol_manager import get_top_symbols, validate_symbol
from data.timeframe_manager import get_timeframe_manager
from strategies.dependency_checker import check_strategy_dependencies
from strategies.kawamoku_demo import KawamokuStrategy
from strategies.registry import get_strategy, list_strategies
from strategies.registry_v2 import get_registry

# v0.4 Components
from strategies.simple_sma_v2 import SimpleSMAStrategyV2


class TestE2EStrategyWorkflow(unittest.TestCase):
    """端到端策略工作流測試"""

    def setUp(self):
        """設置測試環境"""
        self.pipeline = get_pipeline()
        self.registry = get_registry()

    def test_strategy_discovery_and_registration(self):
        """測試策略自動發現和註冊"""
        # 1. 列出所有策略
        strategies = list_strategies()

        # 應該至少包含我們的測試策略
        self.assertIn("simplesma", strategies)
        self.assertIn("kawamoku", strategies)

        print(f"✓ 發現 {len(strategies)} 個策略: {strategies}")

    def test_strategy_metadata_and_info(self):
        """測試策略元數據和信息"""
        # 1. 獲取策略實例
        strategy = SimpleSMAStrategyV2()

        # 2. 檢查元數據（返回字典）
        metadata_dict = strategy.get_metadata()
        self.assertIsNotNone(metadata_dict)
        self.assertEqual(metadata_dict["name"], "SimpleSMA")
        self.assertEqual(metadata_dict["version"], "2.0")

        # 3. 檢查參數
        params = strategy.get_parameters()
        self.assertIn("short_window", params)
        self.assertIn("long_window", params)

        # 4. 檢查數據需求
        requirements = strategy.get_data_requirements()
        self.assertGreater(len(requirements), 0)

        print(f"✓ 策略元數據驗證通過: {metadata_dict['name']} v{metadata_dict['version']}")
        print(f"  參數數量: {len(params)}")
        print(f"  數據需求: {len(requirements)}")

    def test_dependency_checking(self):
        """測試策略相依性檢查"""
        # 1. 創建策略
        strategy = SimpleSMAStrategyV2()

        # 2. 檢查相依性
        result = check_strategy_dependencies(strategy)

        # 3. SimpleSMA 應該只需要 OHLCV，在 v0.4 中是可用的
        self.assertTrue(result.is_satisfied)

        print(f"✓ 相依性檢查通過")
        if result.warnings:
            print(f"  警告: {len(result.warnings)}")

    def test_parameter_validation(self):
        """測試參數驗證"""
        strategy = SimpleSMAStrategyV2()

        # Test that parameter specs have validation
        params = strategy.get_parameters()

        # Validate that each param spec can validate values
        short_spec = params["short_window"]
        long_spec = params["long_window"]

        # Valid values should pass
        try:
            short_spec.validate(10)
            long_spec.validate(20)
            validation_passed = True
        except (ValueError, TypeError):
            validation_passed = False

        self.assertTrue(validation_passed)

        # Invalid values should fail
        with self.assertRaises((ValueError, TypeError)):
            short_spec.validate(-1)  # Negative window

        print(f"✓ 參數驗證測試通過")

    def test_symbol_and_timeframe_validation(self):
        """測試交易對和時間週期驗證"""
        # 1. 驗證交易對
        self.assertTrue(validate_symbol("BTCUSDT"))
        self.assertTrue(validate_symbol("ETHUSDT"))
        self.assertFalse(validate_symbol("INVALID"))

        # 2. 獲取前 N 個交易對
        top5 = get_top_symbols(5)
        self.assertEqual(len(top5), 5)
        self.assertEqual(top5[0], "BTCUSDT")

        # 3. 驗證時間週期
        tf_manager = get_timeframe_manager()
        self.assertTrue(tf_manager.validate_timeframe("1h"))
        self.assertTrue(tf_manager.validate_timeframe("1d"))
        self.assertFalse(tf_manager.validate_timeframe("2h"))

        print(f"✓ 交易對和時間週期驗證通過")
        print(f"  前5大交易對: {top5}")


class TestE2EDataPipeline(unittest.TestCase):
    """端到端數據管道測試"""

    def setUp(self):
        """設置測試環境"""
        self.pipeline = DataPipeline()
        self.storage = OHLCVStorage()

    def test_list_available_data(self):
        """測試列出可用數據"""
        available = self.storage.list_available_data()

        # 可能為空（如果沒有數據文件）
        self.assertIsInstance(available, list)

        if available:
            print(f"✓ 發現 {len(available)} 個可用數據文件")
            for item in available[:3]:  # 顯示前3個
                print(f"  - {item['symbol']} {item['timeframe']}")
        else:
            print("⚠ 未發現任何數據文件（這在測試環境中是正常的）")

    def test_data_pipeline_validation(self):
        """測試數據管道驗證"""
        strategy = SimpleSMAStrategyV2()

        # 測試無效的輸入
        result = self.pipeline.load_strategy_data(strategy, "INVALID", "1h")
        self.assertFalse(result.success)
        self.assertIn("Invalid symbol", result.error)

        result = self.pipeline.load_strategy_data(strategy, "BTCUSDT", "invalid")
        self.assertFalse(result.success)
        self.assertIn("Invalid timeframe", result.error)

        print(f"✓ 數據管道驗證測試通過")


class TestE2EBacktestWorkflow(unittest.TestCase):
    """端到端回測工作流測試"""

    def test_create_mock_data_and_run_strategy(self):
        """測試使用模擬數據運行策略"""
        # 1. 創建模擬 OHLCV 數據
        dates = pd.date_range(start="2023-01-01", periods=100, freq="1h")
        mock_data = pd.DataFrame(
            {
                "open": np.random.randn(100).cumsum() + 50000,
                "high": np.random.randn(100).cumsum() + 50100,
                "low": np.random.randn(100).cumsum() + 49900,
                "close": np.random.randn(100).cumsum() + 50000,
                "volume": np.random.randint(1000, 10000, 100),
            },
            index=dates,
        )

        # 確保 high >= low
        mock_data["high"] = mock_data[["open", "close"]].max(axis=1) + 100
        mock_data["low"] = mock_data[["open", "close"]].min(axis=1) - 100

        # 2. 創建策略並生成信號
        strategy = SimpleSMAStrategyV2()
        params = {"short_window": 10, "long_window": 20}

        # 3. 計算信號
        data_dict = {"ohlcv": mock_data}
        signals = strategy.compute_signals(data_dict, params)

        # 4. 驗證信號
        self.assertIsInstance(signals, pd.Series)
        self.assertEqual(len(signals), len(mock_data))
        self.assertTrue(all(signals.isin([0, 1, -1])))

        # 5. 統計信號
        signal_counts = signals.value_counts()

        print(f"✓ 策略信號生成成功")
        print(f"  數據點: {len(mock_data)}")
        print(f"  信號統計:")
        if 1 in signal_counts:
            print(f"    做多信號: {signal_counts[1]}")
        if -1 in signal_counts:
            print(f"    做空信號: {signal_counts[-1]}")
        if 0 in signal_counts:
            print(f"    持平信號: {signal_counts[0]}")

    def test_kawamoku_strategy_with_mock_data(self):
        """測試 Kawamoku 策略使用模擬數據"""
        # 1. 創建模擬數據
        dates = pd.date_range(start="2023-01-01", periods=200, freq="1h")
        mock_data = pd.DataFrame(
            {
                "open": np.random.randn(200).cumsum() + 50000,
                "high": np.random.randn(200).cumsum() + 50100,
                "low": np.random.randn(200).cumsum() + 49900,
                "close": np.random.randn(200).cumsum() + 50000,
                "volume": np.random.randint(1000, 10000, 200),
            },
            index=dates,
        )

        # 確保 high >= low
        mock_data["high"] = mock_data[["open", "close"]].max(axis=1) + 100
        mock_data["low"] = mock_data[["open", "close"]].min(axis=1) - 100

        # 2. 創建 Kawamoku 策略
        strategy = KawamokuStrategy()

        # 3. 使用默認參數
        params = {param: spec.default_value for param, spec in strategy.get_parameters().items()}

        # 4. 生成信號
        data_dict = {"ohlcv": mock_data}
        signals = strategy.compute_signals(data_dict, params)

        # 5. 驗證
        self.assertIsInstance(signals, pd.Series)
        self.assertEqual(len(signals), len(mock_data))

        print(f"✓ Kawamoku 策略測試通過")
        print(f"  參數數量: {len(params)}")
        print(f"  信號統計: {signals.value_counts().to_dict()}")


class TestE2ECLIIntegration(unittest.TestCase):
    """端到端 CLI 整合測試"""

    def test_dynamic_cli_parameter_generation(self):
        """測試動態 CLI 參數生成"""
        strategy = SimpleSMAStrategyV2()
        cli = DynamicCLI()

        # 1. 生成選項
        options = cli.generate_strategy_options(strategy)

        # 2. 驗證
        self.assertIn("short_window", options)
        self.assertIn("long_window", options)

        print(f"✓ 動態 CLI 參數生成成功")
        print(f"  生成的選項: {list(options.keys())}")

    def test_backtest_config_validation(self):
        """測試回測配置驗證"""
        # Test basic config validation using symbol and timeframe managers
        from data.symbol_manager import validate_symbol
        from data.timeframe_manager import get_timeframe_manager

        # 1. Valid config
        self.assertTrue(validate_symbol("BTCUSDT"))
        self.assertTrue(get_timeframe_manager().validate_timeframe("1h"))

        # 2. Invalid config
        self.assertFalse(validate_symbol("INVALID"))
        self.assertFalse(get_timeframe_manager().validate_timeframe("2h"))

        print(f"✓ 回測配置驗證測試通過")


class TestE2EBackwardCompatibility(unittest.TestCase):
    """端到端向後兼容性測試"""

    def test_v03_strategy_still_works(self):
        """測試 v0.3 策略仍然可用"""
        # 1. 獲取 v0.3 策略
        StrategyClass = get_strategy("simple_sma")

        # 2. 驗證是 v0.3 策略
        from backtest.engine import BaseStrategy as V03BaseStrategy

        self.assertTrue(issubclass(StrategyClass, V03BaseStrategy))

        print(f"✓ v0.3 策略向後兼容性測試通過")

    def test_v2_and_v03_strategies_coexist(self):
        """測試 v2.0 和 v0.3 策略共存"""
        strategies = list_strategies()

        # v2.0 策略應該存在
        self.assertIn("simplesma", strategies)  # v2.0
        self.assertIn("kawamoku", strategies)  # v2.0

        # v0.3 策略可以通過手動註冊表訪問
        from strategies.registry import STRATEGY_REGISTRY

        self.assertIn("simple_sma", STRATEGY_REGISTRY)  # v0.3

        print(f"✓ v2.0 和 v0.3 策略共存測試通過")
        print(f"  v2.0 策略數: {len(strategies)}")
        print(f"  手動註冊策略數: {len(STRATEGY_REGISTRY)}")


def run_all_e2e_tests():
    """運行所有端到端測試"""
    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類
    suite.addTests(loader.loadTestsFromTestCase(TestE2EStrategyWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestE2EDataPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestE2EBacktestWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestE2ECLIIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestE2EBackwardCompatibility))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印總結
    print("\n" + "=" * 70)
    print("端到端整合測試總結")
    print("=" * 70)
    print(f"總測試數: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"錯誤: {len(result.errors)}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys

    success = run_all_e2e_tests()
    sys.exit(0 if success else 1)
