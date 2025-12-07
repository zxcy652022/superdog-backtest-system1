"""
Simulated Broker Module v0.3

模擬交易所，負責處理買入、賣出、權益更新等操作。
支援全倉進出（buy_all / sell_all）和指定倉位（buy / sell）。

v0.3 新增：
- 支援做空交易（short selling）
- 支援槓桿交易（leverage）
- 持倉方向感知（long/short/flat）

Design Reference: docs/specs/planned/v0.3_short_leverage_spec.md §2
"""

from dataclasses import dataclass
from typing import List, Literal, Optional

import pandas as pd

# v0.3: 定義持倉方向類型
DirectionType = Literal["long", "short", "flat"]


@dataclass
class Trade:
    """交易記錄（v0.3 擴展）"""

    entry_time: pd.Timestamp  # 進場時間
    exit_time: pd.Timestamp  # 出場時間
    entry_price: float  # 進場價格
    exit_price: float  # 出場價格
    qty: float  # 數量（絕對值）
    pnl: float  # 損益（扣除手續費後）
    return_pct: float  # 報酬率（百分比）
    # v0.3 新增字段（向後兼容：提供默認值）
    direction: DirectionType = "long"  # 持倉方向
    leverage: float = 1.0  # 槓桿倍數


class SimulatedBroker:
    """模擬交易所（v0.3 - 支援做空和槓桿）"""

    def __init__(
        self,
        initial_cash: float,
        fee_rate: float = 0.0005,
        leverage: float = 1.0,  # v0.3 新增：預設1倍（無槓桿）
    ):
        """
        初始化模擬交易所

        Args:
            initial_cash: 初始資金
            fee_rate: 手續費率（預設 0.05%）
            leverage: 槓桿倍數（預設1倍，範圍1-100）

        Raises:
            ValueError: 如果 leverage 不在 1-100 範圍內
        """
        # v0.3: 驗證槓桿倍數
        if leverage < 1 or leverage > 100:
            raise ValueError("Leverage must be between 1 and 100")

        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.fee_rate = fee_rate
        self.leverage = leverage  # v0.3 新增

        # 持倉資訊（v0.3 改進）
        self.position_qty = 0.0
        self.position_direction: DirectionType = "flat"  # v0.3 新增：持倉方向
        self.position_entry_price = 0.0
        self.position_entry_time: Optional[pd.Timestamp] = None

        # 歷史記錄
        self.equity_history: List[tuple] = []  # (time, equity)
        self.trades: List[Trade] = []

    @property
    def has_position(self) -> bool:
        """是否有持倉"""
        # v0.3: 改為檢查 position_qty 和 direction
        return self.position_qty > 0 and self.position_direction != "flat"

    @property
    def is_long(self) -> bool:
        """是否持有多單（v0.3 新增）"""
        return self.has_position and self.position_direction == "long"

    @property
    def is_short(self) -> bool:
        """是否持有空單（v0.3 新增）"""
        return self.has_position and self.position_direction == "short"

    def buy(
        self, size: float, price: float, time: pd.Timestamp, leverage: Optional[float] = None
    ) -> bool:
        """
        買入（v0.3: 開多或平空）

        語義變更（v0.3）:
        - 無持倉: 開多單
        - 持有空單: 平空單（全部或部分）
        - 持有多單: 返回False（不支持加倉）

        Args:
            size: 買入數量（必須 > 0）
            price: 買入價格
            time: 買入時間
            leverage: 本次交易的槓桿倍數（可選，默認使用broker的leverage）

        Returns:
            bool: 是否成功執行
        """
        if size <= 0:
            return False

        # 使用指定槓桿或預設槓桿
        lev = leverage if leverage is not None else self.leverage

        # Case 1: 無持倉 -> 開多單
        if self.position_direction == "flat":
            return self._open_long(size, price, time, lev)

        # Case 2: 持有空單 -> 平空單
        elif self.position_direction == "short":
            return self._close_short(size, price, time)

        # Case 3: 持有多單 -> 不支持加倉
        else:  # self.position_direction == "long"
            return False

    def sell(
        self, size: float, price: float, time: pd.Timestamp, leverage: Optional[float] = None
    ) -> bool:
        """
        賣出（v0.3: 開空或平多）

        語義變更（v0.3）:
        - 無持倉: 開空單
        - 持有多單: 平多單（全部或部分）
        - 持有空單: 返回False（不支持加倉）

        Args:
            size: 賣出數量（必須 > 0）
            price: 賣出價格
            time: 賣出時間
            leverage: 本次交易的槓桿倍數（可選）

        Returns:
            bool: 是否成功執行
        """
        if size <= 0:
            return False

        lev = leverage if leverage is not None else self.leverage

        # Case 1: 無持倉 -> 開空單
        if self.position_direction == "flat":
            return self._open_short(size, price, time, lev)

        # Case 2: 持有多單 -> 平多單
        elif self.position_direction == "long":
            return self._close_long(size, price, time)

        # Case 3: 持有空單 -> 不支持加倉
        else:  # self.position_direction == "short"
            return False

    # === v0.3 新增：內部方法（私有） ===

    def _open_long(self, size: float, price: float, time: pd.Timestamp, leverage: float) -> bool:
        """開多單（內部方法）"""
        # 計算成本（考慮槓桿）
        # 槓桿的簡化模型: 占用資金 = 倉位價值 / leverage
        position_value = size * price
        required_margin = position_value / leverage
        entry_fee = position_value * self.fee_rate
        total_required = required_margin + entry_fee

        # 檢查資金是否足夠（使用較寬鬆的檢查以處理浮點數精度）
        if total_required > self.cash * 1.000001:  # 允許 0.0001% 的誤差
            return False

        # 數值溢出檢查
        if not (0 < total_required < 1e15):  # 合理範圍檢查
            return False

        new_cash = self.cash - total_required
        if new_cash < -1e10 or new_cash > 1e15:  # 防止異常值
            return False

        # 執行開倉
        self.position_qty = size
        self.position_direction = "long"
        self.position_entry_price = price
        self.position_entry_time = time
        self.cash = new_cash

        return True

    def _open_short(self, size: float, price: float, time: pd.Timestamp, leverage: float) -> bool:
        """開空單（內部方法）"""
        # 做空的簡化模型:
        # - 占用資金 = 倉位價值 / leverage
        # - 收入不立即計入cash（簡化處理）
        position_value = size * price
        required_margin = position_value / leverage
        entry_fee = position_value * self.fee_rate
        total_required = required_margin + entry_fee

        # 檢查資金是否足夠（使用較寬鬆的檢查以處理浮點數精度）
        if total_required > self.cash * 1.000001:  # 允許 0.0001% 的誤差
            return False

        # 數值溢出檢查
        if not (0 < total_required < 1e15):
            return False

        new_cash = self.cash - total_required
        if new_cash < -1e10 or new_cash > 1e15:
            return False

        # 執行開倉
        self.position_qty = size
        self.position_direction = "short"
        self.position_entry_price = price
        self.position_entry_time = time
        self.cash = new_cash  # 扣除保證金+手續費

        return True

    def _close_long(self, size: float, price: float, time: pd.Timestamp) -> bool:
        """平多單（內部方法）"""
        if not self.is_long:
            return False

        # 實際平倉數量（不能超過持倉）
        actual_size = min(size, self.position_qty)

        # 計算收益
        revenue = actual_size * price
        fee = revenue * self.fee_rate
        net_revenue = revenue - fee

        # 數值有效性檢查
        if not all(abs(x) < 1e15 for x in [revenue, fee, net_revenue]):
            return False

        # 計算PnL
        entry_cost = actual_size * self.position_entry_price
        # entry_fee已在開倉時扣除，這裡只扣exit_fee
        pnl = net_revenue - entry_cost

        # 計算return_pct（基於entry價格）
        return_pct = (price - self.position_entry_price) / self.position_entry_price

        # 記錄交易（v0.3: 包含direction和leverage）
        trade = Trade(
            entry_time=self.position_entry_time,
            exit_time=time,
            entry_price=self.position_entry_price,
            exit_price=price,
            qty=actual_size,
            pnl=pnl,
            return_pct=return_pct,
            direction="long",
            leverage=self.leverage,
        )
        self.trades.append(trade)

        # 更新cash（退還占用資金 + PnL）
        # 開倉時扣除了: position_value / leverage + fee_entry
        # 平倉時收到: revenue - fee_exit
        released_margin = entry_cost / self.leverage
        cash_change = released_margin + net_revenue

        # 數值溢出檢查
        if not abs(cash_change) < 1e15:
            return False

        new_cash = self.cash + cash_change
        if new_cash < -1e10 or new_cash > 1e15:
            return False

        self.cash = new_cash

        # 更新持倉
        self.position_qty -= actual_size
        if self.position_qty <= 1e-10:
            self._clear_position()

        return True

    def _close_short(self, size: float, price: float, time: pd.Timestamp) -> bool:
        """平空單（內部方法）"""
        if not self.is_short:
            return False

        actual_size = min(size, self.position_qty)

        # 做空的PnL計算: (entry - exit) * size
        # 買入成本
        cost = actual_size * price
        fee = cost * self.fee_rate
        total_cost = cost + fee

        # 數值有效性檢查
        if not all(abs(x) < 1e15 for x in [cost, fee, total_cost]):
            return False

        # 做空收入（在開倉時的理論收入）
        revenue = actual_size * self.position_entry_price

        # PnL = 賣高買低的差價
        pnl = revenue - cost - fee

        # return_pct（做空的回報率）
        return_pct = (self.position_entry_price - price) / self.position_entry_price

        # 記錄交易（v0.3: direction="short"）
        trade = Trade(
            entry_time=self.position_entry_time,
            exit_time=time,
            entry_price=self.position_entry_price,
            exit_price=price,
            qty=actual_size,
            pnl=pnl,
            return_pct=return_pct,
            direction="short",
            leverage=self.leverage,
        )
        self.trades.append(trade)

        # 更新cash
        released_margin = revenue / self.leverage
        cash_change = released_margin - total_cost

        # 數值溢出檢查
        if not abs(cash_change) < 1e15:
            return False

        new_cash = self.cash + cash_change
        if new_cash < -1e10 or new_cash > 1e15:
            return False

        self.cash = new_cash

        # 更新持倉
        self.position_qty -= actual_size
        if self.position_qty <= 1e-10:
            self._clear_position()

        return True

    def _clear_position(self):
        """清空持倉狀態（內部方法）"""
        self.position_qty = 0.0
        self.position_direction = "flat"
        self.position_entry_price = 0.0
        self.position_entry_time = None

    # === v0.2 兼容方法（保留） ===

    def buy_all(self, price: float, time: pd.Timestamp) -> bool:
        """
        全倉買入（v0.2 兼容）

        v0.3: 調用 buy()，size 由當前equity計算
        """
        # v0.3: 使用簡化的equity計算（= cash）
        equity = self.get_current_equity(price)
        size = equity / (price * (1 + self.fee_rate) * self.leverage)
        return self.buy(size, price, time)

    def sell_all(self, price: float, time: pd.Timestamp) -> bool:
        """
        全倉賣出（v0.2 兼容）

        v0.3: 如果有多單，全部平倉；否則開全倉空單
        """
        if self.is_long:
            # 平多單
            return self.sell(self.position_qty, price, time)
        elif self.position_direction == "flat":
            # 開全倉空單
            equity = self.get_current_equity(price)
            size = equity / (price * (1 + self.fee_rate) * self.leverage)
            return self.sell(size, price, time)
        else:
            # 已有空單，不支持加倉
            return False

    def short_all(self, price: float, time: pd.Timestamp) -> bool:
        """
        全倉開空（v0.5 新增）

        Alias for sell_all when no position exists.
        Opens a full short position using all available equity.

        Args:
            price: Entry price
            time: Entry time

        Returns:
            bool: True if successful, False otherwise
        """
        # v0.5: Shorthand for opening short position
        if self.position_direction == "flat":
            equity = self.get_current_equity(price)
            size = equity / (price * (1 + self.fee_rate) / self.leverage)
            return self.sell(size, price, time)
        else:
            # Already have position
            return False

    def update_equity(self, price: float, time: pd.Timestamp):
        """
        更新權益

        v0.3 簡化假設: equity只在平倉時更新，持倉期間不計入mark-to-market

        Args:
            price: 當前價格
            time: 當前時間
        """
        # v0.3 簡化: equity = cash（不計入浮動盈虧）
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
        return pd.Series(equities, index=pd.DatetimeIndex(times), name="equity")

    def get_current_equity(self, price: float) -> float:
        """
        取得當前權益

        v0.3 簡化版: 返回cash，不計入未實現盈虧

        Args:
            price: 當前價格

        Returns:
            float: 當前權益
        """
        # v0.3 簡化: 返回cash（不計入浮動盈虧）
        return self.cash
