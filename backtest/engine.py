"""
Backtest Engine v0.1

Core backtest engine module.
Handles main backtest loop: iterate bars, call strategy, update equity, compute metrics.
"""

from dataclasses import dataclass
from typing import Dict, List, Type
import pandas as pd
from backtest.broker import SimulatedBroker, Trade
from backtest.metrics import compute_basic_metrics


@dataclass
class BacktestResult:
    """Backtest result"""
    equity_curve: pd.Series
    trades: List[Trade]
    metrics: Dict[str, float]


class BaseStrategy:
    """Base strategy class"""

    def __init__(self, broker: SimulatedBroker, data: pd.DataFrame):
        self.broker = broker
        self.data = data

    def on_bar(self, i: int, row: pd.Series):
        raise NotImplementedError("Strategy must implement on_bar method")


def run_backtest(
    data: pd.DataFrame,
    strategy_cls: Type[BaseStrategy],
    initial_cash: float = 10000,
    fee_rate: float = 0.0005
) -> BacktestResult:
    """
    Run backtest

    Args:
        data: OHLCV DataFrame with DatetimeIndex
        strategy_cls: Strategy class (inherits from BaseStrategy)
        initial_cash: Initial capital (default 10000)
        fee_rate: Fee rate (default 0.0005 = 0.05%)

    Returns:
        BacktestResult containing equity curve, trades, and metrics
    """
    _validate_data(data)

    broker = SimulatedBroker(initial_cash=initial_cash, fee_rate=fee_rate)
    strategy = strategy_cls(broker=broker, data=data)

    for i, (timestamp, row) in enumerate(data.iterrows()):
        strategy.on_bar(i, row)
        current_price = row['close']
        broker.update_equity(price=current_price, time=timestamp)

    equity_curve = broker.get_equity_curve()
    trades = broker.trades
    metrics = compute_basic_metrics(equity_curve, trades)

    result = BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        metrics=metrics
    )

    return result


def _validate_data(data: pd.DataFrame):
    if not isinstance(data, pd.DataFrame):
        raise ValueError("Data must be pandas DataFrame")

    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data index must be DatetimeIndex")

    required_columns = ['open', 'high', 'low', 'close', 'volume']
    missing_columns = set(required_columns) - set(data.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    if len(data) == 0:
        raise ValueError("Data cannot be empty")

    if not data.index.is_monotonic_increasing:
        raise ValueError("Data must be sorted by time (ascending)")


def print_backtest_summary(result: BacktestResult):
    """Print backtest summary"""
    print("\n" + "=" * 60)
    print("Backtest Summary")
    print("=" * 60)

    print(f"\nInitial Capital: {result.equity_curve.iloc[0]:.2f}")
    print(f"Final Capital: {result.equity_curve.iloc[-1]:.2f}")
    print(f"Period: {result.equity_curve.index[0]} ~ {result.equity_curve.index[-1]}")

    print(f"\nPerformance Metrics:")
    print(f"  Total Return: {result.metrics['total_return']:.2%}")
    print(f"  Max Drawdown: {result.metrics['max_drawdown']:.2%}")
    print(f"  Num Trades: {result.metrics['num_trades']}")
    print(f"  Win Rate: {result.metrics['win_rate']:.2%}")
    print(f"  Avg Trade Return: {result.metrics['avg_trade_return']:.2%}")
    print(f"  Total PnL: {result.metrics['total_pnl']:.2f}")
    print(f"  Avg PnL: {result.metrics['avg_pnl']:.2f}")

    if len(result.trades) > 0:
        print(f"\nRecent 5 Trades:")
        for i, trade in enumerate(result.trades[-5:], 1):
            print(f"  {i}. {trade.entry_time} -> {trade.exit_time}")
            print(f"     Price: {trade.entry_price:.2f} -> {trade.exit_price:.2f}")
            print(f"     PnL: {trade.pnl:.2f} ({trade.return_pct:.2%})")

    print("\n" + "=" * 60)
