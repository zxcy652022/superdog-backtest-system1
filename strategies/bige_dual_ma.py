"""
幣哥雙均線策略 (BiGe Dual MA Strategy) v1.1

核心邏輯（來自幣哥交易系統）：
1. 六條均線：MA(20,60,120) + EMA(20,60,120)
2. 均線密集 → 均線發散 → 趨勢形成
3. 進場方式：
   - Mode A: 均線密集突破進場
   - Mode B: 首次回踩 MA20 不跌破進場
4. 止損：跌破 MA20（動態追蹤）
5. 加倉：回踩 MA20 不跌破時加倉（30%、50%、或浮盈全投）
6. 止盈方式（三種）：
   - 固定 R 值（1:3, 1:5, 1:8 等）
   - 斐波那契擴展（1.618, 2.618, 3.618）
   - 跌破/突破 MA20
7. 槓桿選項：5x, 10x, 20x, 50x
8. 倉位管理：每筆 10% 本金

特色：
- 低勝率（30-40%）+ 高盈虧比（1:3+）
- 支援多空雙向
- 本金 500 USDT，每倉 10%

API: v0.3 Legacy (需要狀態保存)
Version: v1.1 (加入 OPTIMIZABLE_PARAMS)
Author: DDragon (based on 幣哥交易系統)
"""

from typing import Literal, Optional

import numpy as np
import pandas as pd

from backtest.engine import BaseStrategy
from strategies.base import (
    OptimizableStrategyMixin,
    ParamCategory,
    bool_param,
    choice_param,
    float_param,
    int_param,
)


class BiGeDualMAStrategy(BaseStrategy, OptimizableStrategyMixin):
    """
    幣哥雙均線策略

    進場：均線密集突破或首次回踩 MA20 不跌破
    止損：跌破 MA20
    加倉：回踩 MA20 不跌破（30%、50%、或浮盈）
    止盈：固定 R、斐波那契、或跌破 MA20
    """

    # ===== 可優化參數定義 =====

    OPTIMIZABLE_PARAMS = {
        # === 信號參數 - 影響進場判斷 ===
        "cluster_threshold": float_param(
            default=0.015,
            description="均線密集判定閾值",
            range_min=0.005,
            range_max=0.030,
            step=0.005,
            category=ParamCategory.SIGNAL,
        ),
        "cluster_lookback": int_param(
            default=5,
            description="連續密集 K 線數",
            range_min=3,
            range_max=10,
            step=1,
            category=ParamCategory.SIGNAL,
        ),
        "ma_len_short": int_param(
            default=20,
            description="短期均線週期",
            range_min=10,
            range_max=30,
            step=5,
            category=ParamCategory.SIGNAL,
        ),
        "ma_len_mid": int_param(
            default=60,
            description="中期均線週期",
            range_min=40,
            range_max=80,
            step=10,
            category=ParamCategory.SIGNAL,
        ),
        "ma_len_long": int_param(
            default=120,
            description="長期均線週期",
            range_min=100,
            range_max=200,
            step=20,
            category=ParamCategory.SIGNAL,
        ),
        "pullback_tolerance": float_param(
            default=0.015,
            description="回踩容許範圍",
            range_min=0.010,
            range_max=0.025,
            step=0.005,
            category=ParamCategory.SIGNAL,
        ),
        "require_trend_alignment": bool_param(
            default=True,
            description="要求均線排列",
            category=ParamCategory.SIGNAL,
        ),
        "trend_mode": choice_param(
            default="strict",
            choices=["strict", "loose", "none"],
            description="趨勢判斷模式：strict=完整排列, loose=MA20>MA60, none=不判斷",
            category=ParamCategory.SIGNAL,
        ),
        # === 執行參數 - 影響倉位和出場 ===
        "position_size_pct": float_param(
            default=0.10,
            description="每筆倉位佔比",
            range_min=0.05,
            range_max=0.20,
            step=0.05,
            category=ParamCategory.EXECUTION,
        ),
        "add_position_mode": choice_param(
            default="fixed_50",
            choices=["fixed_30", "fixed_50", "floating_pnl"],
            description="加倉模式",
            category=ParamCategory.EXECUTION,
        ),
        "take_profit_mode": choice_param(
            default="fixed_r",
            choices=["fixed_r", "fibonacci", "ma20_break"],
            description="止盈模式",
            category=ParamCategory.EXECUTION,
        ),
        "stop_loss_mode": choice_param(
            default="ma20",
            choices=["ma20", "fixed_pct", "atr"],
            description="止損模式：ma20=均線止損, fixed_pct=固定百分比, atr=ATR倍數",
            category=ParamCategory.EXECUTION,
        ),
        "atr_stop_multiplier": float_param(
            default=2.0,
            description="ATR 止損倍數",
            range_min=1.0,
            range_max=4.0,
            step=0.5,
            category=ParamCategory.EXECUTION,
        ),
        "stop_loss_confirm_bars": int_param(
            default=10,
            description="止損確認根數：連續 N 根跌破才止損（4H×10=40小時）",
            range_min=5,
            range_max=15,
            step=1,
            category=ParamCategory.EXECUTION,
        ),
        "emergency_stop_atr": float_param(
            default=3.5,
            description="緊急止損 ATR 倍數：單根跌破超過 N 倍 ATR 直接止損（0=禁用）",
            range_min=0.0,
            range_max=5.0,
            step=0.5,
            category=ParamCategory.EXECUTION,
        ),
        "tp1_rr": float_param(
            default=3.0,
            description="TP1 風險回報比",
            range_min=2.0,
            range_max=5.0,
            step=0.5,
            category=ParamCategory.EXECUTION,
        ),
        "tp2_rr": float_param(
            default=5.0,
            description="TP2 風險回報比",
            range_min=4.0,
            range_max=8.0,
            step=1.0,
            category=ParamCategory.EXECUTION,
        ),
        "tp3_rr": float_param(
            default=8.0,
            description="TP3 風險回報比",
            range_min=6.0,
            range_max=12.0,
            step=1.0,
            category=ParamCategory.EXECUTION,
        ),
        "enable_add_position": bool_param(
            default=True,
            description="啟用加倉",
            category=ParamCategory.EXECUTION,
        ),
        "max_add_count": int_param(
            default=5,
            description="最大加倉次數",
            range_min=1,
            range_max=100,
            step=1,
            category=ParamCategory.EXECUTION,
        ),
        # === 動態槓桿（浮雲滾倉模式）===
        "dynamic_leverage": bool_param(
            default=False,
            description="啟用動態槓桿（高槓桿開倉→隨盈利降槓桿）",
            category=ParamCategory.EXECUTION,
        ),
        "initial_leverage": int_param(
            default=50,
            description="初始槓桿倍數（動態槓桿模式）",
            range_min=10,
            range_max=100,
            step=5,
            category=ParamCategory.EXECUTION,
        ),
        "min_leverage": int_param(
            default=5,
            description="最低槓桿倍數（動態槓桿模式）",
            range_min=1,
            range_max=20,
            step=1,
            category=ParamCategory.EXECUTION,
        ),
        # === 風控參數 - 最大回撤保護 ===
        "max_drawdown_pct": float_param(
            default=0.30,
            description="最大允許回撤比例（0.30 = 30%）",
            range_min=0.10,
            range_max=0.50,
            step=0.05,
            category=ParamCategory.EXECUTION,
        ),
        "drawdown_recovery_pct": float_param(
            default=0.50,
            description="回撤恢復比例（從最大回撤恢復 50% 後重新開放交易）",
            range_min=0.30,
            range_max=0.80,
            step=0.10,
            category=ParamCategory.EXECUTION,
        ),
        "drawdown_position_scale": float_param(
            default=0.50,
            description="回撤後倉位縮減比例（0.50 = 倉位減半）",
            range_min=0.25,
            range_max=1.0,
            step=0.25,
            category=ParamCategory.EXECUTION,
        ),
    }

    # ===== 類別方法：參數定義 =====

    @classmethod
    def get_default_parameters(cls):
        """策略參數定義"""
        return {
            # === 均線參數 ===
            "ma_len_short": 20,
            "ma_len_mid": 60,
            "ma_len_long": 120,
            # === 密集檢測 ===
            "cluster_threshold": 0.012,  # 1.2% 判定為密集（優化後）
            "cluster_lookback": 5,  # 連續 N 根 K 線密集才算數
            # === 倉位管理 ===
            "position_size_pct": 0.10,  # 每筆倉位 10%
            "leverage": 7,  # 7x 槓桿（平衡收益與回撤）
            # === 止損 ===
            "stop_loss_mode": "ma20",  # "ma20", "fixed_pct", "atr"
            "fixed_stop_loss_pct": 0.03,  # 固定止損 3%
            "ma20_buffer": 0.020,  # MA20 緩衝 2.0%（避免假突破掃損）
            "atr_stop_multiplier": 2.0,  # ATR 止損倍數
            "stop_loss_confirm_bars": 10,  # 連續 10 根跌破 MA20 才止損（約 40 小時確認，過濾假跌破）
            "emergency_stop_atr": 3.5,  # 緊急止損：單根跌破超過 3.5 倍 ATR 直接止損（防黑天鵝）
            # === 止盈模式 ===
            # "fixed_r": 固定 R 值
            # "fibonacci": 斐波那契擴展
            # "ma20_break": 跌破/突破 MA20
            "take_profit_mode": "fixed_r",
            # === 固定 R 止盈 ===
            "tp1_rr": 3.0,  # TP1: 3R
            "tp2_rr": 5.0,  # TP2: 5R
            "tp3_rr": 8.0,  # TP3: 8R
            "tp1_pct": 0.30,  # TP1 平倉 30%
            "tp2_pct": 0.30,  # TP2 平倉 30%
            # TP3 平掉剩餘
            # === 斐波那契止盈 ===
            "fib_tp1": 1.618,
            "fib_tp2": 2.618,
            "fib_tp3": 3.618,
            # === 加倉參數 ===
            "enable_add_position": True,  # 啟用加倉（趨勢跟隨核心功能）
            # "fixed_30": 固定 30%
            # "fixed_50": 固定 50%
            # "floating_pnl": 浮盈全投
            "add_position_mode": "fixed_50",  # 每次加倉 50%（平衡風險與收益）
            "add_position_fixed_pct": 0.50,  # 固定模式比例
            "add_position_pnl_pct": 1.0,  # 浮盈模式：100% 浮盈
            "add_position_min_interval": 3,  # 最少間隔 3 根 K 線
            "max_add_count": 3,  # 最多加倉 3 次（控制回撤）
            # === 回踩確認 ===
            "pullback_tolerance": 0.018,  # 1.8% 範圍內算回踩（優化後）
            # === 趨勢過濾 ===
            "require_trend_alignment": True,  # 要求均線排列
            "trend_mode": "loose",  # loose=MA20>MA60（更靈活，熊市表現更好）, strict=完整排列, none=不判斷
            # === 動態槓桿（浮雲滾倉模式）===
            "dynamic_leverage": False,  # 預設關閉（匹配昨天配置）
            "initial_leverage": 50,  # 初始高槓桿
            "min_leverage": 5,  # 最低槓桿
            # === 做空突破進場（崩盤模式）===
            "enable_breakout_short": False,  # 關閉 Mode C（測試顯示牛市損失 > 熊市收益）
            "breakout_distance": 0.08,  # 價格遠離 MA20 8% 以上觸發（僅極端崩盤）
            # === 風控：最大回撤保護（預設禁用）===
            "max_drawdown_pct": 1.0,  # 1.0 = 禁用（100% 回撤才觸發）
            "drawdown_recovery_pct": 0.50,  # 回撤恢復 50% 後重新開放交易
            "drawdown_position_scale": 1.0,  # 1.0 = 不縮減倉位
        }

    # ===== 實例方法：初始化 =====

    def __init__(self, broker, data, **kwargs):
        """
        初始化策略

        Args:
            broker: SimulatedBroker 實例
            data: pd.DataFrame OHLCV 數據
            **kwargs: 可選策略參數
        """
        super().__init__(broker, data)

        # 載入默認參數並允許覆蓋
        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        # 設置 broker 槓桿
        self.broker.leverage = self.params["leverage"]

        # Cluster 狀態
        self.cluster_active = False
        self.cluster_high = None
        self.cluster_low = None
        self.cluster_start_bar = None
        self.cluster_consecutive_count = 0

        # 倉位狀態
        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.tp1 = None
        self.tp2 = None
        self.tp3 = None
        self.tp1_hit = False
        self.tp2_hit = False
        self.initial_qty = 0.0
        self.total_qty = 0.0
        self.entry_bar = -999
        self.trade_direction = None  # "long" or "short"

        # 加倉狀態
        self.add_count = 0
        self.last_add_bar = -999

        # 止損確認狀態
        self.below_stop_count = 0  # 連續跌破止損位的根數

        # 動態槓桿狀態（浮雲滾倉模式）
        self.current_leverage = self.params["leverage"]  # 當前槓桿
        self.entry_equity = None  # 進場時的權益（用於計算盈利倍數）

        # 風控：最大回撤保護狀態
        self.peak_equity = self.broker.initial_cash  # 權益最高點
        self.drawdown_triggered = False  # 是否觸發回撤保護
        self.drawdown_trigger_equity = None  # 觸發回撤保護時的權益
        self.position_scale = 1.0  # 當前倉位縮放比例（1.0 = 正常）

        # 預計算指標
        self._calculate_all_indicators()

    def set_parameters(self, **kwargs):
        """設置策略參數"""
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
        self.broker.leverage = self.params["leverage"]
        self._calculate_all_indicators()

    # ===== 核心邏輯：指標計算 =====

    def _calculate_all_indicators(self):
        """預先計算所有技術指標 - 6 條均線"""
        p = self.params
        df = self.data

        # 計算 3 條 SMA
        df["ma20"] = df["close"].rolling(p["ma_len_short"]).mean()
        df["ma60"] = df["close"].rolling(p["ma_len_mid"]).mean()
        df["ma120"] = df["close"].rolling(p["ma_len_long"]).mean()

        # 計算 3 條 EMA
        df["ema20"] = df["close"].ewm(span=p["ma_len_short"], adjust=False).mean()
        df["ema60"] = df["close"].ewm(span=p["ma_len_mid"], adjust=False).mean()
        df["ema120"] = df["close"].ewm(span=p["ma_len_long"], adjust=False).mean()

        # 平均 MA（用於趨勢判斷）
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2
        df["avg120"] = (df["ma120"] + df["ema120"]) / 2

        # ATR（用於斐波那契計算）
        df["atr"] = self._calculate_atr(df, 14)

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

    # ===== 核心邏輯：均線密集檢測 =====

    def _get_all_ma_values(self, row) -> list:
        """獲取 6 條均線的值"""
        return [row["ma20"], row["ma60"], row["ma120"], row["ema20"], row["ema60"], row["ema120"]]

    def _detect_cluster(self, row) -> bool:
        """
        檢測均線密集

        所有 6 條均線在 cluster_threshold 範圍內
        """
        p = self.params
        ma_values = self._get_all_ma_values(row)

        if any(pd.isna(v) for v in ma_values):
            return False

        max_ma = max(ma_values)
        min_ma = min(ma_values)

        if min_ma == 0:
            return False

        spread = (max_ma - min_ma) / min_ma
        return spread < p["cluster_threshold"]

    def _is_uptrend(self, row) -> bool:
        """判斷多頭排列：短均線 > 中均線 > 長均線"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]) or pd.isna(row["avg120"]):
            return False
        return row["avg20"] > row["avg60"] > row["avg120"]

    def _is_downtrend(self, row) -> bool:
        """判斷空頭排列：短均線 < 中均線 < 長均線"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]) or pd.isna(row["avg120"]):
            return False
        return row["avg20"] < row["avg60"] < row["avg120"]

    def _is_loose_uptrend(self, row) -> bool:
        """寬鬆多頭判斷：MA20 > MA60（不要求完整排列，更早進場）"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] > row["avg60"]

    def _is_loose_downtrend(self, row) -> bool:
        """寬鬆空頭判斷：MA20 < MA60（不要求完整排列，更早進場）"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] < row["avg60"]

    # ===== 核心邏輯：進場 =====

    def _check_trend_for_long(self, row) -> bool:
        """檢查多頭趨勢條件"""
        p = self.params
        trend_mode = p.get("trend_mode", "strict")

        if trend_mode == "none":
            return True
        elif trend_mode == "loose":
            return self._is_loose_uptrend(row)
        else:  # strict
            return self._is_uptrend(row)

    def _check_trend_for_short(self, row) -> bool:
        """檢查空頭趨勢條件"""
        p = self.params
        trend_mode = p.get("trend_mode", "strict")

        if trend_mode == "none":
            return True
        elif trend_mode == "loose":
            return self._is_loose_downtrend(row)
        else:  # strict
            return self._is_downtrend(row)

    def _check_long_entry(self, row, i) -> bool:
        """
        多單進場條件

        Mode A: 均線密集突破 + 回踩 MA20 確認
        Mode B: 首次回踩 MA20 不跌破（趨勢已確立）
        """
        p = self.params
        close = row["close"]
        low = row["low"]
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return False

        # 檢查趨勢條件（根據 trend_mode）
        if p["require_trend_alignment"] and not self._check_trend_for_long(row):
            return False

        # Mode A: 均線密集後突破
        if self.cluster_low is not None and self.cluster_high is not None:
            # 價格突破 cluster_high 並回踩 MA20
            price_above_cluster = close > self.cluster_high
            near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            above_cluster_low = low > self.cluster_low
            bullish_close = close > avg20

            if price_above_cluster and near_ma20 and above_cluster_low and bullish_close:
                return True

        # Mode B: 趨勢中首次回踩 MA20
        if self._check_trend_for_long(row):
            near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            not_break_ma20 = low > avg20 * (1 - p["ma20_buffer"])
            bullish_close = close > avg20

            if near_ma20 and not_break_ma20 and bullish_close:
                return True

        return False

    def _check_short_entry(self, row, i) -> bool:
        """
        空單進場條件

        Mode A: 均線密集後跌破 + 反彈 MA20 確認
        Mode B: 首次反彈 MA20 不突破（趨勢已確立）
        Mode C: 趨勢突破進場（崩盤時不等回踩，直接進場）
        """
        p = self.params
        close = row["close"]
        high = row["high"]
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return False

        # 檢查趨勢條件（根據 trend_mode）
        if p["require_trend_alignment"] and not self._check_trend_for_short(row):
            return False

        # Mode A: 均線密集後跌破
        if self.cluster_low is not None and self.cluster_high is not None:
            price_below_cluster = close < self.cluster_low
            near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            below_cluster_high = high < self.cluster_high
            bearish_close = close < avg20

            if price_below_cluster and near_ma20 and below_cluster_high and bearish_close:
                return True

        # Mode B: 趨勢中首次反彈 MA20
        if self._check_trend_for_short(row):
            near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            not_break_ma20 = high < avg20 * (1 + p["ma20_buffer"])
            bearish_close = close < avg20

            if near_ma20 and not_break_ma20 and bearish_close:
                return True

        # Mode C: 趨勢突破進場（崩盤模式）
        # 僅在極端下跌時觸發，避免誤觸發影響牛市表現
        # 條件：完整空頭排列 + 價格遠離 MA20 超過 8% + 強烈下跌動能
        if p.get("enable_breakout_short", True):
            # 必須是完整的空頭排列（MA20 < MA60 < MA120）
            avg60 = row.get("avg60")
            avg120 = row.get("avg120")
            full_downtrend = pd.notna(avg60) and pd.notna(avg120) and avg20 < avg60 < avg120

            if full_downtrend:
                # 價格遠離 MA20 超過 8%（真正的崩盤）
                distance_from_ma20 = (avg20 - close) / avg20
                far_from_ma20 = distance_from_ma20 > p.get("breakout_distance", 0.08)

                # 確認下跌動能：收盤價在當根 K 線下半部
                strong_bearish = (close - row["low"]) / (row["high"] - row["low"] + 0.0001) < 0.3

                if far_from_ma20 and strong_bearish:
                    return True

        return False

    # ===== 核心邏輯：止損計算 =====

    def _calculate_stop_loss(self, row, direction: str) -> float:
        """
        計算止損位置

        根據 stop_loss_mode:
        - "ma20": 跌破/突破 MA20（幣哥核心邏輯）
        - "fixed_pct": 固定百分比止損
        - "atr": ATR 倍數止損（更緊密的止損）
        """
        p = self.params
        close = row["close"]
        avg20 = row["avg20"]

        if p["stop_loss_mode"] == "ma20":
            if direction == "long":
                return avg20 * (1 - p["ma20_buffer"])
            else:  # short
                return avg20 * (1 + p["ma20_buffer"])
        elif p["stop_loss_mode"] == "atr":
            # ATR 止損：入場價 ± ATR * 倍數
            atr = row["atr"]
            multiplier = p["atr_stop_multiplier"]
            if pd.isna(atr) or atr <= 0:
                # 回退到固定百分比
                if direction == "long":
                    return close * (1 - p["fixed_stop_loss_pct"])
                else:
                    return close * (1 + p["fixed_stop_loss_pct"])
            if direction == "long":
                return close - atr * multiplier
            else:  # short
                return close + atr * multiplier
        else:  # fixed_pct
            if direction == "long":
                return close * (1 - p["fixed_stop_loss_pct"])
            else:
                return close * (1 + p["fixed_stop_loss_pct"])

    # ===== 核心邏輯：止盈計算 =====

    def _calculate_take_profits(
        self, entry_price: float, stop_loss: float, direction: str, row
    ) -> tuple:
        """
        計算三個止盈位

        根據 take_profit_mode:
        - "fixed_r": 固定 R 值止盈
        - "fibonacci": 斐波那契擴展止盈
        - "ma20_break": 跌破/突破 MA20 止盈（動態）
        """
        p = self.params
        mode = p["take_profit_mode"]
        R = abs(entry_price - stop_loss)

        if mode == "fixed_r":
            if direction == "long":
                tp1 = entry_price + p["tp1_rr"] * R
                tp2 = entry_price + p["tp2_rr"] * R
                tp3 = entry_price + p["tp3_rr"] * R
            else:
                tp1 = entry_price - p["tp1_rr"] * R
                tp2 = entry_price - p["tp2_rr"] * R
                tp3 = entry_price - p["tp3_rr"] * R

        elif mode == "fibonacci":
            # 使用 ATR 作為波動基準
            atr = row["atr"] if not pd.isna(row["atr"]) else R
            if direction == "long":
                tp1 = entry_price + atr * p["fib_tp1"]
                tp2 = entry_price + atr * p["fib_tp2"]
                tp3 = entry_price + atr * p["fib_tp3"]
            else:
                tp1 = entry_price - atr * p["fib_tp1"]
                tp2 = entry_price - atr * p["fib_tp2"]
                tp3 = entry_price - atr * p["fib_tp3"]

        else:  # ma20_break - 動態止盈，這裡設置為極大值
            if direction == "long":
                tp1 = entry_price * 2  # 暫時設為 100% 漲幅
                tp2 = entry_price * 3
                tp3 = entry_price * 5
            else:
                tp1 = entry_price * 0.5
                tp2 = entry_price * 0.33
                tp3 = entry_price * 0.2

        return tp1, tp2, tp3

    # ===== 核心邏輯：倉位計算 =====

    def _calculate_position_size(self, entry_price: float) -> float:
        """
        計算倉位大小 - 固定比例法 + 槓桿 + 回撤縮放

        實際倉位 = 本金 * position_size_pct * leverage * position_scale / entry_price

        position_scale：回撤保護觸發後的倉位縮放比例
        """
        p = self.params
        equity = self.broker.get_current_equity(entry_price)
        # 每筆交易使用 10% 本金作為保證金
        margin = equity * p["position_size_pct"]
        # 槓桿放大倉位價值（使用當前槓桿，支持動態槓桿）
        leverage = self.current_leverage if hasattr(self, "current_leverage") else p["leverage"]
        # 回撤保護：應用倉位縮放比例
        scale = self._get_position_scale() if hasattr(self, "position_scale") else 1.0
        position_value = margin * leverage * scale
        qty = position_value / entry_price
        return qty

    # ===== 核心邏輯：加倉 =====

    def _check_add_position(self, row, i: int) -> bool:
        """
        檢查是否應該加倉

        條件：
        1. 啟用加倉
        2. 有持倉
        3. 距離上次加倉超過最小間隔
        4. 未達最大加倉次數
        5. 回踩 MA20 未跌破止損
        """
        p = self.params

        if not p["enable_add_position"]:
            return False

        if not self.broker.has_position:
            return False

        if self.add_count >= p["max_add_count"]:
            return False

        bars_since_last = i - max(self.entry_bar, self.last_add_bar)
        if bars_since_last < p["add_position_min_interval"]:
            return False

        close = row["close"]
        low = row["low"]
        high = row["high"]
        avg20 = row["avg20"]

        if self.broker.is_long:
            near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            above_stop = low > self.stop_loss
            bullish_close = close > avg20
            return near_ma20 and above_stop and bullish_close

        elif self.broker.is_short:
            near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            below_stop = high < self.stop_loss
            bearish_close = close < avg20
            return near_ma20 and below_stop and bearish_close

        return False

    def _calculate_add_position_qty(self, current_price: float) -> float:
        """
        計算加倉數量

        - fixed_30: 初始倉位的 30%
        - fixed_50: 初始倉位的 50%
        - floating_pnl: 浮盈的 100%
        """
        p = self.params
        mode = p["add_position_mode"]

        if mode == "fixed_30":
            return self.initial_qty * 0.30
        elif mode == "fixed_50":
            return self.initial_qty * 0.50
        elif mode == "floating_pnl":
            if self.avg_entry_price is None:
                return 0

            if self.broker.is_long:
                unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
            else:
                unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

            if unrealized_pnl <= 0:
                return 0

            add_amount = unrealized_pnl * p["add_position_pnl_pct"]
            return add_amount / current_price
        else:
            return self.initial_qty * p["add_position_fixed_pct"]

    def _update_avg_entry_price(self, new_qty: float, new_price: float):
        """更新平均入場價"""
        if self.avg_entry_price is None or self.total_qty == 0:
            self.avg_entry_price = new_price
            self.total_qty = new_qty
        else:
            total_cost = self.avg_entry_price * self.total_qty + new_price * new_qty
            self.total_qty += new_qty
            self.avg_entry_price = total_cost / self.total_qty

    # ===== 核心邏輯：動態槓桿（浮雲滾倉模式）=====

    def _get_dynamic_leverage(self, current_price: float) -> int:
        """
        計算動態槓桿

        浮雲滾倉邏輯：
        - 本金翻倍 → 槓桿減半
        - 50x → 30x → 20x → 15x → 10x → 5x

        槓桿階梯（根據盈利倍數）：
        - 0-100%: 初始槓桿 (50x)
        - 100-200%: 30x
        - 200-400%: 20x
        - 400-800%: 15x
        - 800-1600%: 10x
        - 1600%+: 最低槓桿 (5x)
        """
        p = self.params

        if not p.get("dynamic_leverage", False):
            return p["leverage"]

        if self.entry_equity is None or self.entry_equity <= 0:
            return p.get("initial_leverage", 50)

        current_equity = self.broker.get_current_equity(current_price)
        profit_multiple = (current_equity / self.entry_equity) - 1  # 盈利倍數

        initial_lev = p.get("initial_leverage", 50)
        min_lev = p.get("min_leverage", 5)

        # 槓桿階梯
        if profit_multiple < 1.0:  # < 100% 盈利
            return initial_lev
        elif profit_multiple < 2.0:  # 100-200%
            return max(30, min_lev)
        elif profit_multiple < 4.0:  # 200-400%
            return max(20, min_lev)
        elif profit_multiple < 8.0:  # 400-800%
            return max(15, min_lev)
        elif profit_multiple < 16.0:  # 800-1600%
            return max(10, min_lev)
        else:  # 1600%+
            return min_lev

    def _update_leverage_if_needed(self, current_price: float):
        """
        檢查並更新槓桿（如果啟用動態槓桿）

        當槓桿需要降低時，更新 broker 的槓桿設置
        """
        p = self.params

        if not p.get("dynamic_leverage", False):
            return

        if not self.broker.has_position:
            return

        new_leverage = self._get_dynamic_leverage(current_price)

        if new_leverage != self.current_leverage:
            self.current_leverage = new_leverage
            self.broker.leverage = new_leverage

    # ===== 核心邏輯：回撤保護 =====

    def _update_drawdown_protection(self, current_price: float) -> bool:
        """
        更新回撤保護狀態

        機制說明：
        1. 追蹤權益最高點（peak_equity）
        2. 當回撤超過 max_drawdown_pct 時，觸發保護
        3. 觸發後：
           - 如果有倉位，強制平倉
           - 後續交易倉位縮減（position_scale）
        4. 當權益從觸發點恢復 drawdown_recovery_pct 後，解除保護

        Returns:
            bool: True 表示當前禁止開新倉（在回撤保護中）
        """
        p = self.params
        current_equity = self.broker.get_current_equity(current_price)

        # 更新權益最高點
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # 計算當前回撤
        current_drawdown = (self.peak_equity - current_equity) / self.peak_equity

        # 檢查是否觸發回撤保護
        if not self.drawdown_triggered:
            if current_drawdown >= p["max_drawdown_pct"]:
                self.drawdown_triggered = True
                self.drawdown_trigger_equity = current_equity
                self.position_scale = p["drawdown_position_scale"]
                return True  # 需要強制平倉
        else:
            # 已在回撤保護中，檢查是否恢復
            if self.drawdown_trigger_equity is not None:
                recovery_target = self.drawdown_trigger_equity * (1 + p["drawdown_recovery_pct"])
                if current_equity >= recovery_target:
                    # 恢復，但不完全重置倉位比例（逐步恢復）
                    self.drawdown_triggered = False
                    self.drawdown_trigger_equity = None
                    # 倉位比例逐步恢復：每次恢復增加 25%
                    self.position_scale = min(1.0, self.position_scale + 0.25)

        return False

    def _get_position_scale(self) -> float:
        """取得當前倉位縮放比例"""
        return self.position_scale

    # ===== 核心邏輯：動態止損更新 =====

    def _update_trailing_stop(self, row):
        """
        更新追蹤止損

        MA20 模式：止損跟隨 MA20 移動
        ATR 模式：止損跟隨價格移動（保持 N 倍 ATR 距離）
        fixed_pct 模式：不追蹤（固定止損）
        """
        p = self.params
        mode = p["stop_loss_mode"]

        if mode == "fixed_pct":
            # 固定百分比不追蹤
            return

        if mode == "ma20":
            # MA20 追蹤止損（幣哥核心邏輯）
            avg20 = row["avg20"]
            if pd.isna(avg20) or self.stop_loss is None:
                return

            if self.broker.is_long:
                new_stop = avg20 * (1 - p["ma20_buffer"])
                if new_stop > self.stop_loss:
                    self.stop_loss = new_stop
            elif self.broker.is_short:
                new_stop = avg20 * (1 + p["ma20_buffer"])
                if new_stop < self.stop_loss:
                    self.stop_loss = new_stop

        elif mode == "atr":
            # ATR 追蹤止損：跟隨價格移動，保持 N 倍 ATR 距離
            atr = row["atr"]
            close = row["close"]
            multiplier = p["atr_stop_multiplier"]

            if pd.isna(atr) or atr <= 0 or self.stop_loss is None:
                return

            if self.broker.is_long:
                # 多單：止損 = 當前價 - ATR * 倍數，只能上移
                new_stop = close - atr * multiplier
                if new_stop > self.stop_loss:
                    self.stop_loss = new_stop
            elif self.broker.is_short:
                # 空單：止損 = 當前價 + ATR * 倍數，只能下移
                new_stop = close + atr * multiplier
                if new_stop < self.stop_loss:
                    self.stop_loss = new_stop

    # ===== 核心邏輯：緊急止損檢查 =====

    def _check_emergency_stop(self, row) -> bool:
        """
        檢查是否觸發緊急止損

        條件：單根 K 線跌破/突破 MA20 的幅度超過 N 倍 ATR
        用途：防止黑天鵝事件（如 2020/3/12、LUNA 崩盤）造成巨大虧損

        Returns:
            bool: True 表示觸發緊急止損
        """
        p = self.params
        emergency_atr = p.get("emergency_stop_atr", 0)

        if emergency_atr <= 0:
            return False

        atr = row["atr"]
        avg20 = row["avg20"]

        if pd.isna(atr) or pd.isna(avg20) or atr <= 0:
            return False

        if self.broker.is_long:
            # 多單：檢查最低價跌破 MA20 的幅度
            low = row["low"]
            breach = avg20 - low  # 跌破幅度（正值表示跌破）
            if breach > 0 and breach > emergency_atr * atr:
                return True

        elif self.broker.is_short:
            # 空單：檢查最高價突破 MA20 的幅度
            high = row["high"]
            breach = high - avg20  # 突破幅度（正值表示突破）
            if breach > 0 and breach > emergency_atr * atr:
                return True

        return False

    # ===== 核心邏輯：主循環 =====

    def on_bar(self, i: int, row: pd.Series):
        """每根 K 線調用一次"""
        if i < self.params["ma_len_long"]:
            return

        current_time = row.name
        current_price = row["close"]

        # === 0. 回撤保護檢查 ===
        force_close = self._update_drawdown_protection(current_price)

        # 如果觸發回撤保護且有倉位，強制平倉
        if force_close and self.broker.has_position:
            if self.broker.is_long:
                self.broker.sell(self.broker.position_qty, current_price, current_time)
            else:
                self.broker.buy(self.broker.position_qty, current_price, current_time)
            self._reset_position_state()
            return

        # === 1. 更新 Cluster 狀態 ===
        is_cluster = self._detect_cluster(row)

        if is_cluster:
            self.cluster_consecutive_count += 1
            ma_values = self._get_all_ma_values(row)

            if self.cluster_consecutive_count >= self.params["cluster_lookback"]:
                if not self.cluster_active:
                    self.cluster_active = True
                    self.cluster_high = max(ma_values)
                    self.cluster_low = min(ma_values)
                    self.cluster_start_bar = i
                else:
                    # 確保 cluster_high/low 不為 None
                    if self.cluster_high is None:
                        self.cluster_high = max(ma_values)
                    else:
                        self.cluster_high = max(self.cluster_high, max(ma_values))
                    if self.cluster_low is None:
                        self.cluster_low = min(ma_values)
                    else:
                        self.cluster_low = min(self.cluster_low, min(ma_values))
        else:
            self.cluster_consecutive_count = 0
            if self.cluster_active:
                self.cluster_active = False
                # 保留 cluster_high/low 供進場判斷

        # === 2. 倉位管理 ===
        if self.broker.has_position:
            # === 2.1 爆倉檢測（v1.2 新增）===
            if self.broker.check_liquidation_in_bar(row):
                liq_price = self.broker.get_liquidation_price()
                self.broker.process_liquidation(current_time, liq_price)
                self._reset_position_state()
                return

            # 動態槓桿更新
            self._update_leverage_if_needed(row["close"])
            self._manage_position(row, current_time, i)
            return

        # === 3. 進場信號檢測（回撤保護期間仍可交易，但倉位縮減）===
        if self._check_long_entry(row, i):
            self._enter_long(row, current_time, i)
        elif self._check_short_entry(row, i):
            self._enter_short(row, current_time, i)

    def _enter_long(self, row, current_time, bar_index: int):
        """執行多單進場"""
        p = self.params
        entry_price = row["close"]
        stop_loss = self._calculate_stop_loss(row, "long")

        # 動態槓桿：開倉時使用初始高槓桿
        if p.get("dynamic_leverage", False):
            self.current_leverage = p.get("initial_leverage", 50)
            self.broker.leverage = self.current_leverage
            self.entry_equity = self.broker.get_current_equity(entry_price)

        qty = self._calculate_position_size(entry_price)

        if qty > 0:
            success = self.broker.buy(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = stop_loss
                self.tp1, self.tp2, self.tp3 = self._calculate_take_profits(
                    entry_price, stop_loss, "long", row
                )
                self.tp1_hit = False
                self.tp2_hit = False
                self.initial_qty = qty
                self.total_qty = qty
                self.add_count = 0
                self.entry_bar = bar_index
                self.last_add_bar = bar_index
                self.trade_direction = "long"
                # 重置 cluster
                self.cluster_high = None
                self.cluster_low = None

    def _enter_short(self, row, current_time, bar_index: int):
        """執行空單進場"""
        p = self.params
        entry_price = row["close"]
        stop_loss = self._calculate_stop_loss(row, "short")

        # 動態槓桿：開倉時使用初始高槓桿
        if p.get("dynamic_leverage", False):
            self.current_leverage = p.get("initial_leverage", 50)
            self.broker.leverage = self.current_leverage
            self.entry_equity = self.broker.get_current_equity(entry_price)

        qty = self._calculate_position_size(entry_price)

        if qty > 0:
            success = self.broker.sell(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = stop_loss
                self.tp1, self.tp2, self.tp3 = self._calculate_take_profits(
                    entry_price, stop_loss, "short", row
                )
                self.tp1_hit = False
                self.tp2_hit = False
                self.initial_qty = qty
                self.total_qty = qty
                self.add_count = 0
                self.entry_bar = bar_index
                self.last_add_bar = bar_index
                self.trade_direction = "short"
                self.cluster_high = None
                self.cluster_low = None

    def _manage_position(self, row, current_time, bar_index: int):
        """管理現有倉位"""
        p = self.params
        current_price = row["close"]
        high = row["high"]
        low = row["low"]
        avg20 = row["avg20"]

        # 更新追蹤止損
        self._update_trailing_stop(row)

        if self.broker.is_long:
            self._manage_long_position(
                row, current_time, bar_index, current_price, high, low, avg20
            )
        elif self.broker.is_short:
            self._manage_short_position(
                row, current_time, bar_index, current_price, high, low, avg20
            )

    def _manage_long_position(
        self,
        row,
        current_time,
        bar_index: int,
        current_price: float,
        high: float,
        low: float,
        avg20: float,
    ):
        """管理多單"""
        p = self.params
        confirm_bars = p.get("stop_loss_confirm_bars", 1)

        # 確保 stop_loss 有效
        if self.stop_loss is None:
            return

        # === 緊急止損檢查（優先於正常止損）===
        if self._check_emergency_stop(row):
            self.broker.sell(self.broker.position_qty, self.stop_loss, current_time)
            self._reset_position_state()
            return

        # 止損檢查：需要連續 N 根跌破才止損
        if low <= self.stop_loss:
            self.below_stop_count += 1
            if self.below_stop_count >= confirm_bars:
                # 確認跌破，執行止損
                self.broker.sell(self.broker.position_qty, self.stop_loss, current_time)
                self._reset_position_state()
                return
            # 還沒確認，繼續觀察（可能是假跌破）
        else:
            # 價格回到止損位上方，重置計數
            self.below_stop_count = 0

        # MA20 跌破止損（take_profit_mode == "ma20_break"）
        if p["take_profit_mode"] == "ma20_break":
            if current_price < avg20 * (1 - p["ma20_buffer"]):
                self.broker.sell(self.broker.position_qty, current_price, current_time)
                self._reset_position_state()
                return

        # 加倉檢查
        if self._check_add_position(row, bar_index):
            add_qty = self._calculate_add_position_qty(current_price)
            if add_qty > 0:
                success = self.broker.buy(add_qty, current_price, current_time)
                if success:
                    self._update_avg_entry_price(add_qty, current_price)
                    self.add_count += 1
                    self.last_add_bar = bar_index
                    # 重新計算止盈
                    self.tp1, self.tp2, self.tp3 = self._calculate_take_profits(
                        self.avg_entry_price, self.stop_loss, "long", row
                    )

        # 分批止盈（非 ma20_break 模式）
        if p["take_profit_mode"] != "ma20_break":
            if not self.tp1_hit and high >= self.tp1:
                qty_to_close = self.initial_qty * p["tp1_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.sell(qty_to_close, self.tp1, current_time)
                self.tp1_hit = True
                # 移動止損到保本
                self.stop_loss = max(self.stop_loss, self.entry_price)

            elif self.tp1_hit and not self.tp2_hit and high >= self.tp2:
                qty_to_close = self.initial_qty * p["tp2_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.sell(qty_to_close, self.tp2, current_time)
                self.tp2_hit = True
                self.stop_loss = max(self.stop_loss, self.tp1)

            elif self.tp2_hit and high >= self.tp3:
                if self.broker.position_qty > 0:
                    self.broker.sell(self.broker.position_qty, self.tp3, current_time)
                self._reset_position_state()

    def _manage_short_position(
        self,
        row,
        current_time,
        bar_index: int,
        current_price: float,
        high: float,
        low: float,
        avg20: float,
    ):
        """管理空單"""
        p = self.params
        confirm_bars = p.get("stop_loss_confirm_bars", 1)

        # 確保 stop_loss 有效
        if self.stop_loss is None:
            return

        # === 緊急止損檢查（優先於正常止損）===
        if self._check_emergency_stop(row):
            self.broker.buy(self.broker.position_qty, self.stop_loss, current_time)
            self._reset_position_state()
            return

        # 止損檢查：需要連續 N 根突破才止損
        if high >= self.stop_loss:
            self.below_stop_count += 1
            if self.below_stop_count >= confirm_bars:
                # 確認突破，執行止損
                self.broker.buy(self.broker.position_qty, self.stop_loss, current_time)
                self._reset_position_state()
                return
            # 還沒確認，繼續觀察（可能是假突破）
        else:
            # 價格回到止損位下方，重置計數
            self.below_stop_count = 0

        # MA20 突破止損
        if p["take_profit_mode"] == "ma20_break":
            if current_price > avg20 * (1 + p["ma20_buffer"]):
                self.broker.buy(self.broker.position_qty, current_price, current_time)
                self._reset_position_state()
                return

        # 加倉檢查
        if self._check_add_position(row, bar_index):
            add_qty = self._calculate_add_position_qty(current_price)
            if add_qty > 0:
                success = self.broker.sell(add_qty, current_price, current_time)
                if success:
                    self._update_avg_entry_price(add_qty, current_price)
                    self.add_count += 1
                    self.last_add_bar = bar_index
                    self.tp1, self.tp2, self.tp3 = self._calculate_take_profits(
                        self.avg_entry_price, self.stop_loss, "short", row
                    )

        # 分批止盈
        if p["take_profit_mode"] != "ma20_break":
            if not self.tp1_hit and low <= self.tp1:
                qty_to_close = self.initial_qty * p["tp1_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.buy(qty_to_close, self.tp1, current_time)
                self.tp1_hit = True
                self.stop_loss = min(self.stop_loss, self.entry_price)

            elif self.tp1_hit and not self.tp2_hit and low <= self.tp2:
                qty_to_close = self.initial_qty * p["tp2_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.buy(qty_to_close, self.tp2, current_time)
                self.tp2_hit = True
                self.stop_loss = min(self.stop_loss, self.tp1)

            elif self.tp2_hit and low <= self.tp3:
                if self.broker.position_qty > 0:
                    self.broker.buy(self.broker.position_qty, self.tp3, current_time)
                self._reset_position_state()

    def _reset_position_state(self):
        """重置倉位狀態"""
        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.tp1 = None
        self.tp2 = None
        self.tp3 = None
        self.tp1_hit = False
        self.tp2_hit = False
        self.initial_qty = 0.0
        self.total_qty = 0.0
        self.below_stop_count = 0  # 重置止損確認計數
        self.add_count = 0
        self.trade_direction = None
        # 動態槓桿：重置為固定槓桿
        self.entry_equity = None
        self.current_leverage = self.params["leverage"]
        self.broker.leverage = self.params["leverage"]
