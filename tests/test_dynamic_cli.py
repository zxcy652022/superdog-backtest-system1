"""
Dynamic CLI 單元測試

測試 CLI 動態參數系統的功能：
- DynamicCLI 參數生成
- ParameterValidator 參數驗證
- BacktestConfigValidator 配置驗證
- CLI 命令輸出

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

import unittest
import click
from click.testing import CliRunner
from cli.dynamic_params import (
    DynamicCLI,
    extract_strategy_params,
    validate_and_convert_params,
    format_strategy_help
)
from cli.parameter_validator import (
    ParameterValidator,
    BacktestConfigValidator
)
from strategies.simple_sma_v2 import SimpleSMAStrategyV2
from strategies.kawamoku_demo import KawamokuStrategy


class TestDynamicCLI(unittest.TestCase):
    """測試 DynamicCLI 參數生成器"""

    def setUp(self):
        """設置測試"""
        self.dynamic_cli = DynamicCLI()
        self.simple_sma = SimpleSMAStrategyV2()
        self.kawamoku = KawamokuStrategy()

    def test_generate_strategy_options_simple_sma(self):
        """測試生成 SimpleSMA 策略選項"""
        options = self.dynamic_cli.generate_strategy_options(self.simple_sma)

        # 應該生成兩個選項
        self.assertEqual(len(options), 2)
        self.assertIn('short_window', options)
        self.assertIn('long_window', options)

        # 選項應該是可調用的（click.option 裝飾器）
        for param_name, option in options.items():
            self.assertTrue(callable(option))

    def test_generate_strategy_options_kawamoku(self):
        """測試生成 Kawamoku 策略選項"""
        options = self.dynamic_cli.generate_strategy_options(self.kawamoku)

        # 應該生成 8 個選項
        self.assertEqual(len(options), 8)
        self.assertIn('momentum_period', options)
        self.assertIn('enable_volume_filter', options)
        self.assertIn('funding_weight', options)

    def test_format_help_text_with_range(self):
        """測試帶範圍的幫助文本"""
        params = self.simple_sma.get_parameters()
        help_text = self.dynamic_cli._format_help_text(
            params['short_window'], 'short_window'
        )

        # 應該包含範圍信息
        self.assertIn('[範圍:', help_text)
        self.assertIn('1-50', help_text)

    def test_format_help_text_bool(self):
        """測試布林參數的幫助文本"""
        params = self.kawamoku.get_parameters()
        help_text = self.dynamic_cli._format_help_text(
            params['enable_volume_filter'], 'enable_volume_filter'
        )

        # 布林參數不應該有範圍
        self.assertNotIn('[範圍:', help_text)
        self.assertIn('啟用成交量過濾', help_text)


class TestExtractStrategyParams(unittest.TestCase):
    """測試策略參數提取"""

    def setUp(self):
        """設置測試"""
        self.strategy = SimpleSMAStrategyV2()

    def test_extract_strategy_params_success(self):
        """測試提取策略參數 - 成功"""
        all_kwargs = {
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'cash': 10000,
            'short_window': 10,
            'long_window': 20,
            'unknown_param': 'value'
        }

        strategy_params = extract_strategy_params(all_kwargs, self.strategy)

        # 應該只包含策略參數
        self.assertEqual(len(strategy_params), 2)
        self.assertEqual(strategy_params['short_window'], 10)
        self.assertEqual(strategy_params['long_window'], 20)
        self.assertNotIn('symbol', strategy_params)
        self.assertNotIn('unknown_param', strategy_params)

    def test_extract_strategy_params_empty(self):
        """測試提取策略參數 - 空結果"""
        all_kwargs = {
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'cash': 10000
        }

        strategy_params = extract_strategy_params(all_kwargs, self.strategy)

        # 應該是空字典
        self.assertEqual(len(strategy_params), 0)


class TestValidateAndConvertParams(unittest.TestCase):
    """測試參數驗證和轉換"""

    def setUp(self):
        """設置測試"""
        self.strategy = SimpleSMAStrategyV2()

    def test_validate_and_convert_success(self):
        """測試驗證和轉換 - 成功"""
        raw_params = {
            'short_window': '10',
            'long_window': '20'
        }

        validated = validate_and_convert_params(raw_params, self.strategy)

        # 應該轉換為整數
        self.assertEqual(validated['short_window'], 10)
        self.assertEqual(validated['long_window'], 20)
        self.assertIsInstance(validated['short_window'], int)

    def test_validate_and_convert_with_defaults(self):
        """測試驗證和轉換 - 使用預設值"""
        raw_params = {}

        validated = validate_and_convert_params(raw_params, self.strategy)

        # 應該使用預設值
        self.assertEqual(validated['short_window'], 10)
        self.assertEqual(validated['long_window'], 20)

    def test_validate_and_convert_out_of_range(self):
        """測試驗證和轉換 - 超出範圍"""
        raw_params = {
            'short_window': '100'  # 超過最大值 50
        }

        with self.assertRaises(click.BadParameter):
            validate_and_convert_params(raw_params, self.strategy)


class TestParameterValidator(unittest.TestCase):
    """測試 ParameterValidator"""

    def setUp(self):
        """設置測試"""
        self.validator = ParameterValidator(verbose=False)
        self.strategy = SimpleSMAStrategyV2()

    def test_validate_success(self):
        """測試驗證 - 成功"""
        params = {
            'short_window': 10,
            'long_window': 20
        }

        validated = self.validator.validate(params, self.strategy)

        self.assertEqual(validated['short_window'], 10)
        self.assertEqual(validated['long_window'], 20)
        self.assertEqual(len(self.validator.errors), 0)

    def test_validate_with_string_conversion(self):
        """測試驗證 - 字符串轉換"""
        params = {
            'short_window': '5',
            'long_window': '25'
        }

        validated = self.validator.validate(params, self.strategy)

        self.assertEqual(validated['short_window'], 5)
        self.assertEqual(validated['long_window'], 25)

    def test_validate_out_of_range(self):
        """測試驗證 - 超出範圍"""
        params = {
            'short_window': 100  # 超過最大值 50
        }

        with self.assertRaises(click.BadParameter):
            self.validator.validate(params, self.strategy)

        self.assertGreater(len(self.validator.errors), 0)

    def test_validate_dependency_check(self):
        """測試驗證 - 相依性檢查"""
        # short_window >= long_window 應該失敗
        params = {
            'short_window': 30,
            'long_window': 20
        }

        with self.assertRaises(click.BadParameter):
            self.validator.validate(params, self.strategy)

    def test_validate_with_unknown_params(self):
        """測試驗證 - 未知參數警告"""
        validator = ParameterValidator(verbose=True)
        params = {
            'short_window': 10,
            'unknown_param': 'value'
        }

        validated = validator.validate(params, self.strategy)

        # 應該有警告
        self.assertGreater(len(validator.warnings), 0)
        # 但驗證應該成功
        self.assertEqual(validated['short_window'], 10)
        self.assertNotIn('unknown_param', validated)


class TestBacktestConfigValidator(unittest.TestCase):
    """測試 BacktestConfigValidator"""

    def setUp(self):
        """設置測試"""
        self.validator = BacktestConfigValidator(verbose=False)
        self.strategy = SimpleSMAStrategyV2()

    def test_validate_config_success(self):
        """測試配置驗證 - 成功"""
        config = {
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'cash': 10000,
            'fee': 0.0005,
            'leverage': 1.0,
            'strategy_params': {
                'short_window': 10,
                'long_window': 20
            }
        }

        validated = self.validator.validate_config(config, self.strategy)

        self.assertEqual(validated['symbol'], 'BTCUSDT')
        self.assertEqual(validated['timeframe'], '1h')
        self.assertEqual(validated['cash'], 10000)
        self.assertEqual(validated['strategy_params']['short_window'], 10)

    def test_validate_config_missing_required(self):
        """測試配置驗證 - 缺少必需參數"""
        config = {
            'timeframe': '1h'
            # 缺少 symbol
        }

        with self.assertRaises(click.BadParameter):
            self.validator.validate_config(config, self.strategy)

    def test_validate_config_invalid_cash(self):
        """測試配置驗證 - 無效資金"""
        config = {
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'cash': -1000  # 負數
        }

        with self.assertRaises(click.BadParameter):
            self.validator.validate_config(config, self.strategy)

    def test_validate_config_invalid_leverage(self):
        """測試配置驗證 - 無效槓桿"""
        config = {
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'leverage': 150  # 超過 100
        }

        with self.assertRaises(click.BadParameter):
            self.validator.validate_config(config, self.strategy)

    def test_validate_config_invalid_timeframe(self):
        """測試配置驗證 - 無效時間週期"""
        config = {
            'symbol': 'BTCUSDT',
            'timeframe': '2h'  # 不在有效列表中
        }

        with self.assertRaises(click.BadParameter):
            self.validator.validate_config(config, self.strategy)

    def test_validate_config_with_defaults(self):
        """測試配置驗證 - 使用預設值"""
        config = {
            'symbol': 'BTCUSDT',
            'timeframe': '1h'
            # 其他參數使用預設值
        }

        validated = self.validator.validate_config(config, self.strategy)

        # 應該使用預設值
        self.assertEqual(validated['cash'], 10000.0)
        self.assertEqual(validated['fee'], 0.0005)
        self.assertEqual(validated['leverage'], 1.0)


class TestFormatStrategyHelp(unittest.TestCase):
    """測試策略幫助信息格式化"""

    def test_format_help_simple_sma(self):
        """測試格式化 SimpleSMA 幫助信息"""
        strategy = SimpleSMAStrategyV2()
        help_text = format_strategy_help(strategy)

        # 應該包含基本信息
        self.assertIn('SimpleSMA', help_text)
        self.assertIn('2.0', help_text)
        self.assertIn('SuperDog Team', help_text)

        # 應該包含參數信息
        self.assertIn('--short-window', help_text)
        self.assertIn('--long-window', help_text)

        # 應該包含數據需求
        self.assertIn('Data Requirements', help_text)
        self.assertIn('ohlcv', help_text)

    def test_format_help_kawamoku(self):
        """測試格式化 Kawamoku 幫助信息"""
        strategy = KawamokuStrategy()
        help_text = format_strategy_help(strategy)

        # 應該包含多個參數
        self.assertIn('--momentum-period', help_text)
        self.assertIn('--enable-volume-filter', help_text)

        # 應該包含多個數據源
        self.assertIn('funding', help_text)
        self.assertIn('optional', help_text)


if __name__ == '__main__':
    unittest.main()
