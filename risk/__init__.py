"""
SuperDog Risk Module v0.6

風控系統模組

包含:
- support_resistance: 支撐壓力位檢測
- stops: 動態止損止盈
- calculator: 風險指標計算
- position_sizer: 倉位管理器

Version: v0.6.0-phase4
"""

from .stops import (
    DynamicStopManager,
    StopLossType,
    StopUpdate,
    TakeProfitType,
    create_atr_stops,
    create_resistance_stops,
)
from .support_resistance import (
    SRLevel,
    SRType,
    SupportResistanceDetector,
    detect_support_resistance,
)

try:
    from .calculator import PositionRisk, RiskCalculator, RiskMetrics, calculate_portfolio_risk
    from .calculator import calculate_position_risk as calc_pos_risk
except ImportError:
    RiskCalculator = None
    RiskMetrics = None
    PositionRisk = None
    calc_pos_risk = None
    calculate_portfolio_risk = None

try:
    from .position_sizer import (
        PositionSize,
        PositionSizer,
        SizingMethod,
        calculate_fixed_risk_size,
        calculate_kelly_size,
    )
except ImportError:
    PositionSizer = None
    PositionSize = None
    SizingMethod = None
    calculate_kelly_size = None
    calculate_fixed_risk_size = None

__all__ = [
    # Support/Resistance
    "SupportResistanceDetector",
    "SRLevel",
    "SRType",
    "detect_support_resistance",
    # Dynamic Stops
    "DynamicStopManager",
    "StopLossType",
    "TakeProfitType",
    "StopUpdate",
    "create_atr_stops",
    "create_resistance_stops",
    # Risk Calculator
    "RiskCalculator",
    "RiskMetrics",
    "PositionRisk",
    "calc_pos_risk",
    "calculate_portfolio_risk",
    # Position Sizer
    "PositionSizer",
    "PositionSize",
    "SizingMethod",
    "calculate_kelly_size",
    "calculate_fixed_risk_size",
]

# Convenience alias
calculate_position_risk = calc_pos_risk

__version__ = "0.6.0-phase4"
