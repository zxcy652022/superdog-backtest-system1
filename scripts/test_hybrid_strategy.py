#!/usr/bin/env python3
"""
混合策略測試：BiGe 進場 + 利潤觸發 + 浮盈加倉

嘗試結合兩種邏輯的優點：
1. BiGe 的進場邏輯（MA20回踩）
2. 浮雲的加倉邏輯（浮盈達到閾值時用浮盈加倉，非MA回踩觸發）
"""

import sys

sys.path.insert(0, "/Users/ddragon/Projects/superdog-quant")

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd

from backtest.broker import SimulatedBroker as Broker


@dataclass
class HybridPosition:
    """混合策略倉位"""

    direction: str  # 'long' or 'short'
    entry_price: float
    qty: float
    leverage: float
    entry_time: datetime
    add_count: int = 0
    total_cost: float = 0  # 總投入成本


class HybridStrategy:
    """
    混合策略：BiGe進場 + 利潤觸發加倉

    進場：MA20回踩
    加倉觸發：浮盈達到倉位價值的X%時加倉（非MA回踩）
    加倉資金：使用浮盈的100%
    槓桿：加倉時降低槓桿
    """

    def __init__(
        self,
        initial_capital: float = 500,
        initial_leverage: float = 10,
        profit_trigger_pct: float = 0.5,  # 浮盈達到倉位價值50%時觸發加倉
        max_add_count: int = 3,
        leverage_reduction: float = 0.7,  # 每次加倉槓桿降為原來的70%
        stop_loss_pct: float = 0.08,
    ):
        self.initial_capital = initial_capital
        self.initial_leverage = initial_leverage
        self.profit_trigger_pct = profit_trigger_pct
        self.max_add_count = max_add_count
        self.leverage_reduction = leverage_reduction
        self.stop_loss_pct = stop_loss_pct

        self.capital = initial_capital
        self.position: Optional[HybridPosition] = None
        self.trades: List[dict] = []
        self.equity_curve = []
        self.liquidations = 0

    def calculate_ma(self, df: pd.DataFrame, period: int) -> pd.Series:
        return df["close"].rolling(period).mean()

    def get_floating_pnl(self, current_price: float) -> float:
        """計算浮動盈虧"""
        if self.position is None:
            return 0

        if self.position.direction == "long":
            return (current_price - self.position.entry_price) * self.position.qty
        else:
            return (self.position.entry_price - current_price) * self.position.qty

    def get_position_value(self, current_price: float) -> float:
        """計算倉位當前價值"""
        if self.position is None:
            return 0
        return current_price * self.position.qty

    def check_liquidation(self, current_price: float) -> bool:
        """檢查是否爆倉"""
        if self.position is None:
            return False

        floating_pnl = self.get_floating_pnl(current_price)
        # 總權益 = 可用資金 + 保證金 + 浮盈
        margin = self.position.total_cost
        total_equity = self.capital + margin + floating_pnl

        return total_equity <= 0

    def open_position(self, direction: str, price: float, time: datetime):
        """開倉"""
        leverage = self.initial_leverage
        # 使用全部可用資金
        margin = self.capital * 0.9  # 留10%作為緩衝
        position_value = margin * leverage
        qty = position_value / price

        self.position = HybridPosition(
            direction=direction,
            entry_price=price,
            qty=qty,
            leverage=leverage,
            entry_time=time,
            add_count=0,
            total_cost=margin,
        )
        self.capital -= margin

    def add_position(self, price: float, time: datetime):
        """加倉：使用浮盈"""
        if self.position is None or self.position.add_count >= self.max_add_count:
            return False

        floating_pnl = self.get_floating_pnl(price)
        if floating_pnl <= 0:
            return False

        # 降低槓桿
        new_leverage = self.position.leverage * self.leverage_reduction

        # 用浮盈的100%加倉（但浮盈要從帳戶中扣除，不能重複使用）
        add_margin = floating_pnl
        add_value = add_margin * new_leverage
        add_qty = add_value / price

        # 計算新的平均入場價（加權平均）
        total_value_before = self.position.entry_price * self.position.qty
        total_value_after = total_value_before + price * add_qty
        new_qty = self.position.qty + add_qty
        new_entry_price = total_value_after / new_qty

        # 更新入場價後，浮盈會變化，需要重新計算
        # 新的入場價 = 加權平均，所以浮盈會減少
        self.position.entry_price = new_entry_price
        self.position.qty = new_qty
        self.position.leverage = new_leverage
        self.position.add_count += 1
        # total_cost 加入浮盈作為新的保證金
        self.position.total_cost += add_margin

        return True

    def close_position(self, price: float, time: datetime, reason: str):
        """平倉"""
        if self.position is None:
            return

        pnl = self.get_floating_pnl(price)

        self.trades.append(
            {
                "entry_time": self.position.entry_time,
                "exit_time": time,
                "direction": self.position.direction,
                "entry_price": self.position.entry_price,
                "exit_price": price,
                "qty": self.position.qty,
                "pnl": pnl,
                "add_count": self.position.add_count,
                "reason": reason,
            }
        )

        # 返還保證金 + 盈虧
        self.capital += self.position.total_cost + pnl
        self.position = None

        if reason == "liquidation":
            self.liquidations += 1

    def run(self, df: pd.DataFrame) -> dict:
        """執行回測"""
        df = df.copy()
        df["ma5"] = self.calculate_ma(df, 5)
        df["ma20"] = self.calculate_ma(df, 20)
        df["ma60"] = self.calculate_ma(df, 60)

        for i in range(60, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]
            price = row["close"]
            time = row["timestamp"] if "timestamp" in row else df.index[i]

            # 記錄權益曲線
            floating_pnl = self.get_floating_pnl(price)
            margin = self.position.total_cost if self.position else 0
            equity = self.capital + margin + floating_pnl
            self.equity_curve.append({"time": time, "equity": equity, "price": price})

            # 檢查爆倉
            if self.position and self.check_liquidation(price):
                self.capital = max(0, self.capital)
                self.close_position(price, time, "liquidation")
                continue

            # 無倉位時：BiGe 進場邏輯
            if self.position is None:
                if self.capital < 10:  # 資金不足
                    continue

                # MA5 > MA20 > MA60 且價格回踩MA20 → 做多
                if prev["ma5"] > prev["ma20"] > prev["ma60"] and prev["low"] <= prev["ma20"] * 1.02:
                    self.open_position("long", price, time)

                # MA5 < MA20 < MA60 且價格回踩MA20 → 做空
                elif (
                    prev["ma5"] < prev["ma20"] < prev["ma60"]
                    and prev["high"] >= prev["ma20"] * 0.98
                ):
                    self.open_position("short", price, time)

            # 有倉位時
            else:
                pos = self.position
                floating_pnl = self.get_floating_pnl(price)
                position_value = self.get_position_value(price)

                # 止損檢查
                loss_pct = -floating_pnl / pos.total_cost if pos.total_cost > 0 else 0
                if loss_pct > self.stop_loss_pct:
                    self.close_position(price, time, "stop_loss")
                    continue

                # 利潤觸發加倉（非MA回踩！）
                if floating_pnl > 0 and pos.add_count < self.max_add_count:
                    profit_ratio = floating_pnl / pos.total_cost
                    # 浮盈達到成本的X%時觸發加倉
                    if profit_ratio >= self.profit_trigger_pct * (pos.add_count + 1):
                        self.add_position(price, time)

                # 趨勢反轉平倉
                if pos.direction == "long":
                    if prev["ma5"] < prev["ma20"]:
                        self.close_position(price, time, "trend_reverse")
                else:
                    if prev["ma5"] > prev["ma20"]:
                        self.close_position(price, time, "trend_reverse")

        return self.get_results()

    def get_results(self) -> dict:
        """獲取回測結果"""
        if not self.trades:
            return {"final_capital": self.capital, "trades": 0}

        trades_df = pd.DataFrame(self.trades)

        long_trades = trades_df[trades_df["direction"] == "long"]
        short_trades = trades_df[trades_df["direction"] == "short"]

        winning = trades_df[trades_df["pnl"] > 0]

        equity_df = pd.DataFrame(self.equity_curve)
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = (equity_df["peak"] - equity_df["equity"]) / equity_df["peak"]
        max_drawdown = equity_df["drawdown"].max()

        return {
            "final_capital": self.capital,
            "total_return_pct": (self.capital - self.initial_capital) / self.initial_capital * 100,
            "total_trades": len(trades_df),
            "win_rate": len(winning) / len(trades_df) * 100 if len(trades_df) > 0 else 0,
            "long_pnl": long_trades["pnl"].sum() if len(long_trades) > 0 else 0,
            "short_pnl": short_trades["pnl"].sum() if len(short_trades) > 0 else 0,
            "max_drawdown": max_drawdown * 100,
            "liquidations": self.liquidations,
            "avg_add_count": trades_df["add_count"].mean(),
        }


def load_data() -> pd.DataFrame:
    """載入數據"""
    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    df = pd.read_csv(data_path)

    if "timestamp" not in df.columns and df.index.name == "timestamp":
        df = df.reset_index()

    # timestamp 是毫秒格式
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df[(df["timestamp"] >= "2020-01-01") & (df["timestamp"] < "2025-01-01")]
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def main():
    print("=" * 80)
    print("混合策略測試：BiGe進場 + 利潤觸發 + 浮盈加倉")
    print("=" * 80)

    df = load_data()
    print(f"數據範圍: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"數據筆數: {len(df)}")
    print()

    # 測試不同配置
    configs = [
        {"name": "浮盈50%觸發 + 10x", "leverage": 10, "trigger": 0.5},
        {"name": "浮盈30%觸發 + 10x", "leverage": 10, "trigger": 0.3},
        {"name": "浮盈50%觸發 + 7x", "leverage": 7, "trigger": 0.5},
        {"name": "浮盈30%觸發 + 7x", "leverage": 7, "trigger": 0.3},
        {"name": "浮盈20%觸發 + 7x", "leverage": 7, "trigger": 0.2},
    ]

    print(f"{'配置':<25} {'最終資金':>15} {'收益率':>12} {'勝率':>8} {'回撤':>8} {'爆倉':>6} {'加倉次':>8}")
    print("-" * 90)

    for cfg in configs:
        strategy = HybridStrategy(
            initial_capital=500,
            initial_leverage=cfg["leverage"],
            profit_trigger_pct=cfg["trigger"],
            max_add_count=3,
            leverage_reduction=0.7,
            stop_loss_pct=0.08,
        )

        results = strategy.run(df.copy())

        print(
            f"{cfg['name']:<25} "
            f"${results['final_capital']:>14,.0f} "
            f"{results['total_return_pct']:>10,.0f}% "
            f"{results['win_rate']:>6.1f}% "
            f"{results['max_drawdown']:>6.1f}% "
            f"{results['liquidations']:>5} "
            f"{results.get('avg_add_count', 0):>7.2f}"
        )

    print()
    print("=" * 80)
    print("對比：原始 BiGe 策略（50%本金加倉）")
    print("=" * 80)

    # 原始BiGe策略對照
    from strategies.bige_dual_ma import BiGeDualMAStrategy

    broker = Broker(initial_capital=500, leverage=7, fee_rate=0.0004)
    bige = BiGeDualMAStrategy(
        broker=broker,
        leverage=7,
        max_leverage=7,
        stop_loss_pct=0.08,
        trailing_stop_pct=None,
        add_position_pct=0.50,
        max_add_count=3,
        add_position_mode="fixed_50",
    )

    bige_results = bige.run(df.copy())

    print(f"BiGe 7x + 50%本金加倉:")
    print(f"  最終資金: ${bige_results['final_capital']:,.0f}")
    print(f"  收益率: {bige_results['total_return_pct']:,.0f}%")
    print(f"  勝率: {bige_results['win_rate']:.1f}%")
    print(f"  做多盈虧: ${bige_results.get('long_pnl', 0):,.0f}")
    print(f"  做空盈虧: ${bige_results.get('short_pnl', 0):,.0f}")


if __name__ == "__main__":
    main()
