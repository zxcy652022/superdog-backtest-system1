"""
Simulated Broker Module v1.2

模擬交易所，負責處理買入、賣出、權益更新等操作。
支援全倉進出（buy_all / sell_all）和指定倉位（buy / sell）。

v0.3 新增：
- 支援做空交易（short selling）
- 支援槓桿交易（leverage）
- 持倉方向感知（long/short/flat）

v0.7 改進：
- get_current_equity() 計入浮動盈虧 (mark-to-market)
- update_equity() 使用真實權益計算
- 權益曲線正確反映持倉期間的價值變化

v1.0 新增：
- 爆倉檢測（liquidation check）
- 維持保證金率設定
- 爆倉事件記錄

v1.2 修復：
- 新增 position_leverage 追蹤開倉時的槓桿
- get_current_equity() 使用 position_leverage 計算保證金
- 加倉時使用加權平均更新 position_leverage
- 修復動態槓桿模式下的權益計算錯誤

Design Reference: docs/v1.0/DESIGN.md
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
    # v1.0 新增
    is_liquidation: bool = False  # 是否為爆倉平倉


@dataclass
class LiquidationEvent:
    """爆倉事件記錄（v1.0 新增）"""

    time: pd.Timestamp  # 爆倉時間
    direction: DirectionType  # 持倉方向
    entry_price: float  # 入場價格
    liquidation_price: float  # 爆倉價格
    position_qty: float  # 持倉數量
    loss: float  # 損失金額（正數）
    leverage: float  # 槓桿倍數


class SimulatedBroker:
    """模擬交易所（v1.0 - 支援做空、槓桿和爆倉檢測）"""

    def __init__(
        self,
        initial_cash: float,
        fee_rate: float = 0.0005,
        leverage: float = 1.0,  # v0.3 新增：預設1倍（無槓桿）
        maintenance_margin_rate: float = 0.005,  # v1.0 新增：維持保證金率（0.5%）
        slippage_rate: float = 0.0005,  # v1.1 新增：滑點率（預設 0.05%）
    ):
        """
        初始化模擬交易所

        Args:
            initial_cash: 初始資金
            fee_rate: 手續費率（預設 0.05%）
            leverage: 槓桿倍數（預設1倍，範圍1-100）
            maintenance_margin_rate: 維持保證金率（預設0.5%，幣安永續合約標準）
            slippage_rate: 滑點率（預設 0.05%，買入價格上浮、賣出價格下浮）

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
        self.maintenance_margin_rate = maintenance_margin_rate  # v1.0 新增
        self.slippage_rate = slippage_rate  # v1.1 新增

        # 持倉資訊（v0.3 改進）
        self.position_qty = 0.0
        self.position_direction: DirectionType = "flat"  # v0.3 新增：持倉方向
        self.position_entry_price = 0.0
        self.position_entry_time: Optional[pd.Timestamp] = None
        self.position_leverage: float = 1.0  # v1.2 新增：開倉時的槓桿（用於權益計算）

        # 歷史記錄
        self.equity_history: List[tuple] = []  # (time, equity)
        self.trades: List[Trade] = []
        self.liquidation_events: List[LiquidationEvent] = []  # v1.0 新增：爆倉事件

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
        買入（v1.1: 開多、平空或加倉）

        語義變更（v1.1）:
        - 無持倉: 開多單
        - 持有空單: 平空單（全部或部分）
        - 持有多單: 加倉（v1.1 新增支援）

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

        # Case 3: 持有多單 -> 加倉（v1.1 新增）
        else:  # self.position_direction == "long"
            return self._add_long(size, price, time, lev)

    def sell(
        self, size: float, price: float, time: pd.Timestamp, leverage: Optional[float] = None
    ) -> bool:
        """
        賣出（v1.1: 開空、平多或加倉）

        語義變更（v1.1）:
        - 無持倉: 開空單
        - 持有多單: 平多單（全部或部分）
        - 持有空單: 加倉（v1.1 新增支援）

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

        # Case 3: 持有空單 -> 加倉（v1.1 新增）
        else:  # self.position_direction == "short"
            return self._add_short(size, price, time, lev)

    # === v1.1 新增：滑點計算 ===

    def _apply_slippage(self, price: float, is_buy: bool) -> float:
        """計算滑點後的實際執行價格

        Args:
            price: 原始價格
            is_buy: 是否為買入操作

        Returns:
            float: 滑點後的價格（買入價格上浮、賣出價格下浮）
        """
        if is_buy:
            # 買入：價格上浮（不利）
            return price * (1 + self.slippage_rate)
        else:
            # 賣出：價格下浮（不利）
            return price * (1 - self.slippage_rate)

    # === v0.3 新增：內部方法（私有） ===

    def _open_long(self, size: float, price: float, time: pd.Timestamp, leverage: float) -> bool:
        """開多單（內部方法）

        v1.1 改進：加入滑點計算，買入價格上浮
        """
        # v1.1: 應用滑點（買入價格上浮）
        actual_price = self._apply_slippage(price, is_buy=True)

        # 計算成本（考慮槓桿）
        # 槓桿的簡化模型: 占用資金 = 倉位價值 / leverage
        position_value = size * actual_price
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

        # 執行開倉（使用滑點後的實際價格）
        self.position_qty = size
        self.position_direction = "long"
        self.position_entry_price = actual_price  # v1.1: 使用實際成交價
        self.position_entry_time = time
        self.position_leverage = leverage  # v1.2: 記錄開倉槓桿
        self.cash = new_cash

        return True

    def _open_short(self, size: float, price: float, time: pd.Timestamp, leverage: float) -> bool:
        """開空單（內部方法）

        v1.1 改進：加入滑點計算，賣出價格下浮
        """
        # v1.1: 應用滑點（賣出/開空價格下浮）
        actual_price = self._apply_slippage(price, is_buy=False)

        # 做空的簡化模型:
        # - 占用資金 = 倉位價值 / leverage
        # - 收入不立即計入cash（簡化處理）
        position_value = size * actual_price
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

        # 執行開倉（使用滑點後的實際價格）
        self.position_qty = size
        self.position_direction = "short"
        self.position_entry_price = actual_price  # v1.1: 使用實際成交價
        self.position_entry_time = time
        self.position_leverage = leverage  # v1.2: 記錄開倉槓桿
        self.cash = new_cash  # 扣除保證金+手續費

        return True

    # === v1.1 新增：加倉方法 ===

    def _add_long(self, size: float, price: float, time: pd.Timestamp, leverage: float) -> bool:
        """多單加倉（v1.1 新增）

        加倉邏輯：
        - 增加持倉數量
        - 更新平均入場價格
        - 扣除新倉位的保證金和手續費

        v1.1 改進：加入滑點計算

        Args:
            size: 加倉數量
            price: 加倉價格
            time: 加倉時間
            leverage: 槓桿倍數

        Returns:
            bool: 是否成功執行
        """
        if not self.is_long:
            return False

        # v1.1: 應用滑點（買入價格上浮）
        actual_price = self._apply_slippage(price, is_buy=True)

        # 計算加倉成本
        add_value = size * actual_price
        required_margin = add_value / leverage
        entry_fee = add_value * self.fee_rate
        total_required = required_margin + entry_fee

        # 檢查資金是否足夠
        if total_required > self.cash * 1.000001:
            return False

        # 數值溢出檢查
        if not (0 < total_required < 1e15):
            return False

        new_cash = self.cash - total_required
        if new_cash < -1e10 or new_cash > 1e15:
            return False

        # 更新平均入場價格（加權平均，使用實際成交價）
        old_value = self.position_qty * self.position_entry_price
        new_value = size * actual_price
        total_qty = self.position_qty + size
        self.position_entry_price = (old_value + new_value) / total_qty

        # v1.2: 更新加權平均槓桿
        old_margin = old_value / self.position_leverage
        new_margin = new_value / leverage
        total_margin = old_margin + new_margin
        self.position_leverage = (old_value + new_value) / total_margin

        # 更新持倉和現金
        self.position_qty = total_qty
        self.cash = new_cash

        return True

    def _add_short(self, size: float, price: float, time: pd.Timestamp, leverage: float) -> bool:
        """空單加倉（v1.1 新增）

        加倉邏輯：
        - 增加空單持倉數量
        - 更新平均入場價格
        - 扣除新倉位的保證金和手續費

        v1.1 改進：加入滑點計算

        Args:
            size: 加倉數量
            price: 加倉價格
            time: 加倉時間
            leverage: 槓桿倍數

        Returns:
            bool: 是否成功執行
        """
        if not self.is_short:
            return False

        # v1.1: 應用滑點（賣出/開空價格下浮）
        actual_price = self._apply_slippage(price, is_buy=False)

        # 計算加倉成本
        add_value = size * actual_price
        required_margin = add_value / leverage
        entry_fee = add_value * self.fee_rate
        total_required = required_margin + entry_fee

        # 檢查資金是否足夠
        if total_required > self.cash * 1.000001:
            return False

        # 數值溢出檢查
        if not (0 < total_required < 1e15):
            return False

        new_cash = self.cash - total_required
        if new_cash < -1e10 or new_cash > 1e15:
            return False

        # 更新平均入場價格（加權平均，使用實際成交價）
        old_value = self.position_qty * self.position_entry_price
        new_value = size * actual_price
        total_qty = self.position_qty + size
        self.position_entry_price = (old_value + new_value) / total_qty

        # v1.2: 更新加權平均槓桿
        old_margin = old_value / self.position_leverage
        new_margin = new_value / leverage
        total_margin = old_margin + new_margin
        self.position_leverage = (old_value + new_value) / total_margin

        # 更新持倉和現金
        self.position_qty = total_qty
        self.cash = new_cash

        return True

    def _close_long(self, size: float, price: float, time: pd.Timestamp) -> bool:
        """平多單（內部方法）

        v1.1 改進：加入滑點計算，賣出價格下浮
        """
        if not self.is_long:
            return False

        # v1.1: 應用滑點（賣出價格下浮）
        actual_price = self._apply_slippage(price, is_buy=False)

        # 實際平倉數量（不能超過持倉）
        actual_size = min(size, self.position_qty)

        # 計算收益（使用滑點後價格）
        revenue = actual_size * actual_price
        fee = revenue * self.fee_rate
        net_revenue = revenue - fee

        # 數值有效性檢查
        if not all(abs(x) < 1e15 for x in [revenue, fee, net_revenue]):
            return False

        # 計算PnL
        entry_cost = actual_size * self.position_entry_price
        # entry_fee已在開倉時扣除，這裡只扣exit_fee
        pnl = net_revenue - entry_cost

        # 計算return_pct（基於entry價格，使用實際成交價）
        return_pct = (actual_price - self.position_entry_price) / self.position_entry_price

        # 記錄交易（v0.3: 包含direction和leverage）
        trade = Trade(
            entry_time=self.position_entry_time,
            exit_time=time,
            entry_price=self.position_entry_price,
            exit_price=actual_price,  # v1.1: 使用實際成交價
            qty=actual_size,
            pnl=pnl,
            return_pct=return_pct,
            direction="long",
            leverage=self.leverage,
        )
        self.trades.append(trade)

        # 更新cash（退還保證金 + 利潤 - 手續費）
        # 開倉時扣除了: entry_cost / leverage + entry_fee
        # 平倉時退回: 保證金 + 價差利潤 - 出場手續費
        # v0.7.4 修復: 槓桿交易中，平倉不是收到「全部賣出金額」，而是「保證金 + 利潤」
        # v1.2 修復: 使用 position_leverage 而非 self.leverage
        released_margin = entry_cost / self.position_leverage
        price_profit = (actual_price - self.position_entry_price) * actual_size  # 價差利潤（使用實際成交價）
        cash_change = released_margin + price_profit - fee

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
        """平空單（內部方法）

        v0.7 修復: 正確計算平空後的現金變化
        v1.1 改進：加入滑點計算，買入價格上浮
        """
        if not self.is_short:
            return False

        # v1.1: 應用滑點（買入/平空價格上浮）
        actual_price = self._apply_slippage(price, is_buy=True)

        actual_size = min(size, self.position_qty)

        # 入場價值（開空時賣出的價值）
        entry_value = actual_size * self.position_entry_price
        # 平倉成本（買入平倉的成本，使用滑點後價格）
        exit_cost = actual_size * actual_price
        exit_fee = exit_cost * self.fee_rate

        # 數值有效性檢查
        if not all(abs(x) < 1e15 for x in [entry_value, exit_cost, exit_fee]):
            return False

        # PnL = 賣高買低的差價 - 手續費
        # (開空時的入場費已在開倉時扣除)
        pnl = entry_value - exit_cost - exit_fee

        # return_pct（做空的回報率，使用實際成交價）
        return_pct = (self.position_entry_price - actual_price) / self.position_entry_price

        # 記錄交易（v0.3: direction="short"）
        trade = Trade(
            entry_time=self.position_entry_time,
            exit_time=time,
            entry_price=self.position_entry_price,
            exit_price=actual_price,  # v1.1: 使用實際成交價
            qty=actual_size,
            pnl=pnl,
            return_pct=return_pct,
            direction="short",
            leverage=self.leverage,
        )
        self.trades.append(trade)

        # v0.7 修復: 正確計算現金變化
        # 開空時扣除: margin + entry_fee = entry_value / leverage + entry_fee
        # 平空時返回: margin + 做空利潤 - exit_fee
        #           = entry_value / leverage + (entry_value - exit_cost) - exit_fee
        #           = entry_value / leverage + entry_value - exit_cost - exit_fee
        # v1.2 修復: 使用 position_leverage 而非 self.leverage
        released_margin = entry_value / self.position_leverage
        gross_profit = entry_value - exit_cost  # 做空毛利（價差，使用實際成交價）
        cash_change = released_margin + gross_profit - exit_fee

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
        self.position_leverage = 1.0  # v1.2: 重置槓桿

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

        v0.7 改進: 計入浮動盈虧 (mark-to-market)

        Args:
            price: 當前價格
            time: 當前時間
        """
        # v0.7: 計算真實權益（包含浮動盈虧）
        equity = self.get_current_equity(price)
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

        v0.7 改進: 計入未實現盈虧 (mark-to-market)
        v1.2 修復: 使用 position_leverage 計算保證金

        Args:
            price: 當前價格

        Returns:
            float: 當前權益 = cash + 浮動盈虧
        """
        if not self.has_position:
            return self.cash

        # 計算浮動盈虧
        position_value = self.position_qty * price
        entry_value = self.position_qty * self.position_entry_price

        if self.position_direction == "long":
            # 多單浮動盈虧 = 當前價值 - 入場價值
            unrealized_pnl = position_value - entry_value
        else:  # short
            # 空單浮動盈虧 = 入場價值 - 當前價值
            unrealized_pnl = entry_value - position_value

        # 計算占用保證金（v1.2: 使用開倉時的槓桿）
        margin_used = entry_value / self.position_leverage

        # 總權益 = cash + 保證金 + 浮動盈虧
        # (cash 在開倉時已扣除保證金，所以要加回來)
        return self.cash + margin_used + unrealized_pnl

    # === v1.0 新增：爆倉檢測 ===

    def get_liquidation_price(self) -> Optional[float]:
        """計算當前持倉的爆倉價格

        公式（簡化版）:
        - 多單: 爆倉價 = 入場價 * (1 - 1/leverage + maintenance_margin_rate)
        - 空單: 爆倉價 = 入場價 * (1 + 1/leverage - maintenance_margin_rate)

        v1.2 修復: 使用 position_leverage 而非 self.leverage

        Returns:
            Optional[float]: 爆倉價格，無持倉時返回 None
        """
        if not self.has_position:
            return None

        entry = self.position_entry_price
        lev = self.position_leverage  # v1.2: 使用開倉時的槓桿
        mmr = self.maintenance_margin_rate

        if self.position_direction == "long":
            # 多單：價格下跌到某點時爆倉
            # 當虧損 = 初始保證金 - 維持保證金時觸發
            # 虧損率 = 1/leverage - mmr
            liq_price = entry * (1 - 1 / lev + mmr)
        else:  # short
            # 空單：價格上漲到某點時爆倉
            liq_price = entry * (1 + 1 / lev - mmr)

        return liq_price

    def check_liquidation(self, current_price: float) -> bool:
        """檢查是否觸發爆倉

        Args:
            current_price: 當前價格

        Returns:
            bool: 是否觸發爆倉
        """
        if not self.has_position:
            return False

        liq_price = self.get_liquidation_price()
        if liq_price is None:
            return False

        if self.position_direction == "long":
            # 多單：當前價格 <= 爆倉價格
            return current_price <= liq_price
        else:  # short
            # 空單：當前價格 >= 爆倉價格
            return current_price >= liq_price

    def check_liquidation_in_bar(self, bar: pd.Series) -> bool:
        """檢查在一根 K 線內是否觸發爆倉

        考慮 K 線的最低/最高價，更精確地判斷是否觸及爆倉價

        Args:
            bar: K 線數據（需包含 high, low）

        Returns:
            bool: 是否觸發爆倉
        """
        if not self.has_position:
            return False

        liq_price = self.get_liquidation_price()
        if liq_price is None:
            return False

        if self.position_direction == "long":
            # 多單：K 線最低價 <= 爆倉價格
            return bar["low"] <= liq_price
        else:  # short
            # 空單：K 線最高價 >= 爆倉價格
            return bar["high"] >= liq_price

    def process_liquidation(self, time: pd.Timestamp, price: float) -> bool:
        """處理爆倉

        強制平倉並記錄爆倉事件，損失全部保證金

        Args:
            time: 爆倉時間
            price: 爆倉執行價格（通常使用爆倉價格或當根 K 線的極端價）

        Returns:
            bool: 是否成功處理爆倉
        """
        if not self.has_position:
            return False

        # 計算損失（全部保證金）
        entry_value = self.position_qty * self.position_entry_price
        margin = entry_value / self.leverage

        # 記錄爆倉事件
        event = LiquidationEvent(
            time=time,
            direction=self.position_direction,
            entry_price=self.position_entry_price,
            liquidation_price=price,
            position_qty=self.position_qty,
            loss=margin,
            leverage=self.leverage,
        )
        self.liquidation_events.append(event)

        # 記錄交易（爆倉也是一筆平倉交易）
        trade = Trade(
            entry_time=self.position_entry_time,
            exit_time=time,
            entry_price=self.position_entry_price,
            exit_price=price,
            qty=self.position_qty,
            pnl=-margin,  # 損失全部保證金
            return_pct=-1.0 / self.leverage + self.maintenance_margin_rate,  # 接近 -100%/leverage
            direction=self.position_direction,
            leverage=self.leverage,
            is_liquidation=True,
        )
        self.trades.append(trade)

        # 清空持倉（保證金已損失，cash 不變）
        self._clear_position()

        return True

    @property
    def was_liquidated(self) -> bool:
        """是否曾經被爆倉（v1.0 新增）"""
        return len(self.liquidation_events) > 0

    @property
    def liquidation_count(self) -> int:
        """爆倉次數（v1.0 新增）"""
        return len(self.liquidation_events)
