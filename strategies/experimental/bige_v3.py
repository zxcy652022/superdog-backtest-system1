"""
BiGe v3 策略 - 改良版雙均線策略

=== 相比 v2 的改進 ===

【進場改良】回踩確認模式
- v2: 均線密集 → 發散突破 → 立即進場
- v3: 均線密集 → 發散突破 → 等回踩 MA20 → 反彈確認 → 進場

好處：避免買在突破高點，讓價格證明趨勢有效

【出場改良】三種可選模式
1. 動態止盈：趨勢強時放寬，弱時收緊
2. ATR 追蹤止損：根據波動度調整止損距離
3. 分批止盈：TP1 出 30%, TP2 出 40%, 剩餘追蹤

【止損改良】
- 統一用 10 根確認（解決 v2 的參數混亂問題）
- ATR 動態止損距離

Version: v3.0
Date: 2026-01-16
Author: DDragon
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from backtest.engine import BaseStrategy


class ExitMode(Enum):
    """出場模式"""

    DYNAMIC = "dynamic"  # 動態止盈
    ATR_TRAILING = "atr"  # ATR 追蹤止損
    PARTIAL = "partial"  # 分批止盈


class EntryState(Enum):
    """進場狀態機"""

    WAITING = "waiting"  # 等待密集
    CLUSTER_FORMING = "forming"  # 密集形成中
    CLUSTER_READY = "ready"  # 密集完成，等突破
    BREAKOUT = "breakout"  # 已突破，等回踩
    PULLBACK = "pullback"  # 回踩中，等反彈
    READY_TO_ENTER = "ready"  # 可以進場


@dataclass
class BreakoutInfo:
    """突破資訊"""

    direction: str  # 'long' or 'short'
    breakout_price: float  # 突破時的價格
    breakout_bar: int  # 突破的 K 線索引
    ma_center: float  # 突破時的 MA 中心
    pullback_touched: bool  # 是否已觸及回踩區
    pullback_bar: Optional[int]  # 回踩的 K 線索引


class BiGeV3Strategy(BaseStrategy):
    """
    BiGe v3 策略 - 改良版雙均線策略

    核心改進：
    1. 回踩確認進場：突破後等回踩 MA20 再進場
    2. 多種出場模式：動態止盈 / ATR 追蹤 / 分批止盈
    3. 參數統一：解決 v2 的配置混亂問題
    """

    @classmethod
    def get_default_parameters(cls):
        """策略參數"""
        return {
            # === 均線參數 ===
            "ma_short": 20,
            "ma_mid": 60,
            "ma_long": 120,
            # === 密集檢測 ===
            "cluster_threshold": 0.03,  # 3% spread 閾值
            "cluster_bars": 3,  # 連續 3 根確認密集
            # === 突破判定 ===
            "breakout_threshold": 0.01,  # 1% 突破閾值
            # === 回踩確認（v3 新增）===
            "pullback_zone_pct": 0.015,  # 回踩區：MA20 ± 1.5%
            "pullback_max_bars": 10,  # 最多等 10 根回踩
            "require_bounce": True,  # 需要反彈確認
            # === 趨勢過濾 ===
            "require_trend": True,  # 需要趨勢過濾
            "trend_strength": 0.0,  # MA20/MA60 最小差距（0 = 只看方向）
            # === 止損參數 ===
            "stop_confirm_bars": 10,  # 止損確認根數（統一！）
            "stop_loss_pct": 0.03,  # 固定止損 3%
            "atr_stop_mult": 2.0,  # ATR 止損倍數
            # === 出場模式 ===
            "exit_mode": "dynamic",  # dynamic / atr / partial
            # === 動態止盈參數 ===
            "tp_base": 0.10,  # 基礎止盈 10%
            "tp_trend_bonus": 0.05,  # 強趨勢額外 5%
            # === 分批止盈參數 ===
            "tp1_pct": 0.05,  # TP1: 5%
            "tp1_size": 0.3,  # TP1 出 30%
            "tp2_pct": 0.10,  # TP2: 10%
            "tp2_size": 0.4,  # TP2 出 40%
            # === 加倉參數 ===
            "enable_add": True,  # 允許加倉
            "add_max_count": 3,  # 最多 3 次
            "add_min_profit": 0.03,  # 盈利 3% 才加倉
            "add_min_interval": 6,  # 間隔 6 根 K 線
            # === 其他 ===
            "long_only": True,  # 只做多
            "min_rr_ratio": 1.5,  # 最小盈虧比
        }

    def __init__(self, broker, data, **kwargs):
        """初始化策略"""
        super().__init__(broker, data)

        self.params = self.get_default_parameters()
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        # 狀態
        self.entry_state = EntryState.WAITING
        self.cluster_count = 0
        self.cluster_center = None
        self.breakout_info: Optional[BreakoutInfo] = None

        # 持倉追蹤
        self.entry_price = None
        self.entry_bar = None
        self.stop_price = None
        self.below_stop_count = 0
        self.add_count = 0
        self.last_add_bar = -999
        self.partial_exits = 0  # 分批出場計數

        # 預計算指標
        self._calculate_indicators()

    def _calculate_indicators(self):
        """計算技術指標"""
        p = self.params
        df = self.data

        # 6 條均線
        df["ma20"] = df["close"].rolling(p["ma_short"]).mean()
        df["ma60"] = df["close"].rolling(p["ma_mid"]).mean()
        df["ma120"] = df["close"].rolling(p["ma_long"]).mean()
        df["ema20"] = df["close"].ewm(span=p["ma_short"], adjust=False).mean()
        df["ema60"] = df["close"].ewm(span=p["ma_mid"], adjust=False).mean()
        df["ema120"] = df["close"].ewm(span=p["ma_long"], adjust=False).mean()

        # MA 中心和平均
        df["ma_center"] = (
            df["ma20"] + df["ma60"] + df["ma120"] + df["ema20"] + df["ema60"] + df["ema120"]
        ) / 6
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2

        # ATR
        tr = pd.concat(
            [
                df["high"] - df["low"],
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1)),
            ],
            axis=1,
        ).max(axis=1)
        df["atr"] = tr.rolling(14).mean()

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

        # 趨勢強度
        df["trend_strength"] = (df["avg20"] - df["avg60"]) / df["avg60"]

    def _is_cluster(self, row) -> bool:
        """均線是否密集"""
        spread = row.get("spread", np.nan)
        if pd.isna(spread):
            return False
        return spread < self.params["cluster_threshold"]

    def _is_uptrend(self, row) -> bool:
        """是否上升趨勢"""
        if not self.params["require_trend"]:
            return True
        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        if pd.isna(avg20) or pd.isna(avg60):
            return False

        # 方向檢查
        if avg20 <= avg60:
            return False

        # 強度檢查（如果有設定）
        if self.params["trend_strength"] > 0:
            strength = (avg20 - avg60) / avg60
            if strength < self.params["trend_strength"]:
                return False

        return True

    def _is_downtrend(self, row) -> bool:
        """是否下降趨勢"""
        if not self.params["require_trend"]:
            return True
        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        if pd.isna(avg20) or pd.isna(avg60):
            return False

        if avg20 >= avg60:
            return False

        if self.params["trend_strength"] > 0:
            strength = (avg60 - avg20) / avg60
            if strength < self.params["trend_strength"]:
                return False

        return True

    def _check_breakout(self, row) -> Optional[str]:
        """檢查是否突破（返回 'long', 'short' 或 None）"""
        if self.cluster_center is None:
            return None

        ma_center = row.get("ma_center")
        close = row["close"]
        threshold = self.params["breakout_threshold"]

        # 向上突破
        if close > ma_center * (1 + threshold):
            if self._is_uptrend(row):
                return "long"

        # 向下突破（如果允許做空）
        if not self.params["long_only"]:
            if close < ma_center * (1 - threshold):
                if self._is_downtrend(row):
                    return "short"

        return None

    def _is_in_pullback_zone(self, row, direction: str) -> bool:
        """檢查價格是否在回踩區"""
        avg20 = row.get("avg20")
        if pd.isna(avg20):
            return False

        zone_pct = self.params["pullback_zone_pct"]
        low = row["low"]
        high = row["high"]

        if direction == "long":
            # 多單回踩：最低價進入 MA20 ± 1.5% 區域
            pullback_upper = avg20 * (1 + zone_pct)
            pullback_lower = avg20 * (1 - zone_pct)
            return low <= pullback_upper and low >= pullback_lower * 0.98  # 稍微放寬下限
        else:
            # 空單回踩：最高價進入 MA20 ± 1.5% 區域
            pullback_upper = avg20 * (1 + zone_pct)
            pullback_lower = avg20 * (1 - zone_pct)
            return high >= pullback_lower and high <= pullback_upper * 1.02

    def _is_bounce_confirmed(self, row, direction: str) -> bool:
        """檢查是否反彈確認"""
        if not self.params["require_bounce"]:
            return True

        avg20 = row.get("avg20")
        close = row["close"]

        if pd.isna(avg20):
            return False

        if direction == "long":
            # 多單反彈：收盤價回到 MA20 上方
            return close > avg20
        else:
            # 空單反彈：收盤價回到 MA20 下方
            return close < avg20

    def _calculate_stop_loss(self, entry_price: float, row, direction: str) -> float:
        """計算止損價"""
        p = self.params
        ma_center = row.get("ma_center", entry_price)
        atr = row.get("atr", entry_price * 0.02)

        if direction == "long":
            # 方法1：固定百分比
            sl_fixed = entry_price * (1 - p["stop_loss_pct"])
            # 方法2：MA 中心 - 2%
            sl_ma = ma_center * 0.98
            # 方法3：ATR 止損
            sl_atr = entry_price - p["atr_stop_mult"] * atr
            # 取最高的（最近的）
            return max(sl_fixed, sl_ma, sl_atr)
        else:
            sl_fixed = entry_price * (1 + p["stop_loss_pct"])
            sl_ma = ma_center * 1.02
            sl_atr = entry_price + p["atr_stop_mult"] * atr
            return min(sl_fixed, sl_ma, sl_atr)

    def _calculate_take_profit(self, entry_price: float, row, direction: str) -> float:
        """計算止盈價（動態模式）"""
        p = self.params
        base_tp = p["tp_base"]

        # 動態調整：根據趨勢強度
        trend_strength = abs(row.get("trend_strength", 0))
        if trend_strength > 0.05:  # 強趨勢
            tp_pct = base_tp + p["tp_trend_bonus"]
        else:
            tp_pct = base_tp

        if direction == "long":
            return entry_price * (1 + tp_pct)
        else:
            return entry_price * (1 - tp_pct)

    def _check_rr_ratio(self, entry: float, stop: float, tp: float, direction: str) -> float:
        """計算盈虧比"""
        if direction == "long":
            risk = entry - stop
            reward = tp - entry
        else:
            risk = stop - entry
            reward = entry - tp

        if risk <= 0:
            return 0
        return reward / risk

    def _reset_entry_state(self):
        """重置進場狀態"""
        self.entry_state = EntryState.WAITING
        self.cluster_count = 0
        self.cluster_center = None
        self.breakout_info = None

    def _reset_position_state(self):
        """重置持倉狀態"""
        self.entry_price = None
        self.entry_bar = None
        self.stop_price = None
        self.below_stop_count = 0
        self.add_count = 0
        self.last_add_bar = -999
        self.partial_exits = 0

    def on_bar(self, i: int, row: pd.Series):
        """每根 K 線調用"""
        if i < self.params["ma_long"]:
            return

        current_time = row.name
        close = row["close"]

        # ========== 有倉位：處理出場邏輯 ==========
        if self.broker.has_position:
            self._handle_position(i, row)
            return

        # ========== 無倉位：進場狀態機 ==========
        is_cluster = self._is_cluster(row)

        # 狀態：等待密集
        if self.entry_state == EntryState.WAITING:
            if is_cluster:
                self.cluster_count = 1
                self.entry_state = EntryState.CLUSTER_FORMING
            return

        # 狀態：密集形成中
        if self.entry_state == EntryState.CLUSTER_FORMING:
            if is_cluster:
                self.cluster_count += 1
                if self.cluster_count >= self.params["cluster_bars"]:
                    self.cluster_center = row.get("ma_center")
                    self.entry_state = EntryState.CLUSTER_READY
            else:
                self._reset_entry_state()
            return

        # 狀態：密集完成，等突破
        if self.entry_state == EntryState.CLUSTER_READY:
            if is_cluster:
                # 還在密集中，更新中心
                self.cluster_center = row.get("ma_center")
            else:
                # 開始發散，檢查突破
                breakout_dir = self._check_breakout(row)
                if breakout_dir:
                    self.breakout_info = BreakoutInfo(
                        direction=breakout_dir,
                        breakout_price=close,
                        breakout_bar=i,
                        ma_center=self.cluster_center,
                        pullback_touched=False,
                        pullback_bar=None,
                    )
                    self.entry_state = EntryState.BREAKOUT
                else:
                    self._reset_entry_state()
            return

        # 狀態：已突破，等回踩
        if self.entry_state == EntryState.BREAKOUT:
            # 檢查是否超時
            if i - self.breakout_info.breakout_bar > self.params["pullback_max_bars"]:
                self._reset_entry_state()
                return

            # 檢查是否進入回踩區
            if self._is_in_pullback_zone(row, self.breakout_info.direction):
                self.breakout_info.pullback_touched = True
                self.breakout_info.pullback_bar = i
                self.entry_state = EntryState.PULLBACK
            return

        # 狀態：回踩中，等反彈
        if self.entry_state == EntryState.PULLBACK:
            # 檢查是否超時
            if i - self.breakout_info.breakout_bar > self.params["pullback_max_bars"]:
                self._reset_entry_state()
                return

            # 檢查反彈確認
            if self._is_bounce_confirmed(row, self.breakout_info.direction):
                # === 進場！===
                self._execute_entry(i, row)
            return

    def _execute_entry(self, i: int, row: pd.Series):
        """執行進場"""
        direction = self.breakout_info.direction
        close = row["close"]
        current_time = row.name

        # 計算止損止盈
        stop_loss = self._calculate_stop_loss(close, row, direction)
        take_profit = self._calculate_take_profit(close, row, direction)

        # 盈虧比檢查
        rr = self._check_rr_ratio(close, stop_loss, take_profit, direction)
        if rr < self.params["min_rr_ratio"]:
            self._reset_entry_state()
            return

        # 執行進場
        if direction == "long":
            success = self.broker.buy_all(close, current_time)
        else:
            success = self.broker.short_all(close, current_time)

        if success:
            self.entry_price = close
            self.entry_bar = i
            self.stop_price = stop_loss
            self.below_stop_count = 0
            self.add_count = 0
            self.last_add_bar = i
            self.partial_exits = 0

        self._reset_entry_state()

    def _handle_position(self, i: int, row: pd.Series):
        """處理持倉邏輯（止損、止盈、加倉）"""
        current_time = row.name
        close = row["close"]
        low = row["low"]
        high = row["high"]
        direction = self.broker.position_direction

        # ===== 1. 更新追蹤止損 =====
        self._update_trailing_stop(row, direction)

        # ===== 2. 檢查止損 =====
        if self._check_stop_loss(row, direction):
            self._close_position(self.stop_price, current_time, "stop_loss")
            return

        # ===== 3. 檢查止盈（根據模式）=====
        exit_mode = self.params["exit_mode"]

        if exit_mode == "dynamic":
            if self._check_dynamic_tp(row, direction):
                tp = self._calculate_take_profit(self.entry_price, row, direction)
                self._close_position(tp, current_time, "take_profit")
                return

        elif exit_mode == "partial":
            self._check_partial_tp(i, row, direction, current_time)

        # ===== 4. 檢查加倉 =====
        if self.params["enable_add"]:
            self._check_add_position(i, row, direction, current_time)

    def _update_trailing_stop(self, row, direction: str):
        """更新追蹤止損"""
        avg20 = row.get("avg20")
        if pd.isna(avg20):
            return

        if direction == "long":
            new_stop = avg20 * 0.98
            if new_stop > self.stop_price:
                self.stop_price = new_stop
        else:
            new_stop = avg20 * 1.02
            if new_stop < self.stop_price:
                self.stop_price = new_stop

    def _check_stop_loss(self, row, direction: str) -> bool:
        """檢查止損（確認式）"""
        low = row["low"]
        high = row["high"]
        confirm_bars = self.params["stop_confirm_bars"]

        if direction == "long":
            if low <= self.stop_price:
                self.below_stop_count += 1
            else:
                self.below_stop_count = 0
        else:
            if high >= self.stop_price:
                self.below_stop_count += 1
            else:
                self.below_stop_count = 0

        return self.below_stop_count >= confirm_bars

    def _check_dynamic_tp(self, row, direction: str) -> bool:
        """檢查動態止盈"""
        tp = self._calculate_take_profit(self.entry_price, row, direction)
        high = row["high"]
        low = row["low"]

        if direction == "long":
            return high >= tp
        else:
            return low <= tp

    def _check_partial_tp(self, i: int, row, direction: str, current_time):
        """檢查分批止盈"""
        p = self.params
        high = row["high"]
        low = row["low"]

        if self.partial_exits >= 2:
            # 已經出了 2 批，剩餘用追蹤止損
            return

        if direction == "long":
            if self.partial_exits == 0:
                # TP1
                tp1 = self.entry_price * (1 + p["tp1_pct"])
                if high >= tp1:
                    qty = self.broker.position_qty * p["tp1_size"]
                    self.broker.sell(qty, tp1, current_time)
                    self.partial_exits = 1
                    # 移動止損到保本
                    self.stop_price = max(self.stop_price, self.entry_price)
            elif self.partial_exits == 1:
                # TP2
                tp2 = self.entry_price * (1 + p["tp2_pct"])
                if high >= tp2:
                    qty = self.broker.position_qty * (p["tp2_size"] / (1 - p["tp1_size"]))
                    self.broker.sell(qty, tp2, current_time)
                    self.partial_exits = 2
                    # 移動止損到 TP1
                    self.stop_price = max(self.stop_price, self.entry_price * (1 + p["tp1_pct"]))
        else:
            # 空單分批止盈（邏輯相反）
            if self.partial_exits == 0:
                tp1 = self.entry_price * (1 - p["tp1_pct"])
                if low <= tp1:
                    qty = self.broker.position_qty * p["tp1_size"]
                    self.broker.buy(qty, tp1, current_time)
                    self.partial_exits = 1
                    self.stop_price = min(self.stop_price, self.entry_price)
            elif self.partial_exits == 1:
                tp2 = self.entry_price * (1 - p["tp2_pct"])
                if low <= tp2:
                    qty = self.broker.position_qty * (p["tp2_size"] / (1 - p["tp1_size"]))
                    self.broker.buy(qty, tp2, current_time)
                    self.partial_exits = 2
                    self.stop_price = min(self.stop_price, self.entry_price * (1 - p["tp1_pct"]))

    def _check_add_position(self, i: int, row, direction: str, current_time):
        """檢查加倉條件"""
        p = self.params

        # 次數限制
        if self.add_count >= p["add_max_count"]:
            return

        # 間隔限制
        if i - self.last_add_bar < p["add_min_interval"]:
            return

        # 盈利門檻
        close = row["close"]
        if direction == "long":
            pnl_pct = (close - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - close) / self.entry_price

        if pnl_pct < p["add_min_profit"]:
            return

        # 回踩條件
        avg20 = row.get("avg20")
        if pd.isna(avg20):
            return

        low = row["low"]
        high = row["high"]
        zone_pct = self.params["pullback_zone_pct"]

        should_add = False
        if direction == "long":
            # 最低價靠近 MA20，收盤在 MA20 上方
            near_ma = abs(low - avg20) / avg20 < zone_pct
            above_ma = close > avg20
            should_add = near_ma and above_ma
        else:
            near_ma = abs(high - avg20) / avg20 < zone_pct
            below_ma = close < avg20
            should_add = near_ma and below_ma

        if should_add:
            # 執行加倉（50% 當前持倉）
            add_qty = self.broker.position_qty * 0.5
            if direction == "long":
                success = self.broker.buy(add_qty, close, current_time)
            else:
                success = self.broker.sell(add_qty, close, current_time)

            if success:
                self.add_count += 1
                self.last_add_bar = i

    def _close_position(self, price: float, time, reason: str):
        """平倉"""
        if self.broker.is_long:
            self.broker.sell(self.broker.position_qty, price, time)
        elif self.broker.is_short:
            self.broker.buy(self.broker.position_qty, price, time)

        self._reset_position_state()


# ===== 便捷函數 =====


def run_bige_v3_backtest(
    data: pd.DataFrame, initial_cash: float = 500, exit_mode: str = "dynamic", **kwargs
):
    """
    執行 BiGe v3 回測

    Args:
        data: OHLCV DataFrame
        initial_cash: 初始資金
        exit_mode: 出場模式 ("dynamic", "atr", "partial")
        **kwargs: 其他策略參數

    Returns:
        BacktestResult
    """
    from backtest.engine import run_backtest

    params = {"exit_mode": exit_mode}
    params.update(kwargs)

    return run_backtest(
        data=data,
        strategy_cls=BiGeV3Strategy,
        initial_cash=initial_cash,
        strategy_params=params,
        leverage=7,
        fee_rate=0.0005,
    )
