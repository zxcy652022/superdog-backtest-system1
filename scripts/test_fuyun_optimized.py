#!/usr/bin/env python3
"""
浮雲滾倉策略優化版測試

問題分析：
1. 原版高槓桿（20x）策略爆倉率極高（157-163次）
2. 純粹的浮雲滾倉在高波動市場風險太大

解決方案：
1. 降低初始槓桿：從 20x 降到 5-7x
2. 加入止損確認機制（連續 N 根跌破才止損）
3. 使用更窄的止損範圍（ATR 倍數）
4. 槓桿遞減更緩慢

這個版本結合：
- 幣哥雙均線策略的進場和止損邏輯
- 浮雲滾倉的利潤觸發加倉機制
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.broker import SimulatedBroker
from backtest.engine import BaseStrategy


class OptimizedFuYunStrategy(BaseStrategy):
    """
    優化版浮雲滾倉策略

    與原版的主要差異：
    1. 初始槓桿較低（5-7x 而非 20x）
    2. 加入止損確認機制
    3. 使用 ATR 止損而非純 MA20 止損
    4. 槓桿遞減更平穩
    """

    # 優化版槓桿遞減序列（更保守）
    LEVERAGE_SCHEDULE = [7, 7, 5, 5, 3, 3, 2, 2, 1, 1]

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
            "pullback_tolerance": 0.018,
            "ma20_buffer": 0.02,
            # 浮雲滾倉參數（優化版）
            "profit_threshold": 0.10,  # 利潤達到 10% 時加倉（更保守）
            "initial_leverage": 7,  # 初始槓桿 7x（更保守）
            "position_size_pct": 0.10,  # 初始倉位 10%
            # 止損參數（優化版）
            "stop_loss_mode": "atr",  # 使用 ATR 止損
            "atr_stop_multiplier": 2.5,  # ATR 止損倍數
            "stop_loss_confirm_bars": 8,  # 連續 8 根跌破才止損
            "emergency_stop_atr": 4.0,  # 緊急止損 ATR 倍數
            # 最大加倉次數
            "max_add_count": 5,
            # 趨勢判斷
            "trend_mode": "loose",
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
        self.initial_margin = 0.0

        # 滾倉狀態
        self.add_count = 0
        self.last_add_profit_pct = 0.0
        self.peak_profit_pct = 0.0

        # 止損確認
        self.below_stop_count = 0

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
        idx = min(self.add_count, len(self.LEVERAGE_SCHEDULE) - 1)
        return self.LEVERAGE_SCHEDULE[idx]

    def _is_uptrend(self, row) -> bool:
        """判斷多頭趨勢"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] > row["avg60"]

    def _is_downtrend(self, row) -> bool:
        """判斷空頭趨勢"""
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] < row["avg60"]

    def _check_long_entry(self, row, i) -> bool:
        """多單進場條件"""
        p = self.params
        close = row["close"]
        low = row["low"]
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return False

        if not self._is_uptrend(row):
            return False

        near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
        not_break_ma20 = low > avg20 * (1 - p["ma20_buffer"])
        bullish_close = close > avg20

        return near_ma20 and not_break_ma20 and bullish_close

    def _check_short_entry(self, row, i) -> bool:
        """空單進場條件"""
        p = self.params
        close = row["close"]
        high = row["high"]
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return False

        if not self._is_downtrend(row):
            return False

        near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
        not_break_ma20 = high < avg20 * (1 + p["ma20_buffer"])
        bearish_close = close < avg20

        return near_ma20 and not_break_ma20 and bearish_close

    def _calculate_stop_loss(self, row, direction: str) -> float:
        """計算止損位置 - 使用 ATR"""
        p = self.params
        close = row["close"]
        atr = row["atr"]

        if pd.isna(atr) or atr <= 0:
            # 回退到 MA20 止損
            avg20 = row["avg20"]
            if direction == "long":
                return avg20 * (1 - p["ma20_buffer"])
            else:
                return avg20 * (1 + p["ma20_buffer"])

        multiplier = p["atr_stop_multiplier"]
        if direction == "long":
            return close - atr * multiplier
        else:
            return close + atr * multiplier

    def _calculate_current_profit_pct(self, current_price: float) -> float:
        """計算當前利潤百分比"""
        if self.initial_margin <= 0:
            return 0.0

        if self.broker.is_long:
            unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
        else:
            unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

        return unrealized_pnl / self.initial_margin

    def _check_add_position_trigger(self, current_price: float) -> bool:
        """檢查是否觸發加倉"""
        p = self.params

        if not self.broker.has_position:
            return False

        if self.add_count >= p["max_add_count"]:
            return False

        current_profit_pct = self._calculate_current_profit_pct(current_price)

        if current_profit_pct <= 0:
            return False

        threshold = p["profit_threshold"]
        next_threshold = (self.add_count + 1) * threshold

        if current_profit_pct >= next_threshold:
            return True

        return False

    def _execute_add_position(self, current_price: float, current_time):
        """執行加倉"""
        # 計算當前浮盈
        if self.broker.is_long:
            unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
        else:
            unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

        if unrealized_pnl <= 0:
            return False

        # 更新槓桿
        new_leverage = self._get_current_leverage()
        self.broker.leverage = new_leverage

        # 計算加倉數量：使用 50% 浮盈作為新保證金（更保守）
        add_margin = unrealized_pnl * 0.5
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

    def _check_emergency_stop(self, row) -> bool:
        """檢查緊急止損"""
        p = self.params
        emergency_atr = p.get("emergency_stop_atr", 0)

        if emergency_atr <= 0:
            return False

        atr = row["atr"]
        avg20 = row["avg20"]

        if pd.isna(atr) or pd.isna(avg20) or atr <= 0:
            return False

        if self.broker.is_long:
            low = row["low"]
            breach = avg20 - low
            if breach > 0 and breach > emergency_atr * atr:
                return True

        elif self.broker.is_short:
            high = row["high"]
            breach = high - avg20
            if breach > 0 and breach > emergency_atr * atr:
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

        self.broker.leverage = p["initial_leverage"]
        self.add_count = 0

        equity = self.broker.get_current_equity(entry_price)
        margin = equity * p["position_size_pct"]
        position_value = margin * p["initial_leverage"]
        qty = position_value / entry_price

        if qty > 0:
            success = self.broker.buy(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = self._calculate_stop_loss(row, "long")
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

        self.broker.leverage = p["initial_leverage"]
        self.add_count = 0

        equity = self.broker.get_current_equity(entry_price)
        margin = equity * p["position_size_pct"]
        position_value = margin * p["initial_leverage"]
        qty = position_value / entry_price

        if qty > 0:
            success = self.broker.sell(qty, entry_price, current_time)
            if success:
                self.entry_price = entry_price
                self.avg_entry_price = entry_price
                self.stop_loss = self._calculate_stop_loss(row, "short")
                self.total_qty = qty
                self.initial_margin = margin
                self.entry_bar = bar_index
                self.trade_direction = "short"
                self.below_stop_count = 0
                self.last_add_profit_pct = 0.0
                self.peak_profit_pct = 0.0

    def _update_trailing_stop(self, row):
        """更新追蹤止損"""
        p = self.params
        close = row["close"]
        atr = row["atr"]

        if pd.isna(atr) or atr <= 0 or self.stop_loss is None:
            return

        multiplier = p["atr_stop_multiplier"]

        if self.broker.is_long:
            new_stop = close - atr * multiplier
            if new_stop > self.stop_loss:
                self.stop_loss = new_stop
        elif self.broker.is_short:
            new_stop = close + atr * multiplier
            if new_stop < self.stop_loss:
                self.stop_loss = new_stop

    def _manage_position(self, row, current_time, bar_index: int):
        """管理現有倉位"""
        p = self.params
        current_price = row["close"]
        high = row["high"]
        low = row["low"]

        # 更新追蹤止損
        self._update_trailing_stop(row)

        # === 緊急止損 ===
        if self._check_emergency_stop(row):
            if self.broker.is_long:
                self.broker.sell(self.broker.position_qty, self.stop_loss, current_time)
            else:
                self.broker.buy(self.broker.position_qty, self.stop_loss, current_time)
            self._reset_position_state()
            return

        # === 止損檢查 ===
        if self.broker.is_long:
            if low <= self.stop_loss:
                self.below_stop_count += 1
                if self.below_stop_count >= p["stop_loss_confirm_bars"]:
                    self.broker.sell(self.broker.position_qty, self.stop_loss, current_time)
                    self._reset_position_state()
                    return
            else:
                self.below_stop_count = 0

        elif self.broker.is_short:
            if high >= self.stop_loss:
                self.below_stop_count += 1
                if self.below_stop_count >= p["stop_loss_confirm_bars"]:
                    self.broker.buy(self.broker.position_qty, self.stop_loss, current_time)
                    self._reset_position_state()
                    return
            else:
                self.below_stop_count = 0

        # === 浮雲滾倉：加倉檢查 ===
        if self._check_add_position_trigger(current_price):
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
        self.broker.leverage = self.params["initial_leverage"]


def load_data(filepath: str) -> pd.DataFrame:
    """載入數據"""
    df = pd.read_csv(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def run_strategy_backtest(data: pd.DataFrame, strategy_class, initial_cash: float = 500, **kwargs):
    """執行回測"""
    broker = SimulatedBroker(
        initial_cash=initial_cash,
        fee_rate=0.0004,
        leverage=kwargs.get("initial_leverage", 7),
        maintenance_margin_rate=0.005,
    )

    strategy = strategy_class(broker=broker, data=data, **kwargs)

    equity_curve = []
    peak_equity = initial_cash
    max_drawdown = 0.0
    add_count_total = 0

    for i, (timestamp, row) in enumerate(data.iterrows()):
        strategy.on_bar(i, row)

        current_equity = broker.get_current_equity(row["close"])
        equity_curve.append(current_equity)

        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity
        if dd > max_drawdown:
            max_drawdown = dd

        # 統計加倉次數
        if hasattr(strategy, "add_count") and strategy.add_count > add_count_total:
            add_count_total = strategy.add_count

    final_equity = broker.get_current_equity(data.iloc[-1]["close"])
    trades = broker.trades
    winning = sum(1 for t in trades if t.pnl > 0)
    total_trades = len(trades)
    win_rate = winning / total_trades if total_trades > 0 else 0
    liquidation_count = sum(1 for t in trades if hasattr(t, "is_liquidation") and t.is_liquidation)

    return {
        "final_equity": final_equity,
        "max_drawdown": max_drawdown,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "liquidation_count": liquidation_count,
        "equity_curve": equity_curve,
    }


def main():
    print("=" * 80)
    print("浮雲滾倉策略優化版測試")
    print("=" * 80)

    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    print(f"\n載入數據: {data_path}")
    data = load_data(data_path)
    print(f"數據範圍: {data.index[0]} ~ {data.index[-1]}")
    print(f"共 {len(data)} 根 K 線")

    # 測試不同配置
    configs = [
        {
            "name": "優化版 v1 (7x 槓桿, 10% 閾值)",
            "params": {
                "profit_threshold": 0.10,
                "initial_leverage": 7,
                "position_size_pct": 0.10,
                "atr_stop_multiplier": 2.5,
            },
        },
        {
            "name": "優化版 v2 (5x 槓桿, 8% 閾值)",
            "params": {
                "profit_threshold": 0.08,
                "initial_leverage": 5,
                "position_size_pct": 0.10,
                "atr_stop_multiplier": 2.0,
            },
        },
        {
            "name": "優化版 v3 (10x 槓桿, 15% 閾值)",
            "params": {
                "profit_threshold": 0.15,
                "initial_leverage": 10,
                "position_size_pct": 0.10,
                "atr_stop_multiplier": 3.0,
            },
        },
        {
            "name": "保守版 (3x 槓桿, 5% 閾值)",
            "params": {
                "profit_threshold": 0.05,
                "initial_leverage": 3,
                "position_size_pct": 0.10,
                "atr_stop_multiplier": 2.0,
            },
        },
        {
            "name": "原始幣哥策略對比 (固定50%加倉)",
            "params": {
                "profit_threshold": 999.0,  # 禁用利潤觸發
                "initial_leverage": 7,
                "position_size_pct": 0.10,
                "atr_stop_multiplier": 2.5,
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
            data.copy(), OptimizedFuYunStrategy, initial_cash=500, **config["params"]
        )

        final_equity = result["final_equity"]
        total_return = (final_equity / 500 - 1) * 100
        max_dd = result["max_drawdown"] * 100
        total_trades = result["total_trades"]
        win_rate = result["win_rate"] * 100
        liquidations = result["liquidation_count"]

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
    print(f"{'策略':<40} {'收益率':>15} {'最大回撤':>12} {'爆倉':>8} {'勝率':>10}")
    print("-" * 90)

    for r in results:
        print(
            f"{r['name']:<40} {r['total_return']:>14,.2f}% {r['max_drawdown']:>11.2f}% {r['liquidations']:>8} {r['win_rate']:>9.2f}%"
        )

    # 分析
    print("\n" + "=" * 80)
    print("分析結論")
    print("=" * 80)

    # 找出最佳策略
    profitable = [r for r in results if r["total_return"] > 0]
    if profitable:
        best = max(profitable, key=lambda x: x["total_return"] / max(x["max_drawdown"], 1))
        print(f"\n風險調整收益最佳: {best['name']}")
        print(f"  收益率: {best['total_return']:,.2f}%")
        print(f"  最大回撤: {best['max_drawdown']:.2f}%")
        print(f"  收益/回撤比: {best['total_return']/max(best['max_drawdown'],1):.2f}")
    else:
        print("\n所有策略都虧損，需要進一步優化")
        best_loss = min(results, key=lambda x: abs(x["total_return"]))
        print(f"虧損最小: {best_loss['name']}")
        print(f"  收益率: {best_loss['total_return']:,.2f}%")


if __name__ == "__main__":
    main()
