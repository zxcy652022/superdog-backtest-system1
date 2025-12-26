#!/usr/bin/env python3
"""
BiGe 雙均線策略 - 完整回測報表
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

TOP_50_COINS = [
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
    "ATOMUSDT",
    "XLMUSDT",
    "ETCUSDT",
    "INJUSDT",
    "STXUSDT",
    "IMXUSDT",
    "HBARUSDT",
    "VETUSDT",
    "MKRUSDT",
    "GRTUSDT",
    "RNDRUSDT",
    "THETAUSDT",
    "FTMUSDT",
    "TIAUSDT",
    "ALGOUSDT",
    "RUNEUSDT",
    "SEIUSDT",
    "AAVEUSDT",
    "FLOWUSDT",
    "SUIUSDT",
    "XTZUSDT",
    "EGLDUSDT",
    "AXSUSDT",
    "SANDUSDT",
    "MANAUSDT",
    "SNXUSDT",
    "EOSUSDT",
    "CRVUSDT",
    "CHZUSDT",
    "APEUSDT",
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


def run_backtest(df: pd.DataFrame) -> Dict:
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(
        initial_cash=INITIAL_CASH,
        slippage_rate=SLIPPAGE,
    )

    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=10,
        dynamic_leverage=True,
        initial_leverage=10,
        min_leverage=5,
        enable_add_position=True,
        max_add_count=100,
        max_drawdown_pct=1.0,
    )

    equity_curve = []
    peak = INITIAL_CASH
    max_dd = 0

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
    lose_trades = [t for t in trades if t.pnl < 0]

    # 計算平均持倉時間
    avg_hold_time = None
    if trades:
        hold_times = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in trades]
        avg_hold_time = np.mean(hold_times)

    # 計算盈虧比
    avg_win = np.mean([t.pnl for t in win_trades]) if win_trades else 0
    avg_lose = abs(np.mean([t.pnl for t in lose_trades])) if lose_trades else 0
    risk_reward = avg_win / avg_lose if avg_lose > 0 else float("inf")

    # 計算爆倉次數
    liquidations = len([t for t in trades if hasattr(t, "is_liquidation") and t.is_liquidation])

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_trades": len(win_trades),
        "lose_trades": len(lose_trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "profit_factor": sum(t.pnl for t in win_trades) / abs(sum(t.pnl for t in lose_trades))
        if lose_trades
        else float("inf"),
        "avg_win": avg_win,
        "avg_lose": avg_lose,
        "risk_reward": risk_reward,
        "avg_hold_hours": avg_hold_time,
        "liquidations": liquidations,
        "equity_curve": equity_curve,
    }


def run_yearly_backtest(df: pd.DataFrame, year: int) -> Dict:
    year_df = df[df.index.year == year]
    if len(year_df) < 100:
        return None
    return run_backtest(year_df)


def main():
    print()
    print("╔" + "═" * 118 + "╗")
    print("║" + " " * 40 + "BiGe 雙均線策略 - 完整回測報表" + " " * 41 + "║")
    print("╚" + "═" * 118 + "╝")

    print()
    print("┌" + "─" * 118 + "┐")
    print(
        "│  策略配置                                                                                                           │"
    )
    print("├" + "─" * 118 + "┤")
    print(
        "│  • 策略名稱：BiGe 雙均線趨勢跟隨策略                                                                                │"
    )
    print(
        "│  • 時間框架：4H (4小時線)                                                                                           │"
    )
    print(
        "│  • 槓桿模式：動態槓桿 (10x → 5x，隨盈利遞減)                                                                        │"
    )
    print(
        "│  • 加倉機制：無限加倉 (max_add_count=100)                                                                           │"
    )
    print(
        "│  • 滑點設置：0.05% (單邊)                                                                                           │"
    )
    print(
        "│  • 回撤保護：禁用                                                                                                   │"
    )
    print(
        "│  • 爆倉檢測：已啟用                                                                                                 │"
    )
    print(
        f"│  • 初始資金：${INITIAL_CASH}                                                                                              │"
    )
    print(
        "│  • 測試區間：2018-2024                                                                                              │"
    )
    print("└" + "─" * 118 + "┘")

    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

    # 收集所有結果
    all_results = []
    yearly_summary = {year: [] for year in years}
    detailed_results = []

    print()
    print("┌" + "─" * 118 + "┐")
    print(
        "│  各幣種年度收益表                                                                                                   │"
    )
    print("├" + "─" * 118 + "┤")

    # 表頭
    header = f"│  {'幣種':<10}"
    for year in years:
        header += f"{year:>12}"
    header += f"{'累計':>16}  │"
    print(header)
    print("├" + "─" * 118 + "┤")

    for symbol in TOP_50_COINS:
        df = load_data(symbol)
        if df is None:
            continue

        coin_name = symbol.replace("USDT", "")
        row = f"│  {coin_name:<10}"

        yearly_returns = []
        yearly_details = {}
        has_data = False

        for year in years:
            result = run_yearly_backtest(df, year)
            if result:
                has_data = True
                yearly_returns.append(result["return_pct"])
                yearly_summary[year].append(result["return_pct"])
                yearly_details[year] = result

                if result["return_pct"] > 1000:
                    row += f"{result['return_pct']/100:>+10.0f}x  "
                else:
                    row += f"{result['return_pct']:>+10.0f}%  "
            else:
                yearly_returns.append(None)
                row += f"{'N/A':>12}"

        if has_data:
            cumulative = 1.0
            for ret in yearly_returns:
                if ret is not None:
                    cumulative *= 1 + ret / 100

            total_return = (cumulative - 1) * 100

            if total_return > 10000:
                row += f"{total_return/100:>+14.0f}x  │"
            else:
                row += f"{total_return:>+14.0f}%  │"

            all_results.append(
                {
                    "symbol": coin_name,
                    "yearly_returns": yearly_returns,
                    "cumulative": total_return,
                    "yearly_details": yearly_details,
                }
            )

            print(row)

    print("├" + "─" * 118 + "┤")

    # 平均值行
    avg_row = f"│  {'平均':<10}"
    for year in years:
        if yearly_summary[year]:
            avg = np.mean(yearly_summary[year])
            if avg > 1000:
                avg_row += f"{avg/100:>+10.0f}x  "
            else:
                avg_row += f"{avg:>+10.0f}%  "
        else:
            avg_row += f"{'N/A':>12}"
    avg_row += " " * 18 + "│"
    print(avg_row)

    # 勝率行
    win_row = f"│  {'勝率':<10}"
    for year in years:
        if yearly_summary[year]:
            wins = len([r for r in yearly_summary[year] if r > 0])
            win_rate = wins / len(yearly_summary[year]) * 100
            win_row += f"{win_rate:>10.0f}%  "
        else:
            win_row += f"{'N/A':>12}"
    win_row += " " * 18 + "│"
    print(win_row)

    print("└" + "─" * 118 + "┘")

    # 總結統計
    print()
    print("┌" + "─" * 118 + "┐")
    print(
        "│  績效總結                                                                                                           │"
    )
    print("├" + "─" * 118 + "┤")

    cumulative_returns = [r["cumulative"] for r in all_results]
    profitable_coins = len([r for r in cumulative_returns if r > 0])

    print(f"│  測試幣種數：{len(all_results):<106}│")
    profit_str = f"{profitable_coins} ({profitable_coins/len(all_results)*100:.0f}%)"
    print(f"│  累計盈利幣種：{profit_str:<101}│")
    print("├" + "─" * 118 + "┤")
    print("│  累計收益統計：" + " " * 102 + "│")
    avg_ret = f"{np.mean(cumulative_returns):+,.0f}%"
    med_ret = f"{np.median(cumulative_returns):+,.0f}%"
    max_ret = f"{max(cumulative_returns):+,.0f}%"
    min_ret = f"{min(cumulative_returns):+,.0f}%"
    print(f"│    • 平均收益：{avg_ret:<99}│")
    print(f"│    • 中位數收益：{med_ret:<97}│")
    print(f"│    • 最佳收益：{max_ret:<99}│")
    print(f"│    • 最差收益：{min_ret:<99}│")

    best = max(all_results, key=lambda x: x["cumulative"])
    worst = min(all_results, key=lambda x: x["cumulative"])

    print("├" + "─" * 118 + "┤")
    best_str = f"{best['symbol']} ({best['cumulative']:+,.0f}%)"
    worst_str = f"{worst['symbol']} ({worst['cumulative']:+,.0f}%)"
    print(f"│  最佳幣種：{best_str:<103}│")
    print(f"│  最差幣種：{worst_str:<103}│")
    print("└" + "─" * 118 + "┘")

    # 年度詳細統計
    print()
    print("┌" + "─" * 118 + "┐")
    print(
        "│  年度詳細統計                                                                                                       │"
    )
    print("├" + "─" * 118 + "┤")
    print(
        f"│  {'年份':<8}{'平均收益':>14}{'勝率':>12}{'測試幣種':>12}{'盈利幣種':>12}{'虧損幣種':>12}{'最佳':>18}{'最差':>18}   │"
    )
    print("├" + "─" * 118 + "┤")

    for year in years:
        if yearly_summary[year]:
            returns = yearly_summary[year]
            avg = np.mean(returns)
            wins = len([r for r in returns if r > 0])
            losses = len([r for r in returns if r <= 0])
            total = len(returns)
            best_ret = max(returns)
            worst_ret = min(returns)

            avg_str = f"{avg:+,.0f}%" if avg < 1000 else f"{avg/100:+,.0f}x"
            best_str = f"{best_ret:+,.0f}%" if best_ret < 1000 else f"{best_ret/100:+,.0f}x"
            worst_str = f"{worst_ret:+,.0f}%"

            row = f"│  {year:<8}{avg_str:>14}{wins/total*100:>10.0f}%{total:>12}{wins:>12}{losses:>12}{best_str:>18}{worst_str:>18}   │"
            print(row)

    print("└" + "─" * 118 + "┘")

    # Top 10 最佳表現
    print()
    print("┌" + "─" * 118 + "┐")
    print(
        "│  Top 10 最佳表現幣種                                                                                                │"
    )
    print("├" + "─" * 118 + "┤")
    print(
        f"│  {'排名':<6}{'幣種':<10}{'累計收益':>18}{'2023':>14}{'2024':>14}                                                     │"
    )
    print("├" + "─" * 118 + "┤")

    sorted_results = sorted(all_results, key=lambda x: x["cumulative"], reverse=True)
    for i, r in enumerate(sorted_results[:10], 1):
        cumul = (
            f"{r['cumulative']:+,.0f}%"
            if r["cumulative"] < 10000
            else f"{r['cumulative']/100:+,.0f}x"
        )

        ret_2023 = r["yearly_returns"][5] if r["yearly_returns"][5] is not None else "N/A"
        ret_2024 = r["yearly_returns"][6] if r["yearly_returns"][6] is not None else "N/A"

        if isinstance(ret_2023, float):
            ret_2023 = f"{ret_2023:+,.0f}%" if ret_2023 < 1000 else f"{ret_2023/100:+,.0f}x"
        if isinstance(ret_2024, float):
            ret_2024 = f"{ret_2024:+,.0f}%" if ret_2024 < 1000 else f"{ret_2024/100:+,.0f}x"

        row = f"│  {i:<6}{r['symbol']:<10}{cumul:>18}{ret_2023:>14}{ret_2024:>14}                                                     │"
        print(row)

    print("└" + "─" * 118 + "┘")

    # Top 10 最差表現
    print()
    print("┌" + "─" * 118 + "┐")
    print(
        "│  Top 10 最差表現幣種                                                                                                │"
    )
    print("├" + "─" * 118 + "┤")
    print(
        f"│  {'排名':<6}{'幣種':<10}{'累計收益':>18}{'2023':>14}{'2024':>14}                                                     │"
    )
    print("├" + "─" * 118 + "┤")

    for i, r in enumerate(sorted_results[-10:][::-1], 1):
        cumul = (
            f"{r['cumulative']:+,.0f}%"
            if r["cumulative"] < 10000
            else f"{r['cumulative']/100:+,.0f}x"
        )

        ret_2023 = r["yearly_returns"][5] if r["yearly_returns"][5] is not None else "N/A"
        ret_2024 = r["yearly_returns"][6] if r["yearly_returns"][6] is not None else "N/A"

        if isinstance(ret_2023, float):
            ret_2023 = f"{ret_2023:+,.0f}%" if ret_2023 < 1000 else f"{ret_2023/100:+,.0f}x"
        if isinstance(ret_2024, float):
            ret_2024 = f"{ret_2024:+,.0f}%" if ret_2024 < 1000 else f"{ret_2024/100:+,.0f}x"

        row = f"│  {i:<6}{r['symbol']:<10}{cumul:>18}{ret_2023:>14}{ret_2024:>14}                                                     │"
        print(row)

    print("└" + "─" * 118 + "┘")

    # 風險警告
    print()
    print("┌" + "─" * 118 + "┐")
    print(
        "│  風險警告                                                                                                           │"
    )
    print("├" + "─" * 118 + "┤")
    print(
        "│  ⚠️  歷史回測結果不代表未來表現                                                                                      │"
    )
    print(
        "│  ⚠️  高槓桿交易具有極高風險，可能導致本金全部損失                                                                    │"
    )
    print(
        "│  ⚠️  實盤交易前請進行充分的模擬測試                                                                                  │"
    )
    print(
        "│  ⚠️  請根據個人風險承受能力調整槓桿和倉位                                                                            │"
    )
    print("└" + "─" * 118 + "┘")

    print()
    print(f"報表生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == "__main__":
    main()
