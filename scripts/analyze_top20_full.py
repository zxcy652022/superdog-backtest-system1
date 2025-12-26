#!/usr/bin/env python3
"""
完整回測：前 20 幣種，全時間範圍
"""

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
        leverage=kwargs.get("leverage", 10),
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
    winning = sum(1 for t in trades if t.pnl > 0)
    total_trades = len(trades)
    win_rate = winning / total_trades if total_trades > 0 else 0
    liquidation_count = sum(1 for t in trades if hasattr(t, "is_liquidation") and t.is_liquidation)

    return {
        "final_equity": final_equity,
        "total_return": (final_equity / initial_cash - 1) * 100,
        "max_drawdown": max_drawdown * 100,
        "total_trades": total_trades,
        "win_rate": win_rate * 100,
        "liquidation_count": liquidation_count,
    }


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
    print("BiGe 雙均線策略 - 前 20 幣種完整回測")
    print("=" * 100)

    data_dir = Path("/Volumes/權志龍的寶藏/SuperDogData/raw/binance")
    timeframe = "4h"

    # 獲取可用幣種
    symbols = get_available_symbols(data_dir, timeframe)
    print(f"\n可用幣種數量: {len(symbols)}")

    # 選擇前 20 個主流幣種
    priority_symbols = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "SOLUSDT",
        "DOTUSDT",
        "MATICUSDT",
        "LTCUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "ATOMUSDT",
        "UNIUSDT",
        "XLMUSDT",
        "ETCUSDT",
        "FILUSDT",
        "TRXUSDT",
        "NEARUSDT",
        "ALGOUSDT",
    ]

    # 篩選實際存在的幣種
    test_symbols = [s for s in priority_symbols if s in symbols]
    print(f"測試幣種: {len(test_symbols)}")
    print(f"  {', '.join(test_symbols[:10])}")
    if len(test_symbols) > 10:
        print(f"  {', '.join(test_symbols[10:])}")

    # 策略配置
    configs = [
        {
            "name": "保守型 7x",
            "params": {
                "leverage": 7,
                "add_position_mode": "fixed_50",
                "max_add_count": 3,
                "trend_mode": "loose",
            },
        },
        {
            "name": "平衡型 10x",
            "params": {
                "leverage": 10,
                "add_position_mode": "fixed_50",
                "max_add_count": 5,
                "trend_mode": "loose",
            },
        },
    ]

    # 執行回測
    all_results = []

    for config in configs:
        print(f"\n{'=' * 100}")
        print(f"配置: {config['name']}")
        print(f"{'=' * 100}")
        print(f"{'幣種':<12} {'數據範圍':<25} {'收益率':>15} {'最大回撤':>12} {'勝率':>10} {'交易數':>8} {'爆倉':>6}")
        print("-" * 100)

        config_results = []

        for symbol in test_symbols:
            filepath = data_dir / timeframe / f"{symbol}_{timeframe}.csv"
            if not filepath.exists():
                continue

            try:
                data = load_data(str(filepath))
                if len(data) < 500:  # 至少 500 根 K 線
                    continue

                result = run_backtest(data, **config["params"])

                date_range = (
                    f"{data.index[0].strftime('%Y-%m')} ~ {data.index[-1].strftime('%Y-%m')}"
                )

                print(
                    f"{symbol:<12} {date_range:<25} {result['total_return']:>14,.0f}% "
                    f"{result['max_drawdown']:>11.1f}% {result['win_rate']:>9.1f}% "
                    f"{result['total_trades']:>8} {result['liquidation_count']:>6}"
                )

                config_results.append(
                    {
                        "symbol": symbol,
                        "config": config["name"],
                        "return": result["total_return"],
                        "max_dd": result["max_drawdown"],
                        "win_rate": result["win_rate"],
                        "trades": result["total_trades"],
                        "liquidations": result["liquidation_count"],
                        "data_range": date_range,
                    }
                )

            except Exception as e:
                print(f"{symbol:<12} 錯誤: {e}")

        if config_results:
            print("-" * 100)

            # 統計
            returns = [r["return"] for r in config_results]
            win_rates = [r["win_rate"] for r in config_results]
            drawdowns = [r["max_dd"] for r in config_results]

            avg_return = sum(returns) / len(returns)
            median_return = sorted(returns)[len(returns) // 2]
            positive_count = sum(1 for r in returns if r > 0)

            print(f"\n統計摘要:")
            print(f"  平均收益率: {avg_return:,.0f}%")
            print(f"  中位數收益: {median_return:,.0f}%")
            print(
                f"  盈利幣種: {positive_count}/{len(config_results)} ({positive_count/len(config_results)*100:.0f}%)"
            )
            print(f"  平均勝率: {sum(win_rates)/len(win_rates):.1f}%")
            print(f"  平均回撤: {sum(drawdowns)/len(drawdowns):.1f}%")

            # Top 5 最佳
            top5 = sorted(config_results, key=lambda x: x["return"], reverse=True)[:5]
            print(f"\n  Top 5 最佳:")
            for i, r in enumerate(top5, 1):
                print(f"    {i}. {r['symbol']}: {r['return']:,.0f}%")

            # Top 3 最差
            bottom3 = sorted(config_results, key=lambda x: x["return"])[:3]
            print(f"\n  Top 3 最差:")
            for i, r in enumerate(bottom3, 1):
                print(f"    {i}. {r['symbol']}: {r['return']:,.0f}%")

        all_results.extend(config_results)

    # 總結
    print(f"\n{'=' * 100}")
    print("總結對比")
    print(f"{'=' * 100}")

    for config in configs:
        config_data = [r for r in all_results if r["config"] == config["name"]]
        if not config_data:
            continue

        returns = [r["return"] for r in config_data]
        avg = sum(returns) / len(returns)
        positive = sum(1 for r in returns if r > 0)

        print(f"\n{config['name']}:")
        print(f"  平均收益: {avg:,.0f}%")
        print(f"  盈利幣種: {positive}/{len(config_data)}")


if __name__ == "__main__":
    main()
