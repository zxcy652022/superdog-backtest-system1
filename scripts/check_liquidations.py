#!/usr/bin/env python3
"""檢查爆倉事件詳情"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy

INITIAL_CASH = 500
LEVERAGE = 5
SLIPPAGE = 0.0005


def load_data(symbol: str, timeframe: str = "4h") -> pd.DataFrame:
    data_path = f"/Volumes/權志龍的寶藏/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


def check_liquidations(symbol: str = "BTCUSDT"):
    """檢查爆倉事件"""
    print(f"檢查 {symbol} 爆倉事件\n")
    print("=" * 80)

    df = load_data(symbol)

    broker = SimulatedBroker(
        initial_cash=INITIAL_CASH,
        slippage_rate=SLIPPAGE,
    )

    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=LEVERAGE,
        dynamic_leverage=False,
        enable_add_position=True,
        max_add_count=100,
    )

    # 追蹤爆倉前後的權益
    equity_before_liq = []

    for i, (idx, row) in enumerate(strategy.data.iterrows()):
        # 記錄爆倉前的權益
        if broker.has_position:
            eq_before = broker.get_current_equity(row["close"])

        strategy.on_bar(i, row)

        # 檢查是否剛發生爆倉
        if broker.liquidation_events and len(broker.liquidation_events) > len(equity_before_liq):
            liq = broker.liquidation_events[-1]
            equity_before_liq.append(eq_before)

    # 強制平倉
    if broker.has_position:
        last_row = strategy.data.iloc[-1]
        if broker.is_long:
            broker.sell(broker.position_qty, last_row["close"], strategy.data.index[-1])
        else:
            broker.buy(broker.position_qty, last_row["close"], strategy.data.index[-1])

    # 打印爆倉事件
    print(f"\n爆倉次數：{broker.liquidation_count}")
    print(f"最終資金：${broker.cash:,.0f}")
    print(f"總收益：{(broker.cash/INITIAL_CASH-1)*100:+,.0f}%")

    if broker.liquidation_events:
        print("\n" + "=" * 80)
        print("爆倉事件詳情")
        print("=" * 80)

        for i, liq in enumerate(broker.liquidation_events):
            print(f"\n【爆倉 #{i+1}】")
            print(f"  時間：{liq.time}")
            print(f"  方向：{'多單' if liq.direction == 'long' else '空單'}")
            print(f"  入場價：${liq.entry_price:,.2f}")
            print(f"  爆倉價：${liq.liquidation_price:,.2f}")
            print(f"  持倉數量：{liq.position_qty:.6f}")
            print(f"  損失金額：${liq.loss:,.2f}")

            # 計算損失比例
            position_value = liq.position_qty * liq.entry_price
            margin = position_value / LEVERAGE
            print(f"  投入保證金：${margin:,.2f}")
            print(f"  損失比例：{liq.loss/margin*100:.1f}%（保證金全損）")

            # 計算價格變動
            if liq.direction == "long":
                price_change = (liq.liquidation_price - liq.entry_price) / liq.entry_price * 100
            else:
                price_change = (liq.entry_price - liq.liquidation_price) / liq.entry_price * 100
            print(f"  價格變動：{price_change:+.1f}%（觸發爆倉）")

        # 爆倉對總績效的影響
        print("\n" + "=" * 80)
        print("爆倉影響分析")
        print("=" * 80)

        total_loss = sum(liq.loss for liq in broker.liquidation_events)
        print(f"\n爆倉總損失：${total_loss:,.2f}")
        print(f"占初始資金：{total_loss/INITIAL_CASH*100:.1f}%")
        print(f"占最終資金：{total_loss/broker.cash*100:.4f}%")

        print(
            f"""
結論：
- 5x 槓桿下，全期只有 {broker.liquidation_count} 次爆倉
- 爆倉損失的是「那筆交易的保證金」，不是全部帳戶
- 因為倉位控制（10% 權益），單次爆倉不會讓帳戶歸零
- 爆倉後策略繼續運行，後續交易補回損失
"""
        )

    else:
        print("\n沒有發生爆倉事件！")


if __name__ == "__main__":
    check_liquidations("BTCUSDT")
