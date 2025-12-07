"""
Backtest Engine v0.5

Core backtest engine module with position sizing, stop-loss, take-profit, and detailed trade logging.
Handles main backtest loop: iterate bars, call strategy, manage positions, compute metrics.

v0.3 新增：
- SL/TP 方向感知（支援多單和空單）
- 支援槓桿參數傳遞

v0.5 新增：
- 支援 v0.3 策略 (legacy API with broker parameter)
- 支援 v0.5 策略 (new Strategy API v2.0)
- 自動檢測策略類型並使用正確的初始化方式

Design Reference: docs/specs/planned/v0.3_short_leverage_spec.md §3
"""

from dataclasses import dataclass
from typing import Dict, List, Type, Optional, Literal
import pandas as pd
import inspect
from backtest.broker import SimulatedBroker, Trade, DirectionType
from backtest.metrics import compute_basic_metrics
from backtest.position_sizer import BasePositionSizer, AllInSizer


@dataclass
class BacktestResult:
    """Backtest result"""
    equity_curve: pd.Series
    trades: List[Trade]
    metrics: Dict[str, float]
    trade_log: Optional[pd.DataFrame] = None  # v0.2: Detailed trade log


class BaseStrategy:
    """Base strategy class (v0.3 Legacy API)

    This is the v0.3 base strategy class for backward compatibility.
    New strategies should use strategies.api_v2.BaseStrategy
    """

    def __init__(self, broker: SimulatedBroker, data: pd.DataFrame):
        self.broker = broker
        self.data = data

    def on_bar(self, i: int, row: pd.Series):
        raise NotImplementedError("Strategy must implement on_bar method")


def _is_v05_strategy(strategy_cls: Type) -> bool:
    """Check if a strategy class uses v0.5 API (Strategy API v2.0)

    Detection logic:
    - v0.5 strategies: __init__(self) - no parameters
    - v0.3 strategies: __init__(self, broker, data) - has parameters

    Args:
        strategy_cls: Strategy class to check

    Returns:
        True if v0.5 strategy, False if v0.3 strategy
    """
    try:
        # Get __init__ signature
        init_sig = inspect.signature(strategy_cls.__init__)
        params = list(init_sig.parameters.keys())

        # Remove 'self' parameter
        if 'self' in params:
            params.remove('self')

        # v0.5 strategies have no parameters (besides self)
        # v0.3 strategies have (broker, data) parameters
        return len(params) == 0
    except Exception:
        # Default to v0.3 if we can't determine
        return False


class _V05StrategyWrapper:
    """Adapter to wrap v0.5 Strategy API v2.0 for use in v0.3 backtest engine

    This wrapper:
    1. Instantiates v0.5 strategy with no parameters
    2. Generates signals using compute_signals()
    3. Converts signals to buy/sell actions via on_bar()
    """

    def __init__(self, strategy_cls: Type, broker: SimulatedBroker, data: pd.DataFrame):
        """Initialize wrapper

        Args:
            strategy_cls: v0.5 strategy class
            broker: Simulated broker instance
            data: OHLCV DataFrame
        """
        # Create v0.5 strategy instance (no parameters)
        self.strategy = strategy_cls()
        self.broker = broker
        self.data = data

        # Get default parameters
        param_specs = self.strategy.get_parameters()
        params = {name: spec.default_value for name, spec in param_specs.items()}

        # Generate signals upfront (v0.5 strategies use vectorized signal generation)
        data_dict = {'ohlcv': data}
        self.signals = self.strategy.compute_signals(data_dict, params)

        # Track previous signal for change detection
        self.prev_signal = 0

    def on_bar(self, i: int, row: pd.Series):
        """Execute trading logic for current bar

        Converts v0.5 signals to v0.3 buy/sell actions:
        - Signal changes from 0 to 1: Buy
        - Signal changes from 1 to 0: Sell
        - Signal changes from 0 to -1: Short
        - Signal changes from -1 to 0: Cover

        Args:
            i: Current bar index
            row: Current bar data
        """
        if i >= len(self.signals):
            return

        current_signal = self.signals.iloc[i]
        current_price = row['close']
        current_time = row.name

        # Signal transition logic
        if current_signal == 1 and self.prev_signal != 1:
            # Enter long position
            if not self.broker.has_position:
                self.broker.buy_all(current_price, current_time)
        elif current_signal == -1 and self.prev_signal != -1:
            # Enter short position
            if self.broker.has_position and self.broker.is_long:
                # Close long first
                self.broker.sell(self.broker.position_qty, current_price, current_time)
            if not self.broker.has_position:
                # Open short
                self.broker.short_all(current_price, current_time)
        elif current_signal == 0 and self.prev_signal != 0:
            # Close any position
            if self.broker.has_position:
                if self.broker.is_long:
                    self.broker.sell(self.broker.position_qty, current_price, current_time)
                elif self.broker.is_short:
                    self.broker.buy(self.broker.position_qty, current_price, current_time)

        self.prev_signal = current_signal


def run_backtest(
    data: pd.DataFrame,
    strategy_cls: Type[BaseStrategy],
    initial_cash: float = 10000,
    fee_rate: float = 0.0005,
    position_sizer: Optional[BasePositionSizer] = None,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    leverage: float = 1.0  # v0.3 新增
) -> BacktestResult:
    """
    Run backtest with position sizing, stop-loss, and take-profit support

    v0.5: Now supports both v0.3 and v0.5 strategy APIs automatically:
    - v0.3 strategies: __init__(broker, data) - legacy API
    - v0.5 strategies: __init__() - new Strategy API v2.0

    Args:
        data: OHLCV DataFrame with DatetimeIndex
        strategy_cls: Strategy class (v0.3 or v0.5 API)
        initial_cash: Initial capital (default 10000)
        fee_rate: Fee rate (default 0.0005 = 0.05%)
        position_sizer: Position sizer (default AllInSizer)
        stop_loss_pct: Stop loss percentage (e.g., 0.02 = 2%)
        take_profit_pct: Take profit percentage (e.g., 0.05 = 5%)
        leverage: Leverage multiplier (default 1.0, range 1-100) - v0.3

    Returns:
        BacktestResult containing equity curve, trades, metrics, and trade log

    Examples:
        # v0.3 strategy (legacy)
        >>> result = run_backtest(data, SimpleSMAStrategy, initial_cash=10000)

        # v0.5 strategy (new API)
        >>> result = run_backtest(data, KawamokuStrategy, initial_cash=10000)
    """
    _validate_data(data)

    # Use AllInSizer if no position sizer provided
    if position_sizer is None:
        position_sizer = AllInSizer(fee_rate=fee_rate)

    # v0.3: Pass leverage to broker
    broker = SimulatedBroker(initial_cash=initial_cash, fee_rate=fee_rate, leverage=leverage)

    # v0.2: Wrap broker.buy_all to respect position_sizer
    # This allows v0.1 strategies (that call buy_all) to work with position_sizer
    original_buy_all = broker.buy_all

    def buy_all_with_sizer(price: float, time):
        """Wrapper that uses position_sizer to calculate size"""
        # Get current equity
        equity = broker.get_current_equity(price)

        # Get size from position_sizer
        size = position_sizer.get_size(equity, price)

        # v0.2 核心規則：size <= 0 時不進場
        if size is None or size <= 0:
            return False

        # Use broker.buy() with calculated size
        return broker.buy(size, price, time)

    # Replace buy_all with our wrapper
    broker.buy_all = buy_all_with_sizer

    # v0.5: Detect strategy type and instantiate accordingly
    is_v05 = _is_v05_strategy(strategy_cls)

    if is_v05:
        # v0.5 Strategy API v2.0: Use wrapper to adapt to v0.3 backtest engine
        strategy = _V05StrategyWrapper(strategy_cls, broker, data)
    else:
        # v0.3 Legacy API: Direct instantiation with broker and data
        strategy = strategy_cls(broker=broker, data=data)

    # Track position for SL/TP and MAE/MFE
    position_tracker = _PositionTracker()

    for i, (timestamp, row) in enumerate(data.iterrows()):
        # Check SL/TP if we have position
        if broker.has_position:
            sl_triggered, tp_triggered, exit_price, exit_reason = _check_sl_tp(
                row=row,
                entry_price=broker.position_entry_price,
                direction=broker.position_direction,  # v0.3: 傳入方向
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct
            )

            # Update MAE/MFE tracking
            position_tracker.update(row['low'], row['high'])

            # Execute SL/TP if triggered
            if sl_triggered or tp_triggered:
                # Record MAE/MFE before closing
                mae = position_tracker.get_mae(broker.position_entry_price)
                mfe = position_tracker.get_mfe(broker.position_entry_price)
                holding_bars = i - position_tracker.entry_bar_index

                # Close position (v0.3: direction-aware)
                if broker.is_long:
                    success = broker.sell(broker.position_qty, exit_price, timestamp)
                elif broker.is_short:
                    success = broker.buy(broker.position_qty, exit_price, timestamp)
                else:
                    success = False

                if success and len(broker.trades) > 0:
                    # Update last trade with additional info
                    last_trade = broker.trades[-1]
                    equity_after = broker.cash  # After selling, no position
                    
                    # Store in position tracker for trade log
                    position_tracker.record_trade_detail(
                        entry_reason="strategy_signal",
                        exit_reason=exit_reason,
                        holding_bars=holding_bars,
                        mae=mae,
                        mfe=mfe,
                        equity_after=equity_after,
                        fee=broker.position_entry_price * last_trade.qty * broker.fee_rate * 2  # entry + exit
                    )

                # Reset tracker
                position_tracker.reset()
                
                # Update equity
                broker.update_equity(price=exit_price, time=timestamp)
                continue

        # Call strategy (may generate buy/sell signals)
        strategy.on_bar(i, row)

        # If strategy just opened a position, start tracking
        if broker.has_position and not position_tracker.is_active:
            position_tracker.start(i, row['low'], row['high'])

        # If position was closed by strategy (not SL/TP), record details
        if not broker.has_position and position_tracker.is_active:
            if len(broker.trades) > 0:
                mae = position_tracker.get_mae(broker.trades[-1].entry_price)
                mfe = position_tracker.get_mfe(broker.trades[-1].entry_price)
                holding_bars = i - position_tracker.entry_bar_index
                equity_after = broker.cash

                position_tracker.record_trade_detail(
                    entry_reason="strategy_signal",
                    exit_reason="strategy_signal",
                    holding_bars=holding_bars,
                    mae=mae,
                    mfe=mfe,
                    equity_after=equity_after,
                    fee=broker.trades[-1].entry_price * broker.trades[-1].qty * broker.fee_rate * 2
                )

            position_tracker.reset()

        # Update equity
        current_price = row['close']
        broker.update_equity(price=current_price, time=timestamp)

    # Build trade log
    trade_log = _build_trade_log(broker.trades, position_tracker.trade_details)

    # Compute metrics
    equity_curve = broker.get_equity_curve()
    trades = broker.trades
    metrics = compute_basic_metrics(equity_curve, trades)

    result = BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        metrics=metrics,
        trade_log=trade_log
    )

    return result


def _check_sl_tp(
    row: pd.Series,
    entry_price: float,
    direction: DirectionType,  # v0.3 新增
    stop_loss_pct: Optional[float],
    take_profit_pct: Optional[float]
) -> tuple:
    """
    Check if stop-loss or take-profit is triggered (v0.3 - 方向感知)

    Args:
        row: Current bar with 'low' and 'high'
        entry_price: Entry price
        direction: Position direction ("long" | "short" | "flat")
        stop_loss_pct: Stop loss percentage (e.g., 0.02 = 2%)
        take_profit_pct: Take profit percentage (e.g., 0.05 = 5%)

    Returns:
        (sl_triggered, tp_triggered, exit_price, exit_reason)

    Notes:
        - 多單: SL價 < 進場價, TP價 > 進場價
        - 空單: SL價 > 進場價, TP價 < 進場價
        - SL 優先於 TP
    """
    sl_triggered = False
    tp_triggered = False
    exit_price = row['close']  # Default to close
    exit_reason = "strategy_signal"

    # === 多單的 SL/TP ===
    if direction == "long":
        # 止損價: entry * (1 - stop_loss_pct)
        if stop_loss_pct is not None and stop_loss_pct > 0:
            sl_price = entry_price * (1 - stop_loss_pct)
        else:
            sl_price = 0

        # 止盈價: entry * (1 + take_profit_pct)
        if take_profit_pct is not None and take_profit_pct > 0:
            tp_price = entry_price * (1 + take_profit_pct)
        else:
            tp_price = float('inf')

        # 檢查觸發（SL 優先）
        if sl_price > 0 and row['low'] <= sl_price:
            sl_triggered = True
            exit_price = sl_price
            exit_reason = "stop_loss"
        elif tp_price < float('inf') and row['high'] >= tp_price:
            tp_triggered = True
            exit_price = tp_price
            exit_reason = "take_profit"

    # === 空單的 SL/TP ===
    elif direction == "short":
        # 止損價: entry * (1 + stop_loss_pct)  # 注意: 空單止損是價格上漲
        if stop_loss_pct is not None and stop_loss_pct > 0:
            sl_price = entry_price * (1 + stop_loss_pct)
        else:
            sl_price = float('inf')

        # 止盈價: entry * (1 - take_profit_pct)  # 注意: 空單止盈是價格下跌
        if take_profit_pct is not None and take_profit_pct > 0:
            tp_price = entry_price * (1 - take_profit_pct)
        else:
            tp_price = 0

        # 檢查觸發（SL 優先）
        if sl_price < float('inf') and row['high'] >= sl_price:
            sl_triggered = True
            exit_price = sl_price
            exit_reason = "stop_loss"
        elif tp_price > 0 and row['low'] <= tp_price:
            tp_triggered = True
            exit_price = tp_price
            exit_reason = "take_profit"

    # === flat 方向（無持倉，不應該進入這個函數） ===
    # 如果 direction == "flat"，返回預設值（不觸發）

    return sl_triggered, tp_triggered, exit_price, exit_reason


class _PositionTracker:
    """Helper class to track position details for trade log"""

    def __init__(self):
        self.is_active = False
        self.entry_bar_index = 0
        self.lowest_price = float('inf')
        self.highest_price = 0.0
        self.trade_details = []

    def start(self, bar_index: int, low: float, high: float):
        """Start tracking a new position"""
        self.is_active = True
        self.entry_bar_index = bar_index
        self.lowest_price = low
        self.highest_price = high

    def update(self, low: float, high: float):
        """Update MAE/MFE during position"""
        if self.is_active:
            self.lowest_price = min(self.lowest_price, low)
            self.highest_price = max(self.highest_price, high)

    def get_mae(self, entry_price: float) -> float:
        """Get Maximum Adverse Excursion"""
        if entry_price == 0:
            return 0.0
        return (self.lowest_price - entry_price) / entry_price

    def get_mfe(self, entry_price: float) -> float:
        """Get Maximum Favorable Excursion"""
        if entry_price == 0:
            return 0.0
        return (self.highest_price - entry_price) / entry_price

    def record_trade_detail(self, entry_reason: str, exit_reason: str, holding_bars: int,
                           mae: float, mfe: float, equity_after: float, fee: float):
        """Record additional trade details"""
        self.trade_details.append({
            'entry_reason': entry_reason,
            'exit_reason': exit_reason,
            'holding_bars': holding_bars,
            'mae': mae,
            'mfe': mfe,
            'equity_after': equity_after,
            'fee': fee
        })

    def reset(self):
        """Reset tracker"""
        self.is_active = False
        self.entry_bar_index = 0
        self.lowest_price = float('inf')
        self.highest_price = 0.0


def _build_trade_log(trades: List[Trade], trade_details: List[dict]) -> pd.DataFrame:
    """
    Build detailed trade log DataFrame

    Args:
        trades: List of Trade objects
        trade_details: List of additional trade details

    Returns:
        DataFrame with columns: entry_time, exit_time, entry_price, exit_price,
                                size, fee, pnl, pnl_pct, entry_reason, exit_reason,
                                holding_bars, mae, mfe, equity_after
    """
    if len(trades) == 0:
        # Return empty DataFrame with correct columns
        return pd.DataFrame(columns=[
            'entry_time', 'exit_time', 'entry_price', 'exit_price',
            'size', 'fee', 'pnl', 'pnl_pct', 'entry_reason', 'exit_reason',
            'holding_bars', 'mae', 'mfe', 'equity_after'
        ])

    records = []
    for i, trade in enumerate(trades):
        detail = trade_details[i] if i < len(trade_details) else {
            'entry_reason': 'strategy_signal',
            'exit_reason': 'strategy_signal',
            'holding_bars': 0,
            'mae': 0.0,
            'mfe': 0.0,
            'equity_after': 0.0,
            'fee': 0.0
        }

        records.append({
            'entry_time': trade.entry_time,
            'exit_time': trade.exit_time,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'size': trade.qty,
            'fee': detail['fee'],
            'pnl': trade.pnl,
            'pnl_pct': trade.return_pct,
            'entry_reason': detail['entry_reason'],
            'exit_reason': detail['exit_reason'],
            'holding_bars': detail['holding_bars'],
            'mae': detail['mae'],
            'mfe': detail['mfe'],
            'equity_after': detail['equity_after']
        })

    return pd.DataFrame(records)


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
