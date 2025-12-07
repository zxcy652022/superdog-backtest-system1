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

from .experiments import (
    ExperimentConfig,
    ExperimentRun,
    ExperimentResult,
    ExperimentStatus,
    ParameterExpansionMode,
    ParameterRange,
    create_experiment_config,
    load_experiment_config
)

from .experiment_runner import (
    ExperimentRunner,
    ParameterExpander,
    run_experiment
)

from .parameter_optimizer import (
    ParameterOptimizer,
    OptimizationConfig,
    OptimizationMode,
    optimize_parameters
)

from .result_analyzer import (
    ResultAnalyzer,
    AnalysisReport,
    analyze_result
)

# Phase 3: Realistic Execution Model
from .fee_models import (
    FeeCalculator,
    FeeStructure,
    FeeCost,
    InstrumentType,
    OrderType,
    calculate_simple_fee
)

from .slippage_models import (
    SlippageModel,
    SlippageConfig,
    SlippageResult,
    SymbolTier,
    SlippageModelType,
    calculate_simple_slippage
)

from .funding_models import (
    FundingModel,
    FundingConfig,
    FundingResult,
    FundingEvent,
    calculate_simple_funding_cost
)

from .liquidation_models import (
    LiquidationModel,
    MarginConfig,
    LiquidationResult,
    RiskLevel,
    calculate_simple_liquidation_price
)

from .execution_model import (
    RealisticExecutionEngine,
    ExecutionConfig,
    TradeExecution,
    create_default_engine,
    create_conservative_engine
)

__all__ = [
    # Experiments (Phase 2)
    'ExperimentConfig',
    'ExperimentRun',
    'ExperimentResult',
    'ExperimentStatus',
    'ParameterExpansionMode',
    'ParameterRange',
    'create_experiment_config',
    'load_experiment_config',

    # Runner
    'ExperimentRunner',
    'ParameterExpander',
    'run_experiment',

    # Optimizer
    'ParameterOptimizer',
    'OptimizationConfig',
    'OptimizationMode',
    'optimize_parameters',

    # Analyzer
    'ResultAnalyzer',
    'AnalysisReport',
    'analyze_result',

    # Execution Model (Phase 3)
    'RealisticExecutionEngine',
    'ExecutionConfig',
    'TradeExecution',
    'FeeCalculator',
    'FeeStructure',
    'FeeCost',
    'InstrumentType',
    'OrderType',
    'SlippageModel',
    'SlippageConfig',
    'SlippageResult',
    'SymbolTier',
    'SlippageModelType',
    'FundingModel',
    'FundingConfig',
    'FundingResult',
    'FundingEvent',
    'LiquidationModel',
    'MarginConfig',
    'LiquidationResult',
    'RiskLevel',
    'create_default_engine',
    'create_conservative_engine',
    'calculate_simple_fee',
    'calculate_simple_slippage',
    'calculate_simple_funding_cost',
    'calculate_simple_liquidation_price',
]

__version__ = '0.6.0-phase3'
