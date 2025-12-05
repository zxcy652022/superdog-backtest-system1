# -*- coding: utf-8 -*-
"""Tests for Broker v0.3 (Short Selling & Leverage)

Design Reference: docs/specs/planned/v0.3_test_plan.md §2
"""

import sys
import os
sys.path.append(os.path.abspath("."))

import pandas as pd
from backtest.broker import SimulatedBroker, Trade


# === Test Fixtures ===

def create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0):
    """Create a broker instance for testing"""
    return SimulatedBroker(
        initial_cash=initial_cash,
        fee_rate=fee_rate,
        leverage=leverage
    )


def get_time(s: str) -> pd.Timestamp:
    """Helper to create timestamps"""
    return pd.Timestamp(s)


# === Core Functionality Tests (15 tests) ===

def test_leverage_validation():
    """Test leverage validation in __init__"""
    # Valid leverage
    broker = create_broker(leverage=1.0)
    assert broker.leverage == 1.0, "Leverage should be 1.0"

    broker = create_broker(leverage=10.0)
    assert broker.leverage == 10.0, "Leverage should be 10.0"

    broker = create_broker(leverage=100.0)
    assert broker.leverage == 100.0, "Leverage should be 100.0"

    # Invalid leverage < 1
    try:
        create_broker(leverage=0.5)
        assert False, "Should raise ValueError for leverage < 1"
    except ValueError as e:
        assert "between 1 and 100" in str(e), f"Error message should mention range: {e}"

    # Invalid leverage > 100
    try:
        create_broker(leverage=101)
        assert False, "Should raise ValueError for leverage > 100"
    except ValueError as e:
        assert "between 1 and 100" in str(e), f"Error message should mention range: {e}"

    print("OK test_leverage_validation passed")


def test_open_long_no_leverage():
    """Test opening long position without leverage"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open long: buy 10 units at $100
    success = broker.buy(size=10, price=100, time=get_time("2023-01-01"))

    assert success, "Buy should succeed"
    assert broker.has_position, "Should have position"
    assert broker.is_long, "Should be long"
    assert not broker.is_short, "Should not be short"
    assert broker.position_direction == "long", "Direction should be 'long'"
    assert broker.position_qty == 10, f"Position qty should be 10, got {broker.position_qty}"
    assert broker.position_entry_price == 100, f"Entry price should be 100, got {broker.position_entry_price}"

    # Cash calculation: position_value=1000, fee=1, required=1001
    expected_cash = 10000 - 1001
    assert abs(broker.cash - expected_cash) < 0.01, f"Cash should be {expected_cash}, got {broker.cash}"

    print("OK test_open_long_no_leverage passed")


def test_open_long_with_leverage():
    """Test opening long position with 10x leverage"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=10.0)

    # Open long: buy 100 units at $100 (position_value=10000)
    # With 10x leverage: margin = 10000/10 = 1000, fee = 10, total = 1010
    success = broker.buy(size=100, price=100, time=get_time("2023-01-01"))

    assert success, "Buy should succeed with leverage"
    assert broker.is_long, "Should be long"
    assert broker.position_qty == 100, f"Position qty should be 100, got {broker.position_qty}"

    # Cash: 10000 - 1010 = 8990
    expected_cash = 10000 - 1010
    assert abs(broker.cash - expected_cash) < 0.01, f"Cash should be {expected_cash}, got {broker.cash}"

    print("OK test_open_long_with_leverage passed")


def test_close_long_with_profit():
    """Test closing long position with profit"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open long
    broker.buy(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Close long at higher price: sell 10 units at $110
    success = broker.sell(size=10, price=110, time=get_time("2023-01-01 11:00"))

    assert success, "Sell should succeed"
    assert not broker.has_position, "Should not have position"
    assert broker.position_direction == "flat", "Direction should be 'flat'"

    # PnL calculation:
    # Entry cost: 10 * 100 = 1000, entry fee: 1
    # Exit revenue: 10 * 110 = 1100, exit fee: 1.1, net revenue: 1098.9
    # PnL: 1098.9 - 1000 = 98.9
    assert len(broker.trades) == 1, f"Should have 1 trade, got {len(broker.trades)}"
    trade = broker.trades[0]
    assert abs(trade.pnl - 98.9) < 0.01, f"PnL should be 98.9, got {trade.pnl}"
    assert trade.direction == "long", f"Direction should be 'long', got {trade.direction}"
    assert abs(trade.return_pct - 0.1) < 0.001, f"Return pct should be 0.1, got {trade.return_pct}"

    # Cash calculation:
    # Initial: 10000
    # Open: 10000 - (1000/1) - 1 = 8999
    # Close: 8999 + (1000/1) + (1100 - 1.1) = 8999 + 1000 + 1098.9 = 11097.9
    # Net result: 10000 + PnL = 10000 + 98.9 = 10098.9 (approximately, with rounding)
    expected_cash = 11097.9
    assert abs(broker.cash - expected_cash) < 0.01, f"Cash should be {expected_cash}, got {broker.cash}"

    print("OK test_close_long_with_profit passed")


def test_close_long_with_loss():
    """Test closing long position with loss"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open long
    broker.buy(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Close long at lower price: sell 10 units at $90
    success = broker.sell(size=10, price=90, time=get_time("2023-01-01 11:00"))

    assert success, "Sell should succeed"
    assert not broker.has_position, "Should not have position"

    # PnL calculation:
    # Entry cost: 1000
    # Exit revenue: 10 * 90 = 900, fee: 0.9, net: 899.1
    # PnL: 899.1 - 1000 = -100.9
    trade = broker.trades[0]
    assert trade.pnl < 0, f"PnL should be negative, got {trade.pnl}"
    assert abs(trade.pnl - (-100.9)) < 0.01, f"PnL should be -100.9, got {trade.pnl}"

    print("OK test_close_long_with_loss passed")


def test_open_short_no_leverage():
    """Test opening short position without leverage"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open short: sell 10 units at $100
    success = broker.sell(size=10, price=100, time=get_time("2023-01-01"))

    assert success, "Sell should succeed"
    assert broker.has_position, "Should have position"
    assert broker.is_short, "Should be short"
    assert not broker.is_long, "Should not be long"
    assert broker.position_direction == "short", "Direction should be 'short'"
    assert broker.position_qty == 10, f"Position qty should be 10, got {broker.position_qty}"
    assert broker.position_entry_price == 100, f"Entry price should be 100, got {broker.position_entry_price}"

    # Cash: 10000 - margin - fee = 10000 - 1000 - 1 = 8999
    expected_cash = 10000 - 1001
    assert abs(broker.cash - expected_cash) < 0.01, f"Cash should be {expected_cash}, got {broker.cash}"

    print("OK test_open_short_no_leverage passed")


def test_open_short_with_leverage():
    """Test opening short position with 5x leverage"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=5.0)

    # Open short: sell 50 units at $100 (position_value=5000)
    # With 5x leverage: margin = 5000/5 = 1000, fee = 5, total = 1005
    success = broker.sell(size=50, price=100, time=get_time("2023-01-01"))

    assert success, "Sell should succeed with leverage"
    assert broker.is_short, "Should be short"
    assert broker.position_qty == 50, f"Position qty should be 50, got {broker.position_qty}"

    # Cash: 10000 - 1005 = 8995
    expected_cash = 10000 - 1005
    assert abs(broker.cash - expected_cash) < 0.01, f"Cash should be {expected_cash}, got {broker.cash}"

    print("OK test_open_short_with_leverage passed")


def test_close_short_with_profit():
    """Test closing short position with profit (price drops)"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open short at $100
    broker.sell(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Close short at lower price: buy 10 units at $90 (profit from price drop)
    success = broker.buy(size=10, price=90, time=get_time("2023-01-01 11:00"))

    assert success, "Buy should succeed"
    assert not broker.has_position, "Should not have position"
    assert broker.position_direction == "flat", "Direction should be 'flat'"

    # PnL calculation:
    # Entry revenue (theoretical): 10 * 100 = 1000
    # Exit cost: 10 * 90 = 900, fee: 0.9, total cost: 900.9
    # PnL: 1000 - 900 - 0.9 = 99.1
    trade = broker.trades[0]
    assert trade.pnl > 0, f"PnL should be positive, got {trade.pnl}"
    assert abs(trade.pnl - 99.1) < 0.01, f"PnL should be 99.1, got {trade.pnl}"
    assert trade.direction == "short", f"Direction should be 'short', got {trade.direction}"
    assert abs(trade.return_pct - 0.1) < 0.001, f"Return pct should be 0.1, got {trade.return_pct}"

    print("OK test_close_short_with_profit passed")


def test_close_short_with_loss():
    """Test closing short position with loss (price rises)"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open short at $100
    broker.sell(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Close short at higher price: buy 10 units at $110 (loss from price rise)
    success = broker.buy(size=10, price=110, time=get_time("2023-01-01 11:00"))

    assert success, "Buy should succeed"
    assert not broker.has_position, "Should not have position"

    # PnL calculation:
    # Entry revenue: 1000
    # Exit cost: 10 * 110 = 1100, fee: 1.1, total: 1101.1
    # PnL: 1000 - 1100 - 1.1 = -101.1
    trade = broker.trades[0]
    assert trade.pnl < 0, f"PnL should be negative, got {trade.pnl}"
    assert abs(trade.pnl - (-101.1)) < 0.01, f"PnL should be -101.1, got {trade.pnl}"

    print("OK test_close_short_with_loss passed")


def test_partial_close_long():
    """Test partial closing of long position"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open long: 10 units at $100
    broker.buy(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Partial close: sell 6 units at $110
    success = broker.sell(size=6, price=110, time=get_time("2023-01-01 11:00"))

    assert success, "Partial sell should succeed"
    assert broker.has_position, "Should still have position"
    assert broker.is_long, "Should still be long"
    assert broker.position_qty == 4, f"Position qty should be 4, got {broker.position_qty}"

    # Should have 1 trade for the closed portion
    assert len(broker.trades) == 1, f"Should have 1 trade, got {len(broker.trades)}"
    trade = broker.trades[0]
    assert trade.qty == 6, f"Trade qty should be 6, got {trade.qty}"
    assert trade.pnl > 0, f"PnL should be positive, got {trade.pnl}"

    print("OK test_partial_close_long passed")


def test_partial_close_short():
    """Test partial closing of short position"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open short: 10 units at $100
    broker.sell(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Partial close: buy 4 units at $90
    success = broker.buy(size=4, price=90, time=get_time("2023-01-01 11:00"))

    assert success, "Partial buy should succeed"
    assert broker.has_position, "Should still have position"
    assert broker.is_short, "Should still be short"
    assert broker.position_qty == 6, f"Position qty should be 6, got {broker.position_qty}"

    # Should have 1 trade for the closed portion
    assert len(broker.trades) == 1, f"Should have 1 trade, got {len(broker.trades)}"
    trade = broker.trades[0]
    assert trade.qty == 4, f"Trade qty should be 4, got {trade.qty}"
    assert trade.direction == "short", f"Direction should be 'short', got {trade.direction}"

    print("OK test_partial_close_short passed")


def test_reject_buy_when_long():
    """Test that buy is rejected when already long (no adding to position)"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open long
    broker.buy(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Try to buy more (should fail)
    success = broker.buy(size=5, price=100, time=get_time("2023-01-01 11:00"))

    assert not success, "Should reject buy when already long"
    assert broker.position_qty == 10, f"Position qty should remain 10, got {broker.position_qty}"
    assert len(broker.trades) == 0, f"Should have no trades, got {len(broker.trades)}"

    print("OK test_reject_buy_when_long passed")


def test_reject_sell_when_short():
    """Test that sell is rejected when already short (no adding to position)"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Open short
    broker.sell(size=10, price=100, time=get_time("2023-01-01 10:00"))

    # Try to sell more (should fail)
    success = broker.sell(size=5, price=100, time=get_time("2023-01-01 11:00"))

    assert not success, "Should reject sell when already short"
    assert broker.position_qty == 10, f"Position qty should remain 10, got {broker.position_qty}"
    assert len(broker.trades) == 0, f"Should have no trades, got {len(broker.trades)}"

    print("OK test_reject_sell_when_short passed")


def test_insufficient_cash_for_long():
    """Test that long position is rejected when insufficient cash"""
    broker = create_broker(initial_cash=1000, fee_rate=0.001, leverage=1.0)

    # Try to buy 20 units at $100 (needs 2000 + fee)
    success = broker.buy(size=20, price=100, time=get_time("2023-01-01"))

    assert not success, "Should reject buy with insufficient cash"
    assert not broker.has_position, "Should not have position"
    assert broker.cash == 1000, f"Cash should remain 1000, got {broker.cash}"

    print("OK test_insufficient_cash_for_long passed")


def test_insufficient_cash_for_short():
    """Test that short position is rejected when insufficient margin"""
    broker = create_broker(initial_cash=100, fee_rate=0.001, leverage=1.0)

    # Try to short 10 units at $100 (needs margin 1000 + fee)
    success = broker.sell(size=10, price=100, time=get_time("2023-01-01"))

    assert not success, "Should reject sell with insufficient margin"
    assert not broker.has_position, "Should not have position"
    assert broker.cash == 100, f"Cash should remain 100, got {broker.cash}"

    print("OK test_insufficient_cash_for_short passed")


# === Trade Object Tests (3 tests) ===

def test_trade_direction_field():
    """Test that Trade objects have correct direction field"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Long trade
    broker.buy(size=10, price=100, time=get_time("2023-01-01 10:00"))
    broker.sell(size=10, price=110, time=get_time("2023-01-01 11:00"))

    long_trade = broker.trades[0]
    assert long_trade.direction == "long", f"Long trade direction should be 'long', got {long_trade.direction}"

    # Short trade
    broker.sell(size=10, price=100, time=get_time("2023-01-02 10:00"))
    broker.buy(size=10, price=90, time=get_time("2023-01-02 11:00"))

    short_trade = broker.trades[1]
    assert short_trade.direction == "short", f"Short trade direction should be 'short', got {short_trade.direction}"

    print("OK test_trade_direction_field passed")


def test_trade_leverage_field():
    """Test that Trade objects have correct leverage field"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=5.0)

    # Trade with 5x leverage
    broker.buy(size=10, price=100, time=get_time("2023-01-01 10:00"))
    broker.sell(size=10, price=110, time=get_time("2023-01-01 11:00"))

    trade = broker.trades[0]
    assert trade.leverage == 5.0, f"Trade leverage should be 5.0, got {trade.leverage}"

    print("OK test_trade_leverage_field passed")


def test_short_pnl_calculation():
    """Test that short PnL is calculated correctly (entry - exit)"""
    broker = create_broker(initial_cash=10000, fee_rate=0.001, leverage=1.0)

    # Short at 100, close at 90 (profit of ~10 per unit)
    broker.sell(size=10, price=100, time=get_time("2023-01-01 10:00"))
    broker.buy(size=10, price=90, time=get_time("2023-01-01 11:00"))

    trade = broker.trades[0]

    # Expected PnL: (100 - 90) * 10 - fees
    # Revenue: 1000, Cost: 900 + 0.9, PnL: 99.1
    assert abs(trade.pnl - 99.1) < 0.01, f"Short PnL should be 99.1, got {trade.pnl}"

    # Return pct: (entry - exit) / entry = (100 - 90) / 100 = 0.1
    assert abs(trade.return_pct - 0.1) < 0.001, f"Return pct should be 0.1, got {trade.return_pct}"

    print("OK test_short_pnl_calculation passed")


# === Main Test Runner ===

if __name__ == "__main__":
    print("Running Broker v0.3 Tests (Short Selling & Leverage)...")
    print("=" * 60)

    try:
        # Core functionality tests (15)
        test_leverage_validation()
        test_open_long_no_leverage()
        test_open_long_with_leverage()
        test_close_long_with_profit()
        test_close_long_with_loss()
        test_open_short_no_leverage()
        test_open_short_with_leverage()
        test_close_short_with_profit()
        test_close_short_with_loss()
        test_partial_close_long()
        test_partial_close_short()
        test_reject_buy_when_long()
        test_reject_sell_when_short()
        test_insufficient_cash_for_long()
        test_insufficient_cash_for_short()

        # Trade object tests (3)
        test_trade_direction_field()
        test_trade_leverage_field()
        test_short_pnl_calculation()

        print("\n" + "=" * 60)
        print("SUCCESS All 18 Broker v0.3 tests passed!")
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
