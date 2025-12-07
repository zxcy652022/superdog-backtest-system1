"""
Position Sizer v0.6 Phase 4

倉位管理器 - Kelly、固定風險、波動率調整等

核心功能:
- Kelly Criterion 倉位計算
- 固定風險百分比
- 波動率調整倉位
- 最大倉位限制
- 多策略資金分配

Version: v0.6.0-phase4
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np


class SizingMethod(Enum):
    """倉位計算方法"""

    FIXED_AMOUNT = "fixed_amount"  # 固定金額
    FIXED_RISK = "fixed_risk"  # 固定風險百分比
    KELLY = "kelly"  # Kelly Criterion
    VOLATILITY_ADJUSTED = "volatility_adjusted"  # 波動率調整
    EQUITY_PERCENTAGE = "equity_percentage"  # 權益百分比
    OPTIMAL_F = "optimal_f"  # Optimal F


@dataclass
class PositionSize:
    """倉位大小結果

    Example:
        >>> size = sizer.calculate_position_size(
        ...     account_balance=10000,
        ...     entry_price=50000,
        ...     stop_loss=49000
        ... )
        >>> print(f"Size: {size.position_size:.4f} BTC")
        >>> print(f"Value: ${size.position_value:.2f}")
    """

    position_size: float  # 持倉數量
    position_value: float  # 持倉價值
    risk_amount: float  # 風險金額
    risk_pct: float  # 風險百分比
    sizing_method: SizingMethod  # 使用的計算方法
    max_position_reached: bool = False  # 是否達到最大倉位
    leverage: float = 1.0  # 使用的槓桿
    notes: str = ""  # 備註


class PositionSizer:
    """倉位管理器

    提供多種倉位計算方法

    Example:
        >>> sizer = PositionSizer(
        ...     default_risk_pct=0.02,
        ...     max_position_pct=0.3
        ... )
        >>> size = sizer.calculate_position_size(
        ...     account_balance=10000,
        ...     entry_price=50000,
        ...     stop_loss=49000,
        ...     method=SizingMethod.FIXED_RISK
        ... )
    """

    def __init__(
        self,
        default_risk_pct: float = 0.02,  # 默認風險 2%
        max_position_pct: float = 0.3,  # 最大倉位 30%
        max_leverage: float = 10,  # 最大槓桿
        kelly_fraction: float = 0.25,  # Kelly 分數（保守）
    ):
        """初始化倉位管理器

        Args:
            default_risk_pct: 默認風險百分比
            max_position_pct: 最大倉位百分比
            max_leverage: 最大槓桿倍數
            kelly_fraction: Kelly Criterion 使用的分數
        """
        self.default_risk_pct = default_risk_pct
        self.max_position_pct = max_position_pct
        self.max_leverage = max_leverage
        self.kelly_fraction = kelly_fraction

    def calculate_position_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        method: SizingMethod = SizingMethod.FIXED_RISK,
        risk_pct: Optional[float] = None,
        leverage: float = 1.0,
        volatility: Optional[float] = None,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        target_position_value: Optional[float] = None,
    ) -> PositionSize:
        """計算倉位大小

        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            stop_loss: 止損價格
            method: 倉位計算方法
            risk_pct: 風險百分比（可選）
            leverage: 槓桿倍數
            volatility: 波動率（用於波動率調整法）
            win_rate: 勝率（用於 Kelly）
            avg_win: 平均盈利（用於 Kelly）
            avg_loss: 平均虧損（用於 Kelly）
            target_position_value: 目標持倉價值（固定金額法）

        Returns:
            PositionSize: 倉位計算結果
        """
        # 限制槓桿
        leverage = min(leverage, self.max_leverage)

        # 根據方法計算
        if method == SizingMethod.FIXED_AMOUNT:
            return self._fixed_amount_sizing(
                account_balance,
                entry_price,
                stop_loss,
                target_position_value or (account_balance * self.max_position_pct),
                leverage,
            )

        elif method == SizingMethod.FIXED_RISK:
            risk = risk_pct or self.default_risk_pct
            return self._fixed_risk_sizing(account_balance, entry_price, stop_loss, risk, leverage)

        elif method == SizingMethod.KELLY:
            if win_rate is None or avg_win is None or avg_loss is None:
                # 如果沒有提供 Kelly 參數，回退到固定風險
                return self._fixed_risk_sizing(
                    account_balance,
                    entry_price,
                    stop_loss,
                    risk_pct or self.default_risk_pct,
                    leverage,
                )
            return self._kelly_sizing(
                account_balance, entry_price, stop_loss, win_rate, avg_win, avg_loss, leverage
            )

        elif method == SizingMethod.VOLATILITY_ADJUSTED:
            if volatility is None:
                raise ValueError("Volatility is required for VOLATILITY_ADJUSTED method")
            return self._volatility_adjusted_sizing(
                account_balance,
                entry_price,
                stop_loss,
                volatility,
                risk_pct or self.default_risk_pct,
                leverage,
            )

        elif method == SizingMethod.EQUITY_PERCENTAGE:
            equity_pct = risk_pct or self.max_position_pct
            return self._equity_percentage_sizing(
                account_balance, entry_price, equity_pct, leverage
            )

        else:
            raise ValueError(f"Unknown sizing method: {method}")

    def _fixed_amount_sizing(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        target_value: float,
        leverage: float,
    ) -> PositionSize:
        """固定金額倉位計算

        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            stop_loss: 止損價格
            target_value: 目標持倉價值
            leverage: 槓桿倍數

        Returns:
            PositionSize: 倉位結果
        """
        # 計算持倉數量
        position_size = target_value / entry_price

        # 限制最大倉位
        max_value = account_balance * self.max_position_pct * leverage
        if target_value > max_value:
            position_size = max_value / entry_price
            target_value = max_value
            max_reached = True
        else:
            max_reached = False

        # 計算風險
        risk_per_unit = abs(entry_price - stop_loss)
        risk_amount = position_size * risk_per_unit
        risk_pct = risk_amount / account_balance

        return PositionSize(
            position_size=position_size,
            position_value=target_value,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            sizing_method=SizingMethod.FIXED_AMOUNT,
            max_position_reached=max_reached,
            leverage=leverage,
        )

    def _fixed_risk_sizing(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        risk_pct: float,
        leverage: float,
    ) -> PositionSize:
        """固定風險百分比倉位計算

        這是最常用的倉位管理方法

        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            stop_loss: 止損價格
            risk_pct: 風險百分比
            leverage: 槓桿倍數

        Returns:
            PositionSize: 倉位結果

        Example:
            >>> # 風險 2% 的倉位
            >>> size = sizer._fixed_risk_sizing(10000, 50000, 49000, 0.02, 1)
            >>> # 期望風險 = $200 (10000 * 0.02)
            >>> # 止損距離 = $1000 (50000 - 49000)
            >>> # 倉位 = 200 / 1000 = 0.2 BTC
        """
        # 風險金額
        risk_amount = account_balance * risk_pct

        # 每單位風險
        risk_per_unit = abs(entry_price - stop_loss)

        # 計算倉位
        position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0

        # 計算倉位價值
        position_value = position_size * entry_price

        # 檢查最大倉位限制
        max_value = account_balance * self.max_position_pct * leverage
        max_reached = False
        if position_value > max_value:
            position_size = max_value / entry_price
            position_value = max_value
            risk_amount = position_size * risk_per_unit
            risk_pct = risk_amount / account_balance
            max_reached = True

        return PositionSize(
            position_size=position_size,
            position_value=position_value,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            sizing_method=SizingMethod.FIXED_RISK,
            max_position_reached=max_reached,
            leverage=leverage,
        )

    def _kelly_sizing(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        leverage: float,
    ) -> PositionSize:
        """Kelly Criterion 倉位計算

        Kelly = W - (1-W)/R
        W = 勝率
        R = 盈虧比 (avg_win / avg_loss)

        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            stop_loss: 止損價格
            win_rate: 勝率
            avg_win: 平均盈利（百分比）
            avg_loss: 平均虧損（百分比）
            leverage: 槓桿倍數

        Returns:
            PositionSize: 倉位結果

        Example:
            >>> # 勝率 60%, 盈虧比 2:1
            >>> size = sizer._kelly_sizing(
            ...     10000, 50000, 49000,
            ...     win_rate=0.6, avg_win=0.04, avg_loss=0.02, leverage=1
            ... )
        """
        # 計算 Kelly 百分比
        if avg_loss > 0:
            profit_ratio = avg_win / avg_loss
            kelly_pct = win_rate - ((1 - win_rate) / profit_ratio)
        else:
            kelly_pct = 0

        # 使用 Kelly 分數（保守）
        kelly_pct = max(0, kelly_pct) * self.kelly_fraction

        # 限制最大倉位
        kelly_pct = min(kelly_pct, self.max_position_pct)

        # 計算目標持倉價值
        target_value = account_balance * kelly_pct * leverage

        # 計算倉位
        position_size = target_value / entry_price

        # 計算風險
        risk_per_unit = abs(entry_price - stop_loss)
        risk_amount = position_size * risk_per_unit
        risk_pct = risk_amount / account_balance

        notes = f"Kelly: {kelly_pct:.2%} (fraction: {self.kelly_fraction})"

        return PositionSize(
            position_size=position_size,
            position_value=target_value,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            sizing_method=SizingMethod.KELLY,
            max_position_reached=kelly_pct >= self.max_position_pct,
            leverage=leverage,
            notes=notes,
        )

    def _volatility_adjusted_sizing(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        volatility: float,
        base_risk_pct: float,
        leverage: float,
    ) -> PositionSize:
        """波動率調整倉位計算

        根據市場波動率動態調整倉位
        高波動 -> 小倉位
        低波動 -> 大倉位

        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            stop_loss: 止損價格
            volatility: 當前波動率
            base_risk_pct: 基礎風險百分比
            leverage: 槓桿倍數

        Returns:
            PositionSize: 倉位結果
        """
        # 目標波動率（假設為 2%）
        target_volatility = 0.02

        # 波動率調整因子
        volatility_factor = target_volatility / volatility if volatility > 0 else 1

        # 限制調整範圍（0.5x - 2x）
        volatility_factor = np.clip(volatility_factor, 0.5, 2.0)

        # 調整風險百分比
        adjusted_risk_pct = base_risk_pct * volatility_factor

        # 使用固定風險法計算
        result = self._fixed_risk_sizing(
            account_balance, entry_price, stop_loss, adjusted_risk_pct, leverage
        )

        result.sizing_method = SizingMethod.VOLATILITY_ADJUSTED
        result.notes = f"Vol Factor: {volatility_factor:.2f}x (Vol: {volatility:.2%})"

        return result

    def _equity_percentage_sizing(
        self, account_balance: float, entry_price: float, equity_pct: float, leverage: float
    ) -> PositionSize:
        """權益百分比倉位計算

        簡單地使用賬戶權益的固定百分比

        Args:
            account_balance: 賬戶餘額
            entry_price: 入場價格
            equity_pct: 權益百分比
            leverage: 槓桿倍數

        Returns:
            PositionSize: 倉位結果
        """
        # 限制最大倉位
        equity_pct = min(equity_pct, self.max_position_pct)

        # 目標持倉價值
        target_value = account_balance * equity_pct * leverage

        # 計算倉位
        position_size = target_value / entry_price

        return PositionSize(
            position_size=position_size,
            position_value=target_value,
            risk_amount=0,  # 未知（沒有止損信息）
            risk_pct=0,
            sizing_method=SizingMethod.EQUITY_PERCENTAGE,
            max_position_reached=equity_pct >= self.max_position_pct,
            leverage=leverage,
        )

    def allocate_capital(
        self, total_capital: float, strategies: List[Dict], method: str = "equal"
    ) -> Dict[str, float]:
        """多策略資金分配

        Args:
            total_capital: 總資金
            strategies: 策略列表，每個策略包含 {'name': str, 'weight': float, 'sharpe': float, ...}
            method: 分配方法 ('equal', 'weighted', 'risk_parity', 'sharpe_optimized')

        Returns:
            Dict: 策略資金分配 {strategy_name: allocated_capital}

        Example:
            >>> strategies = [
            ...     {'name': 'Strategy A', 'weight': 0.6, 'sharpe': 1.5},
            ...     {'name': 'Strategy B', 'weight': 0.4, 'sharpe': 1.2}
            ... ]
            >>> allocation = sizer.allocate_capital(100000, strategies, 'weighted')
        """
        if method == "equal":
            # 平均分配
            allocation_per_strategy = total_capital / len(strategies)
            return {s["name"]: allocation_per_strategy for s in strategies}

        elif method == "weighted":
            # 按權重分配
            total_weight = sum(s.get("weight", 1.0) for s in strategies)
            return {
                s["name"]: total_capital * s.get("weight", 1.0) / total_weight for s in strategies
            }

        elif method == "risk_parity":
            # 風險平價（根據波動率反向分配）
            volatilities = [s.get("volatility", 0.02) for s in strategies]
            inv_vols = [1 / v if v > 0 else 0 for v in volatilities]
            total_inv_vol = sum(inv_vols)

            return {
                s["name"]: total_capital * (inv_vols[i] / total_inv_vol)
                for i, s in enumerate(strategies)
            }

        elif method == "sharpe_optimized":
            # 按 Sharpe Ratio 分配
            sharpes = [max(s.get("sharpe", 0), 0) for s in strategies]
            total_sharpe = sum(sharpes)

            if total_sharpe == 0:
                # 回退到平均分配
                return {s["name"]: total_capital / len(strategies) for s in strategies}

            return {
                s["name"]: total_capital * (sharpes[i] / total_sharpe)
                for i, s in enumerate(strategies)
            }

        else:
            raise ValueError(f"Unknown allocation method: {method}")

    def calculate_optimal_leverage(
        self, expected_return: float, volatility: float, max_drawdown_tolerance: float = 0.20
    ) -> float:
        """計算最優槓桿

        基於預期收益和波動率

        Args:
            expected_return: 預期年化收益率
            volatility: 年化波動率
            max_drawdown_tolerance: 最大回撤容忍度

        Returns:
            float: 建議槓桿倍數

        Example:
            >>> optimal_lev = sizer.calculate_optimal_leverage(
            ...     expected_return=0.15,
            ...     volatility=0.30,
            ...     max_drawdown_tolerance=0.20
            ... )
        """
        # Kelly Leverage = Expected Return / Variance
        kelly_leverage = expected_return / (volatility**2) if volatility > 0 else 1

        # 基於回撤容忍度的槓桿
        # 假設最大回撤 ≈ 3 * volatility * leverage
        dd_leverage = max_drawdown_tolerance / (3 * volatility) if volatility > 0 else 1

        # 取較保守的值
        optimal = min(kelly_leverage, dd_leverage)

        # 限制在合理範圍
        optimal = np.clip(optimal, 1, self.max_leverage)

        return optimal


# ===== 便捷函數 =====


def calculate_kelly_size(
    account_balance: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    kelly_fraction: float = 0.25,
) -> float:
    """快速計算 Kelly 倉位百分比

    Args:
        account_balance: 賬戶餘額
        win_rate: 勝率
        avg_win: 平均盈利百分比
        avg_loss: 平均虧損百分比
        kelly_fraction: Kelly 分數（建議 0.25-0.5）

    Returns:
        float: Kelly 倉位百分比

    Example:
        >>> kelly_pct = calculate_kelly_size(
        ...     account_balance=10000,
        ...     win_rate=0.6,
        ...     avg_win=0.04,
        ...     avg_loss=0.02,
        ...     kelly_fraction=0.25
        ... )
        >>> print(f"Kelly Position: {kelly_pct:.2%}")
    """
    if avg_loss > 0:
        profit_ratio = avg_win / avg_loss
        kelly_pct = win_rate - ((1 - win_rate) / profit_ratio)
    else:
        kelly_pct = 0

    kelly_pct = max(0, kelly_pct) * kelly_fraction

    return kelly_pct


def calculate_fixed_risk_size(
    account_balance: float, entry_price: float, stop_loss: float, risk_pct: float = 0.02
) -> float:
    """快速計算固定風險倉位

    Args:
        account_balance: 賬戶餘額
        entry_price: 入場價格
        stop_loss: 止損價格
        risk_pct: 風險百分比（默認 2%）

    Returns:
        float: 倉位數量

    Example:
        >>> size = calculate_fixed_risk_size(
        ...     account_balance=10000,
        ...     entry_price=50000,
        ...     stop_loss=49000,
        ...     risk_pct=0.02
        ... )
        >>> print(f"Position Size: {size:.4f} BTC")
    """
    risk_amount = account_balance * risk_pct
    risk_per_unit = abs(entry_price - stop_loss)

    return risk_amount / risk_per_unit if risk_per_unit > 0 else 0
