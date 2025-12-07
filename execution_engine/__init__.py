"""
SuperDog Execution Engine v0.6

�W��y��L�q

;�!D:
- experiments: �WMn�x�P�
- experiment_runner: y��L�
- parameter_optimizer: �x*h
- result_analyzer: P��h

Version: v0.6 Phase 2
"""

from .execution_model import (
    ExecutionConfig,
    RealisticExecutionEngine,
    TradeExecution,
    create_conservative_engine,
    create_default_engine,
)
from .experiment_runner import ExperimentRunner, ParameterExpander, run_experiment
from .experiments import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentRun,
    ExperimentStatus,
    ParameterExpansionMode,
    ParameterRange,
    create_experiment_config,
    load_experiment_config,
)

# Phase 3: Realistic Execution Model
from .fee_models import (
    FeeCalculator,
    FeeCost,
    FeeStructure,
    InstrumentType,
    OrderType,
    calculate_simple_fee,
)
from .funding_models import (
    FundingConfig,
    FundingEvent,
    FundingModel,
    FundingResult,
    calculate_simple_funding_cost,
)
from .liquidation_models import (
    LiquidationModel,
    LiquidationResult,
    MarginConfig,
    RiskLevel,
    calculate_simple_liquidation_price,
)
from .parameter_optimizer import (
    OptimizationConfig,
    OptimizationMode,
    ParameterOptimizer,
    optimize_parameters,
)
from .result_analyzer import AnalysisReport, ResultAnalyzer, analyze_result
from .slippage_models import (
    SlippageConfig,
    SlippageModel,
    SlippageModelType,
    SlippageResult,
    SymbolTier,
    calculate_simple_slippage,
)

__all__ = [
    # Experiments (Phase 2)
    "ExperimentConfig",
    "ExperimentRun",
    "ExperimentResult",
    "ExperimentStatus",
    "ParameterExpansionMode",
    "ParameterRange",
    "create_experiment_config",
    "load_experiment_config",
    # Runner
    "ExperimentRunner",
    "ParameterExpander",
    "run_experiment",
    # Optimizer
    "ParameterOptimizer",
    "OptimizationConfig",
    "OptimizationMode",
    "optimize_parameters",
    # Analyzer
    "ResultAnalyzer",
    "AnalysisReport",
    "analyze_result",
    # Execution Model (Phase 3)
    "RealisticExecutionEngine",
    "ExecutionConfig",
    "TradeExecution",
    "FeeCalculator",
    "FeeStructure",
    "FeeCost",
    "InstrumentType",
    "OrderType",
    "SlippageModel",
    "SlippageConfig",
    "SlippageResult",
    "SymbolTier",
    "SlippageModelType",
    "FundingModel",
    "FundingConfig",
    "FundingResult",
    "FundingEvent",
    "LiquidationModel",
    "MarginConfig",
    "LiquidationResult",
    "RiskLevel",
    "create_default_engine",
    "create_conservative_engine",
    "calculate_simple_fee",
    "calculate_simple_slippage",
    "calculate_simple_funding_cost",
    "calculate_simple_liquidation_price",
]

__version__ = "0.6.0-phase3"
