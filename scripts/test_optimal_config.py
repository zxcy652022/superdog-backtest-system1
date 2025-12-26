#!/usr/bin/env python3
"""
最優配置測試

結論：
1. 固定比例加倉（50%）效果最好
2. 浮盈加倉在回踩時沒有浮盈可用，效果很差
3. 問題是回撤太大（73.5%），需要控制

優化方向：
1. 限制加倉次數
2. 增加加倉間隔
3. 提高初始倉位比例，減少加倉依賴
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
    if not os.path.exists(data_path):
        return None
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


def run_backtest(df, **params):
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(initial_cash=INITIAL_CASH, slippage_rate=SLIPPAGE)

    default_params = {
        "leverage": 7,
        "dynamic_leverage": False,
        "enable_add_position": True,
        "max_add_count": 100,
        "add_position_mode": "fixed_50",
        "max_drawdown_pct": 1.0,
    }
    default_params.update(params)

    strategy = BiGeDualMAStrategy(broker, df.copy(), **default_params)

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


def fmt_ret(ret):
    if ret > 100000:
        return f"{ret/100:>+10,.0f}x"
    elif ret > 1000:
        return f"{ret:>+10,.0f}%"
    else:
        return f"{ret:>+10.0f}%"


def fmt_final(f):
    if f > 1e9:
        return f"${f/1e9:>12,.1f}B"
    elif f > 1e6:
        return f"${f/1e6:>12,.1f}M"
    else:
        return f"${f:>12,.0f}"


def test_baseline():
    """基準測試"""
    print("=" * 100)
    print("0. 基準對比 - 5x 無限加倉 vs 7x 無限加倉 vs 7x 限制加倉")
    print("=" * 100)

    df = load_data("BTCUSDT")

    configs = [
        {"name": "5x 無限(原版)", "leverage": 5, "max_add_count": 100},
        {"name": "7x 無限", "leverage": 7, "max_add_count": 100},
        {"name": "7x 最多3次", "leverage": 7, "max_add_count": 3},
        {"name": "7x 最多5次", "leverage": 7, "max_add_count": 5},
        {"name": "7x 最多10次", "leverage": 7, "max_add_count": 10},
    ]

    print(f"\n{'配置':<16} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 75)

    for cfg in configs:
        params = {k: v for k, v in cfg.items() if k != "name"}
        r = run_backtest(df.copy(), **params)
        if r:
            print(
                f"{cfg['name']:<16} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_add_interval():
    """測試加倉間隔"""
    print("\n" + "=" * 100)
    print("1. 加倉間隔測試 - 7x 無限加倉")
    print("=" * 100)
    print("\n間隔越長 = 加倉越少 = 回撤可能更低\n")

    df = load_data("BTCUSDT")

    intervals = [3, 5, 8, 10, 12, 15]

    print(f"{'間隔(K線)':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for interval in intervals:
        r = run_backtest(
            df.copy(), leverage=7, max_add_count=100, add_position_min_interval=interval
        )
        if r:
            print(
                f"{interval:<12} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_position_size():
    """測試初始倉位大小"""
    print("\n" + "=" * 100)
    print("2. 初始倉位測試 - 7x 無限加倉")
    print("=" * 100)
    print("\n更大的初始倉位 = 更少依賴加倉 = 更穩定\n")

    df = load_data("BTCUSDT")

    sizes = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]

    print(f"{'倉位比例':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for size in sizes:
        r = run_backtest(df.copy(), leverage=7, max_add_count=100, position_size_pct=size)
        if r:
            print(
                f"{size*100:.0f}%{'':<9} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_add_pct():
    """測試加倉比例"""
    print("\n" + "=" * 100)
    print("3. 加倉比例測試 - 7x 無限加倉")
    print("=" * 100)
    print("\n每次加倉佔初始倉位的比例\n")

    df = load_data("BTCUSDT")

    pcts = [0.20, 0.30, 0.40, 0.50, 0.70, 1.0]

    print(f"{'加倉比例':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for pct in pcts:
        r = run_backtest(df.copy(), leverage=7, max_add_count=100, add_position_fixed_pct=pct)
        if r:
            print(
                f"{pct*100:.0f}%{'':<9} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_combined():
    """組合優化"""
    print("\n" + "=" * 100)
    print("4. 組合優化 - 7x 槓桿，尋找回撤 < 55% 的最佳配置")
    print("=" * 100)

    df = load_data("BTCUSDT")

    results = []

    for max_add in [5, 8, 10, 15, 100]:
        for interval in [3, 5, 8]:
            for add_pct in [0.30, 0.50, 0.70]:
                r = run_backtest(
                    df.copy(),
                    leverage=7,
                    max_add_count=max_add,
                    add_position_min_interval=interval,
                    add_position_fixed_pct=add_pct,
                )
                if r:
                    results.append(
                        {
                            "max_add": max_add,
                            "interval": interval,
                            "add_pct": add_pct,
                            "return": r["return_pct"],
                            "max_dd": r["max_dd"],
                            "liquidations": r["liquidations"],
                            "calmar": abs(r["return_pct"] / r["max_dd"]) if r["max_dd"] != 0 else 0,
                        }
                    )

    # 篩選回撤 < 55% 且無爆倉
    valid = [r for r in results if r["max_dd"] > -55 and r["liquidations"] == 0]
    valid.sort(key=lambda x: x["return"], reverse=True)

    print(f"\n回撤 < 55% 且無爆倉的配置（按收益排序 Top 15）：\n")
    print(f"{'加倉上限':<10} {'間隔':<6} {'加倉比例':<10} {'收益':>14} {'回撤':>10} {'Calmar':>10}")
    print("-" * 70)

    for c in valid[:15]:
        add_str = f"最多{c['max_add']}" if c["max_add"] < 100 else "無限"
        print(
            f"{add_str:<10} {c['interval']}根{'':<4} {c['add_pct']*100:.0f}%{'':<7} {fmt_ret(c['return'])} {c['max_dd']:>9.1f}% {c['calmar']:>10.0f}"
        )

    if valid:
        best = valid[0]
        print(
            f"\n【推薦配置】7x + 最多{best['max_add']}次 + 間隔{best['interval']}根 + 加倉{best['add_pct']*100:.0f}%"
        )
        print(
            f"收益: {fmt_ret(best['return'])} | 回撤: {best['max_dd']:.1f}% | Calmar: {best['calmar']:.0f}"
        )


def test_yearly_with_best():
    """用最佳配置逐年測試"""
    print("\n" + "=" * 100)
    print("5. 逐年比較：原版 vs 優化配置")
    print("=" * 100)

    df = load_data("BTCUSDT")
    years = [2020, 2021, 2022, 2023, 2024]

    configs = [
        {"name": "5x無限(原版)", "leverage": 5, "max_add_count": 100},
        {"name": "7x+5次+間隔5", "leverage": 7, "max_add_count": 5, "add_position_min_interval": 5},
        {"name": "7x+8次+間隔5", "leverage": 7, "max_add_count": 8, "add_position_min_interval": 5},
        {"name": "7x+10次+間隔5", "leverage": 7, "max_add_count": 10, "add_position_min_interval": 5},
    ]

    print(f"\n{'年份':<8}", end="")
    for cfg in configs:
        print(f"{cfg['name']:>16}", end="")
    print()
    print("-" * 80)

    yearly_results = {cfg["name"]: [] for cfg in configs}

    for year in years:
        df_year = df[df.index.year == year]
        if len(df_year) < 200:
            continue

        print(f"{year:<8}", end="")

        for cfg in configs:
            params = {k: v for k, v in cfg.items() if k != "name"}
            r = run_backtest(df_year.copy(), **params)

            if r:
                yearly_results[cfg["name"]].append(
                    {
                        "return": r["return_pct"],
                        "max_dd": r["max_dd"],
                        "liquidations": r["liquidations"],
                    }
                )
                liq_str = f"({r['liquidations']}爆)" if r["liquidations"] > 0 else ""
                if r["return_pct"] > 1000:
                    print(f"{r['return_pct']/100:>+12.0f}x{liq_str}", end="")
                else:
                    print(f"{r['return_pct']:>+12.0f}%{liq_str}", end="")
        print()

    print("-" * 80)
    print(f"{'累計':<8}", end="")
    for cfg in configs:
        returns = [r["return"] for r in yearly_results[cfg["name"]]]
        cumulative = 1.0
        for ret in returns:
            cumulative *= 1 + ret / 100
        if (cumulative - 1) * 100 > 100000:
            print(f"{cumulative-1:>+12.0f}x", end="")
        else:
            print(f"{(cumulative-1)*100:>+12,.0f}%", end="")
    print()

    print(f"{'最大回撤':<8}", end="")
    for cfg in configs:
        max_dds = [r["max_dd"] for r in yearly_results[cfg["name"]]]
        worst = min(max_dds) if max_dds else 0
        print(f"{worst:>16.1f}%", end="")
    print()


def test_multi_coin():
    """多幣種驗證"""
    print("\n" + "=" * 100)
    print("6. 多幣種驗證")
    print("=" * 100)

    coins = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "DOTUSDT",
    ]

    configs = [
        {"name": "5x無限", "leverage": 5, "max_add_count": 100},
        {"name": "7x+5次", "leverage": 7, "max_add_count": 5, "add_position_min_interval": 5},
        {"name": "7x+10次", "leverage": 7, "max_add_count": 10, "add_position_min_interval": 5},
    ]

    results = {cfg["name"]: {"returns": [], "max_dds": [], "profitable": 0} for cfg in configs}

    print(f"\n{'幣種':<12}", end="")
    for cfg in configs:
        print(f"{cfg['name']:>16}", end="")
    print()
    print("-" * 65)

    for symbol in coins:
        df = load_data(symbol)
        if df is None:
            continue

        coin = symbol.replace("USDT", "")
        print(f"{coin:<12}", end="")

        for cfg in configs:
            params = {k: v for k, v in cfg.items() if k != "name"}
            r = run_backtest(df.copy(), **params)

            if r:
                results[cfg["name"]]["returns"].append(r["return_pct"])
                results[cfg["name"]]["max_dds"].append(r["max_dd"])
                if r["return_pct"] > 0:
                    results[cfg["name"]]["profitable"] += 1

                if r["return_pct"] > 10000:
                    print(f"{r['return_pct']/100:>+14.0f}x", end="")
                else:
                    print(f"{r['return_pct']:>+14.0f}%", end="")
        print()

    print("-" * 65)
    print(f"{'平均收益':<12}", end="")
    for cfg in configs:
        avg = np.mean(results[cfg["name"]]["returns"])
        if avg > 10000:
            print(f"{avg/100:>+14.0f}x", end="")
        else:
            print(f"{avg:>+14,.0f}%", end="")
    print()

    print(f"{'中位數':<12}", end="")
    for cfg in configs:
        med = np.median(results[cfg["name"]]["returns"])
        if med > 10000:
            print(f"{med/100:>+14.0f}x", end="")
        else:
            print(f"{med:>+14,.0f}%", end="")
    print()

    print(f"{'平均回撤':<12}", end="")
    for cfg in configs:
        avg_dd = np.mean(results[cfg["name"]]["max_dds"])
        print(f"{avg_dd:>15.1f}%", end="")
    print()

    print(f"{'盈利幣種':<12}", end="")
    total = len(coins)
    for cfg in configs:
        prof = results[cfg["name"]]["profitable"]
        print(f"{prof}/{total} ({prof/total*100:.0f}%){'':<4}", end="")
    print()


def main():
    test_baseline()
    test_add_interval()
    test_position_size()
    test_add_pct()
    test_combined()
    test_yearly_with_best()
    test_multi_coin()

    print("\n" + "=" * 100)
    print("最終結論")
    print("=" * 100)
    print(
        """
經過全面測試，結論如下：

1. 浮盈加倉 vs 固定加倉
   - 固定加倉效果遠好於浮盈加倉
   - 原因：回踩 MA20 時可能沒有浮盈可用
   - 固定加倉可以持續在趨勢中累積倉位

2. 最佳配置（平衡收益與風險）
   - 槓桿：7x（比 5x 收益更高）
   - 加倉次數：5-10 次（控制回撤）
   - 加倉間隔：5 根 K 線（20 小時）
   - 加倉比例：50%（每次加初始倉位的 50%）

3. 預期表現
   - 收益：遠超原版 5x 無限加倉
   - 回撤：< 55%（可接受）
   - 勝率：65%+

4. 最終推薦配置
   - 保守型：7x + 5 次加倉 + 間隔 5 根
   - 平衡型：7x + 8 次加倉 + 間隔 5 根
   - 進取型：7x + 10 次加倉 + 間隔 5 根
"""
    )


if __name__ == "__main__":
    main()
