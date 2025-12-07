#!/usr/bin/env python3
"""
SuperDog v0.5 - 完整川沐策略示範

整合所有 6 種永續合約數據源的多因子策略

Data Sources Used:
1. OHLCV - 價格動量和趨勢
2. FUNDING_RATE - 資金費率趨勢
3. OPEN_INTEREST - 持倉量變化
4. BASIS - 期現基差套利
5. LIQUIDATIONS - 市場恐慌逆向
6. LONG_SHORT_RATIO - 情緒逆向指標

Strategy Logic:
- 多因子評分系統 (0-6分)
- 因子權重動態調整
- 風險控制與倉位管理

Usage:
    python3 examples/kawamoku_complete_v05.py
"""

import sys
from pathlib import Path
from typing import Dict, List

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from strategies.api_v2 import BaseStrategy, DataRequirement, DataSource  # noqa: E402


class KawamokuMultiFactorStrategy(BaseStrategy):
    """川沐多因子策略 v0.5

    整合 SuperDog v0.5 的所有 6 種永續合約數據源

    Factor Breakdown:
    1. Price Momentum (OHLCV) - 20%
    2. Funding Rate Trend (FUNDING_RATE) - 15%
    3. Open Interest Change (OPEN_INTEREST) - 15%
    4. Basis Arbitrage (BASIS) - 20%
    5. Liquidation Panic (LIQUIDATIONS) - 15%
    6. Sentiment Contrarian (LONG_SHORT_RATIO) - 15%

    Signal Generation:
    - Each factor contributes 0-1 points
    - Total score: 0-6 points
    - Entry: score >= 4 points
    - Exit: score <= 2 points
    """

    def __init__(self, **params):
        """初始化策略

        Parameters:
            momentum_period: int = 20 - 動量周期
            funding_threshold: float = 0.01 - 資金費率閾值
            oi_threshold: float = 0.05 - 持倉量變化閾值
            basis_threshold: float = 0.5 - 基差閾值
            panic_threshold: str = 'elevated' - 恐慌閾值
            sentiment_threshold: float = 40 - 情緒指數閾值
        """
        super().__init__()

        # 因子參數
        self.momentum_period = params.get("momentum_period", 20)
        self.funding_threshold = params.get("funding_threshold", 0.01)
        self.oi_threshold = params.get("oi_threshold", 0.05)
        self.basis_threshold = params.get("basis_threshold", 0.5)
        self.panic_threshold = params.get("panic_threshold", "elevated")
        self.sentiment_threshold = params.get("sentiment_threshold", 40)

        # 因子權重
        self.weights = {
            "momentum": 0.20,
            "funding": 0.15,
            "oi": 0.15,
            "basis": 0.20,
            "panic": 0.15,
            "sentiment": 0.15,
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        """定義數據需求 (實現抽象方法)

        Returns:
            所有 6 種數據源 (Phase A必需 + Phase B可選)
        """
        return [
            # Phase A - 必需數據
            DataRequirement(DataSource.OHLCV, required=True),
            DataRequirement(DataSource.FUNDING_RATE, required=True),
            DataRequirement(DataSource.OPEN_INTEREST, required=True),
            # Phase B - 可選數據 (提高信號質量)
            DataRequirement(DataSource.BASIS, required=False),
            DataRequirement(DataSource.LIQUIDATIONS, required=False),
            DataRequirement(DataSource.LONG_SHORT_RATIO, required=False),
        ]

    def get_parameters(self) -> Dict:
        """返回策略參數"""
        return {
            "momentum_period": self.momentum_period,
            "funding_threshold": self.funding_threshold,
            "oi_threshold": self.oi_threshold,
            "basis_threshold": self.basis_threshold,
            "panic_threshold": self.panic_threshold,
            "sentiment_threshold": self.sentiment_threshold,
        }

    def compute_signals(self, data: Dict[str, pd.DataFrame]) -> pd.Series:
        """生成交易信號

        Args:
            data: 包含所有數據源的字典

        Returns:
            交易信號 Series (1=做多, -1=做空, 0=無倉位)
        """
        # 獲取OHLCV作為基準
        ohlcv = data["ohlcv"]
        index = ohlcv.index

        # 初始化因子得分
        factor_scores = pd.DataFrame(
            0, index=index, columns=["momentum", "funding", "oi", "basis", "panic", "sentiment"]
        )

        # === 因子 1: 價格動量 (OHLCV) ===
        factor_scores["momentum"] = self._calculate_momentum_factor(ohlcv)

        # === 因子 2: 資金費率趨勢 (FUNDING_RATE) ===
        if "funding_rate" in data:
            factor_scores["funding"] = self._calculate_funding_factor(data["funding_rate"])

        # === 因子 3: 持倉量變化 (OPEN_INTEREST) ===
        if "open_interest" in data:
            factor_scores["oi"] = self._calculate_oi_factor(data["open_interest"])

        # === 因子 4: 期現基差套利 (BASIS) ===
        if "basis" in data:
            factor_scores["basis"] = self._calculate_basis_factor(data["basis"])

        # === 因子 5: 爆倉恐慌逆向 (LIQUIDATIONS) ===
        if "liquidations" in data:
            factor_scores["panic"] = self._calculate_panic_factor(data["liquidations"])

        # === 因子 6: 情緒逆向 (LONG_SHORT_RATIO) ===
        if "long_short_ratio" in data:
            factor_scores["sentiment"] = self._calculate_sentiment_factor(data["long_short_ratio"])

        # 計算總分 (加權)
        total_score = pd.Series(0, index=index)
        for factor, weight in self.weights.items():
            total_score += factor_scores[factor] * weight * 6  # 歸一化到 0-6 分

        # 生成信號
        signals = pd.Series(0, index=index)
        signals[total_score >= 4] = 1  # 做多
        signals[total_score <= 2] = -1  # 做空

        return signals

    def _calculate_momentum_factor(self, ohlcv: pd.DataFrame) -> pd.Series:
        """計算動量因子

        邏輯:
        - 計算 N 日動量 (close / close.shift(N))
        - 動量 > 1: 看多 (1分)
        - 動量 < 1: 看空 (0分)
        """
        momentum = ohlcv["close"] / ohlcv["close"].shift(self.momentum_period)

        factor = pd.Series(0, index=ohlcv.index)
        factor[momentum > 1.0] = 1.0

        return factor

    def _calculate_funding_factor(self, funding: pd.DataFrame) -> pd.Series:
        """計算資金費率因子

        邏輯:
        - 資金費率 < -threshold: 看多 (1分) - 做空者付費
        - 資金費率 > +threshold: 看空 (0分) - 做多者付費
        """
        factor = pd.Series(0.5, index=funding.index)  # 中性

        factor[funding["funding_rate"] < -self.funding_threshold] = 1.0  # 看多
        factor[funding["funding_rate"] > self.funding_threshold] = 0.0  # 看空

        return factor

    def _calculate_oi_factor(self, oi: pd.DataFrame) -> pd.Series:
        """計算持倉量因子

        邏輯:
        - 持倉量增加 + 價格上漲 = 強勢 (1分)
        - 持倉量減少 + 價格下跌 = 弱勢 (0分)
        """
        oi_change = oi["open_interest"].pct_change()

        factor = pd.Series(0.5, index=oi.index)

        # 持倉量顯著增加
        factor[oi_change > self.oi_threshold] = 1.0

        # 持倉量顯著減少
        factor[oi_change < -self.oi_threshold] = 0.0

        return factor

    def _calculate_basis_factor(self, basis: pd.DataFrame) -> pd.Series:
        """計算基差因子

        邏輯:
        - 基差過大 (正基差 > threshold): 做空永續 + 做多現貨 (0.8分)
        - 基差過小 (負基差 < -threshold): 做多永續 + 做空現貨 (1分)
        - 基差正常: 中性 (0.5分)
        """
        factor = pd.Series(0.5, index=basis.index)

        if "basis_pct" in basis.columns:
            # 負基差 - 永續折價 - 看多永續
            factor[basis["basis_pct"] < -self.basis_threshold] = 1.0

            # 正基差 - 永續溢價 - 看空永續
            factor[basis["basis_pct"] > self.basis_threshold] = 0.2

        return factor

    def _calculate_panic_factor(self, liq: pd.DataFrame) -> pd.Series:
        """計算恐慌因子

        邏輯 (逆向指標):
        - 極度恐慌 (extreme): 市場超賣 → 看多 (1分)
        - 高度恐慌 (high): 波動加劇 → 輕微看多 (0.7分)
        - 平靜 (calm): 中性 (0.5分)
        """
        factor = pd.Series(0.5, index=liq.index)

        if "panic_level" in liq.columns:
            factor[liq["panic_level"] == "extreme"] = 1.0  # 逆向做多
            factor[liq["panic_level"] == "high"] = 0.7
            factor[liq["panic_level"] == "calm"] = 0.5

        return factor

    def _calculate_sentiment_factor(self, lsr: pd.DataFrame) -> pd.Series:
        """計算情緒因子

        邏輯 (逆向指標):
        - 極度看多 (sentiment_index > threshold): 逆向看空 (0分)
        - 極度看空 (sentiment_index < -threshold): 逆向看多 (1分)
        - 中性: 0.5分
        """
        factor = pd.Series(0.5, index=lsr.index)

        if "sentiment_index" in lsr.columns:
            # 市場極度看多 → 逆向看空
            factor[lsr["sentiment_index"] > self.sentiment_threshold] = 0.0

            # 市場極度看空 → 逆向看多
            factor[lsr["sentiment_index"] < -self.sentiment_threshold] = 1.0

        return factor


def demo_kawamoku_strategy():
    """示範川沐策略使用"""
    print()
    print("=" * 70)
    print("SuperDog v0.5 - 川沐多因子策略示範")
    print("=" * 70)
    print()

    # 創建策略實例
    strategy = KawamokuMultiFactorStrategy(
        momentum_period=20,
        funding_threshold=0.01,
        oi_threshold=0.05,
        basis_threshold=0.5,
        panic_threshold="elevated",
        sentiment_threshold=40,
    )

    print("策略配置:")
    print(f"  動量周期: {strategy.momentum_period} 天")
    print(f"  資金費率閾值: {strategy.funding_threshold:.2%}")
    print(f"  持倉量變化閾值: {strategy.oi_threshold:.2%}")
    print(f"  基差閾值: {strategy.basis_threshold}%")
    print(f"  恐慌閾值: {strategy.panic_threshold}")
    print(f"  情緒指數閾值: ±{strategy.sentiment_threshold}")
    print()

    print("數據需求:")
    for req in strategy.get_data_requirements():
        status = "必需" if req.required else "可選"
        print(f"  [{status}] {req.source.value}")
    print()

    print("因子權重:")
    for factor, weight in strategy.weights.items():
        print(f"  {factor:<12}: {weight:.0%}")
    print()

    # 創建模擬數據
    print("=" * 70)
    print("模擬回測示例")
    print("=" * 70)
    print()

    dates = pd.date_range("2024-01-01", periods=100, freq="1h")

    # 模擬 OHLCV
    ohlcv = pd.DataFrame(
        {
            "timestamp": dates,
            "open": 100000 + np.random.randn(100) * 1000,
            "high": 101000 + np.random.randn(100) * 1000,
            "low": 99000 + np.random.randn(100) * 1000,
            "close": 100000 + np.cumsum(np.random.randn(100) * 100),  # 隨機遊走
            "volume": 1000000 + np.random.randn(100) * 100000,
        },
        index=dates,
    )

    # 模擬 FUNDING_RATE
    funding = pd.DataFrame(
        {
            "timestamp": dates,
            "funding_rate": np.random.randn(100) * 0.0001,
            "predicted_rate": np.random.randn(100) * 0.0001,
        },
        index=dates,
    )

    # 模擬 OPEN_INTEREST
    oi = pd.DataFrame(
        {
            "timestamp": dates,
            "open_interest": 50000 + np.cumsum(np.random.randn(100) * 100),
            "open_interest_value": 5000000000 + np.cumsum(np.random.randn(100) * 10000000),
        },
        index=dates,
    )

    # 模擬 BASIS
    basis = pd.DataFrame(
        {
            "timestamp": dates,
            "basis": np.random.randn(100) * 50,
            "basis_pct": np.random.randn(100) * 0.5,
            "arbitrage_type": np.random.choice(["none", "cash_and_carry", "reverse"], 100),
        },
        index=dates,
    )

    # 模擬 LIQUIDATIONS
    liquidations = pd.DataFrame(
        {
            "timestamp": dates,
            "total_value": 1000000 + np.abs(np.random.randn(100) * 500000),
            "panic_level": np.random.choice(
                ["calm", "moderate", "elevated", "high", "extreme"], 100
            ),
        },
        index=dates,
    )

    # 模擬 LONG_SHORT_RATIO
    lsr = pd.DataFrame(
        {
            "timestamp": dates,
            "long_ratio": 0.5 + np.random.randn(100) * 0.1,
            "sentiment_index": np.random.randn(100) * 30,
            "contrarian_signal": np.random.choice(
                ["no_signal", "consider_long", "consider_short"], 100
            ),
        },
        index=dates,
    )

    # 組裝數據
    data = {
        "ohlcv": ohlcv,
        "funding_rate": funding,
        "open_interest": oi,
        "basis": basis,
        "liquidations": liquidations,
        "long_short_ratio": lsr,
    }

    # 生成信號
    print("正在生成交易信號...")
    signals = strategy.compute_signals(data)

    # 統計信號
    long_signals = (signals == 1).sum()
    short_signals = (signals == -1).sum()
    no_signals = (signals == 0).sum()

    print()
    print("信號統計:")
    print(f"  做多信號: {long_signals} ({long_signals/len(signals):.1%})")
    print(f"  做空信號: {short_signals} ({short_signals/len(signals):.1%})")
    print(f"  無倉位: {no_signals} ({no_signals/len(signals):.1%})")
    print()

    # 顯示最近信號
    print("最近 10 個信號:")
    recent = pd.DataFrame(
        {
            "時間": ohlcv["timestamp"].iloc[-10:].dt.strftime("%Y-%m-%d %H:%M"),
            "價格": ohlcv["close"].iloc[-10:].round(2),
            "信號": signals.iloc[-10:].map({1: "做多", -1: "做空", 0: "持倉"}),
        }
    )
    print(recent.to_string(index=False))
    print()

    # 因子分析示例
    print("=" * 70)
    print("因子貢獻分析 (最後一個時間點)")
    print("=" * 70)
    print()

    print("各因子當前狀態:")
    print(f"  動量因子: {'看多' if ohlcv['close'].iloc[-1] > ohlcv['close'].iloc[-20] else '看空'}")
    print(f"  資金費率: {funding['funding_rate'].iloc[-1]:.4f}%")
    print(f"  持倉量變化: {(oi['open_interest'].iloc[-1] / oi['open_interest'].iloc[-2] - 1):.2%}")
    print(f"  基差: {basis['basis_pct'].iloc[-1]:.2f}%")
    print(f"  恐慌等級: {liquidations['panic_level'].iloc[-1]}")
    print(f"  情緒指數: {lsr['sentiment_index'].iloc[-1]:.1f}")
    print()

    print("策略特點:")
    print("  ✓ 多因子綜合評分 (6個獨立因子)")
    print("  ✓ 動態權重調整 (可根據市場調整)")
    print("  ✓ 逆向指標應用 (恐慌+情緒)")
    print("  ✓ 套利機會捕捉 (基差因子)")
    print("  ✓ 風險控制集成 (多重確認)")
    print()

    print("使用建議:")
    print("  1. 根據實際市場調整因子權重")
    print("  2. 添加止損止盈邏輯")
    print("  3. 結合資金管理系統")
    print("  4. 使用 BacktestEngine 進行回測")
    print("  5. 監控各因子有效性")
    print()


def main():
    """主函數"""
    demo_kawamoku_strategy()

    print("=" * 70)
    print()
    print("川沐策略示範完成！")
    print()
    print("下一步:")
    print("  1. 下載真實數據進行回測")
    print("  2. 優化因子參數")
    print("  3. 添加風險控制模組")
    print("  4. 實盤測試 (模擬交易)")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
