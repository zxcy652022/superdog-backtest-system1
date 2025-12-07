"""
Strategy API v2.0 單元測試

測試 Strategy API v2.0 的核心功能：
- ParameterSpec 參數規格驗證
- BaseStrategy 基礎接口
- SimpleSMAStrategyV2 實作
- KawamokuStrategy 實作
- 參數驗證和轉換

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

import unittest

import numpy as np
import pandas as pd

from strategies.api_v2 import (
    BaseStrategy,
    DataRequirement,
    DataSource,
    ParameterSpec,
    ParameterType,
    bool_param,
    float_param,
    int_param,
    str_param,
)
from strategies.kawamoku_demo import KawamokuStrategy
from strategies.simple_sma_v2 import SimpleSMAStrategyV2


class TestParameterSpec(unittest.TestCase):
    """測試 ParameterSpec 參數規格"""

    def test_float_validation_success(self):
        """測試浮點數驗證 - 成功案例"""
        spec = ParameterSpec(ParameterType.FLOAT, 0.5, "測試參數", 0.0, 1.0)

        # 正常值
        self.assertEqual(spec.validate(0.5), 0.5)
        self.assertEqual(spec.validate(0.0), 0.0)
        self.assertEqual(spec.validate(1.0), 1.0)

        # 字符串轉換
        self.assertEqual(spec.validate("0.75"), 0.75)

    def test_float_validation_out_of_range(self):
        """測試浮點數驗證 - 範圍錯誤"""
        spec = ParameterSpec(ParameterType.FLOAT, 0.5, "測試參數", 0.0, 1.0)

        # 超出最大值
        with self.assertRaises(ValueError):
            spec.validate(1.5)

        # 低於最小值
        with self.assertRaises(ValueError):
            spec.validate(-0.5)

    def test_int_validation_success(self):
        """測試整數驗證 - 成功案例"""
        spec = ParameterSpec(ParameterType.INT, 20, "週期", 5, 200)

        # 正常值
        self.assertEqual(spec.validate(20), 20)
        self.assertEqual(spec.validate(5), 5)
        self.assertEqual(spec.validate(200), 200)

        # 字符串轉換
        self.assertEqual(spec.validate("100"), 100)

        # 浮點數轉整數
        self.assertEqual(spec.validate(50.9), 50)

    def test_int_validation_out_of_range(self):
        """測試整數驗證 - 範圍錯誤"""
        spec = ParameterSpec(ParameterType.INT, 20, "週期", 5, 200)

        # 超出範圍
        with self.assertRaises(ValueError):
            spec.validate(300)

        with self.assertRaises(ValueError):
            spec.validate(2)

    def test_bool_validation(self):
        """測試布林值驗證"""
        spec = ParameterSpec(ParameterType.BOOL, True, "啟用")

        # 布林值
        self.assertTrue(spec.validate(True))
        self.assertFalse(spec.validate(False))

        # 字符串轉換
        self.assertTrue(spec.validate("true"))
        self.assertTrue(spec.validate("True"))
        self.assertTrue(spec.validate("yes"))
        self.assertTrue(spec.validate("1"))

        self.assertFalse(spec.validate("false"))
        self.assertFalse(spec.validate("False"))
        self.assertFalse(spec.validate("no"))
        self.assertFalse(spec.validate("0"))

        # 無效字符串
        with self.assertRaises(TypeError):
            spec.validate("maybe")

    def test_str_validation_with_choices(self):
        """測試字符串驗證 - 帶選項"""
        spec = ParameterSpec(ParameterType.STR, "buy", "信號類型", choices=["buy", "sell", "both"])

        # 有效選項
        self.assertEqual(spec.validate("buy"), "buy")
        self.assertEqual(spec.validate("sell"), "sell")

        # 無效選項
        with self.assertRaises(ValueError):
            spec.validate("invalid")

    def test_helper_functions(self):
        """測試便捷函數"""
        # float_param
        fp = float_param(0.5, "測試", 0.0, 1.0)
        self.assertEqual(fp.param_type, ParameterType.FLOAT)
        self.assertEqual(fp.default_value, 0.5)
        self.assertEqual(fp.min_value, 0.0)
        self.assertEqual(fp.max_value, 1.0)

        # int_param
        ip = int_param(20, "週期", 5, 200)
        self.assertEqual(ip.param_type, ParameterType.INT)
        self.assertEqual(ip.default_value, 20)

        # bool_param
        bp = bool_param(True, "啟用")
        self.assertEqual(bp.param_type, ParameterType.BOOL)
        self.assertTrue(bp.default_value)

        # str_param
        sp = str_param("buy", "類型", ["buy", "sell"])
        self.assertEqual(sp.param_type, ParameterType.STR)
        self.assertEqual(sp.choices, ["buy", "sell"])


class TestDataRequirement(unittest.TestCase):
    """測試 DataRequirement 數據需求"""

    def test_data_requirement_creation(self):
        """測試創建數據需求"""
        req = DataRequirement(
            source=DataSource.OHLCV, timeframe="1h", lookback_periods=200, required=True
        )

        self.assertEqual(req.source, DataSource.OHLCV)
        self.assertEqual(req.timeframe, "1h")
        self.assertEqual(req.lookback_periods, 200)
        self.assertTrue(req.required)

    def test_data_requirement_defaults(self):
        """測試數據需求預設值"""
        req = DataRequirement(source=DataSource.OHLCV)

        self.assertEqual(req.source, DataSource.OHLCV)
        self.assertIsNone(req.timeframe)
        self.assertEqual(req.lookback_periods, 100)
        self.assertTrue(req.required)


class TestSimpleSMAStrategyV2(unittest.TestCase):
    """測試 SimpleSMAStrategyV2 策略"""

    def setUp(self):
        """設置測試數據"""
        # 創建測試數據（100根K線）
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        np.random.seed(42)

        # 生成模擬價格數據
        close = 100 + np.cumsum(np.random.randn(100) * 2)
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_prices = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1000, 10000, 100)

        self.test_data = pd.DataFrame(
            {"open": open_prices, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )

        self.strategy = SimpleSMAStrategyV2()

    def test_metadata(self):
        """測試策略元數據"""
        metadata = self.strategy.get_metadata()

        self.assertEqual(metadata["name"], "SimpleSMA")
        self.assertEqual(metadata["version"], "2.0")
        self.assertEqual(metadata["author"], "SuperDog Team")
        self.assertIn("short_window", metadata["parameters"])
        self.assertIn("long_window", metadata["parameters"])
        self.assertIn("ohlcv", metadata["data_sources"])

    def test_parameters(self):
        """測試參數規格"""
        params = self.strategy.get_parameters()

        self.assertIn("short_window", params)
        self.assertIn("long_window", params)

        # 檢查參數規格
        short_spec = params["short_window"]
        self.assertEqual(short_spec.param_type, ParameterType.INT)
        self.assertEqual(short_spec.default_value, 10)
        self.assertEqual(short_spec.min_value, 1)
        self.assertEqual(short_spec.max_value, 50)

        long_spec = params["long_window"]
        self.assertEqual(long_spec.param_type, ParameterType.INT)
        self.assertEqual(long_spec.default_value, 20)

    def test_data_requirements(self):
        """測試數據需求"""
        requirements = self.strategy.get_data_requirements()

        self.assertEqual(len(requirements), 1)
        self.assertEqual(requirements[0].source, DataSource.OHLCV)
        self.assertEqual(requirements[0].lookback_periods, 200)
        self.assertTrue(requirements[0].required)

    def test_compute_signals_success(self):
        """測試信號計算 - 成功案例"""
        data = {"ohlcv": self.test_data}
        params = {"short_window": 5, "long_window": 10}

        signals = self.strategy.compute_signals(data, params)

        # 檢查返回類型
        self.assertIsInstance(signals, pd.Series)
        self.assertEqual(len(signals), len(self.test_data))

        # 檢查信號值
        unique_signals = signals.unique()
        for sig in unique_signals:
            self.assertIn(sig, [-1, 0, 1])

    def test_compute_signals_missing_data(self):
        """測試信號計算 - 缺少數據"""
        data = {}  # 空數據
        params = {"short_window": 5, "long_window": 10}

        with self.assertRaises(ValueError):
            self.strategy.compute_signals(data, params)

    def test_compute_signals_insufficient_data(self):
        """測試信號計算 - 數據不足"""
        # 只有 5 根 K 線，但需要 20 根
        short_data = self.test_data.iloc[:5]
        data = {"ohlcv": short_data}
        params = {"short_window": 5, "long_window": 20}

        with self.assertRaises(ValueError):
            self.strategy.compute_signals(data, params)

    def test_validate_parameters(self):
        """測試參數驗證"""
        # 正常參數
        validated = self.strategy.validate_parameters({"short_window": "5", "long_window": "20"})
        self.assertEqual(validated["short_window"], 5)
        self.assertEqual(validated["long_window"], 20)

        # 使用預設值
        validated = self.strategy.validate_parameters({})
        self.assertEqual(validated["short_window"], 10)
        self.assertEqual(validated["long_window"], 20)

        # 超出範圍
        with self.assertRaises(ValueError):
            self.strategy.validate_parameters({"short_window": 100})


class TestKawamokuStrategy(unittest.TestCase):
    """測試 KawamokuStrategy 策略"""

    def setUp(self):
        """設置測試數據"""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(100) * 2)
        high = close + np.abs(np.random.randn(100))
        low = close - np.abs(np.random.randn(100))
        open_prices = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1000, 10000, 100)

        self.test_data = pd.DataFrame(
            {"open": open_prices, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )

        self.strategy = KawamokuStrategy()

    def test_metadata(self):
        """測試策略元數據"""
        metadata = self.strategy.get_metadata()

        self.assertEqual(metadata["name"], "Kawamoku")
        self.assertEqual(metadata["version"], "1.0")
        self.assertEqual(metadata["author"], "DDragon")
        self.assertIn("momentum_period", metadata["parameters"])
        self.assertIn("funding_weight", metadata["parameters"])

    def test_parameters(self):
        """測試參數規格 - 多種類型"""
        params = self.strategy.get_parameters()

        # 整數參數
        self.assertIn("momentum_period", params)
        self.assertEqual(params["momentum_period"].param_type, ParameterType.INT)

        # 浮點參數
        self.assertIn("momentum_threshold", params)
        self.assertEqual(params["momentum_threshold"].param_type, ParameterType.FLOAT)

        # 布林參數
        self.assertIn("enable_volume_filter", params)
        self.assertEqual(params["enable_volume_filter"].param_type, ParameterType.BOOL)

    def test_data_requirements(self):
        """測試數據需求 - 多數據源"""
        requirements = self.strategy.get_data_requirements()

        # 應該有多個數據需求
        self.assertGreater(len(requirements), 1)

        # OHLCV 是必需的
        ohlcv_req = [r for r in requirements if r.source == DataSource.OHLCV]
        self.assertEqual(len(ohlcv_req), 1)
        self.assertTrue(ohlcv_req[0].required)

        # 其他數據源是可選的（v0.5）
        funding_req = [r for r in requirements if r.source == DataSource.FUNDING]
        if funding_req:
            self.assertFalse(funding_req[0].required)

    def test_compute_signals_success(self):
        """測試信號計算 - 成功案例"""
        data = {"ohlcv": self.test_data}
        params = {
            "momentum_period": 5,
            "momentum_threshold": 0.02,
            "volume_ma_period": 20,
            "volume_threshold": 1.5,
            "enable_volume_filter": True,
            "funding_weight": 0.5,
            "oi_threshold": 1.0,
            "basis_lookback": 7,
        }

        signals = self.strategy.compute_signals(data, params)

        # 檢查返回類型
        self.assertIsInstance(signals, pd.Series)
        self.assertEqual(len(signals), len(self.test_data))

        # 檢查信號值
        unique_signals = signals.unique()
        for sig in unique_signals:
            self.assertIn(sig, [-1, 0, 1])

    def test_compute_signals_without_volume_filter(self):
        """測試信號計算 - 關閉成交量過濾"""
        data = {"ohlcv": self.test_data}
        params = {
            "momentum_period": 5,
            "momentum_threshold": 0.02,
            "volume_ma_period": 20,
            "volume_threshold": 1.5,
            "enable_volume_filter": False,  # 關閉
            "funding_weight": 0.5,
            "oi_threshold": 1.0,
            "basis_lookback": 7,
        }

        signals = self.strategy.compute_signals(data, params)

        # 應該能成功計算
        self.assertIsInstance(signals, pd.Series)


class TestBaseStrategyInterface(unittest.TestCase):
    """測試 BaseStrategy 抽象接口"""

    def test_cannot_instantiate_base_strategy(self):
        """測試不能直接實例化 BaseStrategy"""
        with self.assertRaises(TypeError):
            BaseStrategy()

    def test_must_implement_abstract_methods(self):
        """測試必須實作抽象方法"""

        # 創建一個不完整的策略類
        class IncompleteStrategy(BaseStrategy):
            def __init__(self):
                super().__init__()

            def get_parameters(self):
                return {}

            # 缺少 get_data_requirements 和 compute_signals

        # 應該無法實例化
        with self.assertRaises(TypeError):
            IncompleteStrategy()


if __name__ == "__main__":
    unittest.main()
