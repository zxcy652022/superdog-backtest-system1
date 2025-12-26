#!/usr/bin/env python3
"""
加倉策略優化測試 - 浮盈加倉模式

核心概念：用浮盈（已賺到的錢）來加倉，而不是用本金
這樣即使加倉後虧損，也只是「少賺」而不是「虧本金」

測試方向：
1. 浮盈加倉 vs 固定比例加倉
2. 只有盈利時才加倉
3. 浮盈加倉比例：50%, 100%, 150%
4. 加倉次數限制的影響
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from typing import Dict, List

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


def run_backtest(df: pd.DataFrame, **strategy_params) -> dict:
    """執行回測"""
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(
        initial_cash=INITIAL_CASH,
        slippage_rate=SLIPPAGE,
    )

    # 合併默認參數
    params = {
        "leverage": 7,
        "dynamic_leverage": False,
        "enable_add_position": True,
        "max_add_count": 100,
        "max_drawdown_pct": 1.0,
    }
    params.update(strategy_params)

    strategy = BiGeDualMAStrategy(broker, df.copy(), **params)

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

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "liquidations": broker.liquidation_count,
        "avg_add_count": strategy.add_count,  # 最後一筆交易的加倉次數（參考用）
    }


def run_yearly_backtest(df: pd.DataFrame, **params) -> List[dict]:
    """逐年回測"""
    years = [2019, 2020, 2021, 2022, 2023, 2024]
    results = []

    for year in years:
        year_df = df[df.index.year == year]
        if len(year_df) < 100:
            results.append(None)
            continue
        r = run_backtest(year_df, **params)
        results.append(r)

    return results


def format_return(ret: float) -> str:
    """格式化收益"""
    if ret > 100000:
        return f"{ret/100:>+10,.0f}x"
    elif ret > 1000:
        return f"{ret:>+10,.0f}%"
    else:
        return f"{ret:>+10.0f}%"


def format_final(final: float) -> str:
    """格式化最終金額"""
    if final > 1e9:
        return f"${final/1e9:>12,.1f}B"
    elif final > 1e6:
        return f"${final/1e6:>12,.1f}M"
    else:
        return f"${final:>12,.0f}"


def test_floating_pnl_vs_fixed():
    """測試浮盈加倉 vs 固定比例"""
    print("=" * 110)
    print("1. 浮盈加倉 vs 固定比例 - 7x 槓桿")
    print("=" * 110)
    print("\n核心問題：用浮盈加倉（已賺的錢）vs 用本金加倉（風險更高）\n")

    df = load_data("BTCUSDT")

    configs = [
        {"name": "不加倉", "enable_add_position": False},
        {"name": "固定30%", "add_position_mode": "fixed_30"},
        {"name": "固定50%", "add_position_mode": "fixed_50"},
        {"name": "浮盈50%", "add_position_mode": "floating_pnl", "add_position_pnl_pct": 0.50},
        {"name": "浮盈100%", "add_position_mode": "floating_pnl", "add_position_pnl_pct": 1.0},
        {"name": "浮盈150%", "add_position_mode": "floating_pnl", "add_position_pnl_pct": 1.5},
    ]

    print(f"{'配置':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8} {'交易':>6}")
    print("-" * 75)

    for cfg in configs:
        params = {k: v for k, v in cfg.items() if k != "name"}
        r = run_backtest(df.copy(), leverage=7, max_add_count=100, **params)
        if r:
            print(
                f"{cfg['name']:<12} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}% {r['trades']:>6}"
            )


def test_floating_with_add_count():
    """測試浮盈加倉 + 加倉次數限制"""
    print("\n" + "=" * 110)
    print("2. 浮盈加倉 + 加倉次數限制 - 7x 槓桿")
    print("=" * 110)
    print("\n問題：浮盈加倉時，限制次數是否能控制回撤？\n")

    df = load_data("BTCUSDT")

    configs = [
        {
            "name": "浮盈+不限",
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
        {
            "name": "浮盈+10次",
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 10,
        },
        {
            "name": "浮盈+5次",
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 5,
        },
        {
            "name": "浮盈+3次",
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 3,
        },
        {"name": "固定50%+不限", "add_position_mode": "fixed_50", "max_add_count": 100},
        {"name": "固定50%+3次", "add_position_mode": "fixed_50", "max_add_count": 3},
    ]

    print(f"{'配置':<16} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 75)

    for cfg in configs:
        params = {k: v for k, v in cfg.items() if k != "name"}
        r = run_backtest(df.copy(), leverage=7, **params)
        if r:
            print(
                f"{cfg['name']:<16} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_add_interval():
    """測試加倉間隔的影響"""
    print("\n" + "=" * 110)
    print("3. 加倉間隔測試 - 7x 槓桿 + 無限加倉")
    print("=" * 110)
    print("\n間隔越長 = 加倉次數越少 = 回撤可能更低\n")

    df = load_data("BTCUSDT")

    intervals = [1, 2, 3, 5, 8, 10, 15]

    print(f"{'間隔(K線)':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for interval in intervals:
        r = run_backtest(
            df.copy(), leverage=7, max_add_count=100, add_position_min_interval=interval
        )
        if r:
            print(
                f"{interval:<12} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_pullback_tolerance():
    """測試回踩容許範圍"""
    print("\n" + "=" * 110)
    print("4. 回踩容許範圍測試 - 7x 槓桿 + 無限加倉")
    print("=" * 110)
    print("\n範圍越大 = 更容易觸發加倉 = 加倉次數更多\n")

    df = load_data("BTCUSDT")

    tolerances = [0.010, 0.015, 0.018, 0.020, 0.025, 0.030]

    print(f"{'容許範圍':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for tol in tolerances:
        r = run_backtest(df.copy(), leverage=7, max_add_count=100, pullback_tolerance=tol)
        if r:
            print(
                f"{tol*100:.1f}%{'':<8} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_combined_optimization():
    """組合優化：浮盈加倉為主"""
    print("\n" + "=" * 110)
    print("5. 組合優化 - 浮盈加倉模式 - 目標：回撤 < 60%")
    print("=" * 110)

    df = load_data("BTCUSDT")

    results = []

    # 測試浮盈加倉的不同組合
    for leverage in [6, 7, 8]:
        for max_add in [5, 10, 20, 100]:
            for interval in [3, 5, 8]:
                for pnl_pct in [0.5, 1.0, 1.5, 2.0]:
                    r = run_backtest(
                        df.copy(),
                        leverage=leverage,
                        max_add_count=max_add,
                        add_position_min_interval=interval,
                        add_position_mode="floating_pnl",
                        add_position_pnl_pct=pnl_pct,
                    )
                    if r:
                        results.append(
                            {
                                "leverage": leverage,
                                "max_add": max_add,
                                "interval": interval,
                                "pnl_pct": pnl_pct,
                                "mode": "浮盈",
                                "return": r["return_pct"],
                                "max_dd": r["max_dd"],
                                "liquidations": r["liquidations"],
                                "calmar": r["return_pct"] / abs(r["max_dd"])
                                if r["max_dd"] != 0
                                else 0,
                            }
                        )

    # 篩選回撤 < 60% 且無爆倉的配置
    valid = [r for r in results if r["max_dd"] > -60 and r["liquidations"] == 0]
    valid.sort(key=lambda x: x["return"], reverse=True)

    print(f"\n浮盈加倉：回撤 < 60% 且無爆倉的配置（按收益排序 Top 15）：\n")
    print(f"{'槓桿':<6} {'加倉上限':<10} {'間隔':<6} {'浮盈比例':<10} {'收益':>14} {'回撤':>10} {'Calmar':>10}")
    print("-" * 80)

    for c in valid[:15]:
        add_str = f"最多{c['max_add']}" if c["max_add"] < 100 else "無限"
        print(
            f"{c['leverage']}x{'':<4} {add_str:<10} {c['interval']}根{'':<4} {c['pnl_pct']*100:.0f}%{'':<7} {format_return(c['return'])} {c['max_dd']:>9.1f}% {c['calmar']:>10.0f}"
        )


def test_fuyun_rolling():
    """測試浮雲滾倉邏輯"""
    print("\n" + "=" * 110)
    print("6. 浮雲滾倉測試 - 高槓桿+浮盈加倉+動態降槓桿")
    print("=" * 110)
    print(
        """
浮雲滾倉核心邏輯：
1. 初期用高槓桿（20x-50x）快速累積資本
2. 用浮盈（已賺的錢）加倉，不用本金
3. 隨著盈利增加，逐步降低槓桿保護利潤
4. 最終槓桿降到 3-5x 時非常安全

結合幣哥策略的優勢：
- 低勝率但高盈虧比 = 抓到大趨勢行情
- 大趨勢正好適合浮盈滾倉
"""
    )

    df = load_data("BTCUSDT")

    configs = [
        # 傳統固定槓桿
        {
            "name": "固定5x+固定50%",
            "leverage": 5,
            "dynamic_leverage": False,
            "add_position_mode": "fixed_50",
            "max_add_count": 100,
        },
        {
            "name": "固定7x+固定50%",
            "leverage": 7,
            "dynamic_leverage": False,
            "add_position_mode": "fixed_50",
            "max_add_count": 100,
        },
        # 浮雲滾倉：固定槓桿+浮盈加倉
        {
            "name": "固定7x+浮盈100%",
            "leverage": 7,
            "dynamic_leverage": False,
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
        {
            "name": "固定10x+浮盈100%",
            "leverage": 10,
            "dynamic_leverage": False,
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
        # 浮雲滾倉：動態槓桿+浮盈加倉
        {
            "name": "動態20→5x+浮盈",
            "leverage": 20,
            "dynamic_leverage": True,
            "initial_leverage": 20,
            "min_leverage": 5,
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
        {
            "name": "動態30→5x+浮盈",
            "leverage": 30,
            "dynamic_leverage": True,
            "initial_leverage": 30,
            "min_leverage": 5,
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
        {
            "name": "動態50→5x+浮盈",
            "leverage": 50,
            "dynamic_leverage": True,
            "initial_leverage": 50,
            "min_leverage": 5,
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
    ]

    print(f"\n{'配置':<20} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 80)

    for cfg in configs:
        params = {k: v for k, v in cfg.items() if k != "name"}
        r = run_backtest(df.copy(), **params)
        if r:
            print(
                f"{cfg['name']:<20} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_yearly_comparison():
    """逐年比較不同配置"""
    print("\n" + "=" * 110)
    print("7. 逐年比較：固定加倉 vs 浮盈加倉 vs 浮雲滾倉")
    print("=" * 110)

    df = load_data("BTCUSDT")
    years = [2020, 2021, 2022, 2023, 2024]

    configs = [
        {"name": "5x+固定50%", "leverage": 5, "add_position_mode": "fixed_50", "max_add_count": 100},
        {"name": "7x+固定50%", "leverage": 7, "add_position_mode": "fixed_50", "max_add_count": 100},
        {
            "name": "7x+浮盈100%",
            "leverage": 7,
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
        {
            "name": "動態20→5x+浮盈",
            "leverage": 20,
            "dynamic_leverage": True,
            "initial_leverage": 20,
            "min_leverage": 5,
            "add_position_mode": "floating_pnl",
            "add_position_pnl_pct": 1.0,
            "max_add_count": 100,
        },
    ]

    print(f"\n{'年份':<8}", end="")
    for cfg in configs:
        print(f"{cfg['name']:>18}", end="")
    print()
    print("-" * 100)

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
                    print(f"{r['return_pct']/100:>+14.0f}x{liq_str}", end="")
                else:
                    print(f"{r['return_pct']:>+14.0f}%{liq_str}", end="")
        print()

    # 統計
    print("-" * 100)
    print(f"{'累計':<8}", end="")
    for cfg in configs:
        returns = [r["return"] for r in yearly_results[cfg["name"]]]
        cumulative = 1.0
        for ret in returns:
            cumulative *= 1 + ret / 100
        if (cumulative - 1) * 100 > 100000:
            print(f"{cumulative-1:>+14.0f}x", end="")
        else:
            print(f"{(cumulative-1)*100:>+14,.0f}%", end="")
    print()

    print(f"{'最大回撤':<8}", end="")
    for cfg in configs:
        max_dds = [r["max_dd"] for r in yearly_results[cfg["name"]]]
        worst = min(max_dds) if max_dds else 0
        print(f"{worst:>18.1f}%", end="")
    print()


def test_multi_coin():
    """多幣種測試"""
    print("\n" + "=" * 110)
    print("7. 多幣種驗證 - 比較不同加倉策略")
    print("=" * 110)

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
        {"name": "7x+3次", "leverage": 7, "max_add_count": 3},
        {"name": "7x+5次", "leverage": 7, "max_add_count": 5},
        {"name": "7x+10次", "leverage": 7, "max_add_count": 10},
        {"name": "5x+無限", "leverage": 5, "max_add_count": 100},
    ]

    # 收集結果
    results = {cfg["name"]: {"returns": [], "max_dds": [], "profitable": 0} for cfg in configs}

    print(f"\n{'幣種':<12}", end="")
    for cfg in configs:
        print(f"{cfg['name']:>16}", end="")
    print()
    print("-" * 80)

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

    # 統計
    print("-" * 80)
    print(f"{'平均收益':<12}", end="")
    for cfg in configs:
        avg = np.mean(results[cfg["name"]]["returns"])
        if avg > 10000:
            print(f"{avg/100:>+14.0f}x", end="")
        else:
            print(f"{avg:>+14,.0f}%", end="")
    print()

    print(f"{'中位數收益':<12}", end="")
    for cfg in configs:
        med = np.median(results[cfg["name"]]["returns"])
        if med > 10000:
            print(f"{med/100:>+14.0f}x", end="")
        else:
            print(f"{med:>+14,.0f}%", end="")
    print()

    print(f"{'平均最大回撤':<12}", end="")
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
    test_floating_pnl_vs_fixed()
    test_floating_with_add_count()
    test_add_interval()
    test_pullback_tolerance()
    test_combined_optimization()
    test_fuyun_rolling()
    test_yearly_comparison()
    test_multi_coin()

    print("\n" + "=" * 110)
    print("結論與建議 - 浮雲滾倉 + 幣哥策略")
    print("=" * 110)
    print(
        """
浮雲滾倉策略核心邏輯（來源：午飯投資）：

1. 核心理念
   - 用浮盈（已賺的錢）加倉，不是用本金
   - 這樣即使加倉後虧損，也只是「少賺」而不是「虧本金」
   - 初期高槓桿衝刺，盈利後降槓桿保護

2. 與幣哥策略的完美契合
   - 幣哥策略：低勝率（30-40%）+ 高盈虧比（1:3+）
   - 意味著：勝利時會有一大段順向行情
   - 正好適合浮盈滾倉需要大趨勢行情的特性

3. 建議配置
   - 保守型：7x 固定槓桿 + 浮盈 100% 加倉
   - 平衡型：動態 10→5x 槓桿 + 浮盈 100% 加倉
   - 激進型：動態 20→5x 槓桿 + 浮盈 100% 加倉

4. 勝率改善方向（後續優化）
   - 優化進場條件（均線密集度、趨勢強度）
   - 優化止損邏輯（減少假突破掃損）
   - 優化加倉時機（只在趨勢確認後加倉）

Sources:
- 浮雲滾倉策略: https://biquanzhijia.com/forums/topic/bi-quan-bao-fu-fang-fa-fu-yun-gun-cang-pei-lyu-neng-dao
- 午飯投資教學: https://blog.tangly1024.com/article/rolling-positions-and-adding-to-profits-in-trading
"""
    )


if __name__ == "__main__":
    main()
