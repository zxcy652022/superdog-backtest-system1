#!/usr/bin/env python3
"""
Top 50 幣種回測 - 使用恢復後的配置

配置：
- 槓桿：動態（初始 20x → 隨盈利遞減 → 最低 5x）
- 加倉：無限制（max_add_count=100）
- 滑點：0.05%
- 回撤保護：禁用
- 時間：2018-2024
- 時間框架：4H
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy

INITIAL_CASH = 500
SLIPPAGE = 0.0005  # 0.05%

# Top 20 幣種（按市值排序，排除穩定幣）
TOP_20_COINS = [
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
    """載入歷史數據"""
    data_path = f"/Volumes/權志龍的寶藏/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    if not os.path.exists(data_path):
        return None
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


def run_backtest(df: pd.DataFrame) -> Dict:
    """執行單次回測"""
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(
        initial_cash=INITIAL_CASH,
        slippage_rate=SLIPPAGE,
    )

    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=7,  # 7x 槓桿（平衡收益與回撤）
        dynamic_leverage=False,  # 關閉動態槓桿
        enable_add_position=True,
        max_add_count=3,  # 最多加倉 3 次（控制回撤）
        max_drawdown_pct=1.0,  # 禁用回撤保護
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
    lose_trades = [t for t in trades if t.pnl < 0]

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "profit_factor": sum(t.pnl for t in win_trades) / abs(sum(t.pnl for t in lose_trades))
        if lose_trades
        else float("inf"),
    }


def run_yearly_backtest(df: pd.DataFrame, year: int) -> Dict:
    """執行單年回測"""
    year_df = df[df.index.year == year]
    if len(year_df) < 100:
        return None
    return run_backtest(year_df)


def main():
    """主函數"""
    print("=" * 120)
    print("BiGe 雙均線策略 - Top 20 幣種回測")
    print("=" * 120)
    print(f"\n配置：固定槓桿 7x | 加倉=最多3次 | 滑點=0.05% | 回撤保護=禁用")
    print(f"初始資金：${INITIAL_CASH}")
    print(f"時間框架：4H")
    print()

    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

    # 收集所有結果
    all_results = []
    yearly_summary = {year: [] for year in years}

    # 打印表頭
    header = f"{'幣種':<12}"
    for year in years:
        header += f"{year:>12}"
    header += f"{'累計':>14}"
    print(header)
    print("-" * 110)

    available_coins = 0
    profitable_coins = 0

    for symbol in TOP_20_COINS:
        df = load_data(symbol)
        if df is None:
            continue

        available_coins += 1
        coin_name = symbol.replace("USDT", "")
        row = f"{coin_name:<12}"

        yearly_returns = []
        has_data = False

        for year in years:
            result = run_yearly_backtest(df, year)
            if result:
                has_data = True
                yearly_returns.append(result["return_pct"])
                yearly_summary[year].append(result["return_pct"])

                # 格式化顯示
                if result["return_pct"] > 1000:
                    row += f"{result['return_pct']/100:>+10.0f}x  "
                else:
                    row += f"{result['return_pct']:>+10.0f}%  "
            else:
                yearly_returns.append(None)
                row += f"{'N/A':>12}"

        if has_data:
            # 計算累計收益（複利）
            cumulative = 1.0
            for ret in yearly_returns:
                if ret is not None:
                    cumulative *= 1 + ret / 100

            total_return = (cumulative - 1) * 100

            if total_return > 0:
                profitable_coins += 1

            if total_return > 10000:
                row += f"{total_return/100:>+12.0f}x"
            else:
                row += f"{total_return:>+12.0f}%"

            all_results.append(
                {
                    "symbol": coin_name,
                    "yearly_returns": yearly_returns,
                    "cumulative": total_return,
                }
            )

            print(row)

    # 打印年度統計
    print("-" * 110)

    # 平均值行
    avg_row = f"{'平均':<12}"
    for year in years:
        if yearly_summary[year]:
            avg = np.mean(yearly_summary[year])
            if avg > 1000:
                avg_row += f"{avg/100:>+10.0f}x  "
            else:
                avg_row += f"{avg:>+10.0f}%  "
        else:
            avg_row += f"{'N/A':>12}"
    print(avg_row)

    # 勝率行
    win_row = f"{'勝率':<12}"
    for year in years:
        if yearly_summary[year]:
            wins = len([r for r in yearly_summary[year] if r > 0])
            win_rate = wins / len(yearly_summary[year]) * 100
            win_row += f"{win_rate:>10.0f}%  "
        else:
            win_row += f"{'N/A':>12}"
    print(win_row)

    # 總結統計
    print("\n" + "=" * 120)
    print("總結統計")
    print("=" * 120)

    print(f"\n測試幣種數：{available_coins}")
    print(f"有效回測數：{len(all_results)}")
    print(
        f"累計盈利幣種：{profitable_coins} ({profitable_coins/len(all_results)*100:.0f}%)"
        if all_results
        else ""
    )

    if all_results:
        cumulative_returns = [r["cumulative"] for r in all_results]
        print(f"\n累計收益統計：")
        print(f"  平均：{np.mean(cumulative_returns):+,.0f}%")
        print(f"  中位數：{np.median(cumulative_returns):+,.0f}%")
        print(f"  最佳：{max(cumulative_returns):+,.0f}%")
        print(f"  最差：{min(cumulative_returns):+,.0f}%")

        # 找出最佳和最差幣種
        best = max(all_results, key=lambda x: x["cumulative"])
        worst = min(all_results, key=lambda x: x["cumulative"])
        print(f"\n最佳幣種：{best['symbol']} ({best['cumulative']:+,.0f}%)")
        print(f"最差幣種：{worst['symbol']} ({worst['cumulative']:+,.0f}%)")

        # 年度平均
        print(f"\n年度平均收益：")
        for year in years:
            if yearly_summary[year]:
                avg = np.mean(yearly_summary[year])
                wins = len([r for r in yearly_summary[year] if r > 0])
                total = len(yearly_summary[year])
                print(f"  {year}: {avg:+,.0f}% (勝率 {wins/total*100:.0f}%, n={total})")


if __name__ == "__main__":
    main()
