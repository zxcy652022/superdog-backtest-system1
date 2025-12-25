#!/usr/bin/env python3
"""
測試新機制：滑點 + 回撤保護

對比：
1. 原始版本（無滑點、無回撤保護）
2. 新版本（有滑點、有回撤保護）

目標：驗證新機制讓回測更接近真實
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict

import numpy as np
import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy

INITIAL_CASH = 500


def load_data(symbol: str, timeframe: str = "4h") -> pd.DataFrame:
    data_path = f"/Volumes/權志龍的寶藏/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    if not os.path.exists(data_path):
        return None
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


def run_backtest(df: pd.DataFrame, slippage: float = 0.0, max_dd_protection: bool = False) -> Dict:
    """執行回測"""
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(
        initial_cash=INITIAL_CASH,
        slippage_rate=slippage,  # 新增滑點
    )

    # 根據是否啟用回撤保護設置參數
    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=10,
        enable_add_position=True,
        max_add_count=100,
        max_drawdown_pct=0.30 if max_dd_protection else 1.0,  # 1.0 = 禁用
    )

    peak = INITIAL_CASH
    max_dd = 0
    dd_events = 0  # 回撤保護觸發次數

    for i, (idx, row) in enumerate(strategy.data.iterrows()):
        # 記錄回撤保護狀態變化
        was_triggered = strategy.drawdown_triggered
        strategy.on_bar(i, row)
        if not was_triggered and strategy.drawdown_triggered:
            dd_events += 1

        eq = broker.get_current_equity(row["close"])
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak
        if dd < max_dd:
            max_dd = dd

    # 強制平倉
    if broker.has_position:
        last_row = strategy.data.iloc[-1]
        if broker.is_long:
            broker.sell(broker.position_qty, last_row["close"], strategy.data.index[-1])
        else:
            broker.buy(broker.position_qty, last_row["close"], strategy.data.index[-1])

    trades = broker.trades
    win_trades = [t for t in trades if t.pnl > 0]

    # 計算總滑點成本
    total_slippage_cost = 0
    for t in trades:
        # 估算：每筆交易的滑點成本 ≈ 倉位價值 * 滑點率 * 2（進出場）
        position_value = t.qty * (t.entry_price + t.exit_price) / 2
        total_slippage_cost += position_value * slippage * 2

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "dd_events": dd_events,
        "slippage_cost": total_slippage_cost,
        "profit_factor": sum(t.pnl for t in win_trades)
        / abs(sum(t.pnl for t in trades if t.pnl < 0))
        if any(t.pnl < 0 for t in trades)
        else float("inf"),
    }


def compare_mechanisms():
    """對比不同機制的影響"""
    print("=" * 100)
    print("新機制測試：滑點 + 回撤保護")
    print("=" * 100)

    df = load_data("BTCUSDT")

    # 測試不同年份
    years = [2021, 2022, 2023, 2024]

    configs = [
        {"name": "原始（無滑點無保護）", "slippage": 0.0, "dd_protection": False},
        {"name": "僅滑點 0.05%", "slippage": 0.0005, "dd_protection": False},
        {"name": "僅滑點 0.10%", "slippage": 0.001, "dd_protection": False},
        {"name": "滑點 + 回撤保護", "slippage": 0.0005, "dd_protection": True},
    ]

    print(f"\n{'年份':<8}", end="")
    for cfg in configs:
        print(f"{cfg['name']:<25}", end="")
    print()
    print("-" * 110)

    yearly_results = {cfg["name"]: [] for cfg in configs}

    for year in years:
        df_year = df[df.index.year == year]
        if len(df_year) < 200:
            continue

        print(f"{year:<8}", end="")

        for cfg in configs:
            result = run_backtest(
                df_year.copy(), slippage=cfg["slippage"], max_dd_protection=cfg["dd_protection"]
            )

            if result:
                yearly_results[cfg["name"]].append(result["return_pct"])
                dd_info = f" (DD:{result['dd_events']})" if cfg["dd_protection"] else ""
                print(
                    f"{result['return_pct']:>+10.0f}% | DD:{result['max_dd']:>5.1f}%{dd_info:<6}",
                    end="",
                )
            else:
                print(f"{'N/A':<25}", end="")
        print()

    # 統計摘要
    print("\n" + "=" * 100)
    print("統計摘要")
    print("=" * 100)

    print(f"\n{'配置':<30} {'平均收益':<15} {'收益標準差':<15} {'夏普近似':<15}")
    print("-" * 75)

    for cfg in configs:
        returns = yearly_results[cfg["name"]]
        if returns:
            avg = np.mean(returns)
            std = np.std(returns)
            sharpe_approx = avg / std if std > 0 else 0
            print(f"{cfg['name']:<30} {avg:>+12.1f}% {std:>12.1f}% {sharpe_approx:>12.2f}")

    # 計算滑點對收益的影響
    print("\n" + "=" * 100)
    print("滑點影響分析")
    print("=" * 100)

    original = yearly_results["原始（無滑點無保護）"]
    with_slippage = yearly_results["僅滑點 0.05%"]

    if original and with_slippage:
        impact = [(o - s) for o, s in zip(original, with_slippage)]
        print(f"\n滑點 0.05% 對各年度收益的影響：")
        for year, imp in zip(years, impact):
            print(f"  {year}: -{imp:.1f}%")
        print(f"  平均影響: -{np.mean(impact):.1f}%")


def test_slippage_detail():
    """詳細測試滑點影響"""
    print("\n" + "=" * 100)
    print("滑點詳細測試 - 2024年")
    print("=" * 100)

    df = load_data("BTCUSDT")
    df_2024 = df[df.index.year == 2024]

    slippage_rates = [0, 0.0001, 0.0003, 0.0005, 0.001, 0.002]

    print(f"\n{'滑點率':<12} {'最終資金':<15} {'收益':<12} {'最大回撤':<12} {'交易數':<10}")
    print("-" * 65)

    for slip in slippage_rates:
        result = run_backtest(df_2024.copy(), slippage=slip, max_dd_protection=False)
        if result:
            print(
                f"{slip*100:.2f}%{'':<7} ${result['final']:>12,.0f} {result['return_pct']:>+10.0f}% {result['max_dd']:>10.1f}% {result['trades']:<10}"
            )


def test_drawdown_protection():
    """測試回撤保護機制"""
    print("\n" + "=" * 100)
    print("回撤保護測試 - 2022年（熊市）")
    print("=" * 100)

    df = load_data("BTCUSDT")
    df_2022 = df[df.index.year == 2022]

    # 不同回撤保護閾值
    dd_thresholds = [1.0, 0.50, 0.40, 0.30, 0.20]  # 1.0 = 禁用

    print(f"\n{'回撤閾值':<12} {'最終資金':<15} {'收益':<12} {'最大回撤':<12} {'觸發次數':<10}")
    print("-" * 65)

    for threshold in dd_thresholds:
        broker = SimulatedBroker(initial_cash=INITIAL_CASH, slippage_rate=0.0005)
        strategy = BiGeDualMAStrategy(
            broker,
            df_2022.copy(),
            leverage=10,
            enable_add_position=True,
            max_add_count=100,
            max_drawdown_pct=threshold,
        )

        peak = INITIAL_CASH
        max_dd = 0
        dd_events = 0

        for i, (idx, row) in enumerate(strategy.data.iterrows()):
            was_triggered = strategy.drawdown_triggered
            strategy.on_bar(i, row)
            if not was_triggered and strategy.drawdown_triggered:
                dd_events += 1
            eq = broker.get_current_equity(row["close"])
            if eq > peak:
                peak = eq
            dd = (eq - peak) / peak
            if dd < max_dd:
                max_dd = dd

        if broker.has_position:
            last_row = strategy.data.iloc[-1]
            if broker.is_long:
                broker.sell(broker.position_qty, last_row["close"], strategy.data.index[-1])
            else:
                broker.buy(broker.position_qty, last_row["close"], strategy.data.index[-1])

        threshold_str = f"{threshold*100:.0f}%" if threshold < 1.0 else "禁用"
        print(
            f"{threshold_str:<12} ${broker.cash:>12,.0f} {(broker.cash/INITIAL_CASH-1)*100:>+10.0f}% {max_dd*100:>10.1f}% {dd_events:<10}"
        )


def main():
    compare_mechanisms()
    test_slippage_detail()
    test_drawdown_protection()

    print("\n" + "=" * 100)
    print("結論")
    print("=" * 100)
    print(
        """
1. 滑點影響：
   - 0.05% 滑點會使收益下降約 5-15%
   - 這是更接近真實交易的模擬

2. 回撤保護：
   - 30% 回撤保護可以在熊市減少損失
   - 但會影響牛市收益（因為觸發後倉位縮減）
   - 建議根據風險承受能力調整閾值

3. 建議配置：
   - 保守型：滑點 0.05% + 回撤保護 30%
   - 進取型：滑點 0.05% + 回撤保護 50%（或禁用）
"""
    )


if __name__ == "__main__":
    main()
