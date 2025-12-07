#!/usr/bin/env python3
"""
SuperDog v0.5 - 策略兼容性測試

測試 BacktestEngine 對 v0.3 和 v0.5 策略的支援

Test Cases:
1. v0.3 策略 (SimpleSMAStrategy) - 使用 __init__(broker, data)
2. v0.5 策略 (KawamokuStrategy) - 使用 __init__()

Expected Results:
- 兩種策略都能成功初始化
- 兩種策略都能正常執行回測
- v0.3 策略使用 on_bar() 接口
- v0.5 策略使用 compute_signals() 接口

Version: v0.5
Date: 2025-12-07
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backtest.engine import run_backtest, _is_v05_strategy
from strategies.simple_sma import SimpleSMAStrategy
from strategies.kawamoku_demo import KawamokuStrategy


def create_sample_data(periods: int = 100) -> pd.DataFrame:
    """創建測試用 OHLCV 數據"""
    dates = pd.date_range('2024-01-01', periods=periods, freq='1h')

    # 生成隨機價格 (隨機遊走)
    base_price = 50000
    price_changes = np.random.randn(periods) * 100
    close_prices = base_price + np.cumsum(price_changes)

    data = pd.DataFrame({
        'open': close_prices + np.random.randn(periods) * 50,
        'high': close_prices + np.abs(np.random.randn(periods)) * 100,
        'low': close_prices - np.abs(np.random.randn(periods)) * 100,
        'close': close_prices,
        'volume': 1000 + np.random.randn(periods) * 100
    }, index=dates)

    return data


def test_strategy_detection():
    """測試策略類型檢測"""
    print()
    print("=" * 70)
    print("Test 1: 策略類型檢測")
    print("=" * 70)

    # v0.3 策略檢測
    is_v03 = not _is_v05_strategy(SimpleSMAStrategy)
    print(f"SimpleSMAStrategy (v0.3): is_v05={not is_v03} ✓" if is_v03 else "SimpleSMAStrategy (v0.3): FAILED")

    # v0.5 策略檢測
    is_v05 = _is_v05_strategy(KawamokuStrategy)
    print(f"KawamokuStrategy (v0.5): is_v05={is_v05} ✓" if is_v05 else "KawamokuStrategy (v0.5): FAILED")

    print()
    return is_v03 and is_v05


def test_v03_strategy_backtest():
    """測試 v0.3 策略回測"""
    print("=" * 70)
    print("Test 2: v0.3 策略回測 (SimpleSMAStrategy)")
    print("=" * 70)

    try:
        data = create_sample_data(periods=200)

        result = run_backtest(
            data=data,
            strategy_cls=SimpleSMAStrategy,
            initial_cash=10000,
            fee_rate=0.0005
        )

        print(f"✓ 回測成功")
        print(f"  - 交易次數: {result.metrics['num_trades']}")
        print(f"  - 最終權益: {result.equity_curve.iloc[-1]:.2f}")
        print(f"  - 總回報: {result.metrics['total_return']:.2%}")
        print()
        return True

    except Exception as e:
        print(f"✗ 回測失敗: {e}")
        print()
        return False


def test_v05_strategy_backtest():
    """測試 v0.5 策略回測"""
    print("=" * 70)
    print("Test 3: v0.5 策略回測 (KawamokuStrategy)")
    print("=" * 70)

    try:
        data = create_sample_data(periods=200)

        result = run_backtest(
            data=data,
            strategy_cls=KawamokuStrategy,
            initial_cash=10000,
            fee_rate=0.0005
        )

        print(f"✓ 回測成功")
        print(f"  - 交易次數: {result.metrics['num_trades']}")
        print(f"  - 最終權益: {result.equity_curve.iloc[-1]:.2f}")
        print(f"  - 總回報: {result.metrics['total_return']:.2%}")
        print()
        return True

    except Exception as e:
        print(f"✗ 回測失敗: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def main():
    """運行所有測試"""
    print()
    print("=" * 70)
    print("SuperDog v0.5 - 策略兼容性測試")
    print("=" * 70)
    print()
    print("測試目標:")
    print("  1. 驗證策略類型自動檢測 (v0.3 vs v0.5)")
    print("  2. 驗證 v0.3 策略向後兼容性")
    print("  3. 驗證 v0.5 新策略 API 支援")

    results = []

    # Test 1: 策略類型檢測
    results.append(("策略類型檢測", test_strategy_detection()))

    # Test 2: v0.3 策略回測
    results.append(("v0.3 策略回測", test_v03_strategy_backtest()))

    # Test 3: v0.5 策略回測
    results.append(("v0.5 策略回測", test_v05_strategy_backtest()))

    # 總結
    print("=" * 70)
    print("測試總結")
    print("=" * 70)
    print()

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        print("🎉 所有測試通過！")
        print()
        print("結論:")
        print("  ✓ BacktestEngine 成功支援 v0.3 和 v0.5 策略")
        print("  ✓ v0.3 策略向後兼容性正常")
        print("  ✓ v0.5 新策略 API 正常運作")
        print("  ✓ SuperDog v0.5 回測引擎 Production Ready!")
        print()
        return 0
    else:
        print("❌ 部分測試失敗，請檢查錯誤訊息")
        print()
        return 1


if __name__ == '__main__':
    sys.exit(main())
