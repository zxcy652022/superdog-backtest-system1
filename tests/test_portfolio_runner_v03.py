# -*- coding: utf-8 -*-
"""Tests for Portfolio Runner v0.3

Design Reference: docs/specs/planned/v0.3_test_plan.md §5
"""

import sys
import os
sys.path.append(os.path.abspath("."))

from execution_engine.portfolio_runner import (
    RunConfig, SingleRunResult, PortfolioResult, run_portfolio,
    load_configs_from_yaml, _build_position_sizer
)
from backtest.position_sizer import AllInSizer, FixedCashSizer, PercentOfEquitySizer


# === Core Tests (5 tests) ===

def test_run_single_backtest_success():
    """Test successful single backtest execution"""
    config = RunConfig(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h_test",
        initial_cash=10000
    )

    result = run_portfolio([config], verbose=False)

    assert len(result) == 1, f"Should have 1 result, got {len(result)}"
    assert result[0].success, "Backtest should succeed"
    assert result[0].backtest_result is not None, "Should have backtest_result"
    assert result[0].error is None, "Should not have error"
    assert result[0].strategy == "simple_sma", "Strategy name should match"
    assert result[0].symbol == "BTCUSDT", "Symbol should match"

    print("OK test_run_single_backtest_success passed")


def test_run_single_backtest_strategy_not_found():
    """Test backtest failure when strategy not found"""
    config = RunConfig(
        strategy="nonexistent_strategy",
        symbol="BTCUSDT",
        timeframe="1h_test"
    )

    result = run_portfolio([config], verbose=False)

    assert len(result) == 1, f"Should have 1 result, got {len(result)}"
    assert not result[0].success, "Backtest should fail"
    assert result[0].backtest_result is None, "Should not have backtest_result"
    assert result[0].error is not None, "Should have error"
    assert "Strategy not found" in result[0].error, f"Error should mention strategy not found: {result[0].error}"

    print("OK test_run_single_backtest_strategy_not_found passed")


def test_run_single_backtest_data_not_found():
    """Test backtest failure when data file not found"""
    config = RunConfig(
        strategy="simple_sma",
        symbol="NONEXISTENT",
        timeframe="1h"
    )

    result = run_portfolio([config], verbose=False)

    assert len(result) == 1, f"Should have 1 result, got {len(result)}"
    assert not result[0].success, "Backtest should fail"
    assert result[0].error is not None, "Should have error"
    assert "Data file not found" in result[0].error, f"Error should mention data not found: {result[0].error}"

    print("OK test_run_single_backtest_data_not_found passed")


def test_run_multiple_backtests():
    """Test running multiple backtests"""
    configs = [
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test"),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", initial_cash=20000),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", leverage=2.0),
    ]

    result = run_portfolio(configs, verbose=False)

    assert len(result) == 3, f"Should have 3 results, got {len(result)}"
    assert result.count_successful() == 3, f"All 3 should succeed, got {result.count_successful()}"
    assert result.count_failed() == 0, f"None should fail, got {result.count_failed()}"
    assert result.success_rate() == 1.0, f"Success rate should be 100%, got {result.success_rate()}"

    print("OK test_run_multiple_backtests passed")


def test_run_portfolio_with_failures():
    """Test portfolio execution with mixed success/failure"""
    configs = [
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test"),
        RunConfig(strategy="invalid_strategy", symbol="BTCUSDT", timeframe="1h_test"),
        RunConfig(strategy="simple_sma", symbol="INVALID", timeframe="1h"),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test"),
    ]

    result = run_portfolio(configs, verbose=False, fail_fast=False)

    assert len(result) == 4, f"Should have 4 results, got {len(result)}"
    assert result.count_successful() == 2, f"2 should succeed, got {result.count_successful()}"
    assert result.count_failed() == 2, f"2 should fail, got {result.count_failed()}"
    assert result.success_rate() == 0.5, f"Success rate should be 50%, got {result.success_rate()}"

    # Check failed runs
    failed = result.get_failed_runs()
    assert len(failed) == 2, f"Should have 2 failed runs, got {len(failed)}"

    print("OK test_run_portfolio_with_failures passed")


# === Result Object Tests (4 tests) ===

def test_portfolio_result_to_dataframe():
    """Test converting PortfolioResult to DataFrame"""
    configs = [
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test"),
        RunConfig(strategy="invalid", symbol="BTCUSDT", timeframe="1h_test"),
    ]

    result = run_portfolio(configs, verbose=False)

    # Test with only successful runs
    df = result.to_dataframe(include_failed=False)
    assert len(df) == 1, f"Should have 1 row (only successful), got {len(df)}"
    assert "strategy" in df.columns, "Should have 'strategy' column"
    assert "symbol" in df.columns, "Should have 'symbol' column"
    assert "total_return" in df.columns, "Should have 'total_return' column"

    # Test with failed runs included
    df_all = result.to_dataframe(include_failed=True)
    assert len(df_all) == 2, f"Should have 2 rows (all), got {len(df_all)}"
    assert df_all.iloc[1]["status"] == "✗", "Second row should be failed"
    assert df_all.iloc[1]["error"] != "", "Failed row should have error message"

    print("OK test_portfolio_result_to_dataframe passed")


def test_portfolio_result_get_best_by():
    """Test getting best runs by metric"""
    configs = [
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", initial_cash=10000),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", initial_cash=15000),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", initial_cash=20000),
    ]

    result = run_portfolio(configs, verbose=False)

    # Get best by total_return
    best = result.get_best_by("total_return", top_n=1)
    assert len(best) == 1, f"Should return 1 best run, got {len(best)}"
    assert best[0].success, "Best run should be successful"

    # Get top 2
    top_2 = result.get_best_by("total_return", top_n=2)
    assert len(top_2) == 2, f"Should return 2 runs, got {len(top_2)}"

    # Verify ordering (descending)
    if len(top_2) == 2:
        tr1 = top_2[0].get_metric("total_return", 0)
        tr2 = top_2[1].get_metric("total_return", 0)
        assert tr1 >= tr2, f"First should be >= second: {tr1} vs {tr2}"

    print("OK test_portfolio_result_get_best_by passed")


def test_portfolio_result_filter():
    """Test custom filtering"""
    configs = [
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", leverage=1.0),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", leverage=2.0),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", leverage=3.0),
    ]

    result = run_portfolio(configs, verbose=False)

    # Filter by leverage >= 2
    filtered = result.filter(lambda r: r.config.leverage >= 2.0)
    assert len(filtered) == 2, f"Should have 2 runs with leverage >= 2, got {len(filtered)}"

    # Filter by strategy
    by_strategy = result.get_by_strategy("simple_sma")
    assert len(by_strategy) == 3, f"Should have 3 runs for simple_sma, got {len(by_strategy)}"

    # Filter by symbol
    by_symbol = result.get_by_symbol("BTCUSDT")
    assert len(by_symbol) == 3, f"Should have 3 runs for BTCUSDT, got {len(by_symbol)}"

    print("OK test_portfolio_result_filter passed")


def test_single_run_result_get_metrics():
    """Test SingleRunResult.get_metrics()"""
    config = RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test")

    result = run_portfolio([config], verbose=False)
    run = result[0]

    # Get all metrics
    metrics = run.get_metrics()
    assert isinstance(metrics, dict), "Metrics should be a dict"
    assert "total_return" in metrics, "Should have 'total_return' metric"
    assert "num_trades" in metrics, "Should have 'num_trades' metric"

    # Get single metric
    total_return = run.get_metric("total_return")
    assert isinstance(total_return, (int, float)), f"total_return should be numeric, got {type(total_return)}"

    # Get non-existent metric with default
    fake_metric = run.get_metric("nonexistent", default=999)
    assert fake_metric == 999, f"Should return default value 999, got {fake_metric}"

    print("OK test_single_run_result_get_metrics passed")


# === Config Tests (3 tests) ===

def test_run_config_validation():
    """Test RunConfig validation"""
    # Valid config
    config = RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h")
    assert config.strategy == "simple_sma", "Strategy should be set"

    # Missing strategy
    try:
        RunConfig(strategy="", symbol="BTCUSDT", timeframe="1h")
        assert False, "Should raise ValueError for empty strategy"
    except ValueError as e:
        assert "strategy is required" in str(e), f"Error should mention strategy: {e}"

    # Missing symbol
    try:
        RunConfig(strategy="simple_sma", symbol="", timeframe="1h")
        assert False, "Should raise ValueError for empty symbol"
    except ValueError as e:
        assert "symbol is required" in str(e), f"Error should mention symbol: {e}"

    # Invalid leverage
    try:
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h", leverage=0.5)
        assert False, "Should raise ValueError for leverage < 1"
    except ValueError as e:
        assert "leverage must be between 1 and 100" in str(e), f"Error should mention leverage range: {e}"

    # Invalid fee_rate
    try:
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h", fee_rate=0.2)
        assert False, "Should raise ValueError for fee_rate > 0.1"
    except ValueError as e:
        assert "fee_rate must be between 0 and 0.1" in str(e), f"Error should mention fee_rate range: {e}"

    print("OK test_run_config_validation passed")


def test_load_configs_from_yaml():
    """Test loading configs from YAML file"""
    # Create a temporary YAML file
    import tempfile
    yaml_content = """
runs:
  - strategy: simple_sma
    symbol: BTCUSDT
    timeframe: 1h_test
    initial_cash: 10000

  - strategy: simple_sma
    symbol: BTCUSDT
    timeframe: 1h_test
    leverage: 2.0
    stop_loss_pct: 0.02
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        # Load configs
        configs = load_configs_from_yaml(yaml_path)

        assert len(configs) == 2, f"Should load 2 configs, got {len(configs)}"
        assert configs[0].strategy == "simple_sma", "First config strategy should be simple_sma"
        assert configs[0].initial_cash == 10000, "First config initial_cash should be 10000"
        assert configs[1].leverage == 2.0, "Second config leverage should be 2.0"
        assert configs[1].stop_loss_pct == 0.02, "Second config stop_loss_pct should be 0.02"

        print("OK test_load_configs_from_yaml passed")

    finally:
        # Clean up
        os.remove(yaml_path)


def test_position_sizer_config():
    """Test position sizer configuration"""
    # Test AllInSizer (default)
    config1 = RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h")
    sizer1 = _build_position_sizer(config1)
    assert isinstance(sizer1, AllInSizer), "Default should be AllInSizer"

    # Test FixedCashSizer
    config2 = RunConfig(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h",
        position_sizer={"type": "FixedCashSizer", "cash_amount": 5000}
    )
    sizer2 = _build_position_sizer(config2)
    assert isinstance(sizer2, FixedCashSizer), "Should be FixedCashSizer"
    assert sizer2.cash_amount == 5000, "Cash amount should be 5000"

    # Test PercentOfEquitySizer
    config3 = RunConfig(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h",
        position_sizer={"type": "PercentOfEquitySizer", "percent": 0.5}
    )
    sizer3 = _build_position_sizer(config3)
    assert isinstance(sizer3, PercentOfEquitySizer), "Should be PercentOfEquitySizer"
    assert sizer3.percent == 0.5, "Percent should be 0.5"

    # Test invalid type
    config4 = RunConfig(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h",
        position_sizer={"type": "InvalidSizer"}
    )
    try:
        _build_position_sizer(config4)
        assert False, "Should raise ValueError for invalid sizer type"
    except ValueError as e:
        assert "Unknown position sizer type" in str(e), f"Error should mention unknown type: {e}"

    print("OK test_position_sizer_config passed")


# === Main Test Runner ===

if __name__ == "__main__":
    print("Running Portfolio Runner v0.3 Tests...")
    print("=" * 60)

    try:
        # Core tests (5)
        test_run_single_backtest_success()
        test_run_single_backtest_strategy_not_found()
        test_run_single_backtest_data_not_found()
        test_run_multiple_backtests()
        test_run_portfolio_with_failures()

        # Result object tests (4)
        test_portfolio_result_to_dataframe()
        test_portfolio_result_get_best_by()
        test_portfolio_result_filter()
        test_single_run_result_get_metrics()

        # Config tests (3)
        test_run_config_validation()
        test_load_configs_from_yaml()
        test_position_sizer_config()

        print("\n" + "=" * 60)
        print("SUCCESS All 12 Portfolio Runner tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nFAIL Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR Error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
