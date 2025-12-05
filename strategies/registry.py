"""Strategy Registry v0.3

This module provides a centralized registry for all trading strategies.
New strategies can be added by simply importing them and adding to the registry.

Design Reference: docs/specs/planned/v0.3_portfolio_runner_api.md §2.1
"""

from typing import Type, Dict
from backtest.engine import BaseStrategy
from .simple_sma import SimpleSMAStrategy

# Future: import more strategies here
# from .trend_follow import TrendFollowStrategy
# from .mean_reversion import MeanReversionStrategy

STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "simple_sma": SimpleSMAStrategy,
    # Future: add more strategies here
    # "trend_follow": TrendFollowStrategy,
    # "mean_reversion": MeanReversionStrategy,
}


def get_strategy(name: str) -> Type[BaseStrategy]:
    """Get strategy class by name

    Args:
        name: Strategy name (must exist in registry)

    Returns:
        Strategy class

    Raises:
        KeyError: If strategy not found

    Example:
        >>> cls = get_strategy("simple_sma")
        >>> strategy = cls(broker=broker, data=data)
    """
    if name not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise KeyError(
            f"Strategy '{name}' not found. "
            f"Available strategies: {available}"
        )
    return STRATEGY_REGISTRY[name]


def list_strategies() -> list:
    """List all available strategy names

    Returns:
        List of strategy names (sorted)

    Example:
        >>> strategies = list_strategies()
        >>> print(strategies)
        ['mean_reversion', 'simple_sma', 'trend_follow']
    """
    return sorted(STRATEGY_REGISTRY.keys())


def register_strategy(name: str, strategy_class: Type[BaseStrategy]) -> None:
    """Register a new strategy (for dynamic registration)

    Args:
        name: Strategy name (must be unique)
        strategy_class: Strategy class (must inherit from BaseStrategy)

    Raises:
        ValueError: If name already exists
        TypeError: If strategy_class is not a BaseStrategy subclass

    Example:
        >>> register_strategy("my_strategy", MyStrategy)
    """
    if name in STRATEGY_REGISTRY:
        raise ValueError(f"Strategy '{name}' already registered")

    if not issubclass(strategy_class, BaseStrategy):
        raise TypeError(
            f"{strategy_class.__name__} must inherit from BaseStrategy"
        )

    STRATEGY_REGISTRY[name] = strategy_class
