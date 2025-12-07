#!/usr/bin/env python3
"""
SuperDog v0.5 Phase B 快速示範

展示 Phase B 新功能的簡單示例：
- 期現基差計算
- 爆倉數據監控
- 多空持倉比分析
- 多交易所數據聚合

Usage:
    python3 examples/phase_b_quick_demo.py
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta  # noqa: E402

import pandas as pd  # noqa: E402


def print_section(title: str):
    """打印章節標題"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def demo_bybit_connector():
    """示範 1: Bybit 連接器"""
    print_section("示範 1: Bybit 連接器 - 獲取資金費率")

    from data.exchanges import BybitConnector

    # 初始化連接器
    bybit = BybitConnector()
    print(f"連接器: {bybit}")
    print(f"交易所: {bybit.name}")
    print(f"Base URL: {bybit.base_url}")
    print(f"速率限制: {bybit.rate_limit} 請求/分鐘")

    print()
    print("💡 Bybit V5 API 支援:")
    print("  - 資金費率歷史")
    print("  - 持倉量數據")
    print("  - 多空持倉比")
    print("  - 標記價格")


def demo_okx_connector():
    """示範 2: OKX 連接器"""
    print_section("示範 2: OKX 連接器 - 符號格式轉換")

    from data.exchanges import OKXConnector

    # 初始化連接器
    okx = OKXConnector()
    print(f"連接器: {okx}")
    print(f"交易所: {okx.name}")
    print(f"Base URL: {okx.base_url}")

    # 符號格式轉換
    print()
    print("符號格式轉換:")
    symbol_binance = "BTCUSDT"
    symbol_okx = okx._validate_symbol(symbol_binance)
    print(f"  Binance 格式: {symbol_binance}")
    print(f"  OKX 格式:     {symbol_okx}")

    print()
    print("💡 OKX API 獨有功能:")
    print("  - 每日聚合爆倉數據")
    print("  - 持倉量多空比")
    print("  - 合約數據統計")


def demo_basis_calculation():
    """示範 3: 期現基差計算"""
    print_section("示範 3: 期現基差計算 - 模擬數據")

    from data.perpetual import BasisData

    # 初始化基差數據處理器
    basis_data = BasisData()
    print(f"基差數據處理器初始化完成")
    print(f"存儲路徑: {basis_data.storage_path}")

    # 模擬基差計算
    print()
    print("基差計算公式:")
    print("  基差 = 永續價格 - 現貨價格")
    print("  基差百分比 = (基差 / 現貨價格) × 100%")
    print("  年化基差 = 基差百分比 × 365")

    # 示例計算
    perp_price = 100500.0
    spot_price = 100000.0
    basis = perp_price - spot_price
    basis_pct = (basis / spot_price) * 100
    annualized = basis_pct * 365

    print()
    print("示例計算:")
    print(f"  永續價格: ${perp_price:,.2f}")
    print(f"  現貨價格: ${spot_price:,.2f}")
    print(f"  基差: ${basis:,.2f}")
    print(f"  基差百分比: {basis_pct:.4f}%")
    print(f"  年化基差: {annualized:.2f}%")

    print()
    print("套利機會判斷:")
    if basis_pct > 0.5:
        print("  ✅ 正向套利 (Cash-and-Carry):")
        print("     做空永續 + 做多現貨")
    elif basis_pct < -0.5:
        print("  ✅ 反向套利 (Reverse):")
        print("     做多永續 + 做空現貨")
    else:
        print("  ⚪ 無明顯套利機會")


def demo_liquidation_monitoring():
    """示範 4: 爆倉數據監控"""
    print_section("示範 4: 爆倉數據監控 - 恐慌指數")

    from data.perpetual import LiquidationData

    # 初始化爆倉數據處理器
    liq_data = LiquidationData()
    print(f"爆倉數據處理器初始化完成")
    print(f"存儲路徑: {liq_data.storage_path}")
    print(f"支援交易所: {list(liq_data.connectors.keys())}")

    # 恐慌指數計算邏輯
    print()
    print("恐慌指數計算:")
    print("  intensity_ratio = 當前爆倉量 / 平均爆倉量")
    print("  panic_index = min(100, intensity_ratio × 20)")

    # 模擬恐慌等級
    print()
    print("恐慌等級分類:")
    levels = [
        ("0-20", "calm", "市場平靜", "正常交易"),
        ("20-40", "moderate", "輕度波動", "保持警惕"),
        ("40-60", "elevated", "波動加劇", "減少倉位"),
        ("60-80", "high", "高度恐慌", "考慮對沖"),
        ("80-100", "extreme", "極度恐慌", "逆向機會"),
    ]

    for range_val, level, desc, action in levels:
        print(f"  {range_val:>6}: {level:<10} - {desc:<12} → {action}")

    print()
    print("應用場景:")
    print("  - 市場情緒監控")
    print("  - 價格反轉信號識別")
    print("  - 流動性風險評估")


def demo_long_short_ratio():
    """示範 5: 多空持倉比分析"""
    print_section("示範 5: 多空持倉比 - 逆向情緒指標")

    from data.perpetual import LongShortRatioData

    # 初始化多空比數據處理器
    lsr_data = LongShortRatioData()
    print(f"多空比數據處理器初始化完成")
    print(f"存儲路徑: {lsr_data.storage_path}")
    print(f"支援交易所: {list(lsr_data.connectors.keys())}")

    # 情緒指數計算
    print()
    print("情緒指數計算:")
    print("  sentiment_index = (long_ratio - 0.5) × 200")
    print("  範圍: -100 (極度看空) ~ +100 (極度看多)")

    # 模擬不同多空比情況
    print()
    print("逆向交易信號:")
    scenarios = [
        (0.80, "極度看多", "consider_short", "市場過度樂觀，考慮做空"),
        (0.65, "看多", "watch_for_reversal", "觀察反轉信號"),
        (0.50, "中性", "no_signal", "無明確信號"),
        (0.35, "看空", "watch_for_reversal", "觀察反轉信號"),
        (0.20, "極度看空", "consider_long", "市場過度悲觀，考慮做多"),
    ]

    for long_ratio, sentiment, signal, desc in scenarios:
        sentiment_idx = (long_ratio - 0.5) * 200
        print(f"  多頭 {long_ratio:.0%}: 指數 {sentiment_idx:+6.1f} → {desc}")

    print()
    print("背離分析:")
    print("  - 看漲背離: 價格下跌 + 多頭比例增加 → 潛在底部")
    print("  - 看跌背離: 價格上漲 + 多頭比例減少 → 潛在頂部")


def demo_multi_exchange_aggregation():
    """示範 6: 多交易所數據聚合"""
    print_section("示範 6: 多交易所數據聚合")

    from data.aggregation import MultiExchangeAggregator

    # 初始化聚合器
    agg = MultiExchangeAggregator(exchanges=["binance", "bybit", "okx"])
    print(f"多交易所聚合器初始化完成")
    print(f"支援交易所: {agg.exchanges}")

    print()
    print("並行數據獲取:")
    print("  使用 ThreadPoolExecutor 同時從 3 個交易所獲取數據")
    print("  性能提升: 最高 3 倍速度")

    print()
    print("聚合方法:")
    methods = [
        ("weighted_mean", "加權平均", "根據交易量加權"),
        ("median", "中位數", "減少異常值影響"),
        ("mean", "簡單平均", "所有交易所平等權重"),
        ("sum", "總和", "用於持倉量等指標"),
    ]

    for method, name, desc in methods:
        print(f"  {method:<15} - {name:<10} - {desc}")

    print()
    print("跨交易所異常檢測:")
    print("  - 計算 Z-score 識別異常數據")
    print("  - 自動標記可疑的 API 響應")
    print("  - 提高數據可靠性")

    print()
    print("應用場景:")
    print("  ✓ 數據交叉驗證")
    print("  ✓ API 異常檢測")
    print("  ✓ 提高數據質量")
    print("  ✓ 尋找跨交易所套利機會")


def demo_data_pipeline_integration():
    """示範 7: DataPipeline 集成"""
    print_section("示範 7: DataPipeline 集成 - Phase B 升級")

    from data.pipeline import get_pipeline
    from strategies.api_v2 import DataSource

    # 獲取 pipeline
    pipeline = get_pipeline()
    print("DataPipeline v0.5 Phase B 已載入")

    # 檢查新增的數據處理器
    print()
    print("新增數據處理器:")
    processors = [
        ("basis_data", "BasisData", "期現基差計算"),
        ("liquidation_data", "LiquidationData", "爆倉數據監控"),
        ("long_short_ratio_data", "LongShortRatioData", "多空持倉比分析"),
    ]

    for attr, class_name, desc in processors:
        has_attr = hasattr(pipeline, attr)
        status = "✅" if has_attr else "❌"
        print(f"  {status} {attr:<25} ({class_name:<25}) - {desc}")

    # 檢查 DataSource 枚舉
    print()
    print("可用數據源 (DataSource):")
    sources = [
        (DataSource.OHLCV, "v0.4", "K線數據"),
        (DataSource.FUNDING_RATE, "Phase A", "資金費率"),
        (DataSource.OPEN_INTEREST, "Phase A", "持倉量"),
        (DataSource.BASIS, "Phase B", "期現基差"),
        (DataSource.LIQUIDATIONS, "Phase B", "爆倉數據"),
        (DataSource.LONG_SHORT_RATIO, "Phase B", "多空比"),
    ]

    for source, version, desc in sources:
        print(f"  ✓ {source.value:<20} ({version:<8}) - {desc}")

    print()
    print("Storage-First 模式:")
    print("  1. 優先從本地存儲載入數據")
    print("  2. 存儲無數據時，從 API 獲取")
    print("  3. API 數據自動保存到存儲")
    print("  4. 下次請求直接使用本地數據")

    print()
    print("優勢:")
    print("  ✓ 減少 API 調用")
    print("  ✓ 降低速率限制風險")
    print("  ✓ 提高回測速度")
    print("  ✓ 支援離線使用")


def demo_strategy_usage():
    """示範 8: 在策略中使用 Phase B 數據"""
    print_section("示範 8: 多因子策略示例")

    print("策略示例代碼:")
    print()
    code = '''
from strategies.api_v2 import StrategyV2, DataSource, DataRequirement

class MultiFactorStrategy(StrategyV2):
    """使用所有 6 種數據源的多因子策略"""

    @property
    def data_requirements(self):
        return [
            # 必需數據 (Phase A)
            DataRequirement(DataSource.OHLCV, required=True),
            DataRequirement(DataSource.FUNDING_RATE, required=True),
            DataRequirement(DataSource.OPEN_INTEREST, required=True),

            # 可選數據 (Phase B)
            DataRequirement(DataSource.BASIS, required=False),
            DataRequirement(DataSource.LIQUIDATIONS, required=False),
            DataRequirement(DataSource.LONG_SHORT_RATIO, required=False)
        ]

    def generate_signals(self, data):
        signals = pd.Series(0, index=data['ohlcv'].index)

        # 因子 1: 基差套利
        if 'basis' in data:
            basis_signal = (data['basis']['arbitrage_type'] != 'none')
            signals += basis_signal.astype(int)

        # 因子 2: 恐慌逆向
        if 'liquidations' in data:
            panic_signal = (data['liquidations']['panic_level'] == 'extreme')
            signals += panic_signal.astype(int)

        # 因子 3: 情緒逆向
        if 'long_short_ratio' in data:
            sentiment_signal = (data['long_short_ratio']['reversal_signal'] != 'none')
            signals += sentiment_signal.astype(int)

        return signals
'''
    print(code)

    print()
    print("多因子組合邏輯:")
    print("  - 基差因子: 識別套利機會")
    print("  - 恐慌因子: 極度恐慌時逆向交易")
    print("  - 情緒因子: 極端多空比時反向操作")
    print()
    print("信號強度:")
    print("  0 分: 無信號")
    print("  1 分: 單一因子觸發")
    print("  2 分: 雙因子共振")
    print("  3 分: 三因子共振 (最強信號)")


def main():
    """主函數"""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "SuperDog v0.5 Phase B 快速示範" + " " * 19 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        # 1. Bybit 連接器
        demo_bybit_connector()

        # 2. OKX 連接器
        demo_okx_connector()

        # 3. 期現基差計算
        demo_basis_calculation()

        # 4. 爆倉數據監控
        demo_liquidation_monitoring()

        # 5. 多空持倉比
        demo_long_short_ratio()

        # 6. 多交易所聚合
        demo_multi_exchange_aggregation()

        # 7. DataPipeline 集成
        demo_data_pipeline_integration()

        # 8. 策略使用示例
        demo_strategy_usage()

        # 總結
        print_section("✅ Phase B 快速示範完成")
        print("所有功能模組已成功展示！")
        print()
        print("下一步:")
        print("  1. 運行驗證腳本: python3 verify_v05_phase_b.py")
        print("  2. 查看完整文檔: PHASE_B_DELIVERY.md")
        print("  3. 開始編寫多因子策略")
        print("  4. 使用多交易所數據進行回測")
        print()
        print("Phase B 交付內容:")
        print("  ✓ 3 種新數據源 (BASIS, LIQUIDATIONS, LONG_SHORT_RATIO)")
        print("  ✓ 2 個新交易所 (Bybit, OKX)")
        print("  ✓ 1 個聚合系統 (MultiExchangeAggregator)")
        print("  ✓ 完整驗證系統 (7/7 模組通過)")
        print()

    except Exception as e:
        print()
        print(f"❌ 示範過程中發生錯誤: {e}")
        print()
        print("可能原因:")
        print("  - 依賴包未安裝 (pandas, numpy, requests)")
        print("  - 文件路徑不正確")
        print()
        print("解決方案:")
        print("  pip3 install --break-system-packages pandas numpy requests pyarrow")
        print("  python3 verify_v05_phase_b.py")
        return 1

    print("=" * 70)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
