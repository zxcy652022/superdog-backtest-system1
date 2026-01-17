"""
幣哥雙均線策略 v2.4 - 統一架構版

=== v2.4 重大重構（2026-01-05）===
符合 RULES.md 第 2.2 節規範：
- 策略只產生進出場信號
- 不包含槓桿、倉位、止損、加倉等執行邏輯
- 執行邏輯由 backtest/engine.py 根據 ExecutionConfig 處理

這確保所有策略走同一條執行路徑，消除多方邏輯差異。

核心邏輯：
1. 六條均線：MA(20,60,120) + EMA(20,60,120)
2. 均線密集（spread < 3%）連續 3 根 K 線
3. 均線密集 → 發散（突破 1%）→ 產生進場信號
4. 盈虧比門檻：RR >= 1.5 才進場
5. 趨勢過濾：MA20 > MA60 才做多

執行配置（由引擎處理）：
- 止損：確認式 10 根 + 追蹤 MA20 + 緊急 3.5x ATR
- 加倉：回踩 MA20 + 盈利 3% + 間隔 6 根
- 倉位：15% 權益 × 7x 槓桿
- 止盈：10%

Version: v2.4 (統一架構版)
Author: DDragon (based on 幣哥交易系統)
"""

from typing import Optional

import numpy as np
import pandas as pd

from backtest.engine import BaseStrategy
from backtest.strategy_config import (
    AddPositionConfig,
    ExecutionConfig,
    PositionSizingConfig,
    StopConfig,
)
from strategies.base import (
    OptimizableStrategyMixin,
    ParamCategory,
    bool_param,
    float_param,
    int_param,
)


class BiGeDualMAStrategyV2(BaseStrategy, OptimizableStrategyMixin):
    """
    幣哥雙均線策略 v2.4 - 統一架構版

    符合 RULES.md 第 2.2 節：
    - 策略只產生進出場信號
    - 執行邏輯（止損、加倉、倉位管理）由引擎處理
    - 通過 get_execution_config() 告訴引擎需要什麼配置
    """

    # ===== 可優化參數定義 =====
    OPTIMIZABLE_PARAMS = {
        "cluster_threshold": float_param(
            default=0.03,
            description="均線密集判定閾值",
            range_min=0.02,
            range_max=0.05,
            step=0.005,
            category=ParamCategory.SIGNAL,
        ),
        "cluster_lookback": int_param(
            default=3,
            description="連續密集 K 線數",
            range_min=2,
            range_max=5,
            step=1,
            category=ParamCategory.SIGNAL,
        ),
        "min_rr_ratio": float_param(
            default=1.5,
            description="最低盈虧比",
            range_min=1.0,
            range_max=3.0,
            step=0.5,
            category=ParamCategory.SIGNAL,
        ),
        "long_only": bool_param(
            default=True,
            description="只做多模式",
            category=ParamCategory.SIGNAL,
        ),
    }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """返回策略的執行配置（食譜）

        這個方法讓引擎知道：
        1. 使用什麼止損方式（確認式 + 追蹤 + 緊急止損）
        2. 如何加倉（回踩 MA20 + 盈利 3% 門檻）
        3. 倉位大小（15% 權益）
        4. 槓桿和止盈設定
        """
        return ExecutionConfig(
            # 止損配置（v2.1 驗證過的參數）
            stop_config=StopConfig(
                type="confirmed",
                confirm_bars=2,  # 連續 2 根確認（v2.1 驗證有效）
                trailing=True,  # 追蹤止損
                trailing_ma_key="avg20",  # 追蹤 MA20
                trailing_buffer=0.02,  # 緩衝 2%
                emergency_atr_mult=0,  # 禁用緊急止損（有效版本不用）
                fixed_stop_pct=0.03,  # 最大止損 3%
            ),
            # 加倉配置（v2.3 驗證過的參數）
            add_position_config=AddPositionConfig(
                enabled=True,
                max_count=3,  # 最多 3 次加倉
                size_pct=0.5,  # 每次加倉 50%
                min_interval=6,  # 間隔 6 根 K 線（24h）
                min_profit=0.03,  # 盈利 > 3% 才加倉
                pullback_tolerance=0.018,  # 回踩容許 1.8%
                pullback_ma_key="avg20",
            ),
            # 倉位配置
            position_sizing_config=PositionSizingConfig(
                type="percent_of_equity",
                percent=0.15,  # 15% 權益
            ),
            # 止盈和槓桿
            take_profit_pct=0.10,  # 10% 止盈
            leverage=7.0,  # 7x 槓桿
            fee_rate=0.0005,  # 0.05% 手續費
        )

    @classmethod
    def get_default_parameters(cls):
        """策略參數定義 - 只有信號相關參數"""
        return {
            # === 均線參數 ===
            "ma_len_short": 20,
            "ma_len_mid": 60,
            "ma_len_long": 120,
            # === 密集檢測 ===
            "cluster_threshold": 0.03,  # 3%
            "cluster_lookback": 3,  # 3 根
            # === 突破判定 ===
            "breakout_threshold": 0.01,  # 1%
            # === 趨勢過濾 ===
            "require_trend_alignment": True,
            # === 盈虧比門檻 ===
            "min_rr_ratio": 1.5,
            # === 只做多 ===
            "long_only": True,
            # === 止損參數（用於計算 RR ratio）===
            "fixed_stop_loss_pct": 0.03,  # 3%
            "ma_buffer": 0.02,  # 2%
            "take_profit_pct": 0.10,  # 10%
        }

    def __init__(self, broker, data, **kwargs):
        """初始化策略"""
        super().__init__(broker, data)

        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        # Cluster 狀態
        self.cluster_active = False
        self.cluster_center = None
        self.cluster_consecutive_count = 0

        # 止損建議（供引擎使用）
        self._suggested_stop: Optional[float] = None

        self._calculate_all_indicators()

    def set_parameters(self, **kwargs):
        """設置策略參數"""
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
        self._calculate_all_indicators()

    def _calculate_all_indicators(self):
        """預先計算所有技術指標"""
        p = self.params
        df = self.data

        # 6 條均線
        df["ma20"] = df["close"].rolling(p["ma_len_short"]).mean()
        df["ma60"] = df["close"].rolling(p["ma_len_mid"]).mean()
        df["ma120"] = df["close"].rolling(p["ma_len_long"]).mean()
        df["ema20"] = df["close"].ewm(span=p["ma_len_short"], adjust=False).mean()
        df["ema60"] = df["close"].ewm(span=p["ma_len_mid"], adjust=False).mean()
        df["ema120"] = df["close"].ewm(span=p["ma_len_long"], adjust=False).mean()

        # MA 中心（6 條均線的平均）
        df["ma_center"] = (
            df["ma20"] + df["ma60"] + df["ma120"] + df["ema20"] + df["ema60"] + df["ema120"]
        ) / 6

        # 平均 MA
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2

        # ATR（供引擎的緊急止損使用）
        df["atr"] = self._calculate_atr(df, 14)

        # 均線 spread
        def calc_spread(row):
            mas = [
                row["ma20"],
                row["ma60"],
                row["ma120"],
                row["ema20"],
                row["ema60"],
                row["ema120"],
            ]
            mas = [m for m in mas if pd.notna(m)]
            if len(mas) < 6:
                return np.nan
            return (max(mas) - min(mas)) / min(mas)

        df["spread"] = df.apply(calc_spread, axis=1)

    def _calculate_atr(self, df, period=14):
        """計算 ATR"""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def _is_cluster(self, row) -> bool:
        """檢測均線密集（3% 閾值）"""
        spread = row.get("spread", np.nan)
        if pd.isna(spread):
            return False
        return spread < self.params["cluster_threshold"]

    def _is_uptrend(self, row) -> bool:
        """多頭趨勢：MA20 > MA60"""
        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        if pd.isna(avg20) or pd.isna(avg60):
            return False
        return avg20 > avg60

    def _is_downtrend(self, row) -> bool:
        """空頭趨勢：MA20 < MA60"""
        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        if pd.isna(avg20) or pd.isna(avg60):
            return False
        return avg20 < avg60

    def _calculate_stop_loss(self, entry_price: float, ma_center: float, direction: str) -> float:
        """計算止損價（用於 RR ratio 檢查）"""
        p = self.params
        fixed_pct = p["fixed_stop_loss_pct"]
        ma_buffer = p["ma_buffer"]

        if direction == "long":
            sl_fixed = entry_price * (1 - fixed_pct)
            sl_ma = ma_center * (1 - ma_buffer)
            return max(sl_fixed, sl_ma)
        else:
            sl_fixed = entry_price * (1 + fixed_pct)
            sl_ma = ma_center * (1 + ma_buffer)
            return min(sl_fixed, sl_ma)

    def _calculate_take_profit(self, entry_price: float, direction: str) -> float:
        """計算止盈價"""
        tp_pct = self.params["take_profit_pct"]
        if direction == "long":
            return entry_price * (1 + tp_pct)
        else:
            return entry_price * (1 - tp_pct)

    def _check_rr_ratio(
        self, entry: float, stop_loss: float, take_profit: float, direction: str
    ) -> float:
        """計算盈虧比"""
        if direction == "long":
            risk = entry - stop_loss
            reward = take_profit - entry
        else:
            risk = stop_loss - entry
            reward = entry - take_profit

        if risk <= 0:
            return 0
        return reward / risk

    def get_stop_loss(self) -> Optional[float]:
        """獲取建議的止損價（供引擎調用）"""
        return self._suggested_stop

    def on_bar(self, i: int, row: pd.Series):
        """每根 K 線調用 - 只產生進場信號"""
        if i < self.params["ma_len_long"]:
            return

        current_time = row.name
        current_price = row["close"]

        # === 更新 Cluster 狀態 ===
        is_cluster = self._is_cluster(row)
        prev_row = self.data.iloc[i - 1] if i > 0 else None
        was_cluster = self._is_cluster(prev_row) if prev_row is not None else False

        if is_cluster:
            self.cluster_consecutive_count += 1
            if self.cluster_consecutive_count >= self.params["cluster_lookback"]:
                if not self.cluster_active:
                    self.cluster_active = True
                    self.cluster_center = row.get("ma_center")
        else:
            self.cluster_consecutive_count = 0

        # === 如果已有倉位，不產生新信號 ===
        # 倉位管理由引擎的 StopManager 和 AddPositionManager 處理
        if self.broker.has_position:
            return

        # === 進場信號：均線密集 → 發散（突破）===
        if was_cluster and not is_cluster and self.cluster_center is not None:
            ma_center = row.get("ma_center")
            close = row["close"]

            # 突破向上 - 開多
            if close > ma_center * (1 + self.params["breakout_threshold"]):
                if self.params["require_trend_alignment"] and not self._is_uptrend(row):
                    self.cluster_active = False
                    self.cluster_center = None
                    return

                stop_loss = self._calculate_stop_loss(close, ma_center, "long")
                take_profit = self._calculate_take_profit(close, "long")
                rr = self._check_rr_ratio(close, stop_loss, take_profit, "long")

                if rr >= self.params["min_rr_ratio"]:
                    # 記錄止損價供引擎使用
                    self._suggested_stop = stop_loss
                    # 產生買入信號（引擎會通過 PositionSizer 計算實際數量）
                    self.broker.buy_all(close, current_time)

            # 突破向下 - 開空（如果允許）
            elif close < ma_center * (
                1 - self.params["breakout_threshold"]
            ) and not self.params.get("long_only", True):
                if self.params["require_trend_alignment"] and not self._is_downtrend(row):
                    self.cluster_active = False
                    self.cluster_center = None
                    return

                stop_loss = self._calculate_stop_loss(close, ma_center, "short")
                take_profit = self._calculate_take_profit(close, "short")
                rr = self._check_rr_ratio(close, stop_loss, take_profit, "short")

                if rr >= self.params["min_rr_ratio"]:
                    self._suggested_stop = stop_loss
                    self.broker.short_all(close, current_time)

            # 重置 cluster 狀態
            self.cluster_active = False
            self.cluster_center = None
