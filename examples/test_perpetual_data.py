"""
Quick Test Script for Perpetual Data v0.5

測試資金費率和持倉量數據功能

Usage:
    python examples/test_perpetual_data.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta

from data.perpetual import (
    FundingRateData,
    OpenInterestData,
    fetch_funding_rate,
    fetch_open_interest,
    get_latest_funding_rate,
)


def test_funding_rate():
    """測試資金費率功能"""
    print("=" * 70)
    print("測試資金費率數據")
    print("=" * 70)

    # 1. 獲取最新資金費率
    print("\n1. 獲取 BTCUSDT 最新資金費率...")
    try:
        latest = get_latest_funding_rate("BTCUSDT", exchange="binance")
        print(f"   交易對: {latest['symbol']}")
        print(f"   資金費率: {latest['funding_rate']:.6f} ({latest['funding_rate']*100:.4f}%)")
        print(f"   年化費率: {latest['annual_rate']:.2f}%")
        print(f"   標記價格: ${latest['mark_price']:,.2f}")
        print(f"   下次結算: {latest['next_funding_time']}")
        print("   ✓ 成功")
    except Exception as e:
        print(f"   ✗ 失敗: {e}")

    # 2. 獲取歷史資金費率
    print("\n2. 獲取 BTCUSDT 最近7天資金費率...")
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        df = fetch_funding_rate("BTCUSDT", start_time, end_time, exchange="binance")

        if not df.empty:
            print(f"   獲取記錄數: {len(df)}")
            print(f"   時間範圍: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
            print(f"   平均費率: {df['funding_rate'].mean():.6f}")
            print(f"   最高費率: {df['funding_rate'].max():.6f}")
            print(f"   最低費率: {df['funding_rate'].min():.6f}")
            print("\n   最近5筆記錄:")
            print(df[["timestamp", "funding_rate", "annual_rate"]].tail())
            print("   ✓ 成功")
        else:
            print("   ⚠ 未獲取到數據")

    except Exception as e:
        print(f"   ✗ 失敗: {e}")

    # 3. 計算統計指標
    print("\n3. 計算資金費率統計指標...")
    try:
        fr = FundingRateData()
        stats = fr.calculate_statistics(df)

        print(f"   平均費率: {stats['mean']:.6f}")
        print(f"   中位數: {stats['median']:.6f}")
        print(f"   標準差: {stats['std']:.6f}")
        print(f"   正費率比例: {stats['positive_ratio']:.2%}")
        print(f"   負費率比例: {stats['negative_ratio']:.2%}")
        print(f"   極端費率次數: {stats['extreme_count']}")
        print("   ✓ 成功")

    except Exception as e:
        print(f"   ✗ 失敗: {e}")


def test_open_interest():
    """測試持倉量功能"""
    print("\n" + "=" * 70)
    print("測試持倉量數據")
    print("=" * 70)

    # 1. 獲取持倉量數據
    print("\n1. 獲取 BTCUSDT 最近7天持倉量數據...")
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        df = fetch_open_interest("BTCUSDT", start_time, end_time, interval="1h", exchange="binance")

        if not df.empty:
            print(f"   獲取記錄數: {len(df)}")
            print(f"   時間範圍: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
            print(f"   當前持倉量: {df['open_interest'].iloc[-1]:,.0f} 張")
            print(f"   持倉量價值: ${df['open_interest_value'].iloc[-1]:,.0f}")
            print("\n   最近5筆記錄:")
            print(df[["timestamp", "open_interest", "open_interest_value", "oi_change_pct"]].tail())
            print("   ✓ 成功")
        else:
            print("   ⚠ 未獲取到數據")

    except Exception as e:
        print(f"   ✗ 失敗: {e}")
        df = None

    # 2. 分析持倉量趨勢
    if df is not None and not df.empty:
        print("\n2. 分析持倉量趨勢...")
        try:
            oi = OpenInterestData()
            trend = oi.analyze_trend(df, window=24)

            print(f"   當前持倉量: {trend['current_oi']:,.0f}")
            print(f"   平均持倉量: {trend['avg_oi']:,.0f}")
            print(f"   最大持倉量: {trend['max_oi']:,.0f}")
            print(f"   最小持倉量: {trend['min_oi']:,.0f}")
            print(f"   趨勢方向: {trend['trend']}")
            print(f"   24小時變化: {trend['change_24h']:,.0f} ({trend['change_24h_pct']:.2f}%)")
            print(f"   波動率: {trend['volatility']:.2f}%")
            print("   ✓ 成功")

        except Exception as e:
            print(f"   ✗ 失敗: {e}")


def test_data_quality():
    """測試數據品質"""
    print("\n" + "=" * 70)
    print("測試數據品質功能")
    print("=" * 70)

    print("\n1. 檢測資金費率異常值...")
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)

        fr = FundingRateData()
        df = fr.fetch("BTCUSDT", start_time, end_time, exchange="binance")

        if not df.empty:
            df_with_anomalies = fr.detect_anomalies(df, threshold=0.003)  # 0.3%

            anomaly_count = df_with_anomalies["is_anomaly"].sum()
            print(f"   總記錄數: {len(df_with_anomalies)}")
            print(f"   異常值數量: {anomaly_count}")

            if anomaly_count > 0:
                print("\n   異常記錄:")
                anomalies = df_with_anomalies[df_with_anomalies["is_anomaly"]]
                print(anomalies[["timestamp", "funding_rate", "anomaly_type"]].head(10))

            print("   ✓ 成功")
        else:
            print("   ⚠ 未獲取到數據")

    except Exception as e:
        print(f"   ✗ 失敗: {e}")


def main():
    """主測試函數"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "SuperDog v0.5 永續數據測試" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        # 測試資金費率
        test_funding_rate()

        # 測試持倉量
        test_open_interest()

        # 測試數據品質
        test_data_quality()

        print("\n" + "=" * 70)
        print("所有測試完成！")
        print("=" * 70)

    except KeyboardInterrupt:
        print("\n\n測試被用戶中斷")
    except Exception as e:
        print(f"\n\n測試過程中發生錯誤: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
