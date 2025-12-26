#!/usr/bin/env python3
"""
隨機抽樣驗證 - 5 幣種 × 5 次
"""

import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy


def load_data(filepath: str) -> pd.DataFrame:
    """載入數據"""
    df = pd.read_csv(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def run_backtest(data: pd.DataFrame, initial_cash: float = 500, **kwargs) -> dict:
    """執行回測"""
    broker = SimulatedBroker(
        initial_cash=initial_cash,
        fee_rate=0.0004,
        leverage=kwargs.get("leverage", 7),
        maintenance_margin_rate=0.005,
    )

    strategy = BiGeDualMAStrategy(broker=broker, data=data, **kwargs)

    equity_curve = []
    peak_equity = initial_cash
    max_drawdown = 0.0

    for i, (timestamp, row) in enumerate(data.iterrows()):
        strategy.on_bar(i, row)
        current_equity = broker.get_current_equity(row["close"])
        equity_curve.append(current_equity)

        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity
        if dd > max_drawdown:
            max_drawdown = dd

    final_equity = broker.get_current_equity(data.iloc[-1]["close"])
    trades = broker.trades

    # 計算多空分別的盈虧（使用 direction 字段，不做 fallback 推斷）
    long_pnl = sum(t.pnl for t in trades if t.direction == "long")
    short_pnl = sum(t.pnl for t in trades if t.direction == "short")

    winning = sum(1 for t in trades if t.pnl > 0)
    total_trades = len(trades)
    win_rate = winning / total_trades if total_trades > 0 else 0

    # Buy and Hold 計算
    start_price = data.iloc[0]["close"]
    end_price = data.iloc[-1]["close"]
    bh_return = (end_price / start_price - 1) * 100

    return {
        "final_equity": final_equity,
        "total_return": (final_equity / initial_cash - 1) * 100,
        "max_drawdown": max_drawdown * 100,
        "total_trades": total_trades,
        "win_rate": win_rate * 100,
        "long_pnl": long_pnl,
        "short_pnl": short_pnl,
        "bh_return": bh_return,
    }


def format_money(value: float) -> str:
    """格式化金額"""
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.0f}"


def format_pnl(value: float) -> str:
    """格式化盈虧"""
    sign = "+" if value >= 0 else ""
    if abs(value) >= 1_000_000:
        return f"{sign}${value/1_000_000:.1f}M"
    elif abs(value) >= 1_000:
        return f"{sign}${value/1_000:.1f}K"
    else:
        return f"{sign}${value:.0f}"


def get_available_symbols(data_dir: Path, timeframe: str) -> list:
    """獲取可用的幣種"""
    tf_dir = data_dir / timeframe
    if not tf_dir.exists():
        return []

    symbols = []
    for f in tf_dir.glob("*USDT_*.csv"):
        symbol = f.stem.split("_")[0]
        symbols.append(symbol)

    return sorted(set(symbols))


def main():
    print("=" * 100)
    print("BiGe 7x 雙均線策略 - 隨機抽樣驗證 (5 幣種 × 5 次)")
    print("=" * 100)

    data_dir = Path("/Volumes/權志龍的寶藏/SuperDogData/raw/binance")
    timeframe = "4h"

    # 獲取所有可用幣種
    all_symbols = get_available_symbols(data_dir, timeframe)

    # 過濾掉數據太少的幣種
    valid_symbols = []
    for symbol in all_symbols:
        filepath = data_dir / timeframe / f"{symbol}_{timeframe}.csv"
        try:
            df = pd.read_csv(filepath)
            if len(df) >= 1000:  # 至少 1000 根 K 線
                valid_symbols.append(symbol)
        except:
            pass

    print(f"\n可用幣種 (>1000 K線): {len(valid_symbols)}")

    # 固定參數
    params = {
        "leverage": 7,
        "add_position_mode": "fixed_50",
        "max_add_count": 3,
        "trend_mode": "loose",
    }
    print(f"固定參數: 7x 槓桿, fixed_50 加倉, 最多 3 次加倉, loose 趨勢模式")

    # 設定隨機種子
    random.seed(42)

    all_round_results = []

    for round_num in range(1, 6):
        print(f"\n{'=' * 100}")
        print(f"第 {round_num} 輪隨機抽樣")
        print(f"{'=' * 100}")

        # 隨機抽 5 個幣種
        sample_symbols = random.sample(valid_symbols, 5)
        print(f"抽中幣種: {', '.join(sample_symbols)}")

        print(
            f"\n{'幣種':<12} {'收益':>12} {'累計資本':>12} {'回撤':>8} {'勝率':>6} {'做多':>12} {'做空':>12} {'BH':>8}"
        )
        print("-" * 100)

        round_results = []

        for symbol in sample_symbols:
            filepath = data_dir / timeframe / f"{symbol}_{timeframe}.csv"

            try:
                data = load_data(str(filepath))
                result = run_backtest(data, **params)

                print(
                    f"{symbol:<12} {result['total_return']:>+10,.0f}% {format_money(result['final_equity']):>12} "
                    f"{result['max_drawdown']:>7.0f}% {result['win_rate']:>5.0f}% "
                    f"{format_pnl(result['long_pnl']):>12} {format_pnl(result['short_pnl']):>12} "
                    f"{result['bh_return']:>+7.0f}%"
                )

                round_results.append(
                    {
                        "symbol": symbol,
                        "return": result["total_return"],
                        "max_dd": result["max_drawdown"],
                        "win_rate": result["win_rate"],
                    }
                )

            except Exception as e:
                print(f"{symbol:<12} 錯誤: {e}")

        # 該輪統計
        print("-" * 100)
        returns = [r["return"] for r in round_results]
        win_count = sum(1 for r in returns if r > 0)
        avg_return = sum(returns) / len(returns)

        print(f"本輪統計: 平均收益 {avg_return:,.0f}% | 盈利幣種 {win_count}/5 ({win_count/5*100:.0f}%)")

        all_round_results.append(
            {
                "round": round_num,
                "symbols": sample_symbols,
                "avg_return": avg_return,
                "win_count": win_count,
                "results": round_results,
            }
        )

    # 總結
    print(f"\n{'=' * 100}")
    print("五輪隨機抽樣總結")
    print(f"{'=' * 100}")

    print(f"\n{'輪次':<6} {'抽中幣種':<50} {'平均收益':>15} {'盈利/總數':>10}")
    print("-" * 100)

    for r in all_round_results:
        symbols_str = ", ".join(r["symbols"][:3]) + "..."
        print(f"{r['round']:<6} {symbols_str:<50} {r['avg_return']:>+14,.0f}% {r['win_count']}/5")

    print("-" * 100)

    # 總體統計
    all_returns = []
    all_wins = 0
    total_coins = 0

    for r in all_round_results:
        for res in r["results"]:
            all_returns.append(res["return"])
            if res["return"] > 0:
                all_wins += 1
            total_coins += 1

    overall_avg = sum(all_returns) / len(all_returns)
    overall_median = sorted(all_returns)[len(all_returns) // 2]

    print(f"\n總體統計 (25 個樣本):")
    print(f"  平均收益: {overall_avg:,.0f}%")
    print(f"  中位數收益: {overall_median:,.0f}%")
    print(f"  盈利幣種: {all_wins}/{total_coins} ({all_wins/total_coins*100:.0f}%)")

    print(f"\n結論: {'✓ 策略具有穩健性' if all_wins/total_coins >= 0.8 else '⚠ 需要進一步檢視'}")


if __name__ == "__main__":
    main()
