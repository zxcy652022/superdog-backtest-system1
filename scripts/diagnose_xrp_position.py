#!/usr/bin/env python3
"""
診斷 XRP 倉位狀態

分析為什麼 XRP 倉位沒有和其他 4 個幣種一起被平倉
"""

import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from config.production_phase1 import PHASE1_CONFIG  # noqa: E402
from live.binance_broker import BinanceFuturesBroker  # noqa: E402


def main():
    print("=" * 60)
    print("XRP 倉位診斷")
    print("=" * 60)

    broker = BinanceFuturesBroker()
    config = PHASE1_CONFIG

    # 取得所有持倉
    print("\n📊 當前所有持倉:")
    positions = broker.get_all_positions()
    if not positions:
        print("  無持倉")
    else:
        for pos in positions:
            print(f"  {pos.symbol}: {pos.side} {pos.qty} @ {pos.entry_price:.4f}")
            print(f"    未實現盈虧: ${pos.unrealized_pnl:.2f}")

    # 分析 XRP
    print("\n" + "=" * 60)
    print("🔍 XRP 緊急止損分析")
    print("=" * 60)

    symbol = "XRPUSDT"
    position = broker.get_position(symbol)

    if not position:
        print(f"\n❌ {symbol} 無持倉")
        return

    print(f"\n持倉方向: {position.side}")
    print(f"進場價格: {position.entry_price:.4f}")
    print(f"數量: {position.qty}")

    # 取得 K 線
    klines = broker.get_klines(symbol, "4h", 200)
    df = pd.DataFrame(klines)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    # 計算指標
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema60"] = df["close"].ewm(span=60, adjust=False).mean()
    df["avg20"] = (df["ma20"] + df["ema20"]) / 2
    df["avg60"] = (df["ma60"] + df["ema60"]) / 2

    # ATR
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    # 最近幾根 K 線的分析
    print("\n📈 最近 5 根 K 線分析:")
    emergency_atr = config.get("emergency_stop_atr", 3.5)

    for i in range(-5, 0):
        row = df.iloc[i]
        bar_time = row.name

        avg20 = row["avg20"]
        atr = row["atr"]

        if position.side == "SHORT":
            breach = row["high"] - avg20
            breach_ratio = breach / atr if atr > 0 else 0
            trigger = "🚨 觸發!" if breach > 0 and breach > emergency_atr * atr else ""
            print(
                f"\n  [{bar_time}]"
                f"\n    High: {row['high']:.4f}, Close: {row['close']:.4f}"
                f"\n    AVG20: {avg20:.4f}, ATR: {atr:.4f}"
                f"\n    Breach: {breach:.4f} ({breach_ratio:.2f}x ATR) {trigger}"
            )
        else:
            breach = avg20 - row["low"]
            breach_ratio = breach / atr if atr > 0 else 0
            trigger = "🚨 觸發!" if breach > 0 and breach > emergency_atr * atr else ""
            print(
                f"\n  [{bar_time}]"
                f"\n    Low: {row['low']:.4f}, Close: {row['close']:.4f}"
                f"\n    AVG20: {avg20:.4f}, ATR: {atr:.4f}"
                f"\n    Breach: {breach:.4f} ({breach_ratio:.2f}x ATR) {trigger}"
            )

    # 當前狀態
    print("\n" + "=" * 60)
    print("📊 當前狀態")
    print("=" * 60)

    current = df.iloc[-1]
    current_price = broker.get_current_price(symbol)

    print(f"\n當前價格: {current_price:.4f}")
    print(f"AVG20: {current['avg20']:.4f}")
    print(f"ATR(14): {current['atr']:.4f}")

    ma20_buffer = config.get("ma20_buffer", 0.02)
    if position.side == "SHORT":
        stop_loss = current["avg20"] * (1 + ma20_buffer)
        print(f"建議止損位: {stop_loss:.4f} (AVG20 * 1.{int(ma20_buffer*100):02d})")

        breach = current_price - current["avg20"]
        breach_ratio = breach / current["atr"] if current["atr"] > 0 else 0
        print(f"\n當前 Breach: {breach:.4f} ({breach_ratio:.2f}x ATR)")
        print(f"緊急止損閾值: {emergency_atr}x ATR = {emergency_atr * current['atr']:.4f}")

        if breach > 0 and breach > emergency_atr * current["atr"]:
            print("\n⚠️  當前應該觸發緊急止損！")
        else:
            print(f"\n✅ 未達緊急止損閾值 (還差 {emergency_atr * current['atr'] - breach:.4f})")
    else:
        stop_loss = current["avg20"] * (1 - ma20_buffer)
        print(f"建議止損位: {stop_loss:.4f} (AVG20 * 0.{100-int(ma20_buffer*100):02d})")

    # 與其他幣種比較
    print("\n" + "=" * 60)
    print("📊 所有幣種 ATR 比較")
    print("=" * 60)

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    for sym in symbols:
        try:
            klines = broker.get_klines(sym, "4h", 50)
            df_sym = pd.DataFrame(klines)
            close = df_sym["close"].astype(float)
            high = df_sym["high"].astype(float)
            low = df_sym["low"].astype(float)

            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]

            ma20 = close.rolling(20).mean().iloc[-1]
            ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
            avg20 = (ma20 + ema20) / 2

            current_price = float(df_sym["close"].iloc[-1])

            # 計算相對 breach (假設是 SHORT)
            breach = float(df_sym["high"].iloc[-1]) - avg20
            breach_ratio = breach / atr if atr > 0 else 0

            print(f"\n{sym}:")
            print(f"  ATR: {atr:.4f} ({atr/current_price*100:.2f}% of price)")
            print(f"  AVG20: {avg20:.4f}")
            print(f"  Breach Ratio: {breach_ratio:.2f}x ATR")
        except Exception as e:
            print(f"\n{sym}: 獲取數據失敗 - {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
