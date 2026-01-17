"""
QQE Mod 策略 v2.0 - BaseStrategy 兼容版

基於原始 qqe_mod.py，重構為符合 BaseStrategy 接口。
可以使用統一的 run_backtest 引擎執行回測。

QQE = Quantitative Qualitative Estimation
結合 RSI + ATR 的動態平滑指標

特點:
- 適合短線交易 (15m/1h)
- 動態信號確認
- 支援多種信號類型

Version: v2.0
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


class QQEModStrategyV2(BaseStrategy):
    """QQE Mod 策略 - BaseStrategy 兼容版"""

    @classmethod
    def get_default_parameters(cls):
        return {
            # QQE 參數
            "rsi_period": 6,
            "rsi_smoothing": 5,
            "qqe_factor": 3.0,
            "threshold": 3.0,
            "bb_length": 50,
            "bb_mult": 0.35,
            "qqe2_factor": 1.61,
            # 信號類型: "line", "bar", "line_and_bar"
            "signal_type": "line",
            # 止損止盈
            "stop_loss_pct": 0.02,  # 2%
            "take_profit_pct": 0.04,  # 4%
            # 方向
            "allow_short": True,
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """提供執行配置"""
        params = cls.get_default_parameters()
        return ExecutionConfig(
            stop_config=StopConfig(
                type="simple",
                fixed_stop_pct=params["stop_loss_pct"],
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=params["take_profit_pct"],
            leverage=10.0,  # 推薦 10x
            fee_rate=0.0004,
        )

    def __init__(self, broker, data, **kwargs):
        super().__init__(broker, data)

        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        self._calculate_indicators()

    def _calculate_indicators(self):
        """計算 QQE Mod 指標"""
        df = self.data
        close = df["close"]

        rsi_period = self.params["rsi_period"]
        rsi_smoothing = self.params["rsi_smoothing"]
        qqe_factor = self.params["qqe_factor"]
        threshold = self.params["threshold"]
        bb_length = self.params["bb_length"]
        bb_mult = self.params["bb_mult"]
        qqe2_factor = self.params["qqe2_factor"]

        wilders_period = rsi_period * 2 - 1

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        # RSI MA (EMA smoothing)
        rsi_ma = rsi.ewm(span=rsi_smoothing, adjust=False).mean()

        # ATR of RSI
        atr_rsi = abs(rsi_ma - rsi_ma.shift(1))
        ma_atr_rsi = atr_rsi.ewm(span=wilders_period, adjust=False).mean()
        dar = ma_atr_rsi.ewm(span=wilders_period, adjust=False).mean() * qqe_factor

        # Dynamic bands
        rs_index = rsi_ma
        longband = pd.Series(index=df.index, dtype=float)
        shortband = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)

        longband.iloc[0] = 0
        shortband.iloc[0] = 100
        trend.iloc[0] = 1

        for i in range(1, len(df)):
            new_longband = rs_index.iloc[i] - dar.iloc[i]
            new_shortband = rs_index.iloc[i] + dar.iloc[i]

            if (
                rs_index.iloc[i - 1] > longband.iloc[i - 1]
                and rs_index.iloc[i] > longband.iloc[i - 1]
            ):
                longband.iloc[i] = max(longband.iloc[i - 1], new_longband)
            else:
                longband.iloc[i] = new_longband

            if (
                rs_index.iloc[i - 1] < shortband.iloc[i - 1]
                and rs_index.iloc[i] < shortband.iloc[i - 1]
            ):
                shortband.iloc[i] = min(shortband.iloc[i - 1], new_shortband)
            else:
                shortband.iloc[i] = new_shortband

            if rs_index.iloc[i] > shortband.iloc[i - 1]:
                trend.iloc[i] = 1
            elif rs_index.iloc[i] < longband.iloc[i - 1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i - 1]

        fast_atr_rsi_tl = pd.Series(index=df.index, dtype=float)
        for i in range(len(df)):
            if trend.iloc[i] == 1:
                fast_atr_rsi_tl.iloc[i] = longband.iloc[i]
            else:
                fast_atr_rsi_tl.iloc[i] = shortband.iloc[i]

        # Bollinger Bands on QQE
        basis = (fast_atr_rsi_tl - 50).rolling(bb_length).mean()
        dev = bb_mult * (fast_atr_rsi_tl - 50).rolling(bb_length).std()
        upper_bb = basis + dev
        lower_bb = basis - dev

        # QQE 2
        wilders_period2 = rsi_period * 2 - 1
        rsi_ma2 = rsi.ewm(span=rsi_smoothing, adjust=False).mean()
        atr_rsi2 = abs(rsi_ma2 - rsi_ma2.shift(1))
        ma_atr_rsi2 = atr_rsi2.ewm(span=wilders_period2, adjust=False).mean()
        dar2 = ma_atr_rsi2.ewm(span=wilders_period2, adjust=False).mean() * qqe2_factor

        rs_index2 = rsi_ma2
        longband2 = pd.Series(index=df.index, dtype=float)
        shortband2 = pd.Series(index=df.index, dtype=float)
        trend2 = pd.Series(index=df.index, dtype=int)

        longband2.iloc[0] = 0
        shortband2.iloc[0] = 100
        trend2.iloc[0] = 1

        for i in range(1, len(df)):
            new_longband2 = rs_index2.iloc[i] - dar2.iloc[i]
            new_shortband2 = rs_index2.iloc[i] + dar2.iloc[i]

            if (
                rs_index2.iloc[i - 1] > longband2.iloc[i - 1]
                and rs_index2.iloc[i] > longband2.iloc[i - 1]
            ):
                longband2.iloc[i] = max(longband2.iloc[i - 1], new_longband2)
            else:
                longband2.iloc[i] = new_longband2

            if (
                rs_index2.iloc[i - 1] < shortband2.iloc[i - 1]
                and rs_index2.iloc[i] < shortband2.iloc[i - 1]
            ):
                shortband2.iloc[i] = min(shortband2.iloc[i - 1], new_shortband2)
            else:
                shortband2.iloc[i] = new_shortband2

            if rs_index2.iloc[i] > shortband2.iloc[i - 1]:
                trend2.iloc[i] = 1
            elif rs_index2.iloc[i] < longband2.iloc[i - 1]:
                trend2.iloc[i] = -1
            else:
                trend2.iloc[i] = trend2.iloc[i - 1]

        fast_atr_rsi2_tl = pd.Series(index=df.index, dtype=float)
        for i in range(len(df)):
            if trend2.iloc[i] == 1:
                fast_atr_rsi2_tl.iloc[i] = longband2.iloc[i]
            else:
                fast_atr_rsi2_tl.iloc[i] = shortband2.iloc[i]

        # QQE Line
        qqe_line = fast_atr_rsi2_tl - 50

        # Bar colors
        greenbar1 = (rsi_ma2 - 50) > threshold
        greenbar2 = (rsi_ma - 50) > upper_bb
        redbar1 = (rsi_ma2 - 50) < -threshold
        redbar2 = (rsi_ma - 50) < lower_bb

        # 儲存到 DataFrame
        df["qqe_rsi_ma"] = rsi_ma
        df["qqe_rsi_ma2"] = rsi_ma2
        df["qqe_line"] = qqe_line
        df["qqe_upper_bb"] = upper_bb
        df["qqe_lower_bb"] = lower_bb
        df["qqe_greenbar1"] = greenbar1
        df["qqe_greenbar2"] = greenbar2
        df["qqe_redbar1"] = redbar1
        df["qqe_redbar2"] = redbar2
        df["qqe_trend"] = trend
        df["qqe_trend2"] = trend2

        # 生成信號
        self._generate_signals()

    def _generate_signals(self):
        """生成交易信號"""
        df = self.data
        signal_type = self.params["signal_type"]

        if signal_type == "line":
            df["signal_long"] = df["qqe_line"] > 0
            df["signal_short"] = df["qqe_line"] < 0

        elif signal_type == "bar":
            df["signal_long"] = df["qqe_greenbar1"] & df["qqe_greenbar2"]
            df["signal_short"] = df["qqe_redbar1"] & df["qqe_redbar2"]

        elif signal_type == "line_and_bar":
            df["signal_long"] = (
                (df["qqe_line"] > 0)
                & df["qqe_greenbar1"]
                & df["qqe_greenbar2"]
                & ((df["qqe_rsi_ma2"] - 50) > 0)
            )
            df["signal_short"] = (
                (df["qqe_line"] < 0)
                & df["qqe_redbar1"]
                & df["qqe_redbar2"]
                & ((df["qqe_rsi_ma2"] - 50) < 0)
            )
        else:
            df["signal_long"] = False
            df["signal_short"] = False

        # 進場信號（狀態變化時）
        df["entry_long"] = df["signal_long"] & ~df["signal_long"].shift(1).fillna(False)
        df["entry_short"] = df["signal_short"] & ~df["signal_short"].shift(1).fillna(False)

    def on_bar(self, i: int, row: pd.Series):
        if i < self.params["bb_length"]:
            return

        current_time = row.name
        close = row["close"]

        # 有持倉時不進場
        if self.broker.has_position:
            return

        # 檢查進場信號
        if row.get("entry_long", False):
            self.broker.buy_all(close, current_time)
        elif row.get("entry_short", False) and self.params["allow_short"]:
            self.broker.short_all(close, current_time)


# 推薦配置
RECOMMENDED_CONFIG = {
    "timeframe": "15m",
    "rsi_period": 6,
    "rsi_smoothing": 5,
    "qqe_factor": 3.0,
    "signal_type": "line",
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.04,
    "leverage": 10,
}
