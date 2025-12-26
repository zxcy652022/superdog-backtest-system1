#!/usr/bin/env python3
"""檢查回測是否出現不現實的情況"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy

INITIAL_CASH = 500


def load_data(symbol: str, timeframe: str = "4h") -> pd.DataFrame:
    data_path = f"/Volumes/權志龍的寶藍/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    if not os.path.exists(data_path):
        data_path = f"/Volumes/權志龍的寶藏/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


def check_backtest_realism(symbol: str = "BTCUSDT", year: int = 2024):
    """檢查回測的現實性"""
    print(f"\n{'='*60}")
    print(f"現實性檢查: {symbol} {year}")
    print(f"{'='*60}")

    df = load_data(symbol)
    df = df[df.index.year == year]

    broker = SimulatedBroker(initial_cash=INITIAL_CASH, slippage_rate=0.0005)
    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=10,
        dynamic_leverage=False,
        enable_add_position=True,
        max_add_count=100,
    )

    # 追蹤異常情況
    negative_equity_count = 0
    max_leverage_used = 0
    min_equity = INITIAL_CASH
    liquidation_should_have_happened = 0

    for i, (idx, row) in enumerate(strategy.data.iterrows()):
        # 記錄進場前狀態
        had_position = broker.has_position
        entry_price = broker.position_entry_price if had_position else 0

        strategy.on_bar(i, row)

        # 檢查權益
        equity = broker.get_current_equity(row["close"])
        if equity < 0:
            negative_equity_count += 1
            print(f"  ⚠️ 負權益: {idx} equity={equity:.2f}")

        if equity < min_equity:
            min_equity = equity

        # 檢查是否應該爆倉但沒爆倉
        if broker.has_position:
            liq_price = broker.get_liquidation_price()
            if liq_price:
                if broker.is_long and row["low"] < liq_price:
                    liquidation_should_have_happened += 1
                elif broker.is_short and row["high"] > liq_price:
                    liquidation_should_have_happened += 1

    # 強制平倉
    if broker.has_position:
        last_row = strategy.data.iloc[-1]
        if broker.is_long:
            broker.sell(broker.position_qty, last_row["close"], strategy.data.index[-1])
        else:
            broker.buy(broker.position_qty, last_row["close"], strategy.data.index[-1])

    # 統計
    trades = broker.trades
    final_equity = broker.cash

    print(f"\n結果:")
    print(f"  最終資金: ${final_equity:,.0f}")
    print(f"  收益率: {(final_equity/INITIAL_CASH-1)*100:+,.0f}%")
    print(f"  交易數: {len(trades)}")
    print(f"\n現實性檢查:")
    print(f"  負權益次數: {negative_equity_count}")
    print(f"  最低權益: ${min_equity:,.2f}")
    print(f"  應爆倉但未爆倉次數: {liquidation_should_have_happened}")

    if negative_equity_count > 0:
        print(f"\n  ❌ 出現負權益 - 回測不現實")
    elif liquidation_should_have_happened > 0:
        print(f"\n  ⚠️ 有 {liquidation_should_have_happened} 次應該爆倉但未處理")
        print(f"     這意味著回測收益可能被高估")
    else:
        print(f"\n  ✓ 回測看起來是現實的")

    return {
        "final": final_equity,
        "negative_equity": negative_equity_count,
        "missed_liquidations": liquidation_should_have_happened,
    }


def main():
    # 測試幾個代表性的幣種和年份
    test_cases = [
        ("BTCUSDT", 2024),
        ("BTCUSDT", 2022),
        ("ETHUSDT", 2024),
        ("SOLUSDT", 2024),
        ("LINKUSDT", 2024),
    ]

    results = []
    for symbol, year in test_cases:
        try:
            r = check_backtest_realism(symbol, year)
            results.append((symbol, year, r))
        except Exception as e:
            print(f"錯誤: {symbol} {year}: {e}")

    # 總結
    print("\n" + "=" * 60)
    print("總結")
    print("=" * 60)

    total_missed = sum(r[2]["missed_liquidations"] for r in results)
    print(f"\n總共錯過爆倉次數: {total_missed}")

    if total_missed > 0:
        print(
            """
結論：
回測中有多次「應該爆倉但沒有爆倉」的情況。
這意味著：
1. 回測的超高收益部分來自「不現實」的倉位延續
2. 實盤中這些情況會導致爆倉歸零
3. 爆倉檢測是必要的，但會降低回測收益

建議：
- 啟用爆倉檢測以獲得更現實的回測
- 或者降低槓桿（例如 5x）減少爆倉風險
"""
        )
    else:
        print("\n回測現實性良好，沒有明顯問題。")


if __name__ == "__main__":
    main()
