#!/usr/bin/env python3
"""
逐年回測報告 - 使用標準格式
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


def run_backtest_detailed(data: pd.DataFrame, initial_cash: float = 500, **kwargs) -> dict:
    """執行回測並返回詳細結果"""
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


def run_yearly_backtest(data: pd.DataFrame, config_name: str, **params):
    """執行逐年回測 - 連續回測，按年統計"""
    print(f"\n【逐年回測】- {config_name}")
    print(f"{'年份':<6} {'收益':>10} {'累計資本':>12} {'回撤':>8} {'勝率':>6} {'做多':>12} {'做空':>12} {'BH':>8}")

    initial_cash = 500.0

    # 建立 broker 和策略（整個期間共用）
    broker = SimulatedBroker(
        initial_cash=initial_cash,
        fee_rate=0.0004,
        leverage=params.get("leverage", 7),
        maintenance_margin_rate=0.005,
    )
    strategy = BiGeDualMAStrategy(broker=broker, data=data, **params)

    years = sorted(data.index.year.unique())

    # 追蹤每年的統計
    year_start_equity = initial_cash
    year_start_trade_count = 0
    year_peak_equity = initial_cash
    year_max_dd = 0.0
    year_long_pnl = 0.0
    year_short_pnl = 0.0
    current_year = None

    for i, (timestamp, row) in enumerate(data.iterrows()):
        year = timestamp.year

        # 年份變化時，輸出上一年的統計
        if current_year is not None and year != current_year:
            # 計算上一年的統計
            year_end_equity = broker.get_current_equity(prev_close)
            year_return = (year_end_equity / year_start_equity - 1) * 100

            # 計算該年的交易統計
            year_trades = broker.trades[year_start_trade_count:]
            year_trade_count = len(year_trades)
            year_wins = sum(1 for t in year_trades if t.pnl > 0)
            year_win_rate = year_wins / year_trade_count * 100 if year_trade_count > 0 else 0

            # 計算多空盈虧（使用 direction 字段，不做 fallback 推斷）
            for t in year_trades:
                if t.direction == "long":
                    year_long_pnl += t.pnl
                elif t.direction == "short":
                    year_short_pnl += t.pnl

            # Buy and Hold
            bh_return = (prev_close / year_start_price - 1) * 100

            print(
                f"{current_year:<6} {year_return:>+9.0f}% {format_money(year_end_equity):>12} "
                f"{year_max_dd:>7.0f}% {year_win_rate:>5.0f}% "
                f"{format_pnl(year_long_pnl):>12} {format_pnl(year_short_pnl):>12} "
                f"{bh_return:>+7.0f}%"
            )

            # 重置年度統計
            year_start_equity = year_end_equity
            year_start_trade_count = len(broker.trades)
            year_peak_equity = year_end_equity
            year_max_dd = 0.0
            year_long_pnl = 0.0
            year_short_pnl = 0.0
            year_start_price = row["close"]

        if current_year is None or year != current_year:
            year_start_price = row["close"]
            current_year = year

        # 執行策略
        strategy.on_bar(i, row)

        # 更新權益和回撤
        current_equity = broker.get_current_equity(row["close"])
        if current_equity > year_peak_equity:
            year_peak_equity = current_equity
        dd = (year_peak_equity - current_equity) / year_peak_equity * 100
        if dd > year_max_dd:
            year_max_dd = dd

        prev_close = row["close"]

    # 輸出最後一年的統計
    if current_year is not None:
        year_end_equity = broker.get_current_equity(prev_close)
        year_return = (year_end_equity / year_start_equity - 1) * 100

        year_trades = broker.trades[year_start_trade_count:]
        year_trade_count = len(year_trades)
        year_wins = sum(1 for t in year_trades if t.pnl > 0)
        year_win_rate = year_wins / year_trade_count * 100 if year_trade_count > 0 else 0

        # 計算多空盈虧（使用 direction 字段，不做 fallback 推斷）
        for t in year_trades:
            if t.direction == "long":
                year_long_pnl += t.pnl
            elif t.direction == "short":
                year_short_pnl += t.pnl

        bh_return = (prev_close / year_start_price - 1) * 100

        print(
            f"{current_year:<6} {year_return:>+9.0f}% {format_money(year_end_equity):>12} "
            f"{year_max_dd:>7.0f}% {year_win_rate:>5.0f}% "
            f"{format_pnl(year_long_pnl):>12} {format_pnl(year_short_pnl):>12} "
            f"{bh_return:>+7.0f}%"
        )

    final_equity = broker.get_current_equity(data.iloc[-1]["close"])
    return final_equity


def main():
    print("=" * 100)
    print("BiGe 雙均線策略 - 逐年回測報告")
    print("=" * 100)

    # 載入數據
    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    print(f"\n載入數據: {data_path}")
    data = load_data(data_path)
    print(f"數據範圍: {data.index[0]} ~ {data.index[-1]}")
    print(f"共 {len(data)} 根 K 線")

    # 配置列表
    configs = [
        {
            "name": "原始幣哥策略 (7x 固定槓桿 + 50% 加倉)",
            "params": {
                "leverage": 7,
                "add_position_mode": "fixed_50",
                "max_add_count": 3,
                "trend_mode": "loose",
            },
        },
        {
            "name": "保守策略 (5x 固定槓桿 + 50% 加倉)",
            "params": {
                "leverage": 5,
                "add_position_mode": "fixed_50",
                "max_add_count": 3,
                "trend_mode": "loose",
            },
        },
        {
            "name": "積極策略 (10x 固定槓桿 + 50% 加倉)",
            "params": {
                "leverage": 10,
                "add_position_mode": "fixed_50",
                "max_add_count": 5,
                "trend_mode": "loose",
            },
        },
    ]

    results = {}
    for config in configs:
        final_capital = run_yearly_backtest(data, config["name"], **config["params"])
        results[config["name"]] = final_capital

    # 總結
    print("\n" + "=" * 100)
    print("總結")
    print("=" * 100)
    for name, capital in results.items():
        total_return = (capital / 500 - 1) * 100
        print(f"{name}: {format_money(capital)} ({total_return:,.0f}%)")


if __name__ == "__main__":
    main()
