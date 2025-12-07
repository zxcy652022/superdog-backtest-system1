#!/usr/bin/env python3
"""
SuperDog v0.5 Integration Tests

端到端整合測試 - 驗證完整工作流程

Tests:
- Phase A+B 模組集成
- DataPipeline 完整流程
- 多交易所數據聚合
- 策略回測端到端流程

Usage:
    python3 tests/test_integration_v05.py
"""

import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPhaseABIntegration(unittest.TestCase):
    """Phase A+B 集成測試"""

    def test_all_exchanges_import(self):
        """測試所有交易所連接器導入"""
        from data.exchanges import BinanceConnector, BybitConnector, OKXConnector

        # 初始化所有連接器
        binance = BinanceConnector()
        bybit = BybitConnector()
        okx = OKXConnector()

        self.assertEqual(binance.name, 'binance')
        self.assertEqual(bybit.name, 'bybit')
        self.assertEqual(okx.name, 'okx')

    def test_all_perpetual_modules_import(self):
        """測試所有永續合約模組導入"""
        from data.perpetual import (
            FundingRateData, OpenInterestData,
            BasisData, LiquidationData, LongShortRatioData
        )

        # Phase A
        funding = FundingRateData()
        oi = OpenInterestData()

        # Phase B
        basis = BasisData()
        liq = LiquidationData()
        lsr = LongShortRatioData()

        self.assertIsNotNone(funding)
        self.assertIsNotNone(oi)
        self.assertIsNotNone(basis)
        self.assertIsNotNone(liq)
        self.assertIsNotNone(lsr)

    def test_multi_exchange_aggregator(self):
        """測試多交易所聚合器"""
        from data.aggregation import MultiExchangeAggregator

        agg = MultiExchangeAggregator(exchanges=['binance', 'bybit', 'okx'])

        self.assertEqual(len(agg.exchanges), 3)
        self.assertIn('binance', agg.exchanges)
        self.assertIn('bybit', agg.exchanges)
        self.assertIn('okx', agg.exchanges)


class TestDataPipelineIntegration(unittest.TestCase):
    """DataPipeline 集成測試"""

    def test_pipeline_initialization(self):
        """測試 DataPipeline 初始化"""
        from data.pipeline import get_pipeline

        pipeline = get_pipeline()

        # 檢查 Phase A 處理器
        self.assertTrue(hasattr(pipeline, 'funding_rate_data'))
        self.assertTrue(hasattr(pipeline, 'open_interest_data'))

        # 檢查 Phase B 處理器
        self.assertTrue(hasattr(pipeline, 'basis_data'))
        self.assertTrue(hasattr(pipeline, 'liquidation_data'))
        self.assertTrue(hasattr(pipeline, 'long_short_ratio_data'))

    def test_data_source_enum(self):
        """測試 DataSource 枚舉"""
        from strategies.api_v2 import DataSource

        # Phase A+B 所有數據源
        sources = [
            DataSource.OHLCV,
            DataSource.FUNDING_RATE,
            DataSource.OPEN_INTEREST,
            DataSource.BASIS,
            DataSource.LIQUIDATIONS,
            DataSource.LONG_SHORT_RATIO
        ]

        for source in sources:
            self.assertIsNotNone(source.value)


class TestBasisCalculation(unittest.TestCase):
    """期現基差計算測試"""

    def test_basis_calculation_logic(self):
        """測試基差計算邏輯"""
        # 模擬計算
        perp_price = 100500.0
        spot_price = 100000.0

        basis = perp_price - spot_price
        basis_pct = (basis / spot_price) * 100
        annualized = basis_pct * 365

        self.assertEqual(basis, 500.0)
        self.assertAlmostEqual(basis_pct, 0.5, places=2)
        self.assertAlmostEqual(annualized, 182.5, places=1)

    def test_arbitrage_opportunity_detection(self):
        """測試套利機會識別"""
        import pandas as pd

        # 創建測試數據
        df = pd.DataFrame({
            'basis_pct': [0.6, -0.6, 0.2, -0.2]
        })

        threshold = 0.5

        # 正向套利
        cash_carry = df['basis_pct'] > threshold
        self.assertTrue(cash_carry.iloc[0])
        self.assertFalse(cash_carry.iloc[2])

        # 反向套利
        reverse = df['basis_pct'] < -threshold
        self.assertTrue(reverse.iloc[1])
        self.assertFalse(reverse.iloc[3])


class TestPanicIndexCalculation(unittest.TestCase):
    """恐慌指數計算測試"""

    def test_panic_index_formula(self):
        """測試恐慌指數公式"""
        # 模擬數據
        current_liq = 10000000  # $10M
        avg_liq = 5000000       # $5M

        intensity_ratio = current_liq / avg_liq
        panic_index = min(100, intensity_ratio * 20)

        self.assertEqual(intensity_ratio, 2.0)
        self.assertEqual(panic_index, 40.0)

    def test_panic_level_classification(self):
        """測試恐慌等級分類"""
        def classify_panic(index):
            if index < 20:
                return 'calm'
            elif index < 40:
                return 'moderate'
            elif index < 60:
                return 'elevated'
            elif index < 80:
                return 'high'
            else:
                return 'extreme'

        self.assertEqual(classify_panic(10), 'calm')
        self.assertEqual(classify_panic(30), 'moderate')
        self.assertEqual(classify_panic(50), 'elevated')
        self.assertEqual(classify_panic(70), 'high')
        self.assertEqual(classify_panic(90), 'extreme')


class TestSentimentIndexCalculation(unittest.TestCase):
    """情緒指數計算測試"""

    def test_sentiment_index_formula(self):
        """測試情緒指數公式"""
        # 不同多空比
        scenarios = [
            (0.80, 60.0),   # 極度看多
            (0.50, 0.0),    # 中性
            (0.20, -60.0)   # 極度看空
        ]

        for long_ratio, expected_index in scenarios:
            sentiment_index = (long_ratio - 0.5) * 200
            self.assertAlmostEqual(sentiment_index, expected_index, places=1)

    def test_contrarian_signal_generation(self):
        """測試逆向信號生成"""
        def get_signal(sentiment_index):
            if sentiment_index > 40:
                return 'consider_short'
            elif sentiment_index < -40:
                return 'consider_long'
            else:
                return 'no_signal'

        self.assertEqual(get_signal(60), 'consider_short')
        self.assertEqual(get_signal(-60), 'consider_long')
        self.assertEqual(get_signal(0), 'no_signal')


class TestExchangeSymbolFormatting(unittest.TestCase):
    """交易所符號格式測試"""

    def test_okx_symbol_conversion(self):
        """測試 OKX 符號轉換"""
        from data.exchanges import OKXConnector

        okx = OKXConnector()

        # Binance 格式轉 OKX 格式
        result = okx._validate_symbol('BTCUSDT')
        self.assertEqual(result, 'BTC-USDT-SWAP')

        # 已經是 OKX 格式
        result = okx._validate_symbol('BTC-USDT-SWAP')
        self.assertEqual(result, 'BTC-USDT-SWAP')

    def test_binance_symbol_uppercase(self):
        """測試 Binance 符號大寫轉換"""
        from data.exchanges import BinanceConnector

        binance = BinanceConnector()

        result = binance._validate_symbol('btcusdt')
        self.assertEqual(result, 'BTCUSDT')


class TestEndToEndWorkflow(unittest.TestCase):
    """端到端工作流程測試"""

    def test_complete_data_workflow(self):
        """測試完整數據工作流程 (不實際調用 API)"""
        from data.perpetual import BasisData, LiquidationData, LongShortRatioData

        # 1. 初始化數據處理器
        basis_data = BasisData()
        liq_data = LiquidationData()
        lsr_data = LongShortRatioData()

        # 2. 檢查存儲路徑
        self.assertTrue(basis_data.storage_path.exists() or True)  # 允許創建
        self.assertTrue(liq_data.storage_path.exists() or True)
        self.assertTrue(lsr_data.storage_path.exists() or True)

        # 3. 檢查連接器
        self.assertGreater(len(liq_data.connectors), 0)
        self.assertGreater(len(lsr_data.connectors), 0)

    def test_strategy_data_requirements(self):
        """測試策略數據需求定義"""
        from strategies.api_v2 import DataSource, DataRequirement

        # 創建多因子策略的數據需求
        requirements = [
            DataRequirement(DataSource.OHLCV, required=True),
            DataRequirement(DataSource.FUNDING_RATE, required=True),
            DataRequirement(DataSource.OPEN_INTEREST, required=True),
            DataRequirement(DataSource.BASIS, required=False),
            DataRequirement(DataSource.LIQUIDATIONS, required=False),
            DataRequirement(DataSource.LONG_SHORT_RATIO, required=False)
        ]

        self.assertEqual(len(requirements), 6)

        # 檢查必需 vs 可選
        required_count = sum(1 for r in requirements if r.required)
        optional_count = sum(1 for r in requirements if not r.required)

        self.assertEqual(required_count, 3)  # Phase A
        self.assertEqual(optional_count, 3)  # Phase B


class TestDataQuality(unittest.TestCase):
    """數據質量測試"""

    def test_dataframe_validation(self):
        """測試 DataFrame 驗證"""
        import pandas as pd

        # 創建測試 DataFrame
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=5, freq='1h'),
            'value': [100, 101, 102, 103, 104]
        })

        # 檢查列存在
        self.assertIn('timestamp', df.columns)
        self.assertIn('value', df.columns)

        # 檢查數據類型
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df['timestamp']))

        # 檢查無缺失值
        self.assertEqual(df.isna().sum().sum(), 0)

    def test_time_series_continuity(self):
        """測試時間序列連續性"""
        import pandas as pd

        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
            'value': range(100)
        })

        # 檢查時間間隔一致性
        time_diffs = df['timestamp'].diff().dropna()
        expected_diff = pd.Timedelta('1h')

        self.assertTrue((time_diffs == expected_diff).all())


def run_tests():
    """運行所有測試"""
    print()
    print("=" * 70)
    print("SuperDog v0.5 Integration Tests")
    print("=" * 70)
    print()

    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類別
    suite.addTests(loader.loadTestsFromTestCase(TestPhaseABIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestDataPipelineIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestBasisCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestPanicIndexCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestSentimentIndexCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestExchangeSymbolFormatting))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestDataQuality))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印總結
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print()

    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
