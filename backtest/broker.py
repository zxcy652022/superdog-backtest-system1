"""
Simulated Broker Module v0.1

模擬交易所，負責處理買入、賣出、權益更新等操作。
只支援全倉進出（buy_all / sell_all），不支援部分倉位。
"""

from dataclasses import dataclass
from typing import List, Optional
import pandas as pd


@dataclass
class Trade:
    """交易記錄"""
    entry_time: pd.Timestamp  # 進場時間
    exit_time: pd.Timestamp   # 出場時間
    entry_price: float        # 進場價格
    exit_price: float         # 出場價格
    qty: float                # 數量
    pnl: float                # 損益（扣除手續費後）
    return_pct: float         # 報酬率（百分比）


class SimulatedBroker:
    """模擬交易所"""

    def __init__(self, initial_cash: float, fee_rate: float = 0.0005):
        """
        初始化模擬交易所

        Args:
            initial_cash: 初始資金
            fee_rate: 手續費率（預設 0.05%）
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.fee_rate = fee_rate

        # 持倉資訊
        self.position_qty = 0.0
        self.position_entry_price = 0.0
        self.position_entry_time: Optional[pd.Timestamp] = None

        # 歷史記錄
        self.equity_history: List[tuple] = []  # (time, equity)
        self.trades: List[Trade] = []

    @property
    def has_position(self) -> bool:
        """是否有持倉"""
        return self.position_qty > 0

    def buy_all(self, price: float, time: pd.Timestamp) -> bool:
        """
        全倉買入

        Args:
            price: 買入價格
            time: 買入時間

        Returns:
            bool: 是否成功買入
        """
        # 如果已有持倉，不能再買
        if self.has_position:
            return False

        # 計算可買入數量（扣除手續費）
        qty = self.cash / (price * (1 + self.fee_rate))

        if qty <= 0:
            return False

        # 執行買入
        cost = qty * price
        fee = cost * self.fee_rate
        total_cost = cost + fee

        self.position_qty = qty
        self.position_entry_price = price
        self.position_entry_time = time
        self.cash -= total_cost

        return True

    def sell_all(self, price: float, time: pd.Timestamp) -> bool:
        """
        全倉賣出

        Args:
            price: 賣出價格
            time: 賣出時間

        Returns:
            bool: 是否成功賣出
        """
        # 如果沒有持倉，不能賣
        if not self.has_position:
            return False

        # 計算賣出收益
        revenue = self.position_qty * price
        fee = revenue * self.fee_rate
        net_revenue = revenue - fee

        # 計算損益
        entry_cost = self.position_qty * self.position_entry_price
        entry_fee = entry_cost * self.fee_rate
        total_entry_cost = entry_cost + entry_fee
        pnl = net_revenue - entry_cost  # 扣除手續費後的損益
        return_pct = (price - self.position_entry_price) / self.position_entry_price

        # 記錄交易
        trade = Trade(
            entry_time=self.position_entry_time,
            exit_time=time,
            entry_price=self.position_entry_price,
            exit_price=price,
            qty=self.position_qty,
            pnl=pnl - entry_fee,  # 扣除買入和賣出手續費
            return_pct=return_pct
        )
        self.trades.append(trade)

        # 更新現金
        self.cash += net_revenue

        # 清空持倉
        self.position_qty = 0.0
        self.position_entry_price = 0.0
        self.position_entry_time = None

        return True

    def update_equity(self, price: float, time: pd.Timestamp):
        """
        更新權益

        Args:
            price: 當前價格
            time: 當前時間
        """
        if self.has_position:
            # 有持倉：權益 = 現金 + 持倉市值
            position_value = self.position_qty * price
            equity = self.cash + position_value
        else:
            # 無持倉：權益 = 現金
            equity = self.cash

        self.equity_history.append((time, equity))

    def get_equity_curve(self) -> pd.Series:
        """
        取得權益曲線

        Returns:
            pd.Series: 以時間為索引的權益序列
        """
        if not self.equity_history:
            return pd.Series(dtype=float)

        times, equities = zip(*self.equity_history)
        return pd.Series(equities, index=pd.DatetimeIndex(times), name='equity')

    def get_current_equity(self, price: float) -> float:
        """
        取得當前權益

        Args:
            price: 當前價格

        Returns:
            float: 當前權益
        """
        if self.has_position:
            return self.cash + self.position_qty * price
        else:
            return self.cash
