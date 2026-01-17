"""
BiGe 雙均線策略 - 純信號版 v1.2

符合 RULES.md 第 2.2 節規範：
- 策略只產生進出場信號
- 不包含槓桿、倉位、止損、加倉等執行邏輯
- 執行邏輯由 backtest/engine.py 根據 ExecutionConfig 處理

核心邏輯（與 bige_dual_ma_v2.py v2.3 一致）：
1. 六條均線：MA(20,60,120) + EMA(20,60,120)
2. 均線密集（spread < 3%）連續 3 根 K 線
3. 均線密集 → 發散（突破 1%）→ 產生進場信號
4. 盈虧比門檻：RR >= 1.5 才進場
5. 趨勢過濾：MA20 > MA60 才做多
6. 止損計算：max(進場價 -3%, MA中心 -2%)

使用方式：
```python
from backtest.engine import run_backtest
from strategies.bige_signal import BiGeSignalStrategy

# 方式 1：策略自帶配置（推薦）
result = run_backtest(data=df, strategy_cls=BiGeSignalStrategy, initial_cash=500)

# 方式 2：使用便捷函數
from strategies.bige_signal import run_bige_backtest
result = run_bige_backtest(df, initial_cash=500)
```

Version: v1.2
Date: 2026-01-05
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


class BiGeSignalStrategy(BaseStrategy):
    """
    BiGe 雙均線策略 - 純信號版 v1.2

    只產生進場/出場信號，不包含執行邏輯。
    與 bige_dual_ma_v2.py v2.3 邏輯完全一致。

    這個策略實現了「食譜」模式：
    - get_execution_config(): 告訴引擎需要什麼執行配置
    - on_bar(): 只負責產生進場信號
    - 所有執行邏輯（止損、加倉、倉位管理）由引擎處理
    """

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
            # 止損配置（與 v2.3 完全一致）
            stop_config=StopConfig(
                type="confirmed",
                confirm_bars=10,  # 連續 10 根確認
                trailing=True,  # 追蹤止損
                trailing_ma_key="avg20",  # 追蹤 MA20
                trailing_buffer=0.02,  # 緩衝 2%
                emergency_atr_mult=3.5,  # 緊急止損 3.5x ATR
                fixed_stop_pct=0.03,  # 最大止損 3%
            ),
            # 加倉配置（與 v2.3 完全一致）
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

    def __init__(self, broker, data: pd.DataFrame, **kwargs):
        """初始化策略

        Args:
            broker: SimulatedBroker 實例
            data: OHLCV DataFrame
            **kwargs: 策略參數
        """
        super().__init__(broker, data)

        # 策略參數（與 v2.3 一致）
        self.params = {
            # 均線週期
            "ma_len_short": kwargs.get("ma_len_short", 20),
            "ma_len_mid": kwargs.get("ma_len_mid", 60),
            "ma_len_long": kwargs.get("ma_len_long", 120),
            # 均線密集判定（與 v2.3 一致：3% 閾值，3 根確認）
            "cluster_threshold": kwargs.get("cluster_threshold", 0.03),  # 3%
            "cluster_lookback": kwargs.get("cluster_lookback", 3),  # 連續 3 根
            # 突破判定
            "breakout_threshold": kwargs.get("breakout_threshold", 0.01),  # 1%
            # 趨勢過濾（與 v2.3 一致：MA20 > MA60 即可）
            "require_trend": kwargs.get("require_trend", True),
            # 只做多
            "long_only": kwargs.get("long_only", True),
            # 盈虧比門檻（v2.3 關鍵參數）
            "min_rr_ratio": kwargs.get("min_rr_ratio", 1.5),
            # 止損參數（與 v2.3 一致）
            "fixed_stop_loss_pct": kwargs.get("fixed_stop_loss_pct", 0.03),  # 3%
            "ma_buffer": kwargs.get("ma_buffer", 0.02),  # MA 緩衝 2%
            # 止盈參數
            "take_profit_pct": kwargs.get("take_profit_pct", 0.10),  # 10%
        }

        # 預計算指標
        self._precompute_indicators()

        # 狀態追蹤
        self.cluster_active = False
        self.cluster_consecutive_count = 0
        self.cluster_center: Optional[float] = None

        # 止損建議（供引擎使用）
        self._suggested_stop: Optional[float] = None

    def _precompute_indicators(self):
        """預計算技術指標（與 v2.3 一致）"""
        df = self.data
        p = self.params

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

        # 平均 MA（供趨勢判定用）
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2

        # ATR（供緊急止損使用）
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()

        # 均線 spread（與 v2.3 一致的密集判定）
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

    def _is_cluster(self, row: pd.Series) -> bool:
        """檢查均線是否密集（與 v2.3 一致：使用 spread）"""
        spread = row.get("spread", np.nan)
        if pd.isna(spread):
            return False
        return spread < self.params["cluster_threshold"]

    def _is_uptrend(self, row: pd.Series) -> bool:
        """檢查是否上升趨勢（與 v2.3 一致：MA20 > MA60 即可）"""
        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        if pd.isna(avg20) or pd.isna(avg60):
            return False
        return avg20 > avg60

    def _is_downtrend(self, row: pd.Series) -> bool:
        """檢查是否下降趨勢（與 v2.3 一致：MA20 < MA60 即可）"""
        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        if pd.isna(avg20) or pd.isna(avg60):
            return False
        return avg20 < avg60

    def _calculate_stop_loss(self, entry_price: float, ma_center: float, direction: str) -> float:
        """
        計算止損價（與 v2.3 一致）

        邏輯：max(固定止損, MA止損) - 取較近者
        """
        p = self.params
        fixed_pct = p["fixed_stop_loss_pct"]
        ma_buffer = p["ma_buffer"]

        if direction == "long":
            sl_fixed = entry_price * (1 - fixed_pct)  # 進場價 -3%
            sl_ma = ma_center * (1 - ma_buffer)  # MA中心 -2%
            return max(sl_fixed, sl_ma)  # 取較近者（較高的）
        else:
            sl_fixed = entry_price * (1 + fixed_pct)
            sl_ma = ma_center * (1 + ma_buffer)
            return min(sl_fixed, sl_ma)  # 取較近者（較低的）

    def _calculate_take_profit(self, entry_price: float, direction: str) -> float:
        """計算止盈價（與 v2.3 一致：固定 10%）"""
        tp_pct = self.params["take_profit_pct"]
        if direction == "long":
            return entry_price * (1 + tp_pct)
        else:
            return entry_price * (1 - tp_pct)

    def _check_rr_ratio(
        self, entry: float, stop_loss: float, take_profit: float, direction: str
    ) -> float:
        """計算盈虧比（與 v2.3 一致）"""
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
        """每根 K 線調用（與 v2.3 進場邏輯完全一致）"""
        if i < self.params["ma_len_long"]:
            return

        current_time = row.name
        current_price = row["close"]

        # === 更新 Cluster 狀態（與 v2.3 一致）===
        is_cluster = self._is_cluster(row)
        prev_row = self.data.iloc[i - 1] if i > 0 else None
        was_cluster = self._is_cluster(prev_row) if prev_row is not None else False

        if is_cluster:
            self.cluster_consecutive_count += 1
            if self.cluster_consecutive_count >= self.params["cluster_lookback"]:
                if not self.cluster_active:
                    self.cluster_active = True
                    # 記錄 cluster 中心（與 v2.3 一致）
                    self.cluster_center = row.get("ma_center")
        else:
            self.cluster_consecutive_count = 0

        # === 如果已有倉位，不產生新信號 ===
        if self.broker.has_position:
            return

        # === 進場信號：均線密集 → 發散（突破）（與 v2.3 完全一致）===
        if was_cluster and not is_cluster and self.cluster_center is not None:
            ma_center = row.get("ma_center")
            close = row["close"]

            # 突破向上 - 開多（與 v2.3 一致：close > ma_center * 1.01）
            if close > ma_center * (1 + self.params["breakout_threshold"]):
                # 趨勢過濾（與 v2.3 一致）
                if self.params["require_trend"] and not self._is_uptrend(row):
                    self.cluster_active = False
                    self.cluster_center = None
                    return

                # 計算止損止盈（與 v2.3 完全一致）
                stop_loss = self._calculate_stop_loss(close, ma_center, "long")
                take_profit = self._calculate_take_profit(close, "long")

                # 盈虧比檢查（v2.3 關鍵條件）
                rr = self._check_rr_ratio(close, stop_loss, take_profit, "long")
                if rr < self.params["min_rr_ratio"]:
                    self.cluster_active = False
                    self.cluster_center = None
                    return

                # 記錄止損價供引擎使用
                self._suggested_stop = stop_loss

                # 產生買入信號
                self.broker.buy_all(close, current_time)

            # 突破向下 - 開空（如果允許）
            elif (
                close < ma_center * (1 - self.params["breakout_threshold"])
                and not self.params["long_only"]
            ):
                if self.params["require_trend"] and not self._is_downtrend(row):
                    self.cluster_active = False
                    self.cluster_center = None
                    return

                stop_loss = self._calculate_stop_loss(close, ma_center, "short")
                take_profit = self._calculate_take_profit(close, "short")

                rr = self._check_rr_ratio(close, stop_loss, take_profit, "short")
                if rr < self.params["min_rr_ratio"]:
                    self.cluster_active = False
                    self.cluster_center = None
                    return

                self._suggested_stop = stop_loss
                self.broker.short_all(close, current_time)

            # 重置 cluster 狀態
            self.cluster_active = False
            self.cluster_center = None


# === 便捷函數 ===


def run_bige_backtest(
    data: pd.DataFrame,
    initial_cash: float = 500,
    strategy_params: dict = None,
):
    """
    使用 BiGe 策略執行回測

    這是一個便捷函數。策略會自動提供 ExecutionConfig，
    引擎會根據配置自動設置所有執行邏輯。

    Args:
        data: OHLCV DataFrame（需包含 DatetimeIndex）
        initial_cash: 初始資金（預設 500）
        strategy_params: 策略參數覆蓋

    Returns:
        BacktestResult

    Example:
        >>> from strategies.bige_signal import run_bige_backtest
        >>> result = run_bige_backtest(df, initial_cash=500)
        >>> print(f"Return: {result.metrics['total_return']:.2%}")
    """
    from backtest.engine import run_backtest

    # 策略自帶 ExecutionConfig，引擎會自動讀取
    return run_backtest(
        data=data,
        strategy_cls=BiGeSignalStrategy,
        initial_cash=initial_cash,
        strategy_params=strategy_params or {},
        # ExecutionConfig 會由策略的 get_execution_config() 提供
        # 引擎會自動配置：leverage, stop_manager, add_position_manager, position_sizer
    )
