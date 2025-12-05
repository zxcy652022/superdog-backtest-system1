# -*- coding: utf-8 -*-
"""Tests for Text Reporter v0.3

Design Reference: docs/specs/planned/v0.3_text_reporter_spec.md
"""

import sys
import os
sys.path.append(os.path.abspath("."))

import pandas as pd
import numpy as np

from backtest.engine import BacktestResult
from backtest.broker import Trade
from execution_engine.portfolio_runner import RunConfig, SingleRunResult, PortfolioResult
from reports.text_reporter import (
    render_single,
    render_portfolio,
    _format_exit_reason,
)


# === Helpers ===

def _make_equity_curve(values, start="2024-01-01"):
    """Create equity curve series"""
    dates = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=dates)


def _make_trade(entry, exit, qty=1.0, pnl=100.0, ret=0.1):
    return Trade(
        entry_time=pd.Timestamp(entry),
        exit_time=pd.Timestamp(exit),
        entry_price=100,
        exit_price=110,
        qty=qty,
        pnl=pnl,
        return_pct=ret,
        direction="long",
        leverage=1.0,
    )


def _basic_metrics():
    return {
        "total_return": 0.1892,
        "max_drawdown": -0.0834,
        "num_trades": 47,
        "win_rate": 0.5957,
        "avg_trade_return": 0.01,
        "total_pnl": 1892.45,
        "avg_pnl": 40.24,
        "profit_factor": 1.67,
        "avg_win": 124.56,
        "avg_loss": -67.89,
        "win_loss_ratio": 1.83,
        "expectancy": 40.24,
        "max_consecutive_win": 6,
        "max_consecutive_loss": 4,
    }


def _build_result(with_trades=True):
    eq = _make_equity_curve([10000, 10200, 11892.45])
    trades = []
    trade_log = pd.DataFrame()
    metrics = _basic_metrics()

    if with_trades:
        trades = [
            _make_trade("2024-02-25", "2024-02-26", pnl=170.0, ret=0.017),
            _make_trade("2024-02-26", "2024-02-27", pnl=-213.0, ret=-0.0213),
            _make_trade("2024-02-27", "2024-02-28", pnl=244.0, ret=0.0244),
        ]
        trade_log = pd.DataFrame(
            [
                {
                    "entry_time": pd.Timestamp("2024-02-25"),
                    "exit_time": pd.Timestamp("2024-02-26"),
                    "entry_price": 51234,
                    "exit_price": 52108,
                    "pnl": 170.0,
                    "pnl_pct": 0.017,
                    "exit_reason": "take_profit",
                },
                {
                    "entry_time": pd.Timestamp("2024-02-26"),
                    "exit_time": pd.Timestamp("2024-02-27"),
                    "entry_price": 52345,
                    "exit_price": 51230,
                    "pnl": -213.0,
                    "pnl_pct": -0.0213,
                    "exit_reason": "stop_loss",
                },
                {
                    "entry_time": pd.Timestamp("2024-02-27"),
                    "exit_time": pd.Timestamp("2024-02-28"),
                    "entry_price": 51100,
                    "exit_price": 52345,
                    "pnl": 244.0,
                    "pnl_pct": 0.0244,
                    "exit_reason": "strategy_signal",
                },
            ]
        )

    return BacktestResult(
        equity_curve=eq,
        trades=trades,
        metrics=metrics,
        trade_log=trade_log,
    )


# === Tests ===

def test_render_single_basic():
    """Test basic single strategy report rendering"""
    result = _build_result()
    report = render_single(result)

    assert "BACKTEST REPORT" in report
    assert "PERFORMANCE SUMMARY" in report
    assert "TRADE STATISTICS" in report
    assert "RISK METRICS" in report
    assert "RECENT TRADES" in report
    assert "+18.92%" in report  # total return

    print("OK test_render_single_basic passed")


def test_render_single_with_config():
    """Test single strategy report with config"""
    result = _build_result()
    config = RunConfig(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h",
        initial_cash=10000,
        fee_rate=0.0005,
        leverage=1.0,
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
    )

    report = render_single(result, config=config, show_recent_trades=2)
    assert "Strategy          : simple_sma" in report
    assert "Symbol            : BTCUSDT" in report
    assert "Timeframe         : 1h" in report
    assert "Stop Loss         : 2.00%" in report
    assert "Take Profit       : 5.00%" in report
    assert "RECENT TRADES (Last 2)" in report

    print("OK test_render_single_with_config passed")


def test_render_portfolio_success_only():
    """Test portfolio report with only successful runs"""
    run = SingleRunResult(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h",
        config=RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h"),
        success=True,
        backtest_result=_build_result(),
        error=None,
        execution_time=1.0,
    )
    portfolio = PortfolioResult(runs=[run], total_time=1.0)
    report = render_portfolio(portfolio)

    assert "PORTFOLIO BACKTEST REPORT" in report
    assert "RANKING TABLE" in report
    assert "simple_sma" in report
    assert "✓" in report

    print("OK test_render_portfolio_success_only passed")


def test_render_portfolio_with_failures():
    """Test portfolio report with mixed success/failure"""
    success_run = SingleRunResult(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h",
        config=RunConfig(strategy="simple_sma", symbol="BTCUSDT", timeframe="1h"),
        success=True,
        backtest_result=_build_result(),
        error=None,
        execution_time=1.0,
    )
    failed_run = SingleRunResult(
        strategy="invalid",
        symbol="BTCUSDT",
        timeframe="1h",
        config=RunConfig(strategy="invalid", symbol="BTCUSDT", timeframe="1h"),
        success=False,
        backtest_result=None,
        error="Strategy not found: invalid",
        execution_time=0.5,
    )
    portfolio = PortfolioResult(runs=[success_run, failed_run], total_time=1.5)
    report = render_portfolio(portfolio, show_failed=True)

    assert "FAILED RUNS" in report
    assert "Strategy not found" in report
    assert "✗" in report

    print("OK test_render_portfolio_with_failures passed")


def test_render_portfolio_sorting():
    """Test portfolio report sorting"""
    better = SingleRunResult(
        strategy="better",
        symbol="BTCUSDT",
        timeframe="1h",
        config=RunConfig(strategy="better", symbol="BTCUSDT", timeframe="1h"),
        success=True,
        backtest_result=_build_result(),
        error=None,
        execution_time=0.8,
    )
    worse_metrics = _basic_metrics()
    worse_metrics["total_return"] = 0.05
    worse_result = BacktestResult(
        equity_curve=_make_equity_curve([10000, 10500]),
        trades=[],
        metrics=worse_metrics,
        trade_log=pd.DataFrame(),
    )
    worse = SingleRunResult(
        strategy="worse",
        symbol="BTCUSDT",
        timeframe="1h",
        config=RunConfig(strategy="worse", symbol="BTCUSDT", timeframe="1h"),
        success=True,
        backtest_result=worse_result,
        error=None,
        execution_time=1.2,
    )
    portfolio = PortfolioResult(runs=[worse, better], total_time=2.0)
    report = render_portfolio(portfolio, sort_by="total_return")

    first_line = [line for line in report.splitlines() if line.strip().startswith("│ 1")][0]
    assert "better" in first_line, "Higher return should rank first"

    print("OK test_render_portfolio_sorting passed")


def test_render_single_zero_trades():
    """Edge case: no trades should not crash"""
    result = _build_result(with_trades=False)
    result.metrics["num_trades"] = 0
    result.metrics["win_rate"] = 0.0
    report = render_single(result)

    assert "Total Trades      : 0" in report
    assert "Winning Trades    : 0 (0.00%)" in report

    print("OK test_render_single_zero_trades passed")


def test_render_single_all_wins():
    """Edge case: 100% win rate should show PF as ∞"""
    result = _build_result()
    result.metrics["profit_factor"] = float("inf")
    result.metrics["win_rate"] = 1.0
    result.metrics["num_trades"] = 3
    report = render_single(result)

    assert "Profit Factor     : ∞" in report
    assert "Winning Trades    : 3 (100.00%)" in report

    print("OK test_render_single_all_wins passed")


def test_format_large_numbers():
    """Test formatting of large numbers and percentages"""
    result = _build_result()
    result.metrics["total_return"] = 12.3456
    result.metrics["max_drawdown"] = -0.1234
    report = render_single(result)

    assert "+1234.56%" in report  # total return formatted with sign and two decimals
    assert "-12.34%" in report
    assert "10,000.00" in report

    print("OK test_format_large_numbers passed")


def test_format_exit_reason():
    """Ensure exit reason formatting matches mapping"""
    assert _format_exit_reason("stop_loss") == "SL"
    assert _format_exit_reason("take_profit") == "TP"
    assert _format_exit_reason("strategy_signal") == "Signal"
    assert _format_exit_reason("custom") == "custom"

    print("OK test_format_exit_reason passed")


if __name__ == "__main__":
    test_render_single_basic()
    test_render_single_with_config()
    test_render_portfolio_success_only()
    test_render_portfolio_with_failures()
    test_render_portfolio_sorting()
    test_render_single_zero_trades()
    test_render_single_all_wins()
    test_format_large_numbers()
    test_format_exit_reason()
    print("SUCCESS all text reporter tests passed!")
