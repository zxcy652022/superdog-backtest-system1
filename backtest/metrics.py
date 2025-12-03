"""
Metrics Module v0.1

Compute backtest performance metrics.
Includes basic metrics: total return, max drawdown, number of trades, win rate, average return.
"""

import pandas as pd
import numpy as np
from typing import List, Dict
from backtest.broker import Trade


def compute_basic_metrics(equity_curve: pd.Series, trades: List[Trade]) -> Dict[str, float]:
    """
    Compute basic performance metrics

    Args:
        equity_curve: Equity curve (pd.Series with time index)
        trades: List of trades

    Returns:
        Dict of metrics including:
            - total_return: Total return rate
            - max_drawdown: Maximum drawdown
            - num_trades: Number of trades
            - win_rate: Win rate
            - avg_trade_return: Average return per trade
            - total_pnl: Total PnL
            - avg_pnl: Average PnL per trade
    """
    metrics = {}

    if len(equity_curve) == 0:
        return {
            'total_return': 0.0,
            'max_drawdown': 0.0,
            'num_trades': 0,
            'win_rate': 0.0,
            'avg_trade_return': 0.0,
            'total_pnl': 0.0,
            'avg_pnl': 0.0
        }

    # 1. Total return
    initial_equity = equity_curve.iloc[0]
    final_equity = equity_curve.iloc[-1]
    total_return = (final_equity - initial_equity) / initial_equity
    metrics['total_return'] = total_return

    # 2. Max drawdown
    max_drawdown = compute_max_drawdown(equity_curve)
    metrics['max_drawdown'] = max_drawdown

    # 3. Number of trades
    num_trades = len(trades)
    metrics['num_trades'] = num_trades

    # 4. Win rate
    if num_trades > 0:
        winning_trades = sum(1 for trade in trades if trade.pnl > 0)
        win_rate = winning_trades / num_trades
    else:
        win_rate = 0.0
    metrics['win_rate'] = win_rate

    # 5. Average trade return
    if num_trades > 0:
        avg_trade_return = sum(trade.return_pct for trade in trades) / num_trades
    else:
        avg_trade_return = 0.0
    metrics['avg_trade_return'] = avg_trade_return

    # 6. Total PnL
    total_pnl = sum(trade.pnl for trade in trades)
    metrics['total_pnl'] = total_pnl

    # 7. Average PnL
    if num_trades > 0:
        avg_pnl = total_pnl / num_trades
    else:
        avg_pnl = 0.0
    metrics['avg_pnl'] = avg_pnl

    return metrics


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Compute maximum drawdown

    Args:
        equity_curve: Equity curve

    Returns:
        float: Maximum drawdown (negative value)
    """
    if len(equity_curve) == 0:
        return 0.0

    cumulative_max = equity_curve.expanding().max()
    drawdown = (equity_curve - cumulative_max) / cumulative_max
    max_dd = drawdown.min()

    return max_dd if not np.isnan(max_dd) else 0.0


def compute_sharpe_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365 * 24
) -> float:
    """
    Compute Sharpe ratio

    Args:
        equity_curve: Equity curve
        risk_free_rate: Risk-free rate (annualized)
        periods_per_year: Periods per year (8760 for hourly data)

    Returns:
        float: Sharpe ratio
    """
    if len(equity_curve) < 2:
        return 0.0

    returns = equity_curve.pct_change().dropna()

    if len(returns) == 0:
        return 0.0

    mean_return = returns.mean()
    std_return = returns.std()

    if std_return == 0:
        return 0.0

    sharpe = (mean_return * periods_per_year - risk_free_rate) / (std_return * np.sqrt(periods_per_year))

    return sharpe if not np.isnan(sharpe) else 0.0


def compute_extended_metrics(equity_curve: pd.Series, trades: List[Trade]) -> Dict[str, float]:
    """
    Compute extended metrics (basic + advanced)

    Args:
        equity_curve: Equity curve
        trades: List of trades

    Returns:
        Dict of extended metrics
    """
    metrics = compute_basic_metrics(equity_curve, trades)

    metrics['sharpe_ratio'] = compute_sharpe_ratio(equity_curve)

    if len(trades) > 0:
        max_consecutive_losses = 0
        current_losses = 0
        for trade in trades:
            if trade.pnl < 0:
                current_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
            else:
                current_losses = 0
        metrics['max_consecutive_losses'] = max_consecutive_losses
    else:
        metrics['max_consecutive_losses'] = 0

    return metrics
