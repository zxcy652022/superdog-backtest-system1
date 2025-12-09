"""
Position Sizer - 簡單倉位計算器

提供回測引擎使用的簡單倉位計算接口。
更進階的倉位管理請使用 risk.position_sizer 模組。

Version: v0.7
"""

from abc import ABC, abstractmethod


class BasePositionSizer(ABC):
    """倉位計算基類"""

    @abstractmethod
    def get_size(self, equity: float, price: float) -> float:
        """
        計算倉位大小

        Args:
            equity: 當前權益
            price: 進場價格

        Returns:
            float: 倉位大小（<=0 表示不進場）
        """
        raise NotImplementedError


class AllInSizer(BasePositionSizer):
    """全倉進場"""

    def __init__(self, fee_rate: float = 0.0005):
        self.fee_rate = fee_rate

    def get_size(self, equity: float, price: float) -> float:
        if equity <= 0 or price <= 0:
            return 0.0
        return equity / (price * (1 + self.fee_rate))


class FixedCashSizer(BasePositionSizer):
    """固定金額進場"""

    def __init__(self, cash_amount: float, fee_rate: float = 0.0005):
        self.cash_amount = cash_amount
        self.fee_rate = fee_rate

    def get_size(self, equity: float, price: float) -> float:
        if self.cash_amount <= 0 or price <= 0:
            return 0.0
        return self.cash_amount / (price * (1 + self.fee_rate))


class PercentOfEquitySizer(BasePositionSizer):
    """權益百分比進場"""

    def __init__(self, percent: float, fee_rate: float = 0.0005):
        self.percent = percent
        self.fee_rate = fee_rate

    def get_size(self, equity: float, price: float) -> float:
        if equity <= 0 or price <= 0 or self.percent <= 0:
            return 0.0
        amount = equity * self.percent
        return amount / (price * (1 + self.fee_rate))
