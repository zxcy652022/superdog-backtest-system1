#!/usr/bin/env python3
"""
起始時間敏感度測試 - ±3 個月
測試策略是否對起始時間敏感（過擬合檢測）
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

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


def main():
    print("=" * 110)
    print("BiGe 7x 雙均線策略 - 起始時間敏感度測試 (±3 個月)")
    print("=" * 110)

    # 載入數據
    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    print(f"\n載入數據: {data_path}")
    full_data = load_data(data_path)
    print(f"完整數據範圍: {full_data.index[0]} ~ {full_data.index[-1]}")

    # 固定參數
    params = {
        "leverage": 7,
        "add_position_mode": "fixed_50",
        "max_add_count": 3,
        "trend_mode": "loose",
    }
    print(f"固定參數: 7x 槓桿, fixed_50 加倉, 最多 3 次加倉, loose 趨勢模式")

    # 基準起始日期 (2020-01-01)
    base_start = pd.Timestamp("2020-01-01")

    # 測試不同起始時間: -3, -2, -1, 0, +1, +2, +3 個月
    offsets = [-3, -2, -1, 0, 1, 2, 3]

    print(f"\n測試起始時間偏移: {offsets} 個月")
    print(
        f"\n{'起始時間':<20} {'收益':>12} {'累計資本':>12} {'回撤':>8} {'勝率':>6} {'做多':>12} {'做空':>12} {'BH':>8}"
    )
    print("-" * 110)

    results = []

    for offset in offsets:
        start_date = base_start + relativedelta(months=offset)

        # 篩選數據
        data = full_data[full_data.index >= start_date].copy()

        if len(data) < 500:
            print(f"{start_date.strftime('%Y-%m-%d'):<20} 數據不足")
            continue

        result = run_backtest(data, **params)

        offset_str = f"{offset:+d}M" if offset != 0 else "基準"
        start_str = f"{start_date.strftime('%Y-%m-%d')} ({offset_str})"

        print(
            f"{start_str:<20} {result['total_return']:>+10,.0f}% {format_money(result['final_equity']):>12} "
            f"{result['max_drawdown']:>7.0f}% {result['win_rate']:>5.0f}% "
            f"{format_pnl(result['long_pnl']):>12} {format_pnl(result['short_pnl']):>12} "
            f"{result['bh_return']:>+7.0f}%"
        )

        results.append(
            {
                "offset": offset,
                "start_date": start_date,
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "bh_return": result["bh_return"],
            }
        )

    print("-" * 110)

    # 統計分析
    if results:
        returns = [r["return"] for r in results]
        avg_return = sum(returns) / len(returns)
        std_return = np.std(returns)
        min_return = min(returns)
        max_return = max(returns)
        cv = std_return / avg_return * 100 if avg_return != 0 else 0  # 變異係數

        print(f"\n敏感度分析:")
        print(f"  平均收益: {avg_return:,.0f}%")
        print(f"  標準差: {std_return:,.0f}%")
        print(f"  變異係數 (CV): {cv:.1f}%")
        print(f"  最低收益: {min_return:,.0f}%")
        print(f"  最高收益: {max_return:,.0f}%")
        print(f"  收益範圍: {max_return - min_return:,.0f}%")

        # 判斷敏感度
        if cv < 30:
            sensitivity = "低敏感度 ✓ - 策略對起始時間不敏感，穩健性良好"
        elif cv < 60:
            sensitivity = "中等敏感度 ⚠ - 策略有一定的起始時間依賴"
        else:
            sensitivity = "高敏感度 ✗ - 策略對起始時間高度敏感，可能過擬合"

        print(f"\n結論: {sensitivity}")

    # 額外測試：不同幣種的時間敏感度
    print(f"\n{'=' * 110}")
    print("多幣種時間敏感度測試")
    print(f"{'=' * 110}")

    test_symbols = ["ETHUSDT", "BNBUSDT", "SOLUSDT", "LINKUSDT"]
    data_dir = Path("/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h")

    for symbol in test_symbols:
        filepath = data_dir / f"{symbol}_4h.csv"
        if not filepath.exists():
            continue

        full_data = load_data(str(filepath))

        print(f"\n{symbol}:")
        print(f"{'起始偏移':<10} {'收益':>15}")
        print("-" * 30)

        symbol_results = []

        for offset in [-3, 0, 3]:
            start_date = base_start + relativedelta(months=offset)
            data = full_data[full_data.index >= start_date].copy()

            if len(data) < 500:
                continue

            result = run_backtest(data, **params)
            offset_str = f"{offset:+d}M" if offset != 0 else "基準"

            print(f"{offset_str:<10} {result['total_return']:>+14,.0f}%")
            symbol_results.append(result["total_return"])

        if len(symbol_results) >= 2:
            variation = max(symbol_results) - min(symbol_results)
            avg = sum(symbol_results) / len(symbol_results)
            cv = (max(symbol_results) - min(symbol_results)) / avg * 100 if avg > 0 else 0
            print(f"{'變異':<10} {variation:>14,.0f}% (CV: {cv:.0f}%)")

    print(f"\n{'=' * 110}")
    print("總結")
    print(f"{'=' * 110}")
    print(
        """
✓ 策略對起始時間變化的敏感度測試完成
✓ 若所有幣種的變異係數 (CV) < 50%，則策略具有良好的時間穩健性
✓ 若大部分幣種在不同起始時間都能盈利，則策略沒有嚴重的過擬合問題
"""
    )


if __name__ == "__main__":
    main()
