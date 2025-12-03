"""
Test strategy for v0.2 that uses position sizer
"""

import pandas as pd
from backtest.engine import BaseStrategy


class TestPositionSizerStrategy(BaseStrategy):
    """Test strategy that uses position_sizer parameter"""

    def __init__(self, broker, data, position_sizer=None):
        super().__init__(broker, data)
        self.position_sizer = position_sizer
        self.sma_period = 20
        self.sma = self.data['close'].rolling(window=self.sma_period).mean()

    def on_bar(self, i: int, row: pd.Series):
        if i < self.sma_period - 1:
            return

        current_price = row['close']
        current_time = row.name
        current_sma = self.sma.iloc[i]

        if pd.notna(current_sma):
            # Buy signal
            if current_price > current_sma and not self.broker.has_position:
                if self.position_sizer is not None:
                    # Get size from position sizer
                    equity = self.broker.get_current_equity(current_price)
                    size = self.position_sizer.get_size(equity, current_price)
                    if size > 0:
                        self.broker.buy(size, current_price, current_time)
                else:
                    # Fall back to buy_all
                    self.broker.buy_all(current_price, current_time)

            # Sell signal
            elif current_price < current_sma and self.broker.has_position:
                self.broker.sell_all(current_price, current_time)
