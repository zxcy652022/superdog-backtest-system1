#!/usr/bin/env python3
"""
穩健性測試 - 避免過度優化

目標：
1. 不針對特定區間優化
2. 測試不同市場週期的適應性
3. 找出穩定表現的參數組合

測試維度：
- 時間：按季度切分，看每季表現的一致性
- 幣種：前20大幣種，看跨幣種適應性
- 行情類型：牛市/熊市/震盪
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List

import numpy as np
import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy

INITIAL_CASH = 500

# 前20大幣種
TOP_COINS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "SHIBUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "TRXUSDT",
    "MATICUSDT",
    "UNIUSDT",
    "NEARUSDT",
    "LTCUSDT",
    "APTUSDT",
    "FILUSDT",
    "ARBUSDT",
    "OPUSDT",
]


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


def run_backtest(
    df: pd.DataFrame, leverage: int = 7, enable_add: bool = True, max_add: int = 100
) -> Dict:
    """執行回測並返回結果"""
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(initial_cash=INITIAL_CASH)
    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=leverage,
        enable_add_position=enable_add,
        max_add_count=max_add,
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
        "profit_factor": sum(t.pnl for t in win_trades)
        / abs(sum(t.pnl for t in trades if t.pnl < 0))
        if any(t.pnl < 0 for t in trades)
        else float("inf"),
    }


def test_quarterly_consistency():
    """測試季度一致性 - 避免過度擬合特定區間"""
    print("=" * 100)
    print("【1】季度一致性測試 - 檢查策略是否過度擬合特定行情")
    print("=" * 100)

    df = load_data("BTCUSDT")
    if df is None:
        return

    # 按季度切分
    df["quarter"] = df.index.to_period("Q")
    quarters = df["quarter"].unique()

    results = []
    for q in quarters:
        q_df = df[df["quarter"] == q].copy()
        q_df = q_df.drop(columns=["quarter"])

        if len(q_df) < 100:
            continue

        result = run_backtest(q_df, leverage=7)
        if result:
            # 計算該季度的 BTC 漲跌
            btc_return = (q_df.iloc[-1]["close"] / q_df.iloc[0]["close"] - 1) * 100
            result["quarter"] = str(q)
            result["btc_return"] = btc_return
            result["market"] = "牛" if btc_return > 10 else ("熊" if btc_return < -10 else "震盪")
            results.append(result)

    # 打印結果
    print(f"\n{'季度':<12} {'行情':<6} {'BTC漲跌':<10} {'策略收益':<12} {'最大回撤':<10} {'勝率':<8} {'交易數':<8}")
    print("-" * 80)

    for r in results:
        print(
            f"{r['quarter']:<12} {r['market']:<6} {r['btc_return']:>+8.1f}% {r['return_pct']:>+10.1f}% {r['max_dd']:>8.1f}% {r['win_rate']:>6.1f}% {r['trades']:<8}"
        )

    # 統計分析
    returns = [r["return_pct"] for r in results]
    bull_returns = [r["return_pct"] for r in results if r["market"] == "牛"]
    bear_returns = [r["return_pct"] for r in results if r["market"] == "熊"]
    sideways_returns = [r["return_pct"] for r in results if r["market"] == "震盪"]

    print(f"\n統計分析:")
    print(f"  總季度數: {len(results)}")
    print(
        f"  獲利季度: {len([r for r in returns if r > 0])} ({len([r for r in returns if r > 0])/len(returns)*100:.0f}%)"
    )
    print(f"  平均收益: {np.mean(returns):+.1f}%")
    print(f"  收益標準差: {np.std(returns):.1f}%")
    print(f"  最佳季度: {max(returns):+.1f}%")
    print(f"  最差季度: {min(returns):+.1f}%")

    print(f"\n按行情類型:")
    if bull_returns:
        print(f"  牛市 ({len(bull_returns)}季): 平均 {np.mean(bull_returns):+.1f}%")
    if bear_returns:
        print(f"  熊市 ({len(bear_returns)}季): 平均 {np.mean(bear_returns):+.1f}%")
    if sideways_returns:
        print(f"  震盪 ({len(sideways_returns)}季): 平均 {np.mean(sideways_returns):+.1f}%")

    return results


def test_cross_coin_adaptability():
    """測試跨幣種適應性"""
    print("\n" + "=" * 100)
    print("【2】跨幣種適應性測試 - 檢查策略是否只適合特定幣種")
    print("=" * 100)

    results = []

    for symbol in TOP_COINS:
        df = load_data(symbol)
        if df is None:
            continue

        # 只測 2024 年
        df_2024 = df[df.index.year == 2024]
        if len(df_2024) < 100:
            continue

        result = run_backtest(df_2024, leverage=7)
        if result:
            # 計算該幣種 2024 漲跌
            coin_return = (df_2024.iloc[-1]["close"] / df_2024.iloc[0]["close"] - 1) * 100
            result["symbol"] = symbol.replace("USDT", "")
            result["coin_return"] = coin_return
            results.append(result)

    # 按收益排序
    results.sort(key=lambda x: x["return_pct"], reverse=True)

    print(f"\n2024年 前20大幣種表現 (7x槓桿):")
    print(f"\n{'幣種':<10} {'幣種漲跌':<12} {'策略收益':<14} {'最大回撤':<10} {'勝率':<8} {'盈虧比':<10} {'交易數':<8}")
    print("-" * 90)

    for r in results:
        pf = f"{r['profit_factor']:.1f}" if r["profit_factor"] != float("inf") else "∞"
        print(
            f"{r['symbol']:<10} {r['coin_return']:>+10.1f}% {r['return_pct']:>+12.1f}% {r['max_dd']:>8.1f}% {r['win_rate']:>6.1f}% {pf:<10} {r['trades']:<8}"
        )

    # 統計
    returns = [r["return_pct"] for r in results]
    positive = len([r for r in returns if r > 0])

    print(f"\n統計:")
    print(f"  測試幣種: {len(results)}")
    print(f"  獲利幣種: {positive} ({positive/len(results)*100:.0f}%)")
    print(f"  平均收益: {np.mean(returns):+.1f}%")
    print(f"  中位數收益: {np.median(returns):+.1f}%")
    print(f"  最佳: {results[0]['symbol']} {results[0]['return_pct']:+.1f}%")
    print(f"  最差: {results[-1]['symbol']} {results[-1]['return_pct']:+.1f}%")

    return results


def test_parameter_sensitivity():
    """測試參數敏感度 - 檢查是否過度依賴特定參數"""
    print("\n" + "=" * 100)
    print("【3】參數敏感度測試 - 檢查策略是否過度依賴特定參數")
    print("=" * 100)

    df = load_data("BTCUSDT")
    df_2024 = df[df.index.year == 2024]

    # 測試不同槓桿
    leverages = [3, 5, 7, 10, 15, 20]

    print(f"\n槓桿敏感度 (2024 BTC):")
    print(f"{'槓桿':<8} {'收益':<14} {'最大回撤':<12} {'勝率':<10} {'風險調整收益':<15}")
    print("-" * 60)

    for lev in leverages:
        result = run_backtest(df_2024, leverage=lev)
        if result:
            # 風險調整收益 = 收益 / |回撤|
            risk_adj = (
                result["return_pct"] / abs(result["max_dd"])
                if result["max_dd"] != 0
                else float("inf")
            )
            print(
                f"{lev}x{'':<5} {result['return_pct']:>+12.1f}% {result['max_dd']:>10.1f}% {result['win_rate']:>8.1f}% {risk_adj:>13.2f}"
            )

    # 測試加倉 vs 不加倉
    print(f"\n加倉效果對比:")
    print(f"{'配置':<20} {'收益':<14} {'最大回撤':<12} {'交易數':<10}")
    print("-" * 60)

    for enable_add, max_add, name in [
        (False, 0, "不加倉"),
        (True, 2, "最多加2次"),
        (True, 5, "最多加5次"),
        (True, 100, "無限加倉"),
    ]:
        result = run_backtest(df_2024, leverage=7, enable_add=enable_add, max_add=max_add)
        if result:
            print(
                f"{name:<20} {result['return_pct']:>+12.1f}% {result['max_dd']:>10.1f}% {result['trades']:<10}"
            )


def test_yearly_stability():
    """測試年度穩定性"""
    print("\n" + "=" * 100)
    print("【4】年度穩定性測試 - 檢查長期表現")
    print("=" * 100)

    df = load_data("BTCUSDT")
    years = sorted(df.index.year.unique())

    results = []
    for year in years:
        year_df = df[df.index.year == year]
        if len(year_df) < 200:
            continue

        result = run_backtest(year_df, leverage=7)
        if result:
            btc_return = (year_df.iloc[-1]["close"] / year_df.iloc[0]["close"] - 1) * 100
            result["year"] = year
            result["btc_return"] = btc_return
            results.append(result)

    print(f"\nBTC 逐年表現 (7x槓桿):")
    print(f"{'年份':<8} {'BTC漲跌':<12} {'策略收益':<14} {'最大回撤':<12} {'勝率':<10} {'交易數':<8}")
    print("-" * 70)

    for r in results:
        print(
            f"{r['year']:<8} {r['btc_return']:>+10.1f}% {r['return_pct']:>+12.1f}% {r['max_dd']:>10.1f}% {r['win_rate']:>8.1f}% {r['trades']:<8}"
        )

    # 計算複利累計
    cumulative = 1.0
    for r in results:
        cumulative *= 1 + r["return_pct"] / 100

    returns = [r["return_pct"] for r in results]
    print(f"\n長期統計:")
    print(f"  測試年數: {len(results)}")
    print(f"  獲利年數: {len([r for r in returns if r > 0])}")
    print(f"  平均年收益: {np.mean(returns):+.1f}%")
    print(f"  複利累計: {cumulative:.1f}x ({(cumulative-1)*100:.0f}%)")


def main():
    """主函數"""
    print("=" * 100)
    print("BiGe 雙均線策略 - 穩健性測試")
    print("目標：避免過度優化，找出適應性高的配置")
    print("=" * 100)

    # 1. 季度一致性
    test_quarterly_consistency()

    # 2. 跨幣種適應性
    test_cross_coin_adaptability()

    # 3. 參數敏感度
    test_parameter_sensitivity()

    # 4. 年度穩定性
    test_yearly_stability()

    # 結論
    print("\n" + "=" * 100)
    print("【結論】")
    print("=" * 100)
    print(
        """
穩健策略的標準：
1. 季度一致性：大多數季度獲利，不只在特定行情好
2. 跨幣種適應性：在多數主流幣種上都能獲利
3. 參數敏感度：參數小幅變化不會導致績效劇烈改變
4. 年度穩定性：長期複利為正，不會某年大虧

如果策略在以上測試中表現良好，說明它具有較高的適應性，
不是過度優化的結果，更適合實盤使用。
"""
    )


if __name__ == "__main__":
    main()
