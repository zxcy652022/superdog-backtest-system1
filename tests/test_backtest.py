# -*- coding: utf-8 -*-
"""
Backtest Engine v0.1 測試

測試回測引擎的基本功能，包含：
- 載入數據
- 執行回測
- 驗證結果格式
- 驗證績效指標
"""

import sys
import os
sys.path.append(os.path.abspath("."))

from data.storage import load_ohlcv
from backtest.engine import run_backtest, BacktestResult
from strategies.simple_sma import SimpleSMAStrategy


def test_backtest_basic():
    """測試基本回測流程"""

    # 1. 載入測試數據
    csv_path = "data/raw/BTCUSDT_1h_test.csv"
    data = load_ohlcv(csv_path)

    # 確認數據載入成功
    assert len(data) > 0, "數據應該不為空"
    assert 'close' in data.columns, "數據應包含 close 欄位"

    # 2. 執行回測
    result = run_backtest(
        data=data,
        strategy_cls=SimpleSMAStrategy,
        initial_cash=10000,
        fee_rate=0.0005
    )

    # 3. 驗證回測結果類型
    assert isinstance(result, BacktestResult), "回測結果應為 BacktestResult 類型"

    # 4. 驗證權益曲線
    assert len(result.equity_curve) > 0, "權益曲線長度應大於 0"
    assert len(result.equity_curve) == len(data), "權益曲線長度應等於數據長度"

    # 5. 驗證交易記錄
    assert result.metrics["num_trades"] >= 0, "交易數量應大於等於 0"
    assert len(result.trades) == result.metrics["num_trades"], "交易記錄數量應與指標一致"

    # 6. 驗證績效指標
    required_metrics = ['total_return', 'max_drawdown', 'num_trades', 'win_rate', 'avg_trade_return']
    for metric in required_metrics:
        assert metric in result.metrics, f"績效指標應包含 {metric}"

    print(f"\nOK 回測測試通過")
    print(f"   數據長度: {len(data)}")
    print(f"   權益曲線長度: {len(result.equity_curve)}")
    print(f"   交易數量: {result.metrics['num_trades']}")
    print(f"   總報酬: {result.metrics['total_return']:.2%}")


def test_backtest_has_trades():
    """測試回測應該產生交易"""

    # 載入數據
    csv_path = "data/raw/BTCUSDT_1h_test.csv"
    data = load_ohlcv(csv_path)

    # 執行回測
    result = run_backtest(
        data=data,
        strategy_cls=SimpleSMAStrategy,
        initial_cash=10000,
        fee_rate=0.0005
    )

    # 驗證有交易產生
    assert result.metrics["num_trades"] > 0, "SimpleSMAStrategy 應該產生至少一筆交易"

    # 驗證交易記錄的完整性
    for i, trade in enumerate(result.trades):
        assert trade.entry_time is not None, f"交易 {i} 應有進場時間"
        assert trade.exit_time is not None, f"交易 {i} 應有出場時間"
        assert trade.entry_price > 0, f"交易 {i} 進場價格應大於 0"
        assert trade.exit_price > 0, f"交易 {i} 出場價格應大於 0"
        assert trade.qty > 0, f"交易 {i} 數量應大於 0"

    print(f"\nOK 交易測試通過")
    print(f"   總交易數: {len(result.trades)}")
    print(f"   勝率: {result.metrics['win_rate']:.2%}")
    print(f"   平均報酬: {result.metrics['avg_trade_return']:.2%}")


def test_backtest_equity_curve():
    """測試權益曲線的正確性"""

    # 載入數據
    csv_path = "data/raw/BTCUSDT_1h_test.csv"
    data = load_ohlcv(csv_path)

    # 執行回測
    result = run_backtest(
        data=data,
        strategy_cls=SimpleSMAStrategy,
        initial_cash=10000,
        fee_rate=0.0005
    )

    # 驗證權益曲線
    assert result.equity_curve.iloc[0] == 10000, "初始權益應為 10000"
    assert result.equity_curve.iloc[-1] > 0, "最終權益應大於 0"

    # 驗證總報酬率計算正確
    expected_return = (result.equity_curve.iloc[-1] - 10000) / 10000
    assert abs(result.metrics['total_return'] - expected_return) < 0.0001, "總報酬率計算應正確"

    print(f"\nOK 權益曲線測試通過")
    print(f"   初始權益: {result.equity_curve.iloc[0]:.2f}")
    print(f"   最終權益: {result.equity_curve.iloc[-1]:.2f}")
    print(f"   總報酬率: {result.metrics['total_return']:.2%}")


def test_backtest_metrics_validity():
    """測試績效指標的合理性"""

    # 載入數據
    csv_path = "data/raw/BTCUSDT_1h_test.csv"
    data = load_ohlcv(csv_path)

    # 執行回測
    result = run_backtest(
        data=data,
        strategy_cls=SimpleSMAStrategy,
        initial_cash=10000,
        fee_rate=0.0005
    )

    # 驗證指標合理性
    assert 0 <= result.metrics['win_rate'] <= 1, "勝率應在 0-1 之間"
    assert result.metrics['max_drawdown'] <= 0, "最大回撤應為負值或零"
    assert result.metrics['num_trades'] >= 0, "交易數量應大於等於 0"

    print(f"\nOK 指標合理性測試通過")
    print(f"   勝率: {result.metrics['win_rate']:.2%}")
    print(f"   最大回撤: {result.metrics['max_drawdown']:.2%}")
    print(f"   交易數量: {result.metrics['num_trades']}")


if __name__ == "__main__":
    # 直接執行測試
    print("執行 Backtest Engine v0.1 測試...")
    print("=" * 60)

    try:
        test_backtest_basic()
        test_backtest_has_trades()
        test_backtest_equity_curve()
        test_backtest_metrics_validity()

        print("\n" + "=" * 60)
        print("SUCCESS 所有測試通過！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nFAIL 測試失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR 發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
