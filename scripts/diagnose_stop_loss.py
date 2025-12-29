#!/usr/bin/env python3
"""
止損邏輯診斷腳本

分析最近的 K 線數據，檢查止損條件是否正確觸發
用於驗證：
1. 緊急止損 (3.5x ATR) 邏輯
2. 普通止損 (10 根 K 線確認) 邏輯
3. 各幣種的止損狀態

在 VPS 上運行: python3 scripts/diagnose_stop_loss.py
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from config.production_phase1 import PHASE1_CONFIG  # noqa: E402
from live.binance_broker import BinanceFuturesBroker  # noqa: E402


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算策略所需指標"""
    df = df.copy()

    # MA 和 EMA
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

    return df


def check_emergency_stop(row: pd.Series, direction: str, config: dict) -> dict:
    """檢查緊急止損條件"""
    emergency_atr = config.get("emergency_stop_atr", 3.5)
    atr = row["atr"]
    avg20 = row["avg20"]

    result = {
        "triggered": False,
        "direction": direction,
        "avg20": avg20,
        "atr": atr,
        "threshold": emergency_atr * atr,
        "breach": 0,
        "breach_ratio": 0,
    }

    if pd.isna(atr) or pd.isna(avg20) or atr <= 0:
        result["error"] = "指標數據無效"
        return result

    if direction == "short":
        breach = row["high"] - avg20
        result["price_checked"] = row["high"]
        result["check_type"] = "high vs avg20"
    else:  # long
        breach = avg20 - row["low"]
        result["price_checked"] = row["low"]
        result["check_type"] = "avg20 vs low"

    result["breach"] = breach
    result["breach_ratio"] = breach / atr if atr > 0 else 0

    if breach > 0 and breach > emergency_atr * atr:
        result["triggered"] = True

    return result


def analyze_symbol(broker: BinanceFuturesBroker, symbol: str, config: dict):
    """分析單一幣種的止損狀態"""
    print(f"\n{'='*60}")
    print(f"📊 {symbol} 止損分析")
    print("=" * 60)

    # 取得持倉
    position = broker.get_position(symbol)
    if position:
        print(f"\n🔹 持倉狀態:")
        print(f"   方向: {position.side}")
        print(f"   數量: {position.qty}")
        print(f"   進場價: {position.entry_price:.4f}")
        print(f"   未實現盈虧: ${position.unrealized_pnl:.2f}")
        direction = position.side.lower()
    else:
        print(f"\n❌ 無持倉")
        # 假設之前是 SHORT（根據用戶描述）
        direction = "short"
        print(f"   (假設之前為 SHORT 方向進行分析)")

    # 取得 K 線
    klines = broker.get_klines(symbol, "4h", 100)
    df = pd.DataFrame(klines)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = calculate_indicators(df)

    # 計算止損位
    ma20_buffer = config.get("ma20_buffer", 0.02)
    current_avg20 = df["avg20"].iloc[-1]

    if direction == "short":
        stop_loss = current_avg20 * (1 + ma20_buffer)
    else:
        stop_loss = current_avg20 * (1 - ma20_buffer)

    print(f"\n🛡️ 止損參數:")
    print(f"   AVG20: {current_avg20:.4f}")
    print(f"   MA20 Buffer: {ma20_buffer*100:.1f}%")
    print(f"   計算止損位: {stop_loss:.4f}")
    print(f"   ATR(14): {df['atr'].iloc[-1]:.4f}")
    print(
        f"   緊急止損閾值: {config.get('emergency_stop_atr', 3.5)}x ATR = {config.get('emergency_stop_atr', 3.5) * df['atr'].iloc[-1]:.4f}"
    )

    # 分析最近 20 根 K 線
    print(f"\n📈 最近 20 根 K 線緊急止損分析 (方向: {direction.upper()}):")
    print("-" * 100)
    print(
        f"{'時間':<20} {'High':>10} {'Low':>10} {'Close':>10} {'AVG20':>10} {'ATR':>8} {'Breach':>10} {'Ratio':>8} {'觸發?':>6}"
    )
    print("-" * 100)

    triggered_bars = []
    for i in range(-20, 0):
        row = df.iloc[i]
        bar_time = row.name.strftime("%Y-%m-%d %H:%M")
        result = check_emergency_stop(row, direction, config)

        trigger_mark = "🚨 YES" if result["triggered"] else ""
        if result["triggered"]:
            triggered_bars.append(bar_time)

        print(
            f"{bar_time:<20} "
            f"{row['high']:>10.4f} "
            f"{row['low']:>10.4f} "
            f"{row['close']:>10.4f} "
            f"{result['avg20']:>10.4f} "
            f"{result['atr']:>8.4f} "
            f"{result['breach']:>10.4f} "
            f"{result['breach_ratio']:>8.2f}x "
            f"{trigger_mark:>6}"
        )

    print("-" * 100)

    if triggered_bars:
        print(f"\n⚠️ 緊急止損觸發時間點: {', '.join(triggered_bars)}")
    else:
        print(f"\n✅ 最近 20 根 K 線未觸發緊急止損")

    # 普通止損分析
    print(f"\n📊 普通止損分析 (連續 10 根觸及止損位):")
    consecutive_count = 0
    max_consecutive = 0

    for i in range(-20, 0):
        row = df.iloc[i]
        if direction == "short":
            touched = row["high"] >= stop_loss
        else:
            touched = row["low"] <= stop_loss

        if touched:
            consecutive_count += 1
            max_consecutive = max(max_consecutive, consecutive_count)
        else:
            consecutive_count = 0

    confirm_bars = config.get("stop_loss_confirm_bars", 10)
    print(f"   確認根數要求: {confirm_bars}")
    print(f"   最大連續觸及: {max_consecutive}")

    if max_consecutive >= confirm_bars:
        print(f"   ⚠️ 已達普通止損條件！")
    else:
        print(f"   ✅ 未達普通止損條件 (還差 {confirm_bars - max_consecutive} 根)")

    return {
        "symbol": symbol,
        "has_position": position is not None,
        "direction": direction,
        "emergency_triggered": len(triggered_bars) > 0,
        "emergency_bars": triggered_bars,
        "normal_stop_reached": max_consecutive >= confirm_bars,
        "max_consecutive": max_consecutive,
    }


def main():
    print("=" * 60)
    print("🔍 止損邏輯診斷工具")
    print(f"⏰ 時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    broker = BinanceFuturesBroker()
    config = PHASE1_CONFIG

    print(f"\n📋 策略配置:")
    print(f"   緊急止損 ATR 倍數: {config.get('emergency_stop_atr', 3.5)}x")
    print(f"   普通止損確認根數: {config.get('stop_loss_confirm_bars', 10)}")
    print(f"   MA20 緩衝: {config.get('ma20_buffer', 0.02)*100:.1f}%")

    # 分析所有幣種
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    results = []

    for symbol in symbols:
        try:
            result = analyze_symbol(broker, symbol, config)
            results.append(result)
        except Exception as e:
            print(f"\n❌ {symbol} 分析失敗: {e}")

    # 總結
    print("\n" + "=" * 60)
    print("📊 總結")
    print("=" * 60)

    for r in results:
        status = []
        if r["emergency_triggered"]:
            status.append(f"🚨緊急止損({len(r['emergency_bars'])}次)")
        if r["normal_stop_reached"]:
            status.append(f"⚠️普通止損")
        if r["has_position"]:
            status.append(f"📍持倉中")

        status_text = ", ".join(status) if status else "✅正常"
        print(f"  {r['symbol']}: {status_text}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
