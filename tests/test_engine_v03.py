# -*- coding: utf-8 -*-
"""Tests for Engine v0.3 (Direction-aware SL/TP and Leverage)

Design Reference: docs/specs/planned/v0.3_test_plan.md §3
"""

import sys
import os
sys.path.append(os.path.abspath("."))

import pandas as pd
import numpy as np
from backtest.broker import SimulatedBroker
from backtest.engine import _check_sl_tp, run_backtest, BaseStrategy


# === Helper: Create test strategies ===

class SimpleLongStrategy(BaseStrategy):
    """Simple strategy that opens a long position on first bar"""
    def on_bar(self, i: int, row: pd.Series):
        if i == 10 and not self.broker.has_position:
            self.broker.buy_all(price=row['close'], time=row.name)


class SimpleShortStrategy(BaseStrategy):
    """Simple strategy that opens a short position on first bar"""
    def on_bar(self, i: int, row: pd.Series):
        if i == 10 and not self.broker.has_position:
            # Calculate size for short position
            equity = self.broker.get_current_equity(row['close'])
            size = equity / (row['close'] * (1 + 0.0005))  # Same as AllInSizer
            self.broker.sell(size=size, price=row['close'], time=row.name)


# === Helper: Create test data ===

def create_test_data_with_drop(num_bars=50, start_price=100, drop_pct=0.05):
    """Create price data that drops by drop_pct"""
    dates = pd.date_range(start='2024-01-01', periods=num_bars, freq='h')

    # First 10 bars: stable at start_price
    # Bar 11: entry bar
    # Bar 12-20: gradual drop to trigger SL
    prices = [start_price] * 11

    # Gradual drop
    for i in range(11, num_bars):
        if i < 20:
            prices.append(start_price * (1 - drop_pct * (i - 11) / 9))
        else:
            prices.append(start_price * (1 - drop_pct))

    data = pd.DataFrame({
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': [1000] * num_bars
    }, index=dates)

    return data


def create_test_data_with_rise(num_bars=50, start_price=100, rise_pct=0.06):
    """Create price data that rises by rise_pct"""
    dates = pd.date_range(start='2024-01-01', periods=num_bars, freq='h')

    # First 10 bars: stable
    # Bar 11: entry
    # Bar 12-20: gradual rise to trigger TP
    prices = [start_price] * 11

    for i in range(11, num_bars):
        if i < 20:
            prices.append(start_price * (1 + rise_pct * (i - 11) / 9))
        else:
            prices.append(start_price * (1 + rise_pct))

    data = pd.DataFrame({
        'open': prices,
        'high': [p * 1.01 for p in prices],
        'low': [p * 0.99 for p in prices],
        'close': prices,
        'volume': [1000] * num_bars
    }, index=dates)

    return data


# === Core Functionality Tests (8 tests) ===

def test_check_sl_tp_long_stop_loss():
    """Test _check_sl_tp for long position stop loss"""
    # Long position: entry=100, SL=2% → SL price=98
    # Row with low=95 should trigger SL
    row = pd.Series({'low': 95, 'high': 105, 'close': 100})

    sl, tp, price, reason = _check_sl_tp(
        row=row,
        entry_price=100,
        direction="long",
        stop_loss_pct=0.02,
        take_profit_pct=None
    )

    assert sl == True, "SL should be triggered"
    assert tp == False, "TP should not be triggered"
    assert price == 98, f"Exit price should be 98, got {price}"
    assert reason == "stop_loss", f"Exit reason should be 'stop_loss', got {reason}"

    print("OK test_check_sl_tp_long_stop_loss passed")


def test_check_sl_tp_long_take_profit():
    """Test _check_sl_tp for long position take profit"""
    # Long position: entry=100, TP=5% → TP price=105
    # Row with high=106 should trigger TP
    row = pd.Series({'low': 95, 'high': 106, 'close': 100})

    sl, tp, price, reason = _check_sl_tp(
        row=row,
        entry_price=100,
        direction="long",
        stop_loss_pct=None,
        take_profit_pct=0.05
    )

    assert sl == False, "SL should not be triggered"
    assert tp == True, "TP should be triggered"
    assert price == 105, f"Exit price should be 105, got {price}"
    assert reason == "take_profit", f"Exit reason should be 'take_profit', got {reason}"

    print("OK test_check_sl_tp_long_take_profit passed")


def test_check_sl_tp_long_sl_priority():
    """Test that SL has priority over TP for long positions"""
    # Both SL and TP triggered in same bar → SL should win
    row = pd.Series({'low': 95, 'high': 106, 'close': 100})

    sl, tp, price, reason = _check_sl_tp(
        row=row,
        entry_price=100,
        direction="long",
        stop_loss_pct=0.02,  # SL=98
        take_profit_pct=0.05  # TP=105
    )

    assert sl == True, "SL should be triggered"
    assert tp == False, "TP should not be triggered (SL priority)"
    assert reason == "stop_loss", f"Exit reason should be 'stop_loss', got {reason}"

    print("OK test_check_sl_tp_long_sl_priority passed")


def test_check_sl_tp_short_stop_loss():
    """Test _check_sl_tp for short position stop loss"""
    # Short position: entry=100, SL=2% → SL price=102 (price rises)
    # Row with high=103 should trigger SL
    row = pd.Series({'low': 95, 'high': 103, 'close': 100})

    sl, tp, price, reason = _check_sl_tp(
        row=row,
        entry_price=100,
        direction="short",
        stop_loss_pct=0.02,
        take_profit_pct=None
    )

    assert sl == True, "SL should be triggered"
    assert tp == False, "TP should not be triggered"
    assert price == 102, f"Exit price should be 102, got {price}"
    assert reason == "stop_loss", f"Exit reason should be 'stop_loss', got {reason}"

    print("OK test_check_sl_tp_short_stop_loss passed")


def test_check_sl_tp_short_take_profit():
    """Test _check_sl_tp for short position take profit"""
    # Short position: entry=100, TP=5% → TP price=95 (price drops)
    # Row with low=94 should trigger TP
    row = pd.Series({'low': 94, 'high': 105, 'close': 100})

    sl, tp, price, reason = _check_sl_tp(
        row=row,
        entry_price=100,
        direction="short",
        stop_loss_pct=None,
        take_profit_pct=0.05
    )

    assert sl == False, "SL should not be triggered"
    assert tp == True, "TP should be triggered"
    assert price == 95, f"Exit price should be 95, got {price}"
    assert reason == "take_profit", f"Exit reason should be 'take_profit', got {reason}"

    print("OK test_check_sl_tp_short_take_profit passed")


def test_check_sl_tp_short_sl_priority():
    """Test that SL has priority over TP for short positions"""
    # Both SL and TP triggered → SL should win
    row = pd.Series({'low': 94, 'high': 103, 'close': 100})

    sl, tp, price, reason = _check_sl_tp(
        row=row,
        entry_price=100,
        direction="short",
        stop_loss_pct=0.02,  # SL=102
        take_profit_pct=0.05  # TP=95
    )

    assert sl == True, "SL should be triggered"
    assert tp == False, "TP should not be triggered (SL priority)"
    assert reason == "stop_loss", f"Exit reason should be 'stop_loss', got {reason}"

    print("OK test_check_sl_tp_short_sl_priority passed")


def test_long_sl_in_backtest():
    """Test long position SL triggered in actual backtest"""
    data = create_test_data_with_drop(num_bars=50, start_price=100, drop_pct=0.05)

    result = run_backtest(
        data=data,
        strategy_cls=SimpleLongStrategy,
        initial_cash=10000,
        stop_loss_pct=0.02  # 2% SL
    )

    # Verify at least one SL trade
    assert result.trade_log is not None, "Trade log should not be None"
    sl_trades = result.trade_log[result.trade_log['exit_reason'] == 'stop_loss']
    assert len(sl_trades) > 0, f"Expected at least 1 SL trade, got {len(sl_trades)}"

    # Verify direction is long
    assert result.trades[0].direction == "long", "First trade should be long"

    print(f"OK test_long_sl_in_backtest passed (found {len(sl_trades)} SL trades)")


def test_short_sl_in_backtest():
    """Test short position SL triggered in actual backtest"""
    # Price rises → short position loses money → SL triggered
    data = create_test_data_with_rise(num_bars=50, start_price=100, rise_pct=0.06)

    result = run_backtest(
        data=data,
        strategy_cls=SimpleShortStrategy,
        initial_cash=10000,
        stop_loss_pct=0.02  # 2% SL (price rises 2%)
    )

    # Verify at least one SL trade
    assert result.trade_log is not None, "Trade log should not be None"
    sl_trades = result.trade_log[result.trade_log['exit_reason'] == 'stop_loss']
    assert len(sl_trades) > 0, f"Expected at least 1 SL trade, got {len(sl_trades)}"

    # Verify direction is short
    assert result.trades[0].direction == "short", "First trade should be short"

    print(f"OK test_short_sl_in_backtest passed (found {len(sl_trades)} SL trades)")


# === Integration Tests (2 tests) ===

def test_leverage_parameter_passed_to_broker():
    """Test that leverage parameter is correctly passed to broker"""
    data = create_test_data_with_rise(num_bars=30, start_price=100, rise_pct=0.03)

    result = run_backtest(
        data=data,
        strategy_cls=SimpleLongStrategy,
        initial_cash=10000,
        leverage=5.0,  # 5x leverage
        take_profit_pct=0.02  # Add TP to close the position
    )

    # Verify trade was made with leverage
    assert len(result.trades) > 0, "Should have at least 1 trade"
    trade = result.trades[0]
    assert trade.leverage == 5.0, f"Trade leverage should be 5.0, got {trade.leverage}"

    print("OK test_leverage_parameter_passed_to_broker passed")


def test_sl_tp_work_with_leverage():
    """Test that SL/TP work correctly with leverage"""
    data = create_test_data_with_drop(num_bars=50, start_price=100, drop_pct=0.05)

    result = run_backtest(
        data=data,
        strategy_cls=SimpleLongStrategy,
        initial_cash=10000,
        leverage=3.0,
        stop_loss_pct=0.02
    )

    # Should have SL triggered
    sl_trades = result.trade_log[result.trade_log['exit_reason'] == 'stop_loss']
    assert len(sl_trades) > 0, "Should have SL trades with leverage"

    # Verify leverage is recorded
    assert result.trades[0].leverage == 3.0, "Leverage should be 3.0"

    print("OK test_sl_tp_work_with_leverage passed")


# === Main Test Runner ===

if __name__ == "__main__":
    print("Running Engine v0.3 Tests (Direction-aware SL/TP)...")
    print("=" * 60)

    try:
        # Core functionality tests (8)
        test_check_sl_tp_long_stop_loss()
        test_check_sl_tp_long_take_profit()
        test_check_sl_tp_long_sl_priority()
        test_check_sl_tp_short_stop_loss()
        test_check_sl_tp_short_take_profit()
        test_check_sl_tp_short_sl_priority()
        test_long_sl_in_backtest()
        test_short_sl_in_backtest()

        # Integration tests (2)
        test_leverage_parameter_passed_to_broker()
        test_sl_tp_work_with_leverage()

        print("\n" + "=" * 60)
        print("SUCCESS All 10 Engine v0.3 tests passed!")
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
