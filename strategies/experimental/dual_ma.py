"""
DualMA Strategy v2.0 - 雙均線趨勢跟隨策略（加倉版）

核心邏輯：
1. 均線密集 → 發散 → 趨勢
2. 均線密集突破進場
3. 回踩未跌破 → 加倉
4. 固定止損 + 移動止損
5. 三段止盈（可調 R 值）
6. 風險型倉位管理
7. 支援槓桿交易

v2.0 新增：
- 回踩加倉機制（無上限）
- 加倉幅度可調（固定比例 / 浮盈百分比）
- 槓桿支援
- 更多可調參數

API: v0.3 Legacy (需要狀態保存)
Version: v2.0
Author: DDragon
"""

import pandas as pd

from backtest.engine import BaseStrategy


class DualMAStrategyV2(BaseStrategy):
    """
    DualMA 策略 v2.0 - 加倉版

    進場：均線密集突破後回踩確認
    加倉：回踩均線未跌破
    止損：cluster_low 或 swing_low
    止盈：可調 R 值三段
    """

    # ===== 類別方法：參數定義 =====

    @classmethod
    def get_default_parameters(cls):
        """策略參數定義"""
        return {
            # === 均線參數 ===
            "ma_len_short": 20,
            "ma_len_mid": 60,
            "ma_len_long": 120,
            "use_ema": True,
            # === 密集檢測 ===
            "cluster_threshold": 0.01,  # 1%
            # === 風險管理 ===
            "risk_per_trade_pct": 0.01,  # 每筆風險 1%
            "leverage": 10,  # 槓桿倍數
            # === 止盈參數（R 值）===
            "tp1_rr": 2.0,
            "tp2_rr": 4.0,
            "tp3_rr": 8.0,
            # === 分批止盈比例 ===
            "tp1_pct": 0.3,
            "tp2_pct": 0.3,
            # tp3_pct = 1.0 - tp1_pct - tp2_pct (剩餘)
            # === 加倉參數 ===
            "enable_add_position": True,  # 啟用加倉
            "add_position_mode": "floating_pnl",  # "fixed" 或 "floating_pnl"
            "add_position_fixed_pct": 0.5,  # 固定模式：每次加倉 50% 原始倉位
            "add_position_pnl_pct": 1.0,  # 浮盈模式：加倉金額 = 浮盈 * 100%
            "add_position_min_interval": 3,  # 最少間隔 3 根 K 線
            # === 回踩確認 ===
            "pullback_tolerance": 0.02,  # 2%
            # === Swing 回溯期 ===
            "swing_lookback": 20,
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

        # 狀態變數
        self.cluster_high = None
        self.cluster_low = None
        self.cluster_active = False
        self.cluster_break_confirmed = False

        # 倉位狀態
        self.entry_price = None
        self.avg_entry_price = None  # 平均入場價（加倉後）
        self.stop_loss = None
        self.tp1 = None
        self.tp2 = None
        self.tp3 = None
        self.tp1_hit = False
        self.tp2_hit = False
        self.initial_qty = 0.0
        self.total_qty = 0.0  # 總倉位（含加倉）

        # 加倉狀態
        self.add_count = 0  # 加倉次數
        self.last_add_bar = -999  # 上次加倉的 K 線索引
        self.entry_bar = -999  # 進場的 K 線索引

        # 預計算指標
        self._calculate_all_indicators()

    def set_parameters(self, **kwargs):
        """設置策略參數"""
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
        # 更新 broker 槓桿
        self.broker.leverage = self.params["leverage"]
        # 重新計算指標
        self._calculate_all_indicators()

    # ===== 核心邏輯：指標計算 =====

    def _calculate_all_indicators(self):
        """預先計算所有技術指標"""
        p = self.params
        df = self.data

        # 計算 SMA
        df["ma20"] = df["close"].rolling(p["ma_len_short"]).mean()
        df["ma60"] = df["close"].rolling(p["ma_len_mid"]).mean()
        df["ma120"] = df["close"].rolling(p["ma_len_long"]).mean()

        if p["use_ema"]:
            # 計算 EMA
            df["ema20"] = df["close"].ewm(span=p["ma_len_short"], adjust=False).mean()
            df["ema60"] = df["close"].ewm(span=p["ma_len_mid"], adjust=False).mean()
            df["ema120"] = df["close"].ewm(span=p["ma_len_long"], adjust=False).mean()

            # 綜合均線
            df["avg20"] = (df["ma20"] + df["ema20"]) / 2
            df["avg60"] = (df["ma60"] + df["ema60"]) / 2
            df["avg120"] = (df["ma120"] + df["ema120"]) / 2
        else:
            df["avg20"] = df["ma20"]
            df["avg60"] = df["ma60"]
            df["avg120"] = df["ma120"]

        # Swing Low/High
        df["swing_low"] = df["low"].rolling(p["swing_lookback"]).min()
        df["swing_high"] = df["high"].rolling(p["swing_lookback"]).max()

        # ATR（用於動態止損）
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

    def _detect_cluster(self, row):
        """檢測均線密集"""
        p = self.params
        close = row["close"]
        avg20 = row["avg20"]
        avg60 = row["avg60"]
        avg120 = row["avg120"]

        if pd.isna(avg20) or pd.isna(avg60) or pd.isna(avg120):
            return False

        dist_20_60 = abs(avg20 - avg60) / close
        dist_60_120 = abs(avg60 - avg120) / close

        return dist_20_60 < p["cluster_threshold"] and dist_60_120 < p["cluster_threshold"]

    def _is_uptrend(self, row):
        """判斷多頭排列"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]) or pd.isna(row["avg120"]):
            return False
        return row["avg20"] > row["avg60"] and row["avg60"] > row["avg120"]

    def _is_downtrend(self, row):
        """判斷空頭排列"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]) or pd.isna(row["avg120"]):
            return False
        return row["avg20"] < row["avg60"] and row["avg60"] < row["avg120"]

    # ===== 核心邏輯：進場 =====

    def _check_long_entry_mode_a(self, row):
        """多單進場：均線密集突破 + 回踩確認"""
        p = self.params

        if self.cluster_high is None:
            return False

        if not self._is_uptrend(row):
            return False

        close = row["close"]
        low = row["low"]
        avg20 = row["avg20"]

        near_avg20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
        above_cluster = low > self.cluster_low
        bullish_close = close > avg20

        if near_avg20 and above_cluster and bullish_close:
            self.cluster_break_confirmed = True
            return True

        return False

    def _check_short_entry_mode_a(self, row):
        """空單進場：均線密集突破（空頭）"""
        p = self.params

        if self.cluster_low is None:
            return False

        if not self._is_downtrend(row):
            return False

        close = row["close"]
        high = row["high"]
        avg20 = row["avg20"]

        near_avg20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
        below_cluster = high < self.cluster_high
        bearish_close = close < avg20

        if near_avg20 and below_cluster and bearish_close:
            self.cluster_break_confirmed = True
            return True

        return False

    # ===== 核心邏輯：加倉 =====

    def _check_add_position(self, row, i):
        """
        檢查是否應該加倉

        條件：
        1. 啟用加倉
        2. 有持倉
        3. 距離上次加倉/進場超過最小間隔
        4. 回踩均線未跌破止損

        Returns:
            bool: 是否應該加倉
        """
        p = self.params

        if not p["enable_add_position"]:
            return False

        if not self.broker.has_position:
            return False

        # 檢查間隔
        bars_since_last = i - max(self.entry_bar, self.last_add_bar)
        if bars_since_last < p["add_position_min_interval"]:
            return False

        close = row["close"]
        low = row["low"]
        high = row["high"]
        avg20 = row["avg20"]

        if self.broker.is_long:
            # 多單加倉條件：回踩到 avg20 附近，未跌破止損，收盤仍在 avg20 之上
            near_avg20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            above_stop = low > self.stop_loss
            bullish_close = close > avg20

            return near_avg20 and above_stop and bullish_close

        elif self.broker.is_short:
            # 空單加倉條件：反彈到 avg20 附近，未突破止損，收盤仍在 avg20 之下
            near_avg20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            below_stop = high < self.stop_loss
            bearish_close = close < avg20

            return near_avg20 and below_stop and bearish_close

        return False

    def _calculate_add_position_qty(self, current_price):
        """
        計算加倉數量

        Returns:
            float: 加倉數量
        """
        p = self.params

        if p["add_position_mode"] == "fixed":
            # 固定模式：原始倉位的百分比
            return self.initial_qty * p["add_position_fixed_pct"]

        elif p["add_position_mode"] == "floating_pnl":
            # 浮盈模式：浮盈的百分比
            if self.avg_entry_price is None:
                return 0

            if self.broker.is_long:
                unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
            else:  # short
                unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

            if unrealized_pnl <= 0:
                return 0  # 沒有浮盈不加倉

            # 用浮盈的百分比作為加倉金額
            add_amount = unrealized_pnl * p["add_position_pnl_pct"]
            add_qty = add_amount / current_price

            return add_qty

        return 0

    # ===== 核心邏輯：倉位管理 =====

    def _calculate_position_size(self, entry_price, stop_loss, current_price):
        """計算風險型倉位大小"""
        p = self.params
        equity = self.broker.get_current_equity(current_price)
        risk_amount = equity * p["risk_per_trade_pct"]
        sl_distance = abs(entry_price - stop_loss)

        if sl_distance == 0:
            return 0

        qty = risk_amount / sl_distance
        return qty

    def _calculate_stop_loss(self, row, direction):
        """計算止損位置"""
        if direction == "long":
            sl_candidates = []
            if self.cluster_low is not None:
                sl_candidates.append(self.cluster_low * 0.999)
            if not pd.isna(row["swing_low"]):
                sl_candidates.append(row["swing_low"] * 0.999)

            return min(sl_candidates) if sl_candidates else row["close"] * 0.95

        else:  # short
            sl_candidates = []
            if self.cluster_high is not None:
                sl_candidates.append(self.cluster_high * 1.001)
            if not pd.isna(row["swing_high"]):
                sl_candidates.append(row["swing_high"] * 1.001)

            return max(sl_candidates) if sl_candidates else row["close"] * 1.05

    def _calculate_take_profits(self, entry_price, stop_loss, direction):
        """計算三個止盈位"""
        p = self.params
        R = abs(entry_price - stop_loss)

        if direction == "long":
            tp1 = entry_price + p["tp1_rr"] * R
            tp2 = entry_price + p["tp2_rr"] * R
            tp3 = entry_price + p["tp3_rr"] * R
        else:  # short
            tp1 = entry_price - p["tp1_rr"] * R
            tp2 = entry_price - p["tp2_rr"] * R
            tp3 = entry_price - p["tp3_rr"] * R

        return tp1, tp2, tp3

    def _update_avg_entry_price(self, new_qty, new_price):
        """更新平均入場價"""
        if self.avg_entry_price is None or self.total_qty == 0:
            self.avg_entry_price = new_price
            self.total_qty = new_qty
        else:
            # 加權平均
            total_cost = self.avg_entry_price * self.total_qty + new_price * new_qty
            self.total_qty += new_qty
            self.avg_entry_price = total_cost / self.total_qty

    # ===== 核心邏輯：主循環 =====

    def on_bar(self, i: int, row: pd.Series):
        """每根 K 線調用一次"""
        if i < self.params["ma_len_long"]:
            return

        current_time = row.name

        # === 1. 更新 Cluster 狀態 ===
        is_cluster = self._detect_cluster(row)

        if is_cluster:
            avg_values = [row["avg20"], row["avg60"], row["avg120"]]
            if not self.cluster_active:
                self.cluster_active = True
                self.cluster_high = max(avg_values)
                self.cluster_low = min(avg_values)
            else:
                if self.cluster_high is not None:
                    avg_values_high = avg_values + [self.cluster_high]
                    self.cluster_high = max(avg_values_high)
                else:
                    self.cluster_high = max(avg_values)

                if self.cluster_low is not None:
                    avg_values_low = avg_values + [self.cluster_low]
                    self.cluster_low = min(avg_values_low)
                else:
                    self.cluster_low = min(avg_values)
        else:
            if self.cluster_active:
                self.cluster_active = False

        # === 2. 倉位管理：止盈止損 ===
        if self.broker.has_position:
            self._manage_position(row, current_time, i)
            return

        # === 3. 進場信號檢測（無倉位時）===
        if self._check_long_entry_mode_a(row):
            self._enter_long(row, current_time, i)
        elif self._check_short_entry_mode_a(row):
            self._enter_short(row, current_time, i)

    def _enter_long(self, row, current_time, bar_index):
        """執行多單進場"""
        entry_price = row["close"]
        stop_loss = self._calculate_stop_loss(row, "long")
        qty = self._calculate_position_size(entry_price, stop_loss, entry_price)

        if qty > 0:
            success = self.broker.buy(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = stop_loss
                self.tp1, self.tp2, self.tp3 = self._calculate_take_profits(
                    entry_price, stop_loss, "long"
                )
                self.tp1_hit = False
                self.tp2_hit = False
                self.initial_qty = qty
                self.total_qty = qty
                self.add_count = 0
                self.entry_bar = bar_index
                self.last_add_bar = bar_index
                # 重置 cluster 狀態
                self.cluster_high = None
                self.cluster_low = None

    def _enter_short(self, row, current_time, bar_index):
        """執行空單進場"""
        entry_price = row["close"]
        stop_loss = self._calculate_stop_loss(row, "short")
        qty = self._calculate_position_size(entry_price, stop_loss, entry_price)

        if qty > 0:
            success = self.broker.sell(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = stop_loss
                self.tp1, self.tp2, self.tp3 = self._calculate_take_profits(
                    entry_price, stop_loss, "short"
                )
                self.tp1_hit = False
                self.tp2_hit = False
                self.initial_qty = qty
                self.total_qty = qty
                self.add_count = 0
                self.entry_bar = bar_index
                self.last_add_bar = bar_index
                self.cluster_high = None
                self.cluster_low = None

    def _manage_position(self, row, current_time, bar_index):
        """管理現有倉位（止損、止盈、加倉）"""
        p = self.params
        current_price = row["close"]
        high = row["high"]
        low = row["low"]

        if self.broker.is_long:
            # === 多單管理 ===
            # 止損
            if low <= self.stop_loss:
                self.broker.sell(self.broker.position_qty, self.stop_loss, current_time)
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
                        # 重新計算止盈位（基於新的平均入場價）
                        self.tp1, self.tp2, self.tp3 = self._calculate_take_profits(
                            self.avg_entry_price, self.stop_loss, "long"
                        )

            # 三段止盈
            if not self.tp1_hit and high >= self.tp1:
                qty_to_close = self.initial_qty * p["tp1_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.sell(qty_to_close, self.tp1, current_time)
                self.tp1_hit = True
                self.stop_loss = self.entry_price  # 移動止損到保本

            elif self.tp1_hit and not self.tp2_hit and high >= self.tp2:
                qty_to_close = self.initial_qty * p["tp2_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.sell(qty_to_close, self.tp2, current_time)
                self.tp2_hit = True
                self.stop_loss = self.tp1  # 移動止損到 TP1

            elif self.tp2_hit and high >= self.tp3:
                if self.broker.position_qty > 0:
                    self.broker.sell(self.broker.position_qty, self.tp3, current_time)
                self._reset_position_state()

        elif self.broker.is_short:
            # === 空單管理 ===
            # 止損
            if high >= self.stop_loss:
                self.broker.buy(self.broker.position_qty, self.stop_loss, current_time)
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
                            self.avg_entry_price, self.stop_loss, "short"
                        )

            # 三段止盈
            if not self.tp1_hit and low <= self.tp1:
                qty_to_close = self.initial_qty * p["tp1_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.buy(qty_to_close, self.tp1, current_time)
                self.tp1_hit = True
                self.stop_loss = self.entry_price

            elif self.tp1_hit and not self.tp2_hit and low <= self.tp2:
                qty_to_close = self.initial_qty * p["tp2_pct"]
                if qty_to_close > 0 and qty_to_close <= self.broker.position_qty:
                    self.broker.buy(qty_to_close, self.tp2, current_time)
                self.tp2_hit = True
                self.stop_loss = self.tp1

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
        self.add_count = 0
