# -*- coding: utf-8 -*-
"""Integration tests for SuperDog Backtest v0.3"""

import sys
import os
import tempfile
sys.path.append(os.path.abspath("."))

import yaml
from click.testing import CliRunner

from data.storage import load_ohlcv
from strategies.registry import get_strategy
from backtest.engine import run_backtest
from reports.text_reporter import render_single, render_portfolio
from execution_engine.portfolio_runner import (
    RunConfig,
    run_portfolio,
    load_configs_from_yaml,
    PortfolioResult,
)
from cli.main import cli


def _load_sample_data():
    return load_ohlcv("data/raw/BTCUSDT_1h_test.csv")


def test_e2e_single_backtest():
    """
    End-to-end test: Single backtest workflow
    """
    data = _load_sample_data()
    strategy_cls = get_strategy("simple_sma")
    result = run_backtest(data, strategy_cls)

    report = render_single(result, config=RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test"))
    assert "BACKTEST REPORT" in report
    assert "PERFORMANCE SUMMARY" in report

    print("OK test_e2e_single_backtest passed")


def test_e2e_portfolio_backtest():
    """
    End-to-end test: Portfolio backtest workflow
    """
    configs = [
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test"),
        RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h_test", leverage=2.0),
    ]
    result = run_portfolio(configs)
    report = render_portfolio(result)

    assert isinstance(result, PortfolioResult)
    assert "PORTFOLIO BACKTEST REPORT" in report
    assert "RANKING TABLE" in report

    print("OK test_e2e_portfolio_backtest passed")


def test_e2e_yaml_to_report():
    """
    End-to-end test: YAML config to report
    """
    runs = [
        {"strategy": "simple_sma", "symbol": "BTCUSDT", "timeframe": "1h_test"},
    ]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".yml") as tmp:
        yaml_path = tmp.name

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"runs": runs}, f, allow_unicode=True)

    configs = load_configs_from_yaml(yaml_path)
    result = run_portfolio(configs)
    report = render_portfolio(result)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as outf:
        outf.write(report.encode("utf-8"))
        output_path = outf.name

    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PORTFOLIO BACKTEST REPORT" in content

    print("OK test_e2e_yaml_to_report passed")


def test_e2e_cli_workflow():
    """
    End-to-end test: CLI workflow
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "-s", "simple_sma", "-m", "BTCUSDT", "-t", "1h_test"])

    assert result.exit_code == 0, result.output
    assert "BACKTEST REPORT" in result.output

    print("OK test_e2e_cli_workflow passed")


def test_backward_compatibility_v02():
    """
    Test backward compatibility with v0.2
    """
    import tests.test_backtest_v02 as v02_tests
    import inspect

    test_funcs = [
        getattr(v02_tests, name)
        for name in dir(v02_tests)
        if name.startswith("test_") and callable(getattr(v02_tests, name))
    ]

    for fn in test_funcs:
        fn()

    print("OK test_backward_compatibility_v02 passed")


if __name__ == "__main__":
    test_e2e_single_backtest()
    test_e2e_portfolio_backtest()
    test_e2e_yaml_to_report()
    test_e2e_cli_workflow()
    test_backward_compatibility_v02()
    print("SUCCESS all integration v0.3 tests passed!")
