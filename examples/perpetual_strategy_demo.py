#!/usr/bin/env python3
"""
SuperDog v0.5 - 永續數據策略示例

展示如何在實際策略中使用資金費率和持倉量數據

這個示例展示：
1. 資金費率情緒分析
2. 持倉量動能分析
3. 多因子信號生成
4. 與價格數據結合使用

Usage:
    python3 examples/perpetual_strategy_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta

from data.perpetual import (
    FundingRateData,
    OpenInterestData,
    analyze_oi_trend,
    get_latest_funding_rate,
)


def market_sentiment_analysis():
    """市場情緒分析 - 使用資金費率"""
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "市場情緒分析" + " " * 36 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    try:
        # 獲取當前資金費率
        funding = get_latest_funding_rate("BTCUSDT")

        annual_rate = funding["annual_rate"]
        funding_rate = funding["funding_rate"]

        print("📊 當前市場狀態")
        print(f"  交易對: {funding['symbol']}")
        print(f"  資金費率: {funding_rate:.6f} ({funding_rate*100:.4f}%)")
        print(f"  年化費率: {annual_rate:.2f}%")
        print(f"  標記價格: ${funding['mark_price']:,.2f}")
        print()

        # 情緒判斷
        print("🎯 市場情緒分析")
        if annual_rate > 50:
            sentiment = "極度貪婪"
            signal = "⚠️  多頭過熱，考慮減倉或做空"
            color = "🔴"
        elif annual_rate > 20:
            sentiment = "貪婪"
            signal = "⚡ 多頭強勢，注意風險"
            color = "🟠"
        elif annual_rate > 0:
            sentiment = "偏多"
            signal = "✓ 市場正常，可持有多單"
            color = "🟢"
        elif annual_rate > -20:
            sentiment = "偏空"
            signal = "✓ 市場正常，可持有空單"
            color = "🟢"
        elif annual_rate > -50:
            sentiment = "恐慌"
            signal = "⚡ 空頭強勢，注意風險"
            color = "🟠"
        else:
            sentiment = "極度恐慌"
            signal = "⚠️  空頭過熱，考慮減倉或做多"
            color = "🔴"

        print(f"  情緒指標: {color} {sentiment}")
        print(f"  年化費率: {annual_rate:.2f}%")
        print(f"  交易建議: {signal}")
        print()

        # 歷史分析
        print("📈 歷史趨勢分析（最近7天）")
        fr = FundingRateData()
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        df = fr.fetch("BTCUSDT", start_time, end_time)

        if not df.empty:
            stats = fr.calculate_statistics(df)

            print(f"  平均費率: {stats['mean']:.6f}")
            print(f"  中位數: {stats['median']:.6f}")
            print(f"  標準差: {stats['std']:.6f}")
            print(f"  正費率比例: {stats['positive_ratio']:.1%}")
            print(f"  負費率比例: {stats['negative_ratio']:.1%}")

            # 極端值檢測
            anomalies = fr.detect_anomalies(df, threshold=0.005)
            anomaly_count = anomalies["is_anomaly"].sum()

            if anomaly_count > 0:
                print(f"  ⚠️  檢測到 {anomaly_count} 次極端費率")

        print()

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        print("   提示: 需要網絡連接以訪問 Binance API")
        print()


def capital_flow_analysis():
    """資金流向分析 - 使用持倉量"""
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "資金流向分析" + " " * 36 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    try:
        # 獲取持倉量趨勢
        trend = analyze_oi_trend("BTCUSDT", interval="1h")

        print("📊 持倉量動能")
        print(f"  當前持倉量: {trend['current_oi']:,.0f} 張")
        print(f"  平均持倉量: {trend['avg_oi']:,.0f} 張")
        print(f"  最高持倉量: {trend['max_oi']:,.0f} 張")
        print(f"  最低持倉量: {trend['min_oi']:,.0f} 張")
        print()

        # 趨勢分析
        trend_direction = trend["trend"]
        change_24h = trend["change_24h"]
        change_24h_pct = trend["change_24h_pct"]
        volatility = trend["volatility"]

        print("🎯 趨勢分析")
        print(f"  趨勢方向: {trend_direction.upper()}")
        print(f"  24h 變化: {change_24h:+,.0f} ({change_24h_pct:+.2f}%)")
        print(f"  波動率: {volatility:.2f}%")
        print()

        # 信號判斷
        print("⚡ 交易信號")

        if trend_direction == "increasing":
            if change_24h_pct > 10:
                signal = "🟢 強力買入信號 - 資金大量流入"
            elif change_24h_pct > 5:
                signal = "🟢 買入信號 - 資金持續流入"
            else:
                signal = "🟡 弱買入 - 資金緩慢流入"
        elif trend_direction == "decreasing":
            if change_24h_pct < -10:
                signal = "🔴 強力賣出信號 - 資金大量流出"
            elif change_24h_pct < -5:
                signal = "🔴 賣出信號 - 資金持續流出"
            else:
                signal = "🟡 弱賣出 - 資金緩慢流出"
        else:
            signal = "⚪ 中性 - 資金流動平穩"

        print(f"  {signal}")
        print()

        # 詳細分析
        print("📈 詳細分析")

        oi = OpenInterestData()
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        df = oi.fetch("BTCUSDT", start_time, end_time, interval="1h")

        if not df.empty:
            # 檢測突增/突減
            spikes = oi.detect_spikes(df, threshold=2.0)
            spike_count = spikes["is_spike"].sum()

            if spike_count > 0:
                surge_count = (spikes["spike_type"] == "surge").sum()
                drop_count = (spikes["spike_type"] == "drop").sum()

                print(f"  突增次數: {surge_count}")
                print(f"  突減次數: {drop_count}")

                if surge_count > drop_count * 2:
                    print("  解讀: 🟢 持續建倉，看漲")
                elif drop_count > surge_count * 2:
                    print("  解讀: 🔴 持續平倉，看跌")
                else:
                    print("  解讀: 🟡 建倉/平倉交替，震盪")

        print()

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        print("   提示: 需要網絡連接以訪問 Binance API")
        print()


def multi_factor_signal():
    """多因子信號生成 - 結合資金費率和持倉量"""
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 18 + "多因子信號生成" + " " * 34 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    try:
        # 1. 資金費率因子
        funding = get_latest_funding_rate("BTCUSDT")
        annual_rate = funding["annual_rate"]

        # 標準化資金費率分數 (-100 到 +100)
        funding_score = max(-100, min(100, annual_rate))

        # 2. 持倉量因子
        trend = analyze_oi_trend("BTCUSDT", interval="1h")
        change_24h_pct = trend["change_24h_pct"]

        # 標準化持倉量分數 (-100 到 +100)
        oi_score = max(-100, min(100, change_24h_pct * 5))

        print("📊 因子得分")
        print(f"  資金費率因子: {funding_score:+.2f} / 100")
        print(f"  持倉量因子:   {oi_score:+.2f} / 100")
        print()

        # 3. 綜合信號
        # 資金費率權重 40%，持倉量權重 60%
        composite_score = funding_score * 0.4 + oi_score * 0.6

        print("⚡ 綜合信號")
        print(f"  綜合得分: {composite_score:+.2f} / 100")
        print()

        # 4. 信號解讀
        print("🎯 交易建議")

        if composite_score > 50:
            signal = "🟢 強力買入"
            reason = "資金費率低 + 持倉量增加 → 看漲"
            action = "建議做多或加倉"
        elif composite_score > 20:
            signal = "🟢 買入"
            reason = "多頭信號 → 偏多"
            action = "可適量做多"
        elif composite_score > -20:
            signal = "🟡 中性"
            reason = "信號不明確 → 觀望"
            action = "等待更明確信號"
        elif composite_score > -50:
            signal = "🔴 賣出"
            reason = "空頭信號 → 偏空"
            action = "可適量做空"
        else:
            signal = "🔴 強力賣出"
            reason = "資金費率高 + 持倉量減少 → 看跌"
            action = "建議做空或減倉"

        print(f"  信號: {signal}")
        print(f"  得分: {composite_score:+.2f}")
        print(f"  理由: {reason}")
        print(f"  操作: {action}")
        print()

        # 5. 風險提示
        print("⚠️  風險提示")

        if abs(funding_score) > 80:
            print("  - 資金費率極端，市場可能反轉")

        if abs(oi_score) > 80:
            print("  - 持倉量劇烈變化，注意風險")

        if abs(composite_score) < 20:
            print("  - 信號不明確，建議觀望")

        print()

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        print("   提示: 需要網絡連接以訪問 Binance API")
        print()


def strategy_integration_example():
    """策略整合示例 - 展示如何在實際策略中使用"""
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 18 + "策略整合示例" + " " * 36 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    print("💡 在你的策略中使用永續數據：")
    print()

    code_example = '''
from strategies.api_v2 import BaseStrategy, DataSource, DataRequirement

class PerpetualStrategy(BaseStrategy):
    """使用永續數據的策略範例"""

    def get_data_requirements(self):
        return [
            DataRequirement(DataSource.OHLCV, required=True),
            DataRequirement(DataSource.FUNDING, required=True),
            DataRequirement(DataSource.OPEN_INTEREST, required=True)
        ]

    def compute_signals(self, data, params):
        # 獲取數據
        ohlcv = data['ohlcv']
        funding = data['funding_rate']
        oi = data['open_interest']

        # 計算指標
        price = ohlcv['close']
        funding_rate = funding['funding_rate']
        oi_change = oi['oi_change_pct']

        # 生成信號
        signals = pd.Series(0, index=ohlcv.index)

        # 多頭信號：資金費率低 + 持倉量增加 + 價格上漲
        long_condition = (
            (funding_rate < 0.0001) &      # 資金費率低
            (oi_change > 5) &               # 持倉量增加
            (price > price.shift(1))        # 價格上漲
        )
        signals[long_condition] = 1

        # 空頭信號：資金費率高 + 持倉量減少 + 價格下跌
        short_condition = (
            (funding_rate > 0.0005) &      # 資金費率高
            (oi_change < -5) &              # 持倉量減少
            (price < price.shift(1))        # 價格下跌
        )
        signals[short_condition] = -1

        return signals
'''

    print(code_example)

    print("✅ 使用方法：")
    print()
    print("  1. 定義數據需求（get_data_requirements）")
    print("  2. DataPipeline 自動載入所有數據")
    print("  3. 在 compute_signals 中結合使用")
    print("  4. 生成更準確的交易信號")
    print()


def main():
    """主函數"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "SuperDog v0.5 永續數據策略示例" + " " * 22 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    # 1. 市場情緒分析
    market_sentiment_analysis()

    # 2. 資金流向分析
    capital_flow_analysis()

    # 3. 多因子信號
    multi_factor_signal()

    # 4. 策略整合示例
    strategy_integration_example()

    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 25 + "示例完成" + " " * 36 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    print("💡 提示：")
    print("   - 這些數據可以直接用於你的交易策略")
    print("   - 結合價格、資金費率和持倉量可以生成更準確的信號")
    print("   - 建議在回測中驗證策略效果")
    print()


if __name__ == "__main__":
    main()
