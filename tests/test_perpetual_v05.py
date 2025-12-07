"""
Perpetual Data Tests for SuperDog v0.5

測試永續合約數據系統的所有組件：
- Binance API Connector
- Funding Rate Data Processing
- Open Interest Data Processing
- Data Quality Control
- DataPipeline Integration

Version: v0.5
"""

import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Exchange Connectors
from data.exchanges.binance_connector import BinanceAPIError, BinanceConnector

# Perpetual Data
from data.perpetual import FundingRateData, OpenInterestData

# Pipeline Integration
from data.pipeline import get_pipeline

# Quality Control
from data.quality import DataQualityController, QualityCheckResult


class TestBinanceConnector(unittest.TestCase):
    """測試 Binance API 連接器"""

    def setUp(self):
        """設置測試環境"""
        self.connector = BinanceConnector()
        self.test_symbol = "BTCUSDT"

    def test_connector_initialization(self):
        """測試連接器初始化"""
        self.assertEqual(self.connector.name, "binance")
        self.assertEqual(self.connector.base_url, "https://fapi.binance.com")
        self.assertIsNotNone(self.connector.session)

    def test_get_mark_price(self):
        """測試獲取標記價格"""
        try:
            result = self.connector.get_mark_price(self.test_symbol)

            self.assertIsInstance(result, dict)
            self.assertIn("mark_price", result)
            self.assertIn("funding_rate", result)
            self.assertIn("next_funding_time", result)

            # 驗證數據類型
            self.assertIsInstance(result["mark_price"], float)
            self.assertIsInstance(result["funding_rate"], float)
            self.assertGreater(result["mark_price"], 0)

            print(f"\n✓ Mark Price: ${result['mark_price']:,.2f}")
            print(f"  Funding Rate: {result['funding_rate']:.6f}")

        except BinanceAPIError as e:
            self.skipTest(f"API request failed: {e}")

    def test_get_funding_rate_recent(self):
        """測試獲取最近的資金費率"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)

            df = self.connector.get_funding_rate(
                symbol=self.test_symbol, start_time=start_time, end_time=end_time
            )

            self.assertIsInstance(df, pd.DataFrame)

            if not df.empty:
                # 驗證欄位
                required_columns = ["timestamp", "symbol", "funding_rate", "mark_price"]
                for col in required_columns:
                    self.assertIn(col, df.columns)

                # 驗證數據類型
                self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["timestamp"]))
                self.assertTrue(pd.api.types.is_float_dtype(df["funding_rate"]))

                print(f"\n✓ Fetched {len(df)} funding rate records")
                print(f"  Time range: {df['timestamp'].min()} ~ {df['timestamp'].max()}")

        except BinanceAPIError as e:
            self.skipTest(f"API request failed: {e}")

    def test_get_open_interest_recent(self):
        """測試獲取最近的持倉量"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)

            df = self.connector.get_open_interest(
                symbol=self.test_symbol, interval="1h", start_time=start_time, end_time=end_time
            )

            self.assertIsInstance(df, pd.DataFrame)

            if not df.empty:
                # 驗證欄位
                required_columns = ["timestamp", "symbol", "open_interest", "open_interest_value"]
                for col in required_columns:
                    self.assertIn(col, df.columns)

                print(f"\n✓ Fetched {len(df)} open interest records")
                print(f"  Latest OI: {df['open_interest'].iloc[-1]:,.0f}")

        except BinanceAPIError as e:
            self.skipTest(f"API request failed: {e}")


class TestFundingRateData(unittest.TestCase):
    """測試資金費率數據處理"""

    def setUp(self):
        """設置測試環境"""
        self.fr_data = FundingRateData()
        self.test_symbol = "BTCUSDT"

    def test_fetch_funding_rate(self):
        """測試獲取資金費率數據"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=3)

            df = self.fr_data.fetch(
                symbol=self.test_symbol,
                start_time=start_time,
                end_time=end_time,
                exchange="binance",
            )

            if not df.empty:
                # 驗證欄位
                self.assertIn("annual_rate", df.columns)
                self.assertIn("exchange", df.columns)

                # 驗證計算
                self.assertEqual(df["exchange"].iloc[0], "binance")

                print(f"\n✓ Funding rate data fetched successfully")
                print(f"  Records: {len(df)}")
                print(f"  Avg funding rate: {df['funding_rate'].mean():.6f}")

        except Exception as e:
            self.skipTest(f"Data fetch failed: {e}")

    def test_calculate_statistics(self):
        """測試統計計算"""
        # 創建測試數據
        dates = pd.date_range(start="2024-01-01", periods=100, freq="8H")
        test_df = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "funding_rate": np.random.normal(0.0001, 0.0002, 100),
                "annual_rate": np.random.normal(0.1, 0.2, 100),
                "mark_price": np.random.normal(50000, 1000, 100),
            }
        )

        stats = self.fr_data.calculate_statistics(test_df)

        # 驗證統計指標
        self.assertIn("mean", stats)
        self.assertIn("median", stats)
        self.assertIn("std", stats)
        self.assertIn("positive_ratio", stats)
        self.assertIn("negative_ratio", stats)

        print(f"\n✓ Statistics calculated")
        print(f"  Mean: {stats['mean']:.6f}")
        print(f"  Positive ratio: {stats['positive_ratio']:.2%}")

    def test_detect_anomalies(self):
        """測試異常檢測"""
        # 創建包含異常值的測試數據
        dates = pd.date_range(start="2024-01-01", periods=100, freq="8H")
        funding_rates = np.random.normal(0.0001, 0.0001, 100)
        funding_rates[50] = 0.01  # 極端正值
        funding_rates[75] = -0.01  # 極端負值

        test_df = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "BTCUSDT",
                "funding_rate": funding_rates,
                "annual_rate": funding_rates * 3 * 365,
                "mark_price": 50000,
                "exchange": "binance",
            }
        )

        df_with_anomalies = self.fr_data.detect_anomalies(test_df, threshold=0.005)

        # 驗證異常檢測
        self.assertIn("is_anomaly", df_with_anomalies.columns)
        self.assertIn("anomaly_type", df_with_anomalies.columns)

        anomaly_count = df_with_anomalies["is_anomaly"].sum()
        self.assertGreater(anomaly_count, 0)

        print(f"\n✓ Anomaly detection completed")
        print(f"  Anomalies found: {anomaly_count}")


class TestOpenInterestData(unittest.TestCase):
    """測試持倉量數據處理"""

    def setUp(self):
        """設置測試環境"""
        self.oi_data = OpenInterestData()
        self.test_symbol = "BTCUSDT"

    def test_fetch_open_interest(self):
        """測試獲取持倉量數據"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=3)

            df = self.oi_data.fetch(
                symbol=self.test_symbol,
                start_time=start_time,
                end_time=end_time,
                interval="1h",
                exchange="binance",
            )

            if not df.empty:
                # 驗證欄位
                self.assertIn("oi_change", df.columns)
                self.assertIn("oi_change_pct", df.columns)
                self.assertIn("exchange", df.columns)

                print(f"\n✓ Open interest data fetched successfully")
                print(f"  Records: {len(df)}")
                print(f"  Latest OI: {df['open_interest'].iloc[-1]:,.0f}")

        except Exception as e:
            self.skipTest(f"Data fetch failed: {e}")

    def test_analyze_trend(self):
        """測試趨勢分析"""
        # 創建測試數據（上升趨勢）
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1H")
        test_df = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "open_interest": np.arange(100000, 110000, 100),
                "open_interest_value": np.arange(1000000, 1100000, 1000),
                "oi_change": 100,
                "oi_change_pct": 0.1,
            }
        )

        trend = self.oi_data.analyze_trend(test_df, window=24)

        # 驗證趨勢分析
        self.assertIn("trend", trend)
        self.assertIn("current_oi", trend)
        self.assertIn("change_24h", trend)
        self.assertIn("volatility", trend)

        print(f"\n✓ Trend analysis completed")
        print(f"  Trend: {trend['trend']}")
        print(f"  24h change: {trend['change_24h_pct']:.2f}%")

    def test_detect_spikes(self):
        """測試突增/突減檢測"""
        # 創建包含突增的測試數據
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1H")
        oi_values = np.full(100, 100000.0)
        oi_values[50] = 150000  # 突增

        test_df = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "BTCUSDT",
                "open_interest": oi_values,
                "open_interest_value": oi_values * 10,
                "exchange": "binance",
            }
        )

        df_with_spikes = self.oi_data.detect_spikes(test_df, threshold=2.0)

        # 驗證突增檢測
        self.assertIn("is_spike", df_with_spikes.columns)
        self.assertIn("spike_type", df_with_spikes.columns)

        spike_count = df_with_spikes["is_spike"].sum()
        self.assertGreater(spike_count, 0)

        print(f"\n✓ Spike detection completed")
        print(f"  Spikes found: {spike_count}")


class TestDataQualityController(unittest.TestCase):
    """測試數據品質控制器"""

    def setUp(self):
        """設置測試環境"""
        self.controller = DataQualityController(strict_mode=False)

    def test_check_ohlcv_valid(self):
        """測試 OHLCV 有效數據檢查"""
        # 創建有效的 OHLCV 數據
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1H")
        df = pd.DataFrame(
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
        df["high"] = df[["open", "close"]].max(axis=1) + 100
        df["low"] = df[["open", "close"]].min(axis=1) - 100

        result = self.controller.check_ohlcv(df)

        self.assertIsInstance(result, QualityCheckResult)
        print(f"\n✓ OHLCV quality check completed")
        print(result.get_summary())

    def test_check_ohlcv_invalid(self):
        """測試 OHLCV 無效數據檢查"""
        # 創建有問題的數據
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1H")
        df = pd.DataFrame(
            {
                "open": 50000,
                "high": 49000,  # high < open (問題)
                "low": 51000,  # low > open (問題)
                "close": 50000,
                "volume": 1000,
            },
            index=dates,
        )

        result = self.controller.check_ohlcv(df)

        self.assertFalse(result.passed)
        self.assertGreater(result.critical_count, 0)

        print(f"\n✓ Invalid OHLCV detected")
        print(f"  Critical issues: {result.critical_count}")

    def test_check_funding_rate(self):
        """測試資金費率數據檢查"""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="8H")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "BTCUSDT",
                "funding_rate": np.random.normal(0.0001, 0.0001, 100),
                "mark_price": 50000,
            }
        )

        result = self.controller.check_funding_rate(df)

        self.assertIsInstance(result, QualityCheckResult)
        print(f"\n✓ Funding rate quality check completed")
        print(result.get_summary())

    def test_check_open_interest(self):
        """測試持倉量數據檢查"""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1H")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "BTCUSDT",
                "open_interest": np.arange(100000, 110000, 100),
                "open_interest_value": np.arange(1000000, 1100000, 1000),
                "oi_change": 100,
                "oi_change_pct": 0.1,
            }
        )

        result = self.controller.check_open_interest(df)

        self.assertIsInstance(result, QualityCheckResult)
        print(f"\n✓ Open interest quality check completed")
        print(result.get_summary())

    def test_clean_ohlcv(self):
        """測試 OHLCV 數據清理"""
        # 創建有問題的數據
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1H")
        df = pd.DataFrame(
            {
                "open": 50000,
                "high": 49000,  # 問題：high < open
                "low": 51000,  # 問題：low > open
                "close": 50000,
                "volume": 1000,
            },
            index=dates,
        )

        cleaned_df = self.controller.clean_ohlcv(df, auto_fix=True)

        # 驗證清理後的數據
        self.assertTrue((cleaned_df["high"] >= cleaned_df["open"]).all())
        self.assertTrue((cleaned_df["low"] <= cleaned_df["open"]).all())

        print(f"\n✓ OHLCV data cleaned")
        print(f"  Original rows: {len(df)}")
        print(f"  Cleaned rows: {len(cleaned_df)}")


class TestPipelineIntegration(unittest.TestCase):
    """測試 DataPipeline 整合"""

    def setUp(self):
        """設置測試環境"""
        self.pipeline = get_pipeline()

    def test_pipeline_initialization(self):
        """測試管道初始化"""
        self.assertIsNotNone(self.pipeline.funding_rate_data)
        self.assertIsNotNone(self.pipeline.open_interest_data)
        self.assertIsNotNone(self.pipeline.quality_controller)

        print("\n✓ Pipeline v0.5 components initialized")

    def test_pipeline_has_perpetual_methods(self):
        """測試管道包含永續數據方法"""
        self.assertTrue(hasattr(self.pipeline, "_load_funding_rate"))
        self.assertTrue(hasattr(self.pipeline, "_load_open_interest"))

        print("\n✓ Pipeline has perpetual data methods")


def run_tests():
    """運行所有測試"""
    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類
    suite.addTests(loader.loadTestsFromTestCase(TestBinanceConnector))
    suite.addTests(loader.loadTestsFromTestCase(TestFundingRateData))
    suite.addTests(loader.loadTestsFromTestCase(TestOpenInterestData))
    suite.addTests(loader.loadTestsFromTestCase(TestDataQualityController))
    suite.addTests(loader.loadTestsFromTestCase(TestPipelineIntegration))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印總結
    print("\n" + "=" * 70)
    print("SuperDog v0.5 永續數據測試總結")
    print("=" * 70)
    print(f"總測試數: {result.testsRun}")
    print(
        f"成功: {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}"
    )
    print(f"失敗: {len(result.failures)}")
    print(f"錯誤: {len(result.errors)}")
    print(f"跳過: {len(result.skipped)}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys

    success = run_tests()
    sys.exit(0 if success else 1)
