"""
Perpetual Contract Data Processing for SuperDog v0.5

永續合約數據處理模組 - 提供完整的永續合約數據生態系統

Modules:
- funding_rate: 資金費率數據處理 (Phase A)
- open_interest: 持倉量數據處理 (Phase A)
- basis: 期現基差計算 (Phase B)
- liquidations: 爆倉數據監控 (Phase B)
- long_short_ratio: 多空持倉比分析 (Phase B)

Version: v0.5 Phase B
"""

from .funding_rate import (
    FundingRateData,
    fetch_funding_rate,
    get_latest_funding_rate
)

from .open_interest import (
    OpenInterestData,
    fetch_open_interest,
    analyze_oi_trend
)

from .basis import (
    BasisData,
    calculate_basis,
    find_arbitrage_opportunities
)

from .liquidations import (
    LiquidationData,
    fetch_liquidations,
    calculate_panic_index
)

from .long_short_ratio import (
    LongShortRatioData,
    fetch_long_short_ratio,
    calculate_sentiment
)

__all__ = [
    # Phase A
    'FundingRateData',
    'fetch_funding_rate',
    'get_latest_funding_rate',
    'OpenInterestData',
    'fetch_open_interest',
    'analyze_oi_trend',
    # Phase B
    'BasisData',
    'calculate_basis',
    'find_arbitrage_opportunities',
    'LiquidationData',
    'fetch_liquidations',
    'calculate_panic_index',
    'LongShortRatioData',
    'fetch_long_short_ratio',
    'calculate_sentiment'
]
