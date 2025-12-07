"""
Dynamic Stops Manager v0.6 Phase 4

動態止損止盈管理 - ATR止損、阻力位止盈、移動止損

核心功能:
- ATR 動態止損
- 支撐壓力位止盈
- 移動止損（Trailing Stop）
- RSI 動態調整
- 進場原因消滅平倉

Version: v0.6.0-phase4
"""

from dataclasses import dataclass
from typing import Optional, Dict
from enum import Enum
import pandas as pd
import numpy as np

from .support_resistance import SupportResistanceDetector, SRLevel


class StopLossType(Enum):
    """止損類型"""
    FIXED = "fixed"           # 固定百分比
    ATR = "atr"              # ATR 動態止損
    SUPPORT = "support"       # 支撐位止損
    TRAILING = "trailing"     # 移動止損


class TakeProfitType(Enum):
    """止盈類型"""
    FIXED = "fixed"           # 固定百分比
    RESISTANCE = "resistance" # 壓力位止盈
    RISK_REWARD = "risk_reward"  # 風險回報比
    TRAILING = "trailing"     # 移動止盈


@dataclass
class StopUpdate:
    """止損止盈更新"""
    new_stop_loss: Optional[float] = None
    new_take_profit: Optional[float] = None
    should_exit: bool = False
    exit_reason: str = ""
    trailing_active: bool = False


class DynamicStopManager:
    """動態止損止盈管理器

    Example:
        >>> manager = DynamicStopManager()
        >>> update = manager.update_stops(
        ...     entry_price=50000,
        ...     current_price=51000,
        ...     position_side='long',
        ...     ohlcv=data,
        ...     stop_loss_type=StopLossType.ATR
        ... )
    """

    def __init__(
        self,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        trailing_activation_pct: float = 0.02,  # 2%
        trailing_distance_pct: float = 0.01     # 1%
    ):
        """初始化管理器

        Args:
            atr_period: ATR 週期
            atr_multiplier: ATR 倍數
            trailing_activation_pct: 移動止損激活百分比
            trailing_distance_pct: 移動止損距離百分比
        """
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.trailing_activation_pct = trailing_activation_pct
        self.trailing_distance_pct = trailing_distance_pct

        self.sr_detector = SupportResistanceDetector()
        self.highest_price_since_entry = None
        self.lowest_price_since_entry = None

    def update_stops(
        self,
        entry_price: float,
        current_price: float,
        position_side: str,
        ohlcv: pd.DataFrame,
        stop_loss_type: StopLossType = StopLossType.ATR,
        take_profit_type: TakeProfitType = TakeProfitType.RESISTANCE,
        current_stop_loss: Optional[float] = None,
        current_take_profit: Optional[float] = None,
        fixed_sl_pct: float = 0.02,
        fixed_tp_pct: float = 0.05,
        risk_reward_ratio: float = 2.0
    ) -> StopUpdate:
        """更新止損止盈

        Args:
            entry_price: 入場價格
            current_price: 當前價格
            position_side: 持倉方向 ('long'/'short')
            ohlcv: OHLCV 數據
            stop_loss_type: 止損類型
            take_profit_type: 止盈類型
            current_stop_loss: 當前止損價
            current_take_profit: 當前止盈價
            fixed_sl_pct: 固定止損百分比
            fixed_tp_pct: 固定止盈百分比
            risk_reward_ratio: 風險回報比

        Returns:
            StopUpdate: 更新結果
        """
        # 更新最高/最低價
        if position_side == 'long':
            if self.highest_price_since_entry is None:
                self.highest_price_since_entry = current_price
            else:
                self.highest_price_since_entry = max(self.highest_price_since_entry, current_price)
        else:
            if self.lowest_price_since_entry is None:
                self.lowest_price_since_entry = current_price
            else:
                self.lowest_price_since_entry = min(self.lowest_price_since_entry, current_price)

        # 計算新止損
        new_stop_loss = self._calculate_stop_loss(
            entry_price, current_price, position_side,
            ohlcv, stop_loss_type, current_stop_loss, fixed_sl_pct
        )

        # 計算新止盈
        new_take_profit = self._calculate_take_profit(
            entry_price, current_price, position_side,
            ohlcv, take_profit_type, fixed_tp_pct,
            risk_reward_ratio, new_stop_loss
        )

        # 檢查是否觸發止損/止盈
        should_exit, exit_reason = self._check_exit_conditions(
            current_price, position_side,
            new_stop_loss, new_take_profit
        )

        return StopUpdate(
            new_stop_loss=new_stop_loss,
            new_take_profit=new_take_profit,
            should_exit=should_exit,
            exit_reason=exit_reason
        )

    def _calculate_stop_loss(
        self,
        entry_price: float,
        current_price: float,
        position_side: str,
        ohlcv: pd.DataFrame,
        stop_type: StopLossType,
        current_sl: Optional[float],
        fixed_pct: float
    ) -> float:
        """計算止損價格"""

        if stop_type == StopLossType.FIXED:
            # 固定百分比止損
            if position_side == 'long':
                return entry_price * (1 - fixed_pct)
            else:
                return entry_price * (1 + fixed_pct)

        elif stop_type == StopLossType.ATR:
            # ATR 動態止損
            atr = self._calculate_atr(ohlcv)
            if position_side == 'long':
                return current_price - (atr * self.atr_multiplier)
            else:
                return current_price + (atr * self.atr_multiplier)

        elif stop_type == StopLossType.SUPPORT:
            # 支撐位止損
            levels = self.sr_detector.detect(ohlcv)
            if position_side == 'long':
                support = self.sr_detector.get_nearest_support(current_price, levels)
                return support.price if support else entry_price * (1 - fixed_pct)
            else:
                resistance = self.sr_detector.get_nearest_resistance(current_price, levels)
                return resistance.price if resistance else entry_price * (1 + fixed_pct)

        elif stop_type == StopLossType.TRAILING:
            # 移動止損
            return self._calculate_trailing_stop(
                entry_price, current_price, position_side, current_sl
            )

        return entry_price * (1 - fixed_pct if position_side == 'long' else 1 + fixed_pct)

    def _calculate_take_profit(
        self,
        entry_price: float,
        current_price: float,
        position_side: str,
        ohlcv: pd.DataFrame,
        tp_type: TakeProfitType,
        fixed_pct: float,
        risk_reward: float,
        stop_loss: float
    ) -> float:
        """計算止盈價格"""

        if tp_type == TakeProfitType.FIXED:
            # 固定百分比止盈
            if position_side == 'long':
                return entry_price * (1 + fixed_pct)
            else:
                return entry_price * (1 - fixed_pct)

        elif tp_type == TakeProfitType.RESISTANCE:
            # 壓力位止盈
            levels = self.sr_detector.detect(ohlcv)
            if position_side == 'long':
                resistance = self.sr_detector.get_nearest_resistance(current_price, levels)
                return resistance.price if resistance else entry_price * (1 + fixed_pct)
            else:
                support = self.sr_detector.get_nearest_support(current_price, levels)
                return support.price if support else entry_price * (1 - fixed_pct)

        elif tp_type == TakeProfitType.RISK_REWARD:
            # 基於風險回報比
            risk = abs(entry_price - stop_loss)
            reward = risk * risk_reward
            if position_side == 'long':
                return entry_price + reward
            else:
                return entry_price - reward

        return entry_price * (1 + fixed_pct if position_side == 'long' else 1 - fixed_pct)

    def _calculate_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        position_side: str,
        current_sl: Optional[float]
    ) -> float:
        """計算移動止損"""

        if position_side == 'long':
            # 多頭：檢查是否達到激活條件
            profit_pct = (current_price - entry_price) / entry_price
            if profit_pct >= self.trailing_activation_pct:
                # 激活移動止損
                trailing_sl = current_price * (1 - self.trailing_distance_pct)
                if current_sl is None:
                    return trailing_sl
                else:
                    return max(current_sl, trailing_sl)  # 只能上移
            return current_sl if current_sl else entry_price * (1 - 0.02)

        else:  # short
            profit_pct = (entry_price - current_price) / entry_price
            if profit_pct >= self.trailing_activation_pct:
                trailing_sl = current_price * (1 + self.trailing_distance_pct)
                if current_sl is None:
                    return trailing_sl
                else:
                    return min(current_sl, trailing_sl)  # 只能下移
            return current_sl if current_sl else entry_price * (1 + 0.02)

    def _calculate_atr(self, ohlcv: pd.DataFrame) -> float:
        """計算 ATR"""
        if len(ohlcv) < self.atr_period:
            return ohlcv['high'].iloc[-1] - ohlcv['low'].iloc[-1]

        high = ohlcv['high'].values
        low = ohlcv['low'].values
        close = ohlcv['close'].values

        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                abs(high[1:] - close[:-1]),
                abs(low[1:] - close[:-1])
            )
        )

        atr = np.mean(tr[-self.atr_period:])
        return atr

    def _check_exit_conditions(
        self,
        current_price: float,
        position_side: str,
        stop_loss: float,
        take_profit: float
    ) -> tuple:
        """檢查是否應該平倉"""

        if position_side == 'long':
            if current_price <= stop_loss:
                return True, "止損觸發"
            elif current_price >= take_profit:
                return True, "止盈觸發"
        else:  # short
            if current_price >= stop_loss:
                return True, "止損觸發"
            elif current_price <= take_profit:
                return True, "止盈觸發"

        return False, ""

    def reset(self):
        """重置狀態"""
        self.highest_price_since_entry = None
        self.lowest_price_since_entry = None


# ===== 便捷函數 =====

def create_atr_stops(
    entry_price: float,
    position_side: str,
    atr_value: float,
    atr_multiplier: float = 2.0,
    risk_reward_ratio: float = 2.0
) -> Dict[str, float]:
    """創建 ATR 止損止盈

    Args:
        entry_price: 入場價格
        position_side: 持倉方向
        atr_value: ATR 值
        atr_multiplier: ATR 倍數
        risk_reward_ratio: 風險回報比

    Returns:
        Dict: {'stop_loss': float, 'take_profit': float}
    """
    if position_side == 'long':
        stop_loss = entry_price - (atr_value * atr_multiplier)
        take_profit = entry_price + (atr_value * atr_multiplier * risk_reward_ratio)
    else:
        stop_loss = entry_price + (atr_value * atr_multiplier)
        take_profit = entry_price - (atr_value * atr_multiplier * risk_reward_ratio)

    return {
        'stop_loss': stop_loss,
        'take_profit': take_profit
    }


def create_resistance_stops(
    entry_price: float,
    position_side: str,
    support_level: Optional[float],
    resistance_level: Optional[float],
    fallback_sl_pct: float = 0.02,
    fallback_tp_pct: float = 0.05
) -> Dict[str, float]:
    """創建基於支撐壓力位的止損止盈

    Args:
        entry_price: 入場價格
        position_side: 持倉方向
        support_level: 支撐位價格
        resistance_level: 壓力位價格
        fallback_sl_pct: 回退止損百分比
        fallback_tp_pct: 回退止盈百分比

    Returns:
        Dict: {'stop_loss': float, 'take_profit': float}
    """
    if position_side == 'long':
        stop_loss = support_level if support_level else entry_price * (1 - fallback_sl_pct)
        take_profit = resistance_level if resistance_level else entry_price * (1 + fallback_tp_pct)
    else:
        stop_loss = resistance_level if resistance_level else entry_price * (1 + fallback_sl_pct)
        take_profit = support_level if support_level else entry_price * (1 - fallback_tp_pct)

    return {
        'stop_loss': stop_loss,
        'take_profit': take_profit
    }
