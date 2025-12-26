#!/usr/bin/env python3
"""
浮雲滾倉策略 - 逐年績效分析（標準報表格式）

初始資金: $500 USDT
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.broker import SimulatedBroker
from backtest.engine import BaseStrategy


class OptimizedFuYunStrategy(BaseStrategy):
    """優化版浮雲滾倉策略"""

    LEVERAGE_SCHEDULE = [7, 7, 5, 5, 3, 3, 2, 2, 1, 1]

    def __init__(self, broker, data, **kwargs):
        self.broker = broker
        self.data = data

        self.params = {
            "ma_len_short": 20,
            "ma_len_mid": 60,
            "ma_len_long": 120,
            "pullback_tolerance": 0.018,
            "ma20_buffer": 0.02,
            "profit_threshold": 0.08,
            "initial_leverage": 5,
            "position_size_pct": 0.10,
            "stop_loss_mode": "atr",
            "atr_stop_multiplier": 2.0,
            "stop_loss_confirm_bars": 8,
            "emergency_stop_atr": 4.0,
            "max_add_count": 5,
            "trend_mode": "loose",
        }
        self.params.update(kwargs)

        self.broker.leverage = self.params["initial_leverage"]

        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.entry_bar = -999
        self.trade_direction = None
        self.total_qty = 0.0
        self.initial_margin = 0.0
        self.add_count = 0
        self.last_add_profit_pct = 0.0
        self.peak_profit_pct = 0.0
        self.below_stop_count = 0

        # 統計用
        self.long_pnl = 0.0
        self.short_pnl = 0.0

        self._calculate_all_indicators()

    def _calculate_all_indicators(self):
        p = self.params
        df = self.data

        df["ma20"] = df["close"].rolling(p["ma_len_short"]).mean()
        df["ma60"] = df["close"].rolling(p["ma_len_mid"]).mean()
        df["ma120"] = df["close"].rolling(p["ma_len_long"]).mean()
        df["ema20"] = df["close"].ewm(span=p["ma_len_short"], adjust=False).mean()
        df["ema60"] = df["close"].ewm(span=p["ma_len_mid"], adjust=False).mean()
        df["ema120"] = df["close"].ewm(span=p["ma_len_long"], adjust=False).mean()
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2
        df["avg120"] = (df["ma120"] + df["ema120"]) / 2

        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()

    def _get_current_leverage(self) -> int:
        idx = min(self.add_count, len(self.LEVERAGE_SCHEDULE) - 1)
        return self.LEVERAGE_SCHEDULE[idx]

    def _is_uptrend(self, row) -> bool:
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] > row["avg60"]

    def _is_downtrend(self, row) -> bool:
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] < row["avg60"]

    def _check_long_entry(self, row, i) -> bool:
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
        p = self.params
        close = row["close"]
        atr = row["atr"]

        if pd.isna(atr) or atr <= 0:
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
        if self.initial_margin <= 0:
            return 0.0

        if self.broker.is_long:
            unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
        else:
            unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

        return unrealized_pnl / self.initial_margin

    def _check_add_position_trigger(self, current_price: float) -> bool:
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

        return current_profit_pct >= next_threshold

    def _execute_add_position(self, current_price: float, current_time):
        if self.broker.is_long:
            unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
        else:
            unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

        if unrealized_pnl <= 0:
            return False

        new_leverage = self._get_current_leverage()
        self.broker.leverage = new_leverage

        add_margin = unrealized_pnl * 0.5
        add_position_value = add_margin * new_leverage
        add_qty = add_position_value / current_price

        if add_qty <= 0:
            return False

        if self.broker.is_long:
            success = self.broker.buy(add_qty, current_price, current_time)
        else:
            success = self.broker.sell(add_qty, current_price, current_time)

        if success:
            old_total_cost = self.avg_entry_price * self.total_qty
            new_total_cost = old_total_cost + current_price * add_qty
            self.total_qty += add_qty
            self.avg_entry_price = new_total_cost / self.total_qty
            self.add_count += 1
            self.last_add_profit_pct = self._calculate_current_profit_pct(current_price)
            return True

        return False

    def _check_emergency_stop(self, row) -> bool:
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
        if i < self.params["ma_len_long"]:
            return

        current_time = row.name
        current_price = row["close"]

        if self.broker.has_position:
            if self.broker.check_liquidation_in_bar(row):
                liq_price = self.broker.get_liquidation_price()
                self.broker.process_liquidation(current_time, liq_price)
                self._reset_position_state()
                return

            self._manage_position(row, current_time, i)
            return

        if self._check_long_entry(row, i):
            self._enter_long(row, current_time, i)
        elif self._check_short_entry(row, i):
            self._enter_short(row, current_time, i)

    def _enter_long(self, row, current_time, bar_index: int):
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

    def _enter_short(self, row, current_time, bar_index: int):
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

    def _update_trailing_stop(self, row):
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
        p = self.params
        current_price = row["close"]
        high = row["high"]
        low = row["low"]

        self._update_trailing_stop(row)

        if self._check_emergency_stop(row):
            if self.broker.is_long:
                self.broker.sell(self.broker.position_qty, self.stop_loss, current_time)
            else:
                self.broker.buy(self.broker.position_qty, self.stop_loss, current_time)
            self._reset_position_state()
            return

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

        if self._check_add_position_trigger(current_price):
            self._execute_add_position(current_price, current_time)

    def _reset_position_state(self):
        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.total_qty = 0.0
        self.initial_margin = 0.0
        self.add_count = 0
        self.below_stop_count = 0
        self.trade_direction = None
        self.broker.leverage = self.params["initial_leverage"]


def load_data(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def run_backtest_period(data: pd.DataFrame, initial_cash: float, **kwargs):
    """執行回測並返回詳細統計"""
    broker = SimulatedBroker(
        initial_cash=initial_cash,
        fee_rate=0.0004,
        leverage=kwargs.get("initial_leverage", 5),
        maintenance_margin_rate=0.005,
    )

    strategy = OptimizedFuYunStrategy(broker=broker, data=data, **kwargs)

    peak_equity = initial_cash
    max_drawdown = 0.0

    for i, (timestamp, row) in enumerate(data.iterrows()):
        strategy.on_bar(i, row)

        current_equity = broker.get_current_equity(row["close"])
        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity
        if dd > max_drawdown:
            max_drawdown = dd

    final_equity = broker.get_current_equity(data.iloc[-1]["close"])
    trades = broker.trades

    # 計算勝率
    winning = sum(1 for t in trades if t.pnl > 0)
    total_trades = len(trades)
    win_rate = winning / total_trades if total_trades > 0 else 0

    # 計算爆倉次數
    liquidations = sum(1 for t in trades if hasattr(t, "is_liquidation") and t.is_liquidation)

    # 計算做多/做空盈虧
    long_pnl = 0.0
    short_pnl = 0.0
    for t in trades:
        if hasattr(t, "direction"):
            if t.direction == "long":
                long_pnl += t.pnl
            else:
                short_pnl += t.pnl
        else:
            # 如果沒有 direction 屬性，根據 qty 正負判斷
            if t.qty > 0:
                long_pnl += t.pnl
            else:
                short_pnl += t.pnl

    # Buy & Hold 收益
    start_price = data.iloc[0]["close"]
    end_price = data.iloc[-1]["close"]
    bh_return = (end_price / start_price - 1) * 100

    return {
        "final_equity": final_equity,
        "max_drawdown": max_drawdown,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "liquidations": liquidations,
        "long_pnl": long_pnl,
        "short_pnl": short_pnl,
        "bh_return": bh_return,
    }


def format_pnl(pnl: float) -> str:
    """格式化盈虧"""
    if abs(pnl) >= 1e9:
        return f"{'+' if pnl >= 0 else ''}{pnl/1e9:.1f}B"
    elif abs(pnl) >= 1e6:
        return f"{'+' if pnl >= 0 else ''}{pnl/1e6:.1f}M"
    elif abs(pnl) >= 1e3:
        return f"{'+' if pnl >= 0 else ''}${pnl/1e3:.1f}K"
    else:
        return f"{'+' if pnl >= 0 else ''}${pnl:.0f}"


def format_equity(equity: float) -> str:
    """格式化資金"""
    if equity >= 1e9:
        return f"${equity/1e9:.1f}B"
    elif equity >= 1e6:
        return f"${equity/1e6:.1f}M"
    elif equity >= 1e3:
        return f"${equity/1e3:.1f}K"
    else:
        return f"${equity:.0f}"


def main():
    print("=" * 100)
    print("浮雲滾倉策略 - 逐年績效分析")
    print("=" * 100)
    print("\n策略配置: 5x 槓桿, 8% 利潤閾值加倉, ATR 2.0 止損")
    print("初始資金: $500 USDT")

    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    data = load_data(data_path)

    # 逐年分析（複利累積）
    print("\n【逐年回測】")
    print(f"{'年份':<6} {'收益':>10} {'累計資本':>12} {'回撤':>8} {'勝率':>6} {'做多':>12} {'做空':>12} {'BH':>8}")
    print("-" * 85)

    cumulative_equity = 500
    years = range(2019, 2026)

    for year in years:
        year_data = data[data.index.year == year].copy()
        if len(year_data) < 120:
            continue

        result = run_backtest_period(year_data, initial_cash=cumulative_equity)

        year_return = (result["final_equity"] / cumulative_equity - 1) * 100
        ret_str = f"+{year_return:.0f}%" if year_return >= 0 else f"{year_return:.0f}%"

        print(
            f"{year:<6} {ret_str:>10} {format_equity(result['final_equity']):>12} "
            f"{-result['max_drawdown']*100:>7.0f}% {result['win_rate']*100:>5.0f}% "
            f"{format_pnl(result['long_pnl']):>12} {format_pnl(result['short_pnl']):>12} "
            f"{'+' if result['bh_return'] >= 0 else ''}{result['bh_return']:.0f}%"
        )

        cumulative_equity = result["final_equity"]

    print("-" * 85)
    total_return = (cumulative_equity / 500 - 1) * 100
    print(
        f"{'總計':<6} {'+' + f'{total_return:.0f}' if total_return >= 0 else f'{total_return:.0f}'}% {format_equity(cumulative_equity):>12}"
    )

    # 完整回測統計
    print("\n" + "=" * 100)
    print("完整回測統計 (2019-2025)")
    print("=" * 100)

    result = run_backtest_period(data.copy(), initial_cash=500)
    total_return = (result["final_equity"] / 500 - 1) * 100

    print(
        f"""
初始資金:     $500
最終資金:     {format_equity(result['final_equity'])}
總收益率:     +{total_return:,.0f}%
收益倍數:     {result['final_equity']/500:.1f}x
最大回撤:     {result['max_drawdown']*100:.1f}%
總交易數:     {result['total_trades']}
勝率:         {result['win_rate']*100:.1f}%
爆倉次數:     {result['liquidations']}
做多盈虧:     {format_pnl(result['long_pnl'])}
做空盈虧:     {format_pnl(result['short_pnl'])}
Buy & Hold:   {'+' if result['bh_return'] >= 0 else ''}{result['bh_return']:.0f}%
"""
    )


if __name__ == "__main__":
    main()
