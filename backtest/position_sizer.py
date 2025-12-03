"""
Position Sizer Module v0.2

Provides different position sizing strategies for backtest.
Controls how much capital to allocate per trade.
"""

from abc import ABC, abstractmethod


class BasePositionSizer(ABC):
    """Abstract base class for position sizers"""

    @abstractmethod
    def get_size(self, equity: float, price: float) -> float:
        """
        Calculate position size

        Args:
            equity: Current equity
            price: Entry price

        Returns:
            float: Position size (can be fractional, <= 0 means no entry)
        """
        raise NotImplementedError("Subclass must implement get_size()")


class AllInSizer(BasePositionSizer):
    """All-in position sizer - uses all available equity"""

    def __init__(self, fee_rate: float = 0.0005):
        """
        Args:
            fee_rate: Transaction fee rate
        """
        self.fee_rate = fee_rate

    def get_size(self, equity: float, price: float) -> float:
        """
        Calculate all-in position size

        Args:
            equity: Current equity
            price: Entry price

        Returns:
            float: Maximum position size after accounting for fees
        """
        if equity <= 0 or price <= 0:
            return 0.0

        # size = equity / (price * (1 + fee_rate))
        size = equity / (price * (1 + self.fee_rate))
        return size


class FixedCashSizer(BasePositionSizer):
    """Fixed cash amount position sizer"""

    def __init__(self, cash_amount: float, fee_rate: float = 0.0005):
        """
        Args:
            cash_amount: Fixed cash amount to use per trade
            fee_rate: Transaction fee rate
        """
        self.cash_amount = cash_amount
        self.fee_rate = fee_rate

    def get_size(self, equity: float, price: float) -> float:
        """
        Calculate fixed cash position size

        Args:
            equity: Current equity (not used, but kept for interface consistency)
            price: Entry price

        Returns:
            float: Position size for fixed cash amount
        """
        if self.cash_amount <= 0 or price <= 0:
            return 0.0

        # size = cash_amount / (price * (1 + fee_rate))
        size = self.cash_amount / (price * (1 + self.fee_rate))
        return size


class PercentOfEquitySizer(BasePositionSizer):
    """Percent of equity position sizer"""

    def __init__(self, percent: float, fee_rate: float = 0.0005):
        """
        Args:
            percent: Percentage of equity to use (0.0 to 1.0)
            fee_rate: Transaction fee rate
        """
        self.percent = percent
        self.fee_rate = fee_rate

    def get_size(self, equity: float, price: float) -> float:
        """
        Calculate percent of equity position size

        Args:
            equity: Current equity
            price: Entry price

        Returns:
            float: Position size for percentage of equity
        """
        if equity <= 0 or price <= 0 or self.percent <= 0:
            return 0.0

        # amount = equity * percent
        # size = amount / (price * (1 + fee_rate))
        amount = equity * self.percent
        size = amount / (price * (1 + self.fee_rate))
        return size
