# -*- coding: utf-8 -*-
"""CLI tests for v0.3"""

import sys
import os
import tempfile
import json
sys.path.append(os.path.abspath("."))

from click.testing import CliRunner
from cli.main import cli


def _make_temp_yaml(runs):
    """Create temp YAML file for portfolio tests"""
    import yaml

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".yml")
    with open(tmp.name, "w", encoding="utf-8") as f:
        yaml.safe_dump({"runs": runs}, f)
    return tmp.name


def test_cli_run_success():
    """Test CLI run command with valid arguments"""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "run",
        "-s", "simple_sma",
        "-m", "BTCUSDT",
        "-t", "1h_test"
    ])

    assert result.exit_code == 0, result.output
    assert "BACKTEST REPORT" in result.output

    print("OK test_cli_run_success passed")


def test_cli_run_invalid_strategy():
    """Test CLI run with invalid strategy"""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "run",
        "-s", "invalid",
        "-m", "BTCUSDT",
        "-t", "1h_test"
    ])

    assert result.exit_code != 0
    assert "Error" in result.output

    print("OK test_cli_run_invalid_strategy passed")


def test_cli_portfolio_success():
    """Test CLI portfolio command"""
    yaml_path = _make_temp_yaml([
        {
            "strategy": "simple_sma",
            "symbol": "BTCUSDT",
            "timeframe": "1h_test",
        }
    ])
    runner = CliRunner()
    result = runner.invoke(cli, ["portfolio", "-c", yaml_path])

    assert result.exit_code == 0, result.output
    assert "PORTFOLIO BACKTEST REPORT" in result.output
    assert "simple_sma" in result.output

    print("OK test_cli_portfolio_success passed")


def test_cli_list_strategies():
    """Test CLI list command"""
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])

    assert result.exit_code == 0
    assert "simple_sma" in result.output

    print("OK test_cli_list_strategies passed")


def test_cli_output_to_file():
    """Test CLI output redirection"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "report.txt")
        runner = CliRunner()
        result = runner.invoke(cli, [
            "run",
            "-s", "simple_sma",
            "-m", "BTCUSDT",
            "-t", "1h_test",
            "-o", output_path
        ])

        assert result.exit_code == 0, result.output
        assert os.path.exists(output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "BACKTEST REPORT" in content

    print("OK test_cli_output_to_file passed")


if __name__ == "__main__":
    test_cli_run_success()
    test_cli_run_invalid_strategy()
    test_cli_portfolio_success()
    test_cli_list_strategies()
    test_cli_output_to_file()
    print("SUCCESS all CLI v0.3 tests passed!")
