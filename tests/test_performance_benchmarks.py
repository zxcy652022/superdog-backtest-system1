"""
Performance Benchmark Tests for SuperDog v0.4

測試系統性能指標：
1. 數據載入速度
2. 策略計算性能
3. 記憶體使用
4. 回測速度
5. 多交易對處理能力

Version: v0.4
"""

import time
import tracemalloc
import unittest

import numpy as np
import pandas as pd

from data.pipeline import DataPipeline
from data.timeframe_manager import TimeframeManager
from data.universe.symbols import get_top_symbols
from strategies.kawamoku_demo import KawamokuStrategy

# v0.4 Components
from strategies.simple_sma_v2 import SimpleSMAStrategyV2


class PerformanceBenchmark(unittest.TestCase):
    """性能基準測試"""

    @classmethod
    def setUpClass(cls):
        """設置測試數據"""
        # 創建大型測試數據集
        cls.small_data = cls._create_ohlcv_data(1000)  # 1K bars
        cls.medium_data = cls._create_ohlcv_data(10000)  # 10K bars
        cls.large_data = cls._create_ohlcv_data(100000)  # 100K bars

    @staticmethod
    def _create_ohlcv_data(size: int) -> pd.DataFrame:
        """創建測試 OHLCV 數據"""
        dates = pd.date_range(start="2020-01-01", periods=size, freq="1h")
        data = pd.DataFrame(
            {
                "open": np.random.randn(size).cumsum() + 50000,
                "high": np.random.randn(size).cumsum() + 50100,
                "low": np.random.randn(size).cumsum() + 49900,
                "close": np.random.randn(size).cumsum() + 50000,
                "volume": np.random.randint(1000, 10000, size),
            },
            index=dates,
        )

        # 確保 high >= low
        data["high"] = data[["open", "close"]].max(axis=1) + 100
        data["low"] = data[["open", "close"]].min(axis=1) - 100

        return data

    def test_data_loading_performance(self):
        """測試數據載入性能"""
        pipeline = DataPipeline()

        # 測試快取性能
        start_time = time.time()
        for _ in range(100):
            pipeline.clear_cache()  # 清除快取
        clear_time = time.time() - start_time

        print(f"\n數據載入性能:")
        print(f"  快取清除 (100次): {clear_time*1000:.2f}ms")

        self.assertLess(clear_time, 1.0, "快取清除應該在1秒內完成")

    def test_strategy_computation_performance(self):
        """測試策略計算性能"""
        strategy = SimpleSMAStrategyV2()
        params = {"short_window": 10, "long_window": 20}

        # 測試不同數據量的計算時間
        results = {}

        for name, data in [
            ("Small (1K)", self.small_data),
            ("Medium (10K)", self.medium_data),
            ("Large (100K)", self.large_data),
        ]:
            data_dict = {"ohlcv": data}

            start_time = time.time()
            signals = strategy.compute_signals(data_dict, params)
            elapsed = time.time() - start_time

            results[name] = elapsed

            # 驗證結果
            self.assertEqual(len(signals), len(data))

        print(f"\nSimpleSMA 策略計算性能:")
        for name, elapsed in results.items():
            bars_per_sec = (
                len(
                    self.small_data
                    if "Small" in name
                    else self.medium_data
                    if "Medium" in name
                    else self.large_data
                )
                / elapsed
            )
            print(f"  {name}: {elapsed*1000:.2f}ms ({bars_per_sec:.0f} bars/sec)")

        # 性能要求：至少 1000 bars/sec
        self.assertGreater(
            len(self.small_data) / results["Small (1K)"], 1000, "SimpleSMA 應該至少達到 1000 bars/sec"
        )

    def test_kawamoku_performance(self):
        """測試 Kawamoku 策略性能"""
        strategy = KawamokuStrategy()
        params = {param: spec.default_value for param, spec in strategy.get_parameters().items()}

        data_dict = {"ohlcv": self.medium_data}

        start_time = time.time()
        signals = strategy.compute_signals(data_dict, params)
        elapsed = time.time() - start_time

        bars_per_sec = len(self.medium_data) / elapsed

        print(f"\nKawamoku 策略計算性能:")
        print(f"  10K bars: {elapsed*1000:.2f}ms ({bars_per_sec:.0f} bars/sec)")

        self.assertEqual(len(signals), len(self.medium_data))
        # Kawamoku 更複雜，至少 500 bars/sec
        self.assertGreater(bars_per_sec, 500, "Kawamoku 應該至少達到 500 bars/sec")

    def test_memory_usage(self):
        """測試記憶體使用"""
        tracemalloc.start()

        strategy = SimpleSMAStrategyV2()
        params = {"short_window": 10, "long_window": 20}
        data_dict = {"ohlcv": self.large_data}

        # 計算前的記憶體
        tracemalloc.reset_peak()

        # 執行計算
        signals = strategy.compute_signals(data_dict, params)

        # 獲取峰值記憶體
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024

        print(f"\n記憶體使用測試:")
        print(f"  峰值記憶體: {peak_mb:.2f} MB")
        print(f"  當前記憶體: {current/1024/1024:.2f} MB")
        print(f"  數據量: 100K bars")

        # 記憶體使用應該合理（100K bars 應該在 100MB 以內）
        self.assertLess(peak_mb, 100, "100K bars 的記憶體使用應該在 100MB 以內")

    def test_multiple_symbol_processing(self):
        """測試多交易對處理性能"""
        strategy = SimpleSMAStrategyV2()
        params = {"short_window": 10, "long_window": 20}

        # 模擬 10 個交易對
        symbols = get_top_symbols(10)
        data_dict = {"ohlcv": self.medium_data}

        start_time = time.time()

        results = {}
        for symbol in symbols:
            signals = strategy.compute_signals(data_dict, params)
            results[symbol] = signals

        elapsed = time.time() - start_time

        total_bars = len(self.medium_data) * len(symbols)
        bars_per_sec = total_bars / elapsed

        print(f"\n多交易對處理性能:")
        print(f"  交易對數量: {len(symbols)}")
        print(f"  總 bars: {total_bars:,}")
        print(f"  總時間: {elapsed*1000:.2f}ms")
        print(f"  處理速度: {bars_per_sec:.0f} bars/sec")

        self.assertEqual(len(results), len(symbols))

    def test_timeframe_resampling_performance(self):
        """測試時間週期重採樣性能"""
        manager = TimeframeManager()

        # 測試重採樣性能
        start_time = time.time()
        resampled = manager.resample_ohlcv(self.large_data, "1h", "4h")
        elapsed = time.time() - start_time

        print(f"\n時間週期重採樣性能:")
        print(f"  輸入: 100K bars (1h)")
        print(f"  輸出: {len(resampled)} bars (4h)")
        print(f"  時間: {elapsed*1000:.2f}ms")

        # 重採樣應該很快（100K bars 在 1 秒內）
        self.assertLess(elapsed, 1.0, "重採樣應該在 1 秒內完成")

    def test_data_validation_performance(self):
        """測試數據驗證性能"""
        # 測試數據清理性能（dropna, etc）
        bad_data = self.medium_data.copy()
        bad_data.loc[bad_data.index[100:200], "close"] = np.nan

        start_time = time.time()
        # 模擬數據驗證過程
        validated = bad_data.dropna()
        # 驗證價格邏輯
        invalid_mask = validated["high"] < validated["low"]
        validated = validated[~invalid_mask]
        elapsed = time.time() - start_time

        print(f"\n數據驗證性能:")
        print(f"  輸入: {len(bad_data)} bars")
        print(f"  輸出: {len(validated)} bars")
        print(f"  移除: {len(bad_data) - len(validated)} bars")
        print(f"  時間: {elapsed*1000:.2f}ms")

        # 驗證應該很快
        self.assertLess(elapsed, 0.5, "數據驗證應該在 0.5 秒內完成")


class PerformanceRegressionTest(unittest.TestCase):
    """性能回歸測試"""

    def test_no_performance_regression(self):
        """測試確保沒有性能回歸"""
        # 基準性能（v0.3）
        baseline_bars_per_sec = 1000

        # 測試當前性能
        strategy = SimpleSMAStrategyV2()
        params = {"short_window": 10, "long_window": 20}

        dates = pd.date_range(start="2023-01-01", periods=10000, freq="1h")
        data = pd.DataFrame(
            {
                "open": np.random.randn(10000).cumsum() + 50000,
                "high": np.random.randn(10000).cumsum() + 50100,
                "low": np.random.randn(10000).cumsum() + 49900,
                "close": np.random.randn(10000).cumsum() + 50000,
                "volume": np.random.randint(1000, 10000, 10000),
            },
            index=dates,
        )

        data["high"] = data[["open", "close"]].max(axis=1) + 100
        data["low"] = data[["open", "close"]].min(axis=1) - 100

        data_dict = {"ohlcv": data}

        start_time = time.time()
        signals = strategy.compute_signals(data_dict, params)
        elapsed = time.time() - start_time

        current_bars_per_sec = len(data) / elapsed

        print(f"\n性能回歸測試:")
        print(f"  基準性能: {baseline_bars_per_sec} bars/sec")
        print(f"  當前性能: {current_bars_per_sec:.0f} bars/sec")

        improvement = (current_bars_per_sec - baseline_bars_per_sec) / baseline_bars_per_sec * 100

        if improvement > 0:
            print(f"  ✓ 性能提升: +{improvement:.1f}%")
        else:
            print(f"  ⚠ 性能下降: {improvement:.1f}%")

        # v0.4 不應該比 v0.3 慢
        self.assertGreaterEqual(
            current_bars_per_sec, baseline_bars_per_sec * 0.8, "v0.4 性能不應該顯著低於 v0.3"  # 允許 20% 的容差
        )


def run_benchmarks():
    """運行性能基準測試"""
    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類
    suite.addTests(loader.loadTestsFromTestCase(PerformanceBenchmark))
    suite.addTests(loader.loadTestsFromTestCase(PerformanceRegressionTest))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印總結
    print("\n" + "=" * 70)
    print("性能基準測試總結")
    print("=" * 70)
    print(f"總測試數: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"錯誤: {len(result.errors)}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys

    success = run_benchmarks()
    sys.exit(0 if success else 1)
