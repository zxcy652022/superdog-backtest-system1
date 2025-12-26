#!/usr/bin/env python3
"""
浮雲滾倉策略測試 - 正確實現版本 v2

核心邏輯（根據幣哥/午飯教學影片原文）：
1. 觸發條件：本金翻倍（浮盈 = 100% 初始保證金）時加倉
   - 注意：不是 MA20 回踩！
   - 原文：「本金翻倍就要加倉」
2. 加倉方式：使用 100% 浮盈加倉
3. 槓桿遞減：20x → 15x → 10x → 5x → 3x → 1x

關鍵公式（來自加密货币滚仓交易方法影片）：
- 開倉: $100, 20x槓桿
- 漲 5% → 本金翻倍到 $200 → 加倉（仍用 20x）
- 漲 10% → 本金翻倍到 $400 → 加倉（仍用 20x）
- 漲 15% → 本金翻倍到 $800 → 加倉（降槓桿到 15x）
- 漲 22.5% → 本金翻倍到 $1600 → 加倉（降槓桿到 10x）
- ...持續直到槓桿降到 1x

核心差異：
- 之前錯誤：MA20 回踩 → 觸發浮盈加倉（矛盾！回踩時浮盈已減少）
- 正確邏輯：本金翻倍 → 觸發加倉（在有最大浮盈時加倉）
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.broker import SimulatedBroker
from backtest.engine import BaseStrategy


class FuYunRollingStrategy(BaseStrategy):
    """
    浮雲滾倉策略

    核心邏輯：
    1. 進場：使用幣哥雙均線信號（MA20回踩 + 趨勢確認）
    2. 加倉觸發：利潤達到閾值（如5%、10%...）
    3. 加倉方式：使用全部浮盈加倉
    4. 槓桿遞減：20x → 15x → 10x → 5x → 3x → 1x
    5. 止損：跌破 MA20（幣哥核心邏輯）
    """

    # 槓桿遞減序列（根據幣哥/午飯的設定）
    # 午飯版本: 50x → 30x → 20x → 15x → 10x → 5x
    # 幣哥版本: 20x × 3 → 15x → 10x → 5x → 3x → 1x
    LEVERAGE_SCHEDULES = {
        50: [50, 30, 20, 15, 10, 5, 3, 1, 1, 1],  # 午飯版本
        20: [20, 20, 20, 15, 10, 5, 3, 1, 1, 1],  # 幣哥版本
        15: [15, 15, 10, 7, 5, 3, 2, 1, 1, 1],  # 15x 版本
        10: [10, 10, 7, 5, 3, 2, 1, 1, 1, 1],  # 保守版本
        7: [7, 7, 5, 4, 3, 2, 1, 1, 1, 1],  # 7x 版本
        5: [5, 5, 4, 3, 2, 1, 1, 1, 1, 1],  # 最保守版本
    }

    @classmethod
    def get_leverage_schedule(cls, initial_leverage: int) -> list:
        """根據初始槓桿獲取對應的遞減序列"""
        if initial_leverage in cls.LEVERAGE_SCHEDULES:
            return cls.LEVERAGE_SCHEDULES[initial_leverage]
        # 預設使用 10x 版本（表現最好）
        return cls.LEVERAGE_SCHEDULES[10]

    def __init__(self, broker, data, **kwargs):
        self.broker = broker
        self.data = data

        # 策略參數
        self.params = {
            # 均線參數
            "ma_len_short": 20,
            "ma_len_mid": 60,
            "ma_len_long": 120,
            # 進場參數
            "pullback_tolerance": 0.018,  # 回踩容許範圍
            "ma20_buffer": 0.02,  # MA20 緩衝
            # 浮雲滾倉參數
            "profit_threshold": 0.05,  # 利潤達到 5% 時加倉
            "use_dynamic_leverage": True,  # 使用動態槓桿
            "initial_leverage": 20,  # 初始槓桿
            "position_size_pct": 0.10,  # 初始倉位 10%
            # 止損參數
            "stop_loss_confirm_bars": 10,  # 連續 N 根跌破才止損
            "emergency_stop_atr": 3.5,  # 緊急止損 ATR 倍數
            # 止損模式：'ma20' 或 'drawdown'
            "stop_loss_mode": "ma20",  # 預設 MA20 止損
            "max_drawdown_pct": 0.10,  # 最大回撤止損（10%）
            # 趨勢判斷
            "trend_mode": "loose",  # loose=MA20>MA60
        }
        self.params.update(kwargs)

        # 設置初始槓桿
        self.broker.leverage = self.params["initial_leverage"]

        # 倉位狀態
        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.entry_bar = -999
        self.trade_direction = None
        self.total_qty = 0.0
        self.initial_margin = 0.0  # 初始保證金

        # 滾倉狀態
        self.add_count = 0  # 加倉次數
        self.last_add_profit_pct = 0.0  # 上次加倉時的利潤百分比
        self.peak_profit_pct = 0.0  # 最高利潤百分比（用於追蹤）

        # 止損確認
        self.below_stop_count = 0

        # 追蹤止損狀態（用於回撤止損模式）
        self.peak_price = None  # 持倉期間最高/最低價

        # Cluster 狀態
        self.cluster_active = False
        self.cluster_high = None
        self.cluster_low = None
        self.cluster_start_bar = None
        self.cluster_consecutive_count = 0

        # 預計算指標
        self._calculate_all_indicators()

    def _calculate_all_indicators(self):
        """預先計算所有技術指標"""
        p = self.params
        df = self.data

        # 計算 SMA
        df["ma20"] = df["close"].rolling(p["ma_len_short"]).mean()
        df["ma60"] = df["close"].rolling(p["ma_len_mid"]).mean()
        df["ma120"] = df["close"].rolling(p["ma_len_long"]).mean()

        # 計算 EMA
        df["ema20"] = df["close"].ewm(span=p["ma_len_short"], adjust=False).mean()
        df["ema60"] = df["close"].ewm(span=p["ma_len_mid"], adjust=False).mean()
        df["ema120"] = df["close"].ewm(span=p["ma_len_long"], adjust=False).mean()

        # 平均 MA
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2
        df["avg120"] = (df["ma120"] + df["ema120"]) / 2

        # ATR
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()

    def _get_current_leverage(self) -> int:
        """根據加倉次數獲取當前應使用的槓桿"""
        schedule = self.get_leverage_schedule(self.params["initial_leverage"])
        idx = min(self.add_count, len(schedule) - 1)
        return schedule[idx]

    def _is_uptrend(self, row) -> bool:
        """判斷多頭趨勢（寬鬆模式：MA20 > MA60）"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] > row["avg60"]

    def _is_downtrend(self, row) -> bool:
        """判斷空頭趨勢（寬鬆模式：MA20 < MA60）"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] < row["avg60"]

    def _check_long_entry(self, row, i) -> bool:
        """多單進場條件：回踩 MA20 不跌破"""
        p = self.params
        close = row["close"]
        low = row["low"]
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return False

        if not self._is_uptrend(row):
            return False

        # 回踩 MA20 不跌破
        near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
        not_break_ma20 = low > avg20 * (1 - p["ma20_buffer"])
        bullish_close = close > avg20

        return near_ma20 and not_break_ma20 and bullish_close

    def _check_short_entry(self, row, i) -> bool:
        """空單進場條件：反彈 MA20 不突破"""
        p = self.params
        close = row["close"]
        high = row["high"]
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return False

        if not self._is_downtrend(row):
            return False

        # 反彈 MA20 不突破
        near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
        not_break_ma20 = high < avg20 * (1 + p["ma20_buffer"])
        bearish_close = close < avg20

        return near_ma20 and not_break_ma20 and bearish_close

    def _calculate_current_profit_pct(self, current_price: float) -> float:
        """計算當前利潤百分比（相對於初始保證金）"""
        if self.initial_margin <= 0:
            return 0.0

        if self.broker.is_long:
            unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
        else:
            unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

        return unrealized_pnl / self.initial_margin

    def _check_pullback_trigger(self, row) -> bool:
        """
        檢查回踩 MA20 觸發（幣哥方式）
        條件：價格回踩到 MA20 附近但不跌破
        """
        p = self.params
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return False

        close = row["close"]
        low = row["low"]
        high = row["high"]

        tolerance = p.get("pullback_tolerance", 0.018)
        buffer = p.get("ma20_buffer", 0.02)

        if self.broker.is_long:
            # 多單：回踩 MA20 不跌破
            near_ma20 = abs(low - avg20) / avg20 < tolerance
            not_break = low > avg20 * (1 - buffer)
            bullish = close > avg20
            return near_ma20 and not_break and bullish
        else:
            # 空單：反彈 MA20 不突破
            near_ma20 = abs(high - avg20) / avg20 < tolerance
            not_break = high < avg20 * (1 + buffer)
            bearish = close < avg20
            return near_ma20 and not_break and bearish

    def _check_double_trigger(self, current_price: float) -> bool:
        """
        檢查本金翻倍觸發（浮雲方式）
        條件：當前利潤 = 當前保證金 × 100%
        """
        current_leverage = self._get_current_leverage()

        if self.broker.is_long:
            price_change_pct = (current_price - self.avg_entry_price) / self.avg_entry_price
        else:
            price_change_pct = (self.avg_entry_price - current_price) / self.avg_entry_price

        if price_change_pct <= 0:
            return False

        # 本金盈利百分比 = 價格變化 × 槓桿
        profit_pct = price_change_pct * current_leverage

        # 觸發條件：盈利 >= 100%（本金翻倍）
        return profit_pct >= 1.0

    def _check_add_position_trigger(self, current_price: float, row=None) -> bool:
        """
        檢查是否觸發加倉

        支援多種觸發模式：
        1. double: 本金翻倍觸發（浮雲方式）
        2. pullback: 回踩 MA20 觸發（幣哥方式）
        3. hybrid: 任一條件觸發
        4. profit_pct: 利潤百分比觸發
        """
        p = self.params

        if not self.broker.has_position:
            return False

        trigger_mode = p.get("trigger_mode", "double")

        if trigger_mode == "double":
            return self._check_double_trigger(current_price)

        elif trigger_mode == "pullback":
            if row is None:
                return False
            return self._check_pullback_trigger(row)

        elif trigger_mode == "hybrid":
            # 任一條件滿足就觸發
            double_triggered = self._check_double_trigger(current_price)
            pullback_triggered = self._check_pullback_trigger(row) if row is not None else False
            return double_triggered or pullback_triggered

        elif trigger_mode == "profit_pct":
            # 利潤百分比觸發模式
            current_leverage = self._get_current_leverage()
            trigger_pct = p.get("add_trigger_pct", 0.50)

            if self.broker.is_long:
                price_change_pct = (current_price - self.avg_entry_price) / self.avg_entry_price
            else:
                price_change_pct = (self.avg_entry_price - current_price) / self.avg_entry_price

            if price_change_pct <= 0:
                return False

            profit_pct = price_change_pct * current_leverage
            return profit_pct >= trigger_pct

        else:
            # 閾值模式
            current_profit_pct = self._calculate_current_profit_pct(current_price)
            if current_profit_pct <= 0:
                return False
            threshold = p.get("profit_threshold", 0.50)
            next_threshold = (self.add_count + 1) * threshold
            return current_profit_pct >= next_threshold

    def _execute_add_position(self, current_price: float, current_time):
        """
        執行加倉

        支援兩種加倉模式：
        1. floating_pnl: 使用全部浮盈加倉（浮雲方式）
        2. fixed_50: 固定 50% 當前倉位加倉（幣哥方式）
        3. fixed_30: 固定 30% 當前倉位加倉
        """
        p = self.params
        add_mode = p.get("add_mode", "floating_pnl")

        # 計算當前浮盈
        if self.broker.is_long:
            unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
        else:
            unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

        # 更新槓桿
        new_leverage = self._get_current_leverage()
        self.broker.leverage = new_leverage

        # 根據加倉模式計算加倉數量
        if add_mode == "floating_pnl":
            # 浮盈加倉：使用全部浮盈作為新保證金
            if unrealized_pnl <= 0:
                return False
            add_margin = unrealized_pnl
        elif add_mode == "fixed_50":
            # 固定 50% 加倉：使用當前權益的 50% 作為新保證金
            equity = self.broker.get_current_equity(current_price)
            add_margin = equity * 0.50 * p["position_size_pct"]
        elif add_mode == "fixed_30":
            # 固定 30% 加倉
            equity = self.broker.get_current_equity(current_price)
            add_margin = equity * 0.30 * p["position_size_pct"]
        else:
            # 預設使用浮盈
            if unrealized_pnl <= 0:
                return False
            add_margin = unrealized_pnl

        if add_margin <= 0:
            return False

        add_position_value = add_margin * new_leverage
        add_qty = add_position_value / current_price

        if add_qty <= 0:
            return False

        # 執行加倉
        if self.broker.is_long:
            success = self.broker.buy(add_qty, current_price, current_time)
        else:
            success = self.broker.sell(add_qty, current_price, current_time)

        if success:
            # 更新狀態
            old_total_cost = self.avg_entry_price * self.total_qty
            new_total_cost = old_total_cost + current_price * add_qty
            self.total_qty += add_qty
            self.avg_entry_price = new_total_cost / self.total_qty

            self.add_count += 1
            self.last_add_profit_pct = self._calculate_current_profit_pct(current_price)

            return True

        return False

    def on_bar(self, i: int, row: pd.Series):
        """每根 K 線調用一次"""
        if i < self.params["ma_len_long"]:
            return

        current_time = row.name
        current_price = row["close"]

        # === 1. 倉位管理 ===
        if self.broker.has_position:
            # 爆倉檢測
            if self.broker.check_liquidation_in_bar(row):
                liq_price = self.broker.get_liquidation_price()
                self.broker.process_liquidation(current_time, liq_price)
                self._reset_position_state()
                return

            self._manage_position(row, current_time, i)
            return

        # === 2. 進場信號檢測 ===
        if self._check_long_entry(row, i):
            self._enter_long(row, current_time, i)
        elif self._check_short_entry(row, i):
            self._enter_short(row, current_time, i)

    def _enter_long(self, row, current_time, bar_index: int):
        """執行多單進場"""
        p = self.params
        entry_price = row["close"]

        # 使用初始槓桿
        self.broker.leverage = p["initial_leverage"]
        self.add_count = 0

        # 計算初始倉位
        equity = self.broker.get_current_equity(entry_price)
        margin = equity * p["position_size_pct"]
        position_value = margin * p["initial_leverage"]
        qty = position_value / entry_price

        if qty > 0:
            success = self.broker.buy(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = row["avg20"] * (1 - p["ma20_buffer"])
                self.total_qty = qty
                self.initial_margin = margin
                self.entry_bar = bar_index
                self.trade_direction = "long"
                self.below_stop_count = 0
                self.last_add_profit_pct = 0.0
                self.peak_profit_pct = 0.0

    def _enter_short(self, row, current_time, bar_index: int):
        """執行空單進場"""
        p = self.params
        entry_price = row["close"]

        # 使用初始槓桿
        self.broker.leverage = p["initial_leverage"]
        self.add_count = 0

        # 計算初始倉位
        equity = self.broker.get_current_equity(entry_price)
        margin = equity * p["position_size_pct"]
        position_value = margin * p["initial_leverage"]
        qty = position_value / entry_price

        if qty > 0:
            success = self.broker.sell(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = row["avg20"] * (1 + p["ma20_buffer"])
                self.total_qty = qty
                self.initial_margin = margin
                self.entry_bar = bar_index
                self.trade_direction = "short"
                self.below_stop_count = 0
                self.last_add_profit_pct = 0.0
                self.peak_profit_pct = 0.0

    def _manage_position(self, row, current_time, bar_index: int):
        """管理現有倉位"""
        p = self.params
        current_price = row["close"]
        high = row["high"]
        low = row["low"]
        avg20 = row["avg20"]
        avg60 = row["avg60"]
        stop_mode = p.get("stop_loss_mode", "ma20")

        # === 更新追蹤最高/最低價（用於回撤止損）===
        if self.broker.is_long:
            if self.peak_price is None or high > self.peak_price:
                self.peak_price = high
        elif self.broker.is_short:
            if self.peak_price is None or low < self.peak_price:
                self.peak_price = low

        # === 止損檢查（根據模式）===
        should_stop = False
        stop_price = current_price
        current_leverage = self._get_current_leverage()

        if stop_mode == "none_until_complete":
            # 滾倉期間不止損，只在槓桿降到 1x 後才啟動 MA20 止損
            if current_leverage <= 1:
                # 槓桿已降到最低，啟動 MA20 止損
                if pd.notna(avg20):
                    if self.broker.is_long:
                        new_stop = avg20 * (1 - p["ma20_buffer"])
                        if self.stop_loss is None or new_stop > self.stop_loss:
                            self.stop_loss = new_stop
                        if low <= self.stop_loss:
                            should_stop = True
                            stop_price = self.stop_loss
                    elif self.broker.is_short:
                        new_stop = avg20 * (1 + p["ma20_buffer"])
                        if self.stop_loss is None or new_stop < self.stop_loss:
                            self.stop_loss = new_stop
                        if high >= self.stop_loss:
                            should_stop = True
                            stop_price = self.stop_loss

        elif stop_mode == "trend_reversal":
            # 趨勢反轉止損：只在趨勢反轉時止損
            # 多單：MA20 < MA60 時止損
            # 空單：MA20 > MA60 時止損
            if pd.notna(avg20) and pd.notna(avg60):
                if self.broker.is_long and avg20 < avg60:
                    should_stop = True
                    stop_price = current_price
                elif self.broker.is_short and avg20 > avg60:
                    should_stop = True
                    stop_price = current_price

        elif stop_mode == "ma60":
            # MA60 止損模式（更寬鬆）
            if pd.notna(avg60):
                if self.broker.is_long:
                    new_stop = avg60 * (1 - p["ma20_buffer"])
                    if self.stop_loss is None or new_stop > self.stop_loss:
                        self.stop_loss = new_stop
                    if low <= self.stop_loss:
                        self.below_stop_count += 1
                        if self.below_stop_count >= p["stop_loss_confirm_bars"]:
                            should_stop = True
                            stop_price = self.stop_loss
                    else:
                        self.below_stop_count = 0
                elif self.broker.is_short:
                    new_stop = avg60 * (1 + p["ma20_buffer"])
                    if self.stop_loss is None or new_stop < self.stop_loss:
                        self.stop_loss = new_stop
                    if high >= self.stop_loss:
                        self.below_stop_count += 1
                        if self.below_stop_count >= p["stop_loss_confirm_bars"]:
                            should_stop = True
                            stop_price = self.stop_loss
                    else:
                        self.below_stop_count = 0

        elif stop_mode == "drawdown":
            # 回撤止損模式：從最高點回撤超過 N%
            max_dd = p.get("max_drawdown_pct", 0.10)
            if self.broker.is_long and self.peak_price:
                drawdown = (self.peak_price - low) / self.peak_price
                if drawdown >= max_dd:
                    should_stop = True
                    stop_price = self.peak_price * (1 - max_dd)
            elif self.broker.is_short and self.peak_price:
                drawdown = (high - self.peak_price) / self.peak_price
                if drawdown >= max_dd:
                    should_stop = True
                    stop_price = self.peak_price * (1 + max_dd)

        else:
            # MA20 止損模式（原邏輯）
            if pd.notna(avg20):
                if self.broker.is_long:
                    new_stop = avg20 * (1 - p["ma20_buffer"])
                    if self.stop_loss is None or new_stop > self.stop_loss:
                        self.stop_loss = new_stop
                elif self.broker.is_short:
                    new_stop = avg20 * (1 + p["ma20_buffer"])
                    if self.stop_loss is None or new_stop < self.stop_loss:
                        self.stop_loss = new_stop

            if self.broker.is_long:
                if low <= self.stop_loss:
                    self.below_stop_count += 1
                    if self.below_stop_count >= p["stop_loss_confirm_bars"]:
                        should_stop = True
                        stop_price = self.stop_loss
                else:
                    self.below_stop_count = 0
            elif self.broker.is_short:
                if high >= self.stop_loss:
                    self.below_stop_count += 1
                    if self.below_stop_count >= p["stop_loss_confirm_bars"]:
                        should_stop = True
                        stop_price = self.stop_loss
                else:
                    self.below_stop_count = 0

        # 執行止損
        if should_stop:
            if self.broker.is_long:
                self.broker.sell(self.broker.position_qty, stop_price, current_time)
            else:
                self.broker.buy(self.broker.position_qty, stop_price, current_time)
            self._reset_position_state()
            return

        # === 浮雲滾倉：檢查加倉觸發 ===
        if self._check_add_position_trigger(current_price, row):
            self._execute_add_position(current_price, current_time)

        # === 更新最高利潤 ===
        current_profit = self._calculate_current_profit_pct(current_price)
        if current_profit > self.peak_profit_pct:
            self.peak_profit_pct = current_profit

    def _reset_position_state(self):
        """重置倉位狀態"""
        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.total_qty = 0.0
        self.initial_margin = 0.0
        self.add_count = 0
        self.below_stop_count = 0
        self.trade_direction = None
        self.last_add_profit_pct = 0.0
        self.peak_profit_pct = 0.0
        self.peak_price = None  # 重置追蹤最高價
        # 重置槓桿
        self.broker.leverage = self.params["initial_leverage"]


def load_data(filepath: str) -> pd.DataFrame:
    """載入數據"""
    df = pd.read_csv(filepath)
    # 轉換毫秒時間戳為 datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def run_strategy_backtest(data: pd.DataFrame, strategy_class, initial_cash: float = 500, **kwargs):
    """執行回測 - 直接運行策略"""
    # 創建 broker
    broker = SimulatedBroker(
        initial_cash=initial_cash,
        fee_rate=0.0004,
        leverage=kwargs.get("initial_leverage", 20),
        maintenance_margin_rate=0.005,
    )

    # 創建策略
    strategy = strategy_class(broker=broker, data=data, **kwargs)

    # 執行回測
    equity_curve = []
    peak_equity = initial_cash
    max_drawdown = 0.0

    for i, (timestamp, row) in enumerate(data.iterrows()):
        # 調用策略
        strategy.on_bar(i, row)

        # 更新權益
        current_equity = broker.get_current_equity(row["close"])
        equity_curve.append(current_equity)

        # 計算回撤
        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity
        if dd > max_drawdown:
            max_drawdown = dd

    # 計算指標
    final_equity = broker.get_current_equity(data.iloc[-1]["close"])

    # 計算勝率
    trades = broker.trades
    winning = sum(1 for t in trades if t.pnl > 0)
    total_trades = len(trades)
    win_rate = winning / total_trades if total_trades > 0 else 0

    # 計算爆倉次數
    liquidation_count = sum(1 for t in trades if hasattr(t, "is_liquidation") and t.is_liquidation)

    return {
        "final_equity": final_equity,
        "max_drawdown": max_drawdown,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "liquidation_count": liquidation_count,
    }


def main():
    print("=" * 80)
    print("浮雲滾倉策略測試 - 正確實現版本")
    print("=" * 80)

    # 載入數據
    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    print(f"\n載入數據: {data_path}")
    data = load_data(data_path)
    print(f"數據範圍: {data.index[0]} ~ {data.index[-1]}")
    print(f"共 {len(data)} 根 K 線")

    # 測試不同配置
    configs = [
        # === 觸發方式對比 ===
        # 浮雲原版：本金翻倍（100% 利潤）觸發
        {
            "name": "浮雲 10x 本金翻倍觸發",
            "params": {
                "trigger_mode": "double",  # 本金翻倍
                "initial_leverage": 10,
                "position_size_pct": 0.05,
                "stop_loss_mode": "ma20",
            },
        },
        # BiGe 原版：回踩 MA20 觸發
        {
            "name": "BiGe 10x 回踩MA20觸發",
            "params": {
                "trigger_mode": "pullback",  # 回踩 MA20 觸發
                "initial_leverage": 10,
                "position_size_pct": 0.05,
                "stop_loss_mode": "ma20",
            },
        },
        # === 混合模式：回踩 + 本金翻倍 ===
        {
            "name": "混合 10x（回踩+翻倍）",
            "params": {
                "trigger_mode": "hybrid",  # 任一條件觸發
                "initial_leverage": 10,
                "position_size_pct": 0.05,
                "stop_loss_mode": "ma20",
            },
        },
        # === 加倉方式對比 ===
        # 浮雲：100% 浮盈加倉
        {
            "name": "浮雲 10x 浮盈加倉",
            "params": {
                "trigger_mode": "double",
                "add_mode": "floating_pnl",  # 100% 浮盈
                "initial_leverage": 10,
                "position_size_pct": 0.05,
                "stop_loss_mode": "ma20",
            },
        },
        # BiGe：固定 50% 加倉
        {
            "name": "BiGe 10x 固定50%加倉",
            "params": {
                "trigger_mode": "pullback",
                "add_mode": "fixed_50",  # 固定 50%
                "initial_leverage": 10,
                "position_size_pct": 0.05,
                "stop_loss_mode": "ma20",
            },
        },
        # === 最佳組合候選 ===
        {
            "name": "回踩觸發 + 浮盈加倉",
            "params": {
                "trigger_mode": "pullback",
                "add_mode": "floating_pnl",
                "initial_leverage": 10,
                "position_size_pct": 0.05,
                "stop_loss_mode": "ma20",
            },
        },
        {
            "name": "翻倍觸發 + 固定50%加倉",
            "params": {
                "trigger_mode": "double",
                "add_mode": "fixed_50",
                "initial_leverage": 10,
                "position_size_pct": 0.05,
                "stop_loss_mode": "ma20",
            },
        },
    ]

    print("\n" + "=" * 80)
    print("回測結果")
    print("=" * 80)

    results = []

    for config in configs:
        print(f"\n--- {config['name']} ---")

        result = run_strategy_backtest(
            data.copy(), FuYunRollingStrategy, initial_cash=500, **config["params"]
        )

        final_equity = result["final_equity"]
        total_return = (final_equity / 500 - 1) * 100
        max_dd = result.get("max_drawdown", 0) * 100
        total_trades = result.get("total_trades", 0)
        win_rate = result.get("win_rate", 0) * 100
        liquidations = result.get("liquidation_count", 0)

        results.append(
            {
                "name": config["name"],
                "final_equity": final_equity,
                "total_return": total_return,
                "max_drawdown": max_dd,
                "total_trades": total_trades,
                "win_rate": win_rate,
                "liquidations": liquidations,
            }
        )

        print(f"最終權益: ${final_equity:,.2f}")
        print(f"總收益率: {total_return:,.2f}%")
        print(f"最大回撤: {max_dd:.2f}%")
        print(f"總交易數: {total_trades}")
        print(f"勝率: {win_rate:.2f}%")
        print(f"爆倉次數: {liquidations}")

    # 結果對比表
    print("\n" + "=" * 80)
    print("結果對比表")
    print("=" * 80)
    print(f"{'策略':<40} {'收益率':>15} {'最大回撤':>12} {'爆倉':>8}")
    print("-" * 80)

    for r in results:
        print(
            f"{r['name']:<40} {r['total_return']:>14,.2f}% {r['max_drawdown']:>11.2f}% {r['liquidations']:>8}"
        )

    # 分析最佳配置
    print("\n" + "=" * 80)
    print("分析")
    print("=" * 80)

    # 按收益排序
    sorted_by_return = sorted(results, key=lambda x: x["total_return"], reverse=True)
    print(f"\n收益最高: {sorted_by_return[0]['name']}")
    print(f"  收益率: {sorted_by_return[0]['total_return']:,.2f}%")
    print(f"  最大回撤: {sorted_by_return[0]['max_drawdown']:.2f}%")

    # 按風險調整收益排序（收益/回撤）
    for r in results:
        r["risk_adjusted"] = r["total_return"] / max(r["max_drawdown"], 1)

    sorted_by_risk_adj = sorted(results, key=lambda x: x["risk_adjusted"], reverse=True)
    print(f"\n風險調整收益最高: {sorted_by_risk_adj[0]['name']}")
    print(f"  收益率: {sorted_by_risk_adj[0]['total_return']:,.2f}%")
    print(f"  最大回撤: {sorted_by_risk_adj[0]['max_drawdown']:.2f}%")
    print(f"  風險調整收益: {sorted_by_risk_adj[0]['risk_adjusted']:.2f}")

    # 對比說明
    print("\n" + "=" * 80)
    print("對比分析（與之前測試的比較）")
    print("=" * 80)
    print()
    print("之前的錯誤實現：")
    print("  - BiGe + MA20 回踩觸發 + floating_pnl 加倉")
    print("  - 結果：-98%（失敗）")
    print("  - 原因：回踩時浮盈已經消失或為負，無法加倉")
    print()
    print("之前的成功實現：")
    print("  - BiGe + MA20 回踩觸發 + fixed_50% 加倉")
    print("  - 結果：+85,620%（成功）")
    print("  - 原因：固定比例加倉不依賴浮盈，只依賴趨勢信號")
    print()
    print("正確的浮雲滾倉：")
    print("  - BiGe 進場 + 本金翻倍觸發 + 100% 浮盈加倉")
    print("  - 核心：在盈利最大時（而非回踩時）觸發加倉")
    print("  - 槓桿：隨盈利遞減，保護利潤")


if __name__ == "__main__":
    main()
