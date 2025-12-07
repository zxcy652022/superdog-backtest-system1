"""
Multi-Exchange Data Aggregation for SuperDog v0.5

多交易所數據聚合 - 整合多個交易所的數據源

Version: v0.5 Phase B
"""

from .multi_exchange import (
    MultiExchangeAggregator,
    aggregate_funding_rates,
    aggregate_open_interest,
    compare_exchanges,
)

__all__ = [
    "MultiExchangeAggregator",
    "aggregate_funding_rates",
    "aggregate_open_interest",
    "compare_exchanges",
]
