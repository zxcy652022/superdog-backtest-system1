"""Strategy Registry v0.4

This module provides a centralized registry for all trading strategies.
New strategies can be added by simply importing them and adding to the registry.

v0.4 changes:
- Support for both v0.3 (legacy) and v2.0 (new API) strategies
- Automatic strategy type detection
- Integration with StrategyRegistryV2 for auto-discovery
- Backward compatible API

Design Reference:
- v0.3: docs/specs/planned/v0.3_portfolio_runner_api.md §2.1
- v0.4: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from typing import Type, Dict, Union, List
from backtest.engine import BaseStrategy as V03BaseStrategy

# v2.0 Registry (auto-discovery)
try:
    from .registry_v2 import get_registry, StrategyRegistryV2
    HAS_REGISTRY_V2 = True
except ImportError:
    HAS_REGISTRY_V2 = False
    get_registry = None

# v0.3 strategies (legacy) - for manual registration
from .simple_sma import SimpleSMAStrategy

# v2.0 strategies (new API) - for manual registration
try:
    from .simple_sma_v2 import SimpleSMAStrategyV2
    from .kawamoku_demo import KawamokuStrategy
    HAS_V2_STRATEGIES = True
except ImportError:
    HAS_V2_STRATEGIES = False

# Manual registry (legacy, for backward compatibility)
STRATEGY_REGISTRY: Dict[str, Type] = {
    # v0.3 strategies (legacy)
    "simple_sma": SimpleSMAStrategy,
}

# v0.4: Register v2.0 strategies if available
if HAS_V2_STRATEGIES:
    STRATEGY_REGISTRY.update({
        "simple_sma_v2": SimpleSMAStrategyV2,
        "kawamoku_demo": KawamokuStrategy,
    })

# Future: import more strategies here
# from .trend_follow import TrendFollowStrategy
# from .mean_reversion import MeanReversionStrategy
# STRATEGY_REGISTRY["trend_follow"] = TrendFollowStrategy


def get_strategy(name: str) -> Type[V03BaseStrategy]:
    """Get strategy class by name

    v0.4: Now uses RegistryV2 for auto-discovered strategies,
    falls back to manual registry for backward compatibility

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
    # v0.4: Try RegistryV2 first (auto-discovery)
    if HAS_REGISTRY_V2:
        try:
            registry_v2 = get_registry()
            return registry_v2.get_strategy(name)
        except KeyError:
            pass  # Fall back to manual registry

    # Fallback: Manual registry
    if name not in STRATEGY_REGISTRY:
        available = ", ".join(sorted(STRATEGY_REGISTRY.keys()))
        raise KeyError(
            f"Strategy '{name}' not found. "
            f"Available strategies: {available}"
        )

    return STRATEGY_REGISTRY[name]


def list_strategies() -> List[str]:
    """List all available strategy names

    v0.4: Now includes auto-discovered strategies from RegistryV2

    Returns:
        List of strategy names (sorted)

    Example:
        >>> strategies = list_strategies()
        >>> print(strategies)
        ['kawamoku_demo', 'simple_sma', 'simple_sma_v2']
    """
    # v0.4: Use RegistryV2 if available
    if HAS_REGISTRY_V2:
        registry_v2 = get_registry()
        return registry_v2.list_strategies()

    # Fallback: Manual registry
    return sorted(STRATEGY_REGISTRY.keys())


def register_strategy(name: str, strategy_class: Type[V03BaseStrategy]) -> None:
    """Register a new strategy (for dynamic registration)

    v0.4: Now also registers in RegistryV2 if available

    Args:
        name: Strategy name (must be unique)
        strategy_class: Strategy class (must inherit from BaseStrategy)

    Raises:
        ValueError: If name already exists
        TypeError: If strategy_class is not a BaseStrategy subclass

    Example:
        >>> register_strategy("my_strategy", MyStrategy)
    """
    # Check in both registries
    if name in STRATEGY_REGISTRY:
        raise ValueError(f"Strategy '{name}' already registered")

    if HAS_REGISTRY_V2:
        registry_v2 = get_registry()
        try:
            registry_v2.get_strategy(name)
            raise ValueError(f"Strategy '{name}' already registered in RegistryV2")
        except KeyError:
            pass

    if not issubclass(strategy_class, V03BaseStrategy):
        raise TypeError(
            f"{strategy_class.__name__} must inherit from BaseStrategy"
        )

    # Register in manual registry
    STRATEGY_REGISTRY[name] = strategy_class

    # v0.4: Also register in RegistryV2 if available
    if HAS_REGISTRY_V2:
        registry_v2 = get_registry()
        registry_v2.register_strategy(name, strategy_class)
