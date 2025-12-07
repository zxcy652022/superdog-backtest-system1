"""
Universe Management System Tests (v0.6 Phase 1)

完整的單元測試套件，測試幣種宇宙管理系統的所有核心功能

Test Coverage:
- UniverseCalculator: 7 tests
- UniverseManager: 8 tests
- ClassificationRules: 3 tests
- Integration: 2 tests

Total: 20 test cases

Version: v0.6 Phase 1
Author: DDragon
"""

import json
import shutil

# 添加項目根目錄到路徑
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.universe_calculator import (
    AssetTypeInfo,
    OIMetrics,
    UniverseCalculator,
    VolumeMetrics,
    calculate_all_metrics,
)
from data.universe_manager import (
    ClassificationRules,
    SymbolMetadata,
    UniverseManager,
    UniverseSnapshot,
    get_universe_manager,
)


class TestUniverseCalculator(unittest.TestCase):
    """測試UniverseCalculator類"""

    def setUp(self):
        """測試前設置"""
        # 創建臨時數據目錄
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"
        self.data_dir.mkdir()

        # 創建測試數據
        self._create_test_data()

        # 創建計算器實例
        self.calculator = UniverseCalculator(data_dir=str(self.data_dir))

    def tearDown(self):
        """測試後清理"""
        shutil.rmtree(self.temp_dir)

    def _create_test_data(self):
        """創建測試用的OHLCV數據"""
        dates = pd.date_range("2024-01-01", periods=100, freq="1D")

        # BTC: 高流動性幣種
        btc_data = pd.DataFrame(
            {
                "open": 45000 + np.random.randn(100) * 1000,
                "high": 46000 + np.random.randn(100) * 1000,
                "low": 44000 + np.random.randn(100) * 1000,
                "close": 45000 + np.cumsum(np.random.randn(100) * 100),
                "volume": 50000 + np.random.randn(100) * 5000,  # 高成交量
            },
            index=dates,
        )
        btc_data.to_csv(self.data_dir / "BTCUSDT_1d.csv")

        # ETH: 中等流動性
        eth_data = pd.DataFrame(
            {
                "open": 2500 + np.random.randn(100) * 100,
                "high": 2600 + np.random.randn(100) * 100,
                "low": 2400 + np.random.randn(100) * 100,
                "close": 2500 + np.cumsum(np.random.randn(100) * 10),
                "volume": 30000 + np.random.randn(100) * 3000,
            },
            index=dates,
        )
        eth_data.to_csv(self.data_dir / "ETHUSDT_1d.csv")

        # 低流動性幣種 (用於測試過濾)
        low_vol_data = pd.DataFrame(
            {
                "open": 1 + np.random.randn(100) * 0.1,
                "high": 1.1 + np.random.randn(100) * 0.1,
                "low": 0.9 + np.random.randn(100) * 0.1,
                "close": 1 + np.cumsum(np.random.randn(100) * 0.01),
                "volume": 100 + np.random.randn(100) * 10,  # 低成交量
            },
            index=dates,
        )
        low_vol_data.to_csv(self.data_dir / "LOWCOINUSDT_1d.csv")

    def test_calculate_volume_metrics(self):
        """測試成交額計算"""
        metrics = self.calculator.calculate_volume_metrics("BTCUSDT", days=30)

        self.assertIsInstance(metrics, VolumeMetrics)
        self.assertGreater(metrics.volume_30d_avg, 0)
        self.assertGreater(metrics.volume_7d_avg, 0)
        self.assertGreater(metrics.volume_30d_total, 0)
        self.assertGreaterEqual(metrics.volume_trend, -1)
        self.assertLessEqual(metrics.volume_trend, 1)
        self.assertGreaterEqual(metrics.volume_volatility, 0)

    def test_calculate_volume_metrics_insufficient_data(self):
        """測試數據不足時的行為"""
        # 創建只有3天數據的文件
        dates = pd.date_range("2024-01-01", periods=3, freq="1D")
        short_data = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [95, 96, 97],
                "close": [100, 101, 102],
                "volume": [1000, 1100, 1200],
            },
            index=dates,
        )
        short_data.to_csv(self.data_dir / "SHORTUSDT_1d.csv")

        # 應該拋出ValueError
        with self.assertRaises(ValueError):
            self.calculator.calculate_volume_metrics("SHORTUSDT", days=30)

    def test_calculate_history_days(self):
        """測試上市天數計算"""
        days = self.calculator.calculate_history_days("BTCUSDT")

        # 應該約等於100天（我們創建了100天的數據）
        self.assertGreater(days, 0)
        self.assertLessEqual(days, 105)  # 允許一些誤差

    def test_calculate_oi_metrics_no_perpetual(self):
        """測試沒有永續合約時的持倉量指標"""
        # 對於沒有永續合約的幣種，應返回零值
        metrics = self.calculator.calculate_oi_metrics("BTCUSDT", days=30)

        self.assertIsInstance(metrics, OIMetrics)
        self.assertEqual(metrics.oi_avg_usd, 0)
        self.assertEqual(metrics.oi_trend, 0)
        self.assertEqual(metrics.oi_volatility, 0)
        self.assertEqual(metrics.oi_growth_rate, 0)

    def test_detect_asset_type(self):
        """測試資產類型檢測"""
        # BTC
        btc_info = self.calculator.detect_asset_type("BTCUSDT")
        self.assertIsInstance(btc_info, AssetTypeInfo)
        self.assertFalse(btc_info.is_stablecoin)
        self.assertTrue(btc_info.is_layer1)
        self.assertFalse(btc_info.is_defi)
        self.assertFalse(btc_info.is_meme)

        # 穩定幣
        usdt_info = self.calculator.detect_asset_type("USDTUSDC")
        self.assertTrue(usdt_info.is_stablecoin)

        # DeFi
        uni_info = self.calculator.detect_asset_type("UNIUSDT")
        self.assertTrue(uni_info.is_defi)

        # Meme幣
        doge_info = self.calculator.detect_asset_type("DOGEUSDT")
        self.assertTrue(doge_info.is_meme)

    def test_get_market_cap_rank(self):
        """測試市值排名獲取"""
        # BTC應該是第1
        btc_rank = self.calculator.get_market_cap_rank("BTCUSDT")
        self.assertEqual(btc_rank, 1)

        # ETH應該是第2
        eth_rank = self.calculator.get_market_cap_rank("ETHUSDT")
        self.assertEqual(eth_rank, 2)

        # 未知幣種應該返回None
        unknown_rank = self.calculator.get_market_cap_rank("UNKNOWNUSDT")
        self.assertIsNone(unknown_rank)

    def test_calculate_all_metrics(self):
        """測試一次性計算所有指標"""
        metrics = calculate_all_metrics("BTCUSDT", days=30, calculator=self.calculator)

        # 驗證返回的字典包含所有必需的鍵
        required_keys = [
            "symbol",
            "volume_30d_avg",
            "volume_7d_avg",
            "history_days",
            "oi_avg_usd",
            "oi_trend",
            "is_stablecoin",
            "has_perpetual",
            "is_defi",
            "is_layer1",
            "is_meme",
            "market_cap_rank",
            "last_updated",
        ]

        for key in required_keys:
            self.assertIn(key, metrics)

        self.assertEqual(metrics["symbol"], "BTCUSDT")
        self.assertGreater(metrics["volume_30d_avg"], 0)


class TestClassificationRules(unittest.TestCase):
    """測試ClassificationRules類"""

    def test_classify_large_cap(self):
        """測試大盤分類"""
        # 高成交額的幣種
        metadata = SymbolMetadata(
            symbol="BTCUSDT",
            volume_30d_usd=2_000_000_000,  # $2B
            volume_7d_usd=1_500_000_000,
            history_days=1500,
            market_cap_rank=1,
            oi_avg_usd=1_000_000_000,
            oi_trend=0.5,
            has_perpetual=True,
            is_stablecoin=False,
            is_defi=False,
            is_layer1=True,
            is_meme=False,
            classification="",
            last_updated=datetime.now().isoformat(),
        )

        classification = ClassificationRules.classify_by_market_cap(metadata)
        self.assertEqual(classification, "large_cap")

    def test_classify_mid_cap(self):
        """測試中盤分類"""
        metadata = SymbolMetadata(
            symbol="LINKUSDT",
            volume_30d_usd=200_000_000,  # $200M
            volume_7d_usd=150_000_000,
            history_days=800,
            market_cap_rank=30,
            oi_avg_usd=50_000_000,
            oi_trend=0.2,
            has_perpetual=True,
            is_stablecoin=False,
            is_defi=False,
            is_layer1=False,
            is_meme=False,
            classification="",
            last_updated=datetime.now().isoformat(),
        )

        classification = ClassificationRules.classify_by_market_cap(metadata)
        self.assertEqual(classification, "mid_cap")

    def test_apply_filters(self):
        """測試篩選規則"""
        # 正常幣種（應通過）
        normal_metadata = SymbolMetadata(
            symbol="ETHUSDT",
            volume_30d_usd=5_000_000,  # $5M
            volume_7d_usd=4_000_000,
            history_days=100,
            market_cap_rank=2,
            oi_avg_usd=1_000_000,
            oi_trend=0.1,
            has_perpetual=True,
            is_stablecoin=False,
            is_defi=False,
            is_layer1=True,
            is_meme=False,
            classification="",
            last_updated=datetime.now().isoformat(),
        )

        self.assertTrue(
            ClassificationRules.apply_filters(
                normal_metadata, exclude_stablecoins=True, min_history_days=90, min_volume=1_000_000
            )
        )

        # 穩定幣（應被過濾）
        stablecoin_metadata = SymbolMetadata(
            symbol="USDTUSDC",
            volume_30d_usd=10_000_000,
            volume_7d_usd=9_000_000,
            history_days=500,
            market_cap_rank=3,
            oi_avg_usd=0,
            oi_trend=0,
            has_perpetual=False,
            is_stablecoin=True,
            is_defi=False,
            is_layer1=False,
            is_meme=False,
            classification="",
            last_updated=datetime.now().isoformat(),
        )

        self.assertFalse(
            ClassificationRules.apply_filters(
                stablecoin_metadata,
                exclude_stablecoins=True,
                min_history_days=90,
                min_volume=1_000_000,
            )
        )


class TestUniverseManager(unittest.TestCase):
    """測試UniverseManager類"""

    def setUp(self):
        """測試前設置"""
        # 創建臨時目錄
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"
        self.universe_dir = Path(self.temp_dir) / "universe"
        self.data_dir.mkdir()
        self.universe_dir.mkdir()

        # 創建測試數據
        self._create_test_data()

        # 創建管理器實例
        self.manager = UniverseManager(
            data_dir=str(self.data_dir), universe_dir=str(self.universe_dir)
        )

    def tearDown(self):
        """測試後清理"""
        shutil.rmtree(self.temp_dir)

    def _create_test_data(self):
        """創建測試數據"""
        dates = pd.date_range("2024-01-01", periods=100, freq="1D")

        # 創建3個測試幣種
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        volumes = [50000, 30000, 10000]

        for symbol, vol in zip(symbols, volumes):
            data = pd.DataFrame(
                {
                    "open": 100 + np.random.randn(100) * 10,
                    "high": 110 + np.random.randn(100) * 10,
                    "low": 90 + np.random.randn(100) * 10,
                    "close": 100 + np.cumsum(np.random.randn(100) * 1),
                    "volume": vol + np.random.randn(100) * vol * 0.1,
                },
                index=dates,
            )
            data.to_csv(self.data_dir / f"{symbol}_1d.csv")

    def test_build_universe(self):
        """測試構建宇宙"""
        universe = self.manager.build_universe(
            exclude_stablecoins=True,
            min_history_days=50,
            min_volume=100_000,
            parallel=False,  # 測試時使用串行
        )

        self.assertIsInstance(universe, UniverseSnapshot)
        self.assertIsNotNone(universe.date)
        self.assertGreater(len(universe.symbols), 0)
        self.assertIn("classification", universe.__dict__)
        self.assertIn("statistics", universe.__dict__)

    def test_save_and_load_universe(self):
        """測試保存和加載宇宙快照"""
        # 構建宇宙
        universe = self.manager.build_universe(parallel=False)

        # 保存
        save_path = self.manager.save_universe(universe)
        self.assertTrue(Path(save_path).exists())

        # 加載
        loaded_universe = self.manager.load_universe(universe.date)

        self.assertEqual(loaded_universe.date, universe.date)
        self.assertEqual(len(loaded_universe.symbols), len(universe.symbols))
        self.assertEqual(loaded_universe.statistics, universe.statistics)

    def test_export_config(self):
        """測試匯出配置文件"""
        # 構建宇宙
        universe = self.manager.build_universe(parallel=False)

        # 匯出YAML配置
        yaml_path = self.manager.export_config(
            universe, universe_type="large_cap", top_n=10, format="yaml"
        )

        self.assertTrue(Path(yaml_path).exists())

        # 匯出JSON配置
        json_path = self.manager.export_config(universe, universe_type="mid_cap", format="json")

        self.assertTrue(Path(json_path).exists())

    def test_get_available_dates(self):
        """測試獲取可用日期"""
        # 初始應該沒有快照
        dates = self.manager.get_available_dates()
        self.assertEqual(len(dates), 0)

        # 構建並保存宇宙
        universe = self.manager.build_universe(parallel=False)
        self.manager.save_universe(universe)

        # 現在應該有一個快照
        dates = self.manager.get_available_dates()
        self.assertEqual(len(dates), 1)
        self.assertEqual(dates[0], universe.date)

    def test_discover_symbols(self):
        """測試自動發現幣種"""
        symbols = self.manager._discover_symbols()

        # 應該發現3個幣種
        self.assertEqual(len(symbols), 3)
        self.assertIn("BTCUSDT", symbols)
        self.assertIn("ETHUSDT", symbols)
        self.assertIn("ADAUSDT", symbols)

    def test_calculate_parallel_vs_sequential(self):
        """測試並行和串行計算的一致性"""
        symbols = ["BTCUSDT", "ETHUSDT"]

        # 串行計算
        seq_results = self.manager._calculate_sequential(symbols)

        # 並行計算
        par_results = self.manager._calculate_parallel(symbols, max_workers=2)

        # 結果應該一致
        self.assertEqual(len(seq_results), len(par_results))
        for symbol in symbols:
            if symbol in seq_results and symbol in par_results:
                self.assertEqual(
                    seq_results[symbol].volume_30d_usd, par_results[symbol].volume_30d_usd
                )

    def test_classify_symbols(self):
        """測試幣種分類"""
        # 創建測試元數據
        metadata_dict = {
            "BTC": SymbolMetadata(
                symbol="BTCUSDT",
                volume_30d_usd=2_000_000_000,
                volume_7d_usd=1_500_000_000,
                history_days=1000,
                market_cap_rank=1,
                oi_avg_usd=1_000_000_000,
                oi_trend=0.5,
                has_perpetual=True,
                is_stablecoin=False,
                is_defi=False,
                is_layer1=True,
                is_meme=False,
                classification="large_cap",
                last_updated=datetime.now().isoformat(),
            ),
            "LINK": SymbolMetadata(
                symbol="LINKUSDT",
                volume_30d_usd=150_000_000,
                volume_7d_usd=120_000_000,
                history_days=500,
                market_cap_rank=30,
                oi_avg_usd=50_000_000,
                oi_trend=0.2,
                has_perpetual=True,
                is_stablecoin=False,
                is_defi=False,
                is_layer1=False,
                is_meme=False,
                classification="mid_cap",
                last_updated=datetime.now().isoformat(),
            ),
        }

        classification = self.manager._classify_symbols(metadata_dict)

        self.assertIn("large_cap", classification)
        self.assertIn("mid_cap", classification)
        self.assertEqual(len(classification["large_cap"]), 1)
        self.assertEqual(len(classification["mid_cap"]), 1)

    def test_calculate_statistics(self):
        """測試統計計算"""
        classification = {
            "large_cap": ["BTC", "ETH"],
            "mid_cap": ["LINK", "UNI", "AAVE"],
            "small_cap": ["ABC", "DEF"],
            "micro_cap": ["XYZ"],
        }

        stats = self.manager._calculate_statistics(classification)

        self.assertEqual(stats["total"], 8)
        self.assertEqual(stats["large_cap"], 2)
        self.assertEqual(stats["mid_cap"], 3)
        self.assertEqual(stats["small_cap"], 2)
        self.assertEqual(stats["micro_cap"], 1)


class TestIntegration(unittest.TestCase):
    """整合測試"""

    def setUp(self):
        """測試前設置"""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"
        self.universe_dir = Path(self.temp_dir) / "universe"
        self.data_dir.mkdir()

        self._create_realistic_data()

    def tearDown(self):
        """測試後清理"""
        shutil.rmtree(self.temp_dir)

    def _create_realistic_data(self):
        """創建接近真實的測試數據"""
        dates = pd.date_range("2024-01-01", periods=100, freq="1D")

        # 大盤幣種: BTC
        btc_data = pd.DataFrame(
            {
                "open": 45000 + np.cumsum(np.random.randn(100) * 100),
                "high": 46000 + np.cumsum(np.random.randn(100) * 100),
                "low": 44000 + np.cumsum(np.random.randn(100) * 100),
                "close": 45000 + np.cumsum(np.random.randn(100) * 100),
                "volume": 50000 + np.random.randn(100) * 5000,  # 高成交量
            },
            index=dates,
        )
        btc_data.to_csv(self.data_dir / "BTCUSDT_1d.csv")

        # 中盤幣種: LINK
        link_data = pd.DataFrame(
            {
                "open": 15 + np.cumsum(np.random.randn(100) * 0.5),
                "high": 15.5 + np.cumsum(np.random.randn(100) * 0.5),
                "low": 14.5 + np.cumsum(np.random.randn(100) * 0.5),
                "close": 15 + np.cumsum(np.random.randn(100) * 0.5),
                "volume": 5000 + np.random.randn(100) * 500,
            },
            index=dates,
        )
        link_data.to_csv(self.data_dir / "LINKUSDT_1d.csv")

        # 小盤幣種: LOW
        low_data = pd.DataFrame(
            {
                "open": 0.5 + np.cumsum(np.random.randn(100) * 0.01),
                "high": 0.55 + np.cumsum(np.random.randn(100) * 0.01),
                "low": 0.45 + np.cumsum(np.random.randn(100) * 0.01),
                "close": 0.5 + np.cumsum(np.random.randn(100) * 0.01),
                "volume": 200 + np.random.randn(100) * 20,
            },
            index=dates,
        )
        low_data.to_csv(self.data_dir / "LOWUSDT_1d.csv")

    def test_full_workflow(self):
        """測試完整工作流程"""
        # 1. 創建管理器
        manager = get_universe_manager(
            data_dir=str(self.data_dir), universe_dir=str(self.universe_dir)
        )

        # 2. 構建宇宙
        universe = manager.build_universe(
            exclude_stablecoins=True, min_history_days=50, min_volume=10_000, parallel=False
        )

        # 驗證構建結果
        self.assertGreater(universe.statistics["total"], 0)

        # 3. 保存快照
        save_path = manager.save_universe(universe)
        self.assertTrue(Path(save_path).exists())

        # 4. 加載快照
        loaded = manager.load_universe(universe.date)
        self.assertEqual(loaded.date, universe.date)

        # 5. 匯出配置
        for universe_type in ["large_cap", "mid_cap", "small_cap"]:
            if universe.statistics.get(universe_type, 0) > 0:
                config_path = manager.export_config(
                    universe, universe_type=universe_type, format="json"
                )
                self.assertTrue(Path(config_path).exists())

    def test_performance_requirements(self):
        """測試性能要求"""
        import time

        manager = get_universe_manager(
            data_dir=str(self.data_dir), universe_dir=str(self.universe_dir)
        )

        # 測試構建時間（3個幣種應該很快）
        start_time = time.time()
        universe = manager.build_universe(parallel=False)
        elapsed = time.time() - start_time

        # 3個幣種應該在5秒內完成
        self.assertLess(elapsed, 5.0)

        # 測試保存時間
        start_time = time.time()
        manager.save_universe(universe)
        elapsed = time.time() - start_time

        # 保存應該在1秒內完成
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    # 運行測試
    unittest.main(verbosity=2)
