"""
SuperDog Risk Management v0.6 Phase 4

動態風控系統 - 智能止損止盈、倉位管理、風險控制

主要模組:
- support_resistance: 支撐壓力位檢測
- dynamic_stops: 動態止損止盈
- risk_calculator: 風險指標計算
- position_sizer: 倉位管理器

Version: v0.6.0-phase4
"""

from .support_resistance import (
    SupportResistanceDetector,
    SRLevel,
    SRType,
    detect_support_resistance
)

from .dynamic_stops import (
    DynamicStopManager,
    StopLossType,
    TakeProfitType,
    StopUpdate,
    create_atr_stops,
    create_resistance_stops
)

try:
    from .risk_calculator import (
        RiskCalculator,
        RiskMetrics,
        PositionRisk,
        calculate_position_risk as calc_pos_risk,
        calculate_portfolio_risk
    )
except ImportError:
    RiskCalculator = None
    RiskMetrics = None
    PositionRisk = None
    calc_pos_risk = None
    calculate_portfolio_risk = None

try:
    from .position_sizer import (
        PositionSizer,
        PositionSize,
        SizingMethod,
        calculate_kelly_size,
        calculate_fixed_risk_size
    )
except ImportError:
    PositionSizer = None
    PositionSize = None
    SizingMethod = None
    calculate_kelly_size = None
    calculate_fixed_risk_size = None

__all__ = [
    # Support/Resistance
    'SupportResistanceDetector',
    'SRLevel',
    'SRType',
    'detect_support_resistance',

    # Dynamic Stops
    'DynamicStopManager',
    'StopLossType',
    'TakeProfitType',
    'StopUpdate',
    'create_atr_stops',
    'create_resistance_stops',

    # Risk Calculator
    'RiskCalculator',
    'RiskMetrics',
    'PositionRisk',
    'calc_pos_risk',
    'calculate_portfolio_risk',

    # Position Sizer
    'PositionSizer',
    'PositionSize',
    'SizingMethod',
    'calculate_kelly_size',
    'calculate_fixed_risk_size',
]

# Convenience alias
calculate_position_risk = calc_pos_risk

__version__ = '0.6.0-phase4'
