# -*- coding: utf-8 -*-
"""Tests for Strategy Registry (v0.3)

Design Reference: docs/specs/planned/v0.3_test_plan.md §4
"""

import sys
import os
sys.path.append(os.path.abspath("."))

from strategies.registry import (
    get_strategy,
    list_strategies,
    register_strategy,
    STRATEGY_REGISTRY
)
from backtest.engine import BaseStrategy
from strategies.simple_sma import SimpleSMAStrategy


def test_get_existing_strategy():
    """Test getting an existing strategy"""
    cls = get_strategy("simple_sma")
    assert cls == SimpleSMAStrategy, f"Expected SimpleSMAStrategy, got {cls}"
    assert issubclass(cls, BaseStrategy), "Strategy should inherit from BaseStrategy"
    print("OK test_get_existing_strategy passed")


def test_get_nonexistent_strategy():
    """Test getting a non-existent strategy"""
    try:
        get_strategy("nonexistent_strategy")
        assert False, "Should have raised KeyError"
    except KeyError as e:
        error_msg = str(e)
        assert "not found" in error_msg, f"Error message should contain 'not found': {error_msg}"
        assert "Available strategies" in error_msg, f"Error message should list available strategies: {error_msg}"
        assert "simple_sma" in error_msg, f"Error message should include 'simple_sma': {error_msg}"

    print("OK test_get_nonexistent_strategy passed")


def test_list_strategies():
    """Test listing all strategies"""
    strategies = list_strategies()

    assert isinstance(strategies, list), f"Expected list, got {type(strategies)}"
    assert len(strategies) >= 1, f"Expected at least 1 strategy, got {len(strategies)}"
    assert "simple_sma" in strategies, "'simple_sma' should be in strategies list"
    # Note: trend_follow and mean_reversion are not yet implemented (v0.3)

    # Should be sorted
    assert strategies == sorted(strategies), f"Strategies should be sorted: {strategies}"

    print(f"OK test_list_strategies passed (found {len(strategies)} strategies)")


def test_register_new_strategy():
    """Test registering a new strategy"""
    class MyTestStrategy(BaseStrategy):
        def on_bar(self, i, row):
            pass

    # Backup original registry
    original = STRATEGY_REGISTRY.copy()

    try:
        register_strategy("test_strategy", MyTestStrategy)
        assert "test_strategy" in STRATEGY_REGISTRY, "test_strategy should be in registry"
        assert get_strategy("test_strategy") == MyTestStrategy, "Should retrieve the registered strategy"

        # Verify it appears in list
        assert "test_strategy" in list_strategies(), "test_strategy should appear in list_strategies()"

        print("OK test_register_new_strategy passed")

    finally:
        # Restore original registry
        STRATEGY_REGISTRY.clear()
        STRATEGY_REGISTRY.update(original)


def test_register_duplicate_strategy():
    """Test registering a duplicate strategy name"""
    try:
        register_strategy("simple_sma", SimpleSMAStrategy)
        assert False, "Should have raised ValueError for duplicate registration"
    except ValueError as e:
        assert "already registered" in str(e), f"Error message should contain 'already registered': {e}"

    print("OK test_register_duplicate_strategy passed")


def test_register_invalid_strategy():
    """Test registering a non-BaseStrategy class"""
    class NotAStrategy:
        pass

    try:
        register_strategy("invalid", NotAStrategy)
        assert False, "Should have raised TypeError for invalid strategy class"
    except TypeError as e:
        assert "must inherit from BaseStrategy" in str(e), f"Error message should mention BaseStrategy: {e}"

    print("OK test_register_invalid_strategy passed")


# === Main Test Runner ===

if __name__ == "__main__":
    print("Running Strategy Registry v0.3 Tests...")
    print("=" * 60)

    try:
        test_get_existing_strategy()
        test_get_nonexistent_strategy()
        test_list_strategies()
        test_register_new_strategy()
        test_register_duplicate_strategy()
        test_register_invalid_strategy()

        print("\n" + "=" * 60)
        print("SUCCESS All Strategy Registry tests passed!")
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
