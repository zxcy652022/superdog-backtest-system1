#!/usr/bin/env python3
"""測試不同槓桿模式的效果"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy

INITIAL_CASH = 500
SLIPPAGE = 0.0005


def load_data(symbol: str, timeframe: str = "4h") -> pd.DataFrame:
    data_path = f"/Volumes/權志龍的寶藏/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


def run_backtest(
    df: pd.DataFrame, leverage: int, dynamic: bool = False, initial_lev: int = 20, min_lev: int = 5
) -> dict:
    """執行回測"""
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(
        initial_cash=INITIAL_CASH,
        slippage_rate=SLIPPAGE,
    )

    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=leverage,
        dynamic_leverage=dynamic,
        initial_leverage=initial_lev,
        min_leverage=min_lev,
        enable_add_position=True,
        max_add_count=100,
    )

    peak = INITIAL_CASH
    max_dd = 0

    for i, (idx, row) in enumerate(strategy.data.iterrows()):
        strategy.on_bar(i, row)
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

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "liquidations": broker.liquidation_count,
    }


def test_leverage_modes():
    """測試不同槓桿模式"""
    print("=" * 100)
    print("槓桿模式比較 - BTC 全期 (2019-2025)")
    print("=" * 100)

    df = load_data("BTCUSDT")

    configs = [
        # 固定槓桿
        {"name": "固定 3x", "leverage": 3, "dynamic": False},
        {"name": "固定 5x", "leverage": 5, "dynamic": False},
        {"name": "固定 7x", "leverage": 7, "dynamic": False},
        {"name": "固定 10x", "leverage": 10, "dynamic": False},
        {"name": "固定 15x", "leverage": 15, "dynamic": False},
        {"name": "固定 20x", "leverage": 20, "dynamic": False},
        # 動態槓桿
        {"name": "動態 10→5x", "leverage": 10, "dynamic": True, "init": 10, "min": 5},
        {"name": "動態 15→5x", "leverage": 15, "dynamic": True, "init": 15, "min": 5},
        {"name": "動態 20→5x", "leverage": 20, "dynamic": True, "init": 20, "min": 5},
        {"name": "動態 20→3x", "leverage": 20, "dynamic": True, "init": 20, "min": 3},
        {"name": "動態 30→5x", "leverage": 30, "dynamic": True, "init": 30, "min": 5},
        {"name": "動態 50→5x", "leverage": 50, "dynamic": True, "init": 50, "min": 5},
    ]

    print(f"\n{'模式':<16} {'最終資金':>18} {'收益':>14} {'回撤':>10} {'爆倉':>6} {'勝率':>8} {'交易':>6}")
    print("-" * 85)

    results = []
    for cfg in configs:
        init_lev = cfg.get("init", cfg["leverage"])
        min_lev = cfg.get("min", 5)

        r = run_backtest(
            df.copy(),
            leverage=cfg["leverage"],
            dynamic=cfg["dynamic"],
            initial_lev=init_lev,
            min_lev=min_lev,
        )

        if r:
            # 格式化收益
            if r["return_pct"] > 100000:
                ret_str = f"{r['return_pct']/100:>+12,.0f}x"
            elif r["return_pct"] > 1000:
                ret_str = f"{r['return_pct']:>+12,.0f}%"
            else:
                ret_str = f"{r['return_pct']:>+12.0f}%"

            if r["final"] > 1e9:
                final_str = f"${r['final']/1e9:>14,.1f}B"
            elif r["final"] > 1e6:
                final_str = f"${r['final']/1e6:>14,.1f}M"
            else:
                final_str = f"${r['final']:>14,.0f}"

            print(
                f"{cfg['name']:<16} {final_str} {ret_str} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}% {r['trades']:>6}"
            )

            results.append(
                {
                    "name": cfg["name"],
                    "return": r["return_pct"],
                    "max_dd": r["max_dd"],
                    "liquidations": r["liquidations"],
                    "risk_adj": r["return_pct"] / abs(r["max_dd"]) if r["max_dd"] != 0 else 0,
                }
            )

    # 風險調整收益排名
    print("\n" + "=" * 100)
    print("風險調整收益排名 (收益/回撤)")
    print("=" * 100)

    results.sort(key=lambda x: x["risk_adj"], reverse=True)
    print(f"\n{'排名':<6} {'模式':<16} {'收益':>14} {'回撤':>10} {'爆倉':>6} {'風險調整':>12}")
    print("-" * 70)

    for i, r in enumerate(results):
        if r["return"] > 100000:
            ret_str = f"{r['return']/100:>+12,.0f}x"
        else:
            ret_str = f"{r['return']:>+12,.0f}%"

        print(
            f"{i+1:<6} {r['name']:<16} {ret_str} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['risk_adj']:>12.0f}"
        )


def test_yearly_comparison():
    """逐年比較不同槓桿模式"""
    print("\n\n" + "=" * 100)
    print("逐年比較：固定 5x vs 動態 20→5x vs 固定 10x")
    print("=" * 100)

    df = load_data("BTCUSDT")
    years = [2020, 2021, 2022, 2023, 2024]

    configs = [
        {"name": "固定 5x", "leverage": 5, "dynamic": False},
        {"name": "動態 20→5x", "leverage": 20, "dynamic": True, "init": 20, "min": 5},
        {"name": "固定 10x", "leverage": 10, "dynamic": False},
    ]

    print(f"\n{'年份':<8}", end="")
    for cfg in configs:
        print(f"{cfg['name']:>20}", end="")
    print()
    print("-" * 70)

    yearly_results = {cfg["name"]: [] for cfg in configs}

    for year in years:
        df_year = df[df.index.year == year]
        if len(df_year) < 200:
            continue

        print(f"{year:<8}", end="")

        for cfg in configs:
            init_lev = cfg.get("init", cfg["leverage"])
            min_lev = cfg.get("min", 5)

            r = run_backtest(
                df_year.copy(),
                leverage=cfg["leverage"],
                dynamic=cfg["dynamic"],
                initial_lev=init_lev,
                min_lev=min_lev,
            )

            if r:
                yearly_results[cfg["name"]].append(r["return_pct"])
                liq_info = f" ({r['liquidations']}爆)" if r["liquidations"] > 0 else ""
                if r["return_pct"] > 1000:
                    print(f"{r['return_pct']/100:>+16.0f}x{liq_info}", end="")
                else:
                    print(f"{r['return_pct']:>+16.0f}%{liq_info}", end="")
        print()

    # 統計
    print("-" * 70)
    print(f"{'累計':<8}", end="")
    for cfg in configs:
        returns = yearly_results[cfg["name"]]
        cumulative = 1.0
        for ret in returns:
            cumulative *= 1 + ret / 100
        if (cumulative - 1) * 100 > 100000:
            print(f"{(cumulative-1):>+16.0f}x", end="")
        else:
            print(f"{(cumulative-1)*100:>+16,.0f}%", end="")
    print()


def main():
    test_leverage_modes()
    test_yearly_comparison()

    print("\n" + "=" * 100)
    print("結論")
    print("=" * 100)
    print(
        """
動態槓桿的優勢：
1. 初期高槓桿快速累積資本
2. 獲利後自動降低槓桿保護利潤
3. 兼顧進攻性和防守性

建議配置：
- 激進型：動態 20→5x（高風險高回報）
- 平衡型：動態 15→5x（風險回報平衡）
- 保守型：固定 5x（穩定但較慢）
"""
    )


if __name__ == "__main__":
    main()
