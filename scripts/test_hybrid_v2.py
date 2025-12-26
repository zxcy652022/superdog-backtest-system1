#!/usr/bin/env python3
"""
混合策略測試 V2：正確的浮盈加倉邏輯

關鍵修正：
- 追蹤每一層加倉的成本基礎
- 浮盈只計算一次，不會重複累計
"""

import sys

sys.path.insert(0, "/Users/ddragon/Projects/superdog-quant")

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd


@dataclass
class PositionLayer:
    """單層倉位"""

    entry_price: float
    qty: float
    cost: float  # 這層的保證金成本（真正從資金池扣除的）
    is_from_profit: bool = False  # 是否來自浮盈


@dataclass
class HybridPosition:
    """混合策略倉位（多層）"""

    direction: str
    layers: List[PositionLayer] = field(default_factory=list)
    leverage: float = 10
    entry_time: datetime = None
    realized_profit_used: float = 0  # 已實現並用於加倉的利潤

    @property
    def total_qty(self) -> float:
        return sum(l.qty for l in self.layers)

    @property
    def real_cost(self) -> float:
        """真正從本金扣除的成本（不包括用浮盈加倉的部分）"""
        return sum(l.cost for l in self.layers if not l.is_from_profit)

    @property
    def total_margin(self) -> float:
        """總保證金（包括浮盈加倉）"""
        return sum(l.cost for l in self.layers)

    @property
    def avg_entry_price(self) -> float:
        if not self.layers:
            return 0
        total_value = sum(l.entry_price * l.qty for l in self.layers)
        return total_value / self.total_qty

    def get_floating_pnl(self, current_price: float) -> float:
        """計算總浮盈（相對於所有層的成本）"""
        if not self.layers:
            return 0

        total_pnl = 0
        for layer in self.layers:
            if self.direction == "long":
                total_pnl += (current_price - layer.entry_price) * layer.qty
            else:
                total_pnl += (layer.entry_price - current_price) * layer.qty
        return total_pnl

    def get_first_layer_pnl(self, current_price: float) -> float:
        """計算第一層的浮盈（用於觸發加倉）"""
        if not self.layers:
            return 0

        first_layer = self.layers[0]
        if self.direction == "long":
            return (current_price - first_layer.entry_price) * first_layer.qty
        else:
            return (first_layer.entry_price - current_price) * first_layer.qty


class HybridStrategyV2:
    """
    混合策略 V2：正確實現浮盈加倉

    加倉觸發：最後一層浮盈達到閾值
    加倉資金：使用該層浮盈
    """

    def __init__(
        self,
        initial_capital: float = 500,
        initial_leverage: float = 10,
        profit_trigger_pct: float = 0.5,  # 最後一層浮盈達到成本50%時觸發
        max_add_count: int = 3,
        leverage_reduction: float = 0.7,
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

    def check_liquidation(self, current_price: float) -> bool:
        if self.position is None:
            return False

        floating_pnl = self.position.get_floating_pnl(current_price)
        # 爆倉條件：可用資金 + 真實成本 + 浮盈 <= 0
        total_equity = self.capital + self.position.real_cost + floating_pnl
        return total_equity <= 0

    def get_equity(self, current_price: float) -> float:
        if self.position is None:
            return self.capital
        floating_pnl = self.position.get_floating_pnl(current_price)
        # 權益 = 可用資金 + 真實投入成本 + 浮盈
        return self.capital + self.position.real_cost + floating_pnl

    def open_position(self, direction: str, price: float, time: datetime):
        leverage = self.initial_leverage
        margin = self.capital * 0.9
        position_value = margin * leverage
        qty = position_value / price

        self.position = HybridPosition(
            direction=direction,
            layers=[PositionLayer(entry_price=price, qty=qty, cost=margin)],
            leverage=leverage,
            entry_time=time,
        )
        self.capital -= margin

    def try_add_position(self, price: float, time: datetime) -> bool:
        """嘗試加倉"""
        if self.position is None:
            return False

        add_count = len(self.position.layers) - 1  # 第一層是開倉，不算加倉
        if add_count >= self.max_add_count:
            return False

        # 計算第一層的浮盈（扣除已用於加倉的部分）
        first_layer_pnl = self.position.get_first_layer_pnl(price)
        available_profit = first_layer_pnl - self.position.realized_profit_used

        if available_profit <= 0:
            return False

        # 檢查是否達到觸發閾值（基於第一層成本）
        first_layer = self.position.layers[0]
        profit_ratio = available_profit / first_layer.cost
        if profit_ratio < self.profit_trigger_pct:
            return False

        # 使用可用浮盈加倉
        new_leverage = self.position.leverage * self.leverage_reduction
        add_margin = available_profit  # 用可用的浮盈
        add_value = add_margin * new_leverage
        add_qty = add_value / price

        # 添加新層（標記為來自浮盈）
        self.position.layers.append(
            PositionLayer(entry_price=price, qty=add_qty, cost=add_margin, is_from_profit=True)
        )
        self.position.leverage = new_leverage
        # 記錄已使用的浮盈
        self.position.realized_profit_used += add_margin

        return True

    def close_position(self, price: float, time: datetime, reason: str):
        if self.position is None:
            return

        # 正確邏輯：
        # 開倉：從本金扣 real_cost
        # 加倉：用浮盈，不從本金扣（但浮盈被「鎖定」）
        # 平倉：返還 real_cost + 所有層的浮盈總和

        # 所有層的浮盈總和
        total_pnl = self.position.get_floating_pnl(price)
        real_cost = self.position.real_cost

        self.trades.append(
            {
                "entry_time": self.position.entry_time,
                "exit_time": time,
                "direction": self.position.direction,
                "avg_entry": self.position.avg_entry_price,
                "exit_price": price,
                "qty": self.position.total_qty,
                "pnl": total_pnl,
                "add_count": len(self.position.layers) - 1,
                "reason": reason,
            }
        )

        # 返還：真實成本 + 總浮盈
        self.capital += real_cost + total_pnl

        if reason == "liquidation":
            self.liquidations += 1
            self.capital = max(0, self.capital)

        self.position = None

    def run(self, df: pd.DataFrame) -> dict:
        df = df.copy()
        df["ma5"] = self.calculate_ma(df, 5)
        df["ma20"] = self.calculate_ma(df, 20)
        df["ma60"] = self.calculate_ma(df, 60)

        for i in range(60, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]
            price = row["close"]
            time = row["timestamp"] if "timestamp" in row else df.index[i]

            # 記錄權益
            equity = self.get_equity(price)
            self.equity_curve.append({"time": time, "equity": equity, "price": price})

            # 爆倉檢查
            if self.position and self.check_liquidation(price):
                self.close_position(price, time, "liquidation")
                continue

            # 無倉位時：BiGe 進場邏輯
            if self.position is None:
                if self.capital < 10:
                    continue

                # MA5 > MA20 > MA60 且回踩MA20 → 做多
                if prev["ma5"] > prev["ma20"] > prev["ma60"] and prev["low"] <= prev["ma20"] * 1.02:
                    self.open_position("long", price, time)

                # MA5 < MA20 < MA60 且回踩MA20 → 做空
                elif (
                    prev["ma5"] < prev["ma20"] < prev["ma60"]
                    and prev["high"] >= prev["ma20"] * 0.98
                ):
                    self.open_position("short", price, time)

            else:
                # 有倉位
                pos = self.position
                floating_pnl = pos.get_floating_pnl(price)

                # 止損
                loss_pct = -floating_pnl / pos.real_cost if pos.real_cost > 0 else 0
                if loss_pct > self.stop_loss_pct:
                    self.close_position(price, time, "stop_loss")
                    continue

                # 嘗試加倉
                self.try_add_position(price, time)

                # 趨勢反轉平倉
                if pos.direction == "long":
                    if prev["ma5"] < prev["ma20"]:
                        self.close_position(price, time, "trend_reverse")
                else:
                    if prev["ma5"] > prev["ma20"]:
                        self.close_position(price, time, "trend_reverse")

        return self.get_results()

    def get_results(self) -> dict:
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
    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    df = pd.read_csv(data_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df[(df["timestamp"] >= "2020-01-01") & (df["timestamp"] < "2025-01-01")]
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def format_number(n: float) -> str:
    """格式化大數字"""
    if abs(n) >= 1e12:
        return f"${n/1e12:.1f}T"
    elif abs(n) >= 1e9:
        return f"${n/1e9:.1f}B"
    elif abs(n) >= 1e6:
        return f"${n/1e6:.1f}M"
    elif abs(n) >= 1e3:
        return f"${n/1e3:.1f}K"
    else:
        return f"${n:.0f}"


def main():
    print("=" * 80)
    print("混合策略 V2：BiGe進場 + 利潤觸發 + 浮盈加倉（正確實現）")
    print("=" * 80)

    df = load_data()
    print(f"數據範圍: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
    print(f"數據筆數: {len(df)}")
    print()

    configs = [
        {"name": "7x + 50%觸發", "leverage": 7, "trigger": 0.5},
        {"name": "7x + 30%觸發", "leverage": 7, "trigger": 0.3},
        {"name": "7x + 20%觸發", "leverage": 7, "trigger": 0.2},
        {"name": "10x + 50%觸發", "leverage": 10, "trigger": 0.5},
        {"name": "10x + 30%觸發", "leverage": 10, "trigger": 0.3},
    ]

    print(f"{'配置':<20} {'最終資金':>15} {'收益率':>15} {'勝率':>8} {'回撤':>8} {'爆倉':>6} {'加倉':>6}")
    print("-" * 85)

    for cfg in configs:
        strategy = HybridStrategyV2(
            initial_capital=500,
            initial_leverage=cfg["leverage"],
            profit_trigger_pct=cfg["trigger"],
            max_add_count=3,
            leverage_reduction=0.7,
            stop_loss_pct=0.08,
        )

        results = strategy.run(df.copy())

        return_pct = results["total_return_pct"]
        if return_pct >= 1e9:
            return_str = f"{return_pct/1e9:.1f}B%"
        elif return_pct >= 1e6:
            return_str = f"{return_pct/1e6:.1f}M%"
        else:
            return_str = f"{return_pct:,.0f}%"

        print(
            f"{cfg['name']:<20} "
            f"{format_number(results['final_capital']):>15} "
            f"{return_str:>15} "
            f"{results['win_rate']:>6.1f}% "
            f"{results['max_drawdown']:>6.1f}% "
            f"{results['liquidations']:>5} "
            f"{results.get('avg_add_count', 0):>5.2f}"
        )

    print()
    print("=" * 80)
    print("對比：原始 BiGe 策略（50%本金加倉）")
    print("=" * 80)

    from backtest.engine import run_backtest
    from strategies.bige_dual_ma import BiGeDualMAStrategy

    # 準備 BiGe 需要的數據格式（需要 DatetimeIndex）
    bige_df = df.copy()
    bige_df = bige_df.set_index("timestamp")

    bige_results = run_backtest(
        data=bige_df,
        strategy_cls=BiGeDualMAStrategy,
        initial_cash=500,
        fee_rate=0.0004,
        leverage=7,
        strategy_params={
            "leverage": 7,
            "max_leverage": 7,
            "stop_loss_pct": 0.08,
            "add_position_pct": 0.50,
            "max_add_count": 3,
            "add_position_mode": "fixed_50",
        },
    )

    final_equity = bige_results.equity_curve.iloc[-1] if len(bige_results.equity_curve) > 0 else 500
    win_rate = bige_results.metrics.get("win_rate", 0)
    total_trades = len(bige_results.trades)

    print(f"BiGe 7x + 50%本金加倉:")
    print(f"  最終資金: {format_number(final_equity)}")
    print(f"  收益率: {(final_equity - 500) / 500 * 100:,.0f}%")
    print(f"  勝率: {win_rate * 100:.1f}%")
    print(f"  交易次數: {total_trades}")


if __name__ == "__main__":
    main()
