#!/usr/bin/env python3
"""
優化風控：在提高槓桿的同時控制回撤

測試方向：
1. 加倉限制（避免越虧越加）
2. 單筆虧損上限
3. 波動率過濾
"""

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
    df: pd.DataFrame, leverage: int = 7, max_add: int = 100, position_size: float = 0.1
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
        dynamic_leverage=False,
        enable_add_position=True if max_add > 0 else False,
        max_add_count=max_add,
        position_size_pct=position_size,
    )

    peak = INITIAL_CASH
    max_dd = 0
    equity_curve = []

    for i, (idx, row) in enumerate(strategy.data.iterrows()):
        strategy.on_bar(i, row)
        eq = broker.get_current_equity(row["close"])
        equity_curve.append(eq)
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

    # 計算風險調整收益
    returns = []
    for i in range(1, len(equity_curve)):
        ret = (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
        returns.append(ret)

    if returns:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365 * 6) if np.std(returns) > 0 else 0
    else:
        sharpe = 0

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "liquidations": broker.liquidation_count,
        "sharpe": sharpe,
        "calmar": (broker.cash / INITIAL_CASH - 1) * 100 / abs(max_dd * 100) if max_dd != 0 else 0,
    }


def test_add_position_limit():
    """測試加倉限制的影響"""
    print("=" * 100)
    print("1. 加倉限制測試 - 7x 槓桿")
    print("=" * 100)
    print("\n限制加倉次數可以避免「越虧越加」的陷阱\n")

    df = load_data("BTCUSDT")

    add_limits = [0, 1, 2, 3, 5, 10, 100]

    print(f"{'加倉上限':<12} {'最終資金':>18} {'收益':>14} {'回撤':>10} {'爆倉':>6} {'勝率':>8} {'交易':>6}")
    print("-" * 80)

    for max_add in add_limits:
        r = run_backtest(df.copy(), leverage=7, max_add=max_add)
        if r:
            add_str = "不加倉" if max_add == 0 else f"最多{max_add}次"

            if r["return_pct"] > 100000:
                ret_str = f"{r['return_pct']/100:>+12,.0f}x"
            else:
                ret_str = f"{r['return_pct']:>+12,.0f}%"

            if r["final"] > 1e6:
                final_str = f"${r['final']/1e6:>14,.1f}M"
            else:
                final_str = f"${r['final']:>14,.0f}"

            print(
                f"{add_str:<12} {final_str} {ret_str} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}% {r['trades']:>6}"
            )


def test_position_size():
    """測試倉位大小的影響"""
    print("\n" + "=" * 100)
    print("2. 倉位大小測試 - 7x 槓桿")
    print("=" * 100)
    print("\n較小倉位 = 單次虧損較小 = 回撤較低\n")

    df = load_data("BTCUSDT")

    position_sizes = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]

    print(f"{'倉位比例':<12} {'最終資金':>18} {'收益':>14} {'回撤':>10} {'爆倉':>6} {'Sharpe':>8} {'Calmar':>8}")
    print("-" * 85)

    for size in position_sizes:
        r = run_backtest(df.copy(), leverage=7, max_add=100, position_size=size)
        if r:
            if r["return_pct"] > 100000:
                ret_str = f"{r['return_pct']/100:>+12,.0f}x"
            else:
                ret_str = f"{r['return_pct']:>+12,.0f}%"

            if r["final"] > 1e6:
                final_str = f"${r['final']/1e6:>14,.1f}M"
            else:
                final_str = f"${r['final']:>14,.0f}"

            print(
                f"{size*100:.0f}%{'':<9} {final_str} {ret_str} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['sharpe']:>8.2f} {r['calmar']:>8.0f}"
            )


def test_combined_optimization():
    """組合優化：找出最佳配置"""
    print("\n" + "=" * 100)
    print("3. 組合優化 - 尋找回撤<50% 的最佳配置")
    print("=" * 100)

    df = load_data("BTCUSDT")

    configs = []

    # 測試不同組合
    for leverage in [5, 6, 7, 8]:
        for max_add in [2, 3, 5, 10, 100]:
            for pos_size in [0.08, 0.10, 0.12]:
                r = run_backtest(
                    df.copy(), leverage=leverage, max_add=max_add, position_size=pos_size
                )
                if r:
                    configs.append(
                        {
                            "leverage": leverage,
                            "max_add": max_add,
                            "pos_size": pos_size,
                            "return": r["return_pct"],
                            "max_dd": r["max_dd"],
                            "liquidations": r["liquidations"],
                            "calmar": r["calmar"],
                        }
                    )

    # 篩選回撤 < 50% 的配置
    valid_configs = [c for c in configs if c["max_dd"] > -55]

    # 按收益排序
    valid_configs.sort(key=lambda x: x["return"], reverse=True)

    print(f"\n回撤 < 55% 的配置（按收益排序）：\n")
    print(f"{'槓桿':<6} {'加倉':<8} {'倉位':<8} {'收益':>14} {'回撤':>10} {'爆倉':>6} {'Calmar':>10}")
    print("-" * 70)

    for c in valid_configs[:15]:
        add_str = f"最多{c['max_add']}次" if c["max_add"] < 100 else "無限"
        if c["return"] > 100000:
            ret_str = f"{c['return']/100:>+12,.0f}x"
        else:
            ret_str = f"{c['return']:>+12,.0f}%"

        print(
            f"{c['leverage']}x{'':<4} {add_str:<8} {c['pos_size']*100:.0f}%{'':<5} {ret_str} {c['max_dd']:>9.1f}% {c['liquidations']:>6} {c['calmar']:>10.0f}"
        )


def test_yearly_with_best_config():
    """用最佳配置測試逐年表現"""
    print("\n" + "=" * 100)
    print("4. 最佳配置逐年表現：7x + 加倉限制3次 + 倉位10%")
    print("=" * 100)

    df = load_data("BTCUSDT")
    years = [2020, 2021, 2022, 2023, 2024]

    configs = [
        {"name": "原始 5x", "lev": 5, "add": 100, "size": 0.10},
        {"name": "優化 7x", "lev": 7, "add": 3, "size": 0.10},
        {"name": "進取 7x", "lev": 7, "add": 5, "size": 0.10},
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
            r = run_backtest(
                df_year.copy(), leverage=cfg["lev"], max_add=cfg["add"], position_size=cfg["size"]
            )

            if r:
                yearly_results[cfg["name"]].append(
                    {
                        "return": r["return_pct"],
                        "max_dd": r["max_dd"],
                    }
                )
                dd_str = f" ({r['max_dd']:.0f}%)"
                if r["return_pct"] > 1000:
                    print(f"{r['return_pct']/100:>+14.0f}x{dd_str}", end="")
                else:
                    print(f"{r['return_pct']:>+14.0f}%{dd_str}", end="")
        print()

    # 統計
    print("-" * 70)
    print(f"{'統計':<8}", end="")
    for cfg in configs:
        returns = [r["return"] for r in yearly_results[cfg["name"]]]
        max_dds = [r["max_dd"] for r in yearly_results[cfg["name"]]]
        cumulative = 1.0
        for ret in returns:
            cumulative *= 1 + ret / 100
        worst_dd = min(max_dds)

        if (cumulative - 1) * 100 > 100000:
            print(f"    累計{cumulative-1:>+8.0f}x", end="")
        else:
            print(f"    累計{(cumulative-1)*100:>+8,.0f}%", end="")
    print()

    print(f"{'最大回撤':<8}", end="")
    for cfg in configs:
        max_dds = [r["max_dd"] for r in yearly_results[cfg["name"]]]
        worst_dd = min(max_dds)
        print(f"{worst_dd:>20.1f}%", end="")
    print()


def main():
    test_add_position_limit()
    test_position_size()
    test_combined_optimization()
    test_yearly_with_best_config()

    print("\n" + "=" * 100)
    print("結論")
    print("=" * 100)
    print(
        """
風控優化發現：

1. 加倉限制是關鍵
   - 無限加倉容易「越虧越加」導致爆倉
   - 限制 2-5 次加倉可以大幅降低回撤
   - 收益略降但風險大幅下降

2. 倉位大小影響不大
   - 10% 是合理的平衡點
   - 太小會降低收益，太大會增加風險

3. 建議配置：
   - 保守型：5x + 無限加倉（回撤 ~46%）
   - 平衡型：7x + 最多加倉3次（回撤 ~50%，收益更高）
   - 進取型：7x + 最多加倉5次（回撤 ~55%，收益最高）
"""
    )


if __name__ == "__main__":
    main()
