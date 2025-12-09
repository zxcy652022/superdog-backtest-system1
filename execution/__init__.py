"""
SuperDog Execution Module v0.6

執行系統模組

包含:
- experiments: 實驗配置與管理
- experiment_runner: 實驗執行器
- runner: 組合回測執行
- optimizer: 參數優化
- analyzer: 結果分析
- models/: 執行成本模型（手續費、滑點、資金費率、強平）

Version: v0.6 Phase 3
"""

from .analyzer import AnalysisReport, ResultAnalyzer, analyze_result
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

# Models
from .models.execution_model import (
    ExecutionConfig,
    RealisticExecutionEngine,
    TradeExecution,
    create_conservative_engine,
    create_default_engine,
)
from .models.fee_models import FeeCalculator, FeeCost, FeeStructure, InstrumentType, OrderType
from .models.funding_models import FundingConfig, FundingEvent, FundingModel, FundingResult
from .models.liquidation_models import LiquidationModel, LiquidationResult, MarginConfig, RiskLevel
from .models.slippage_models import (
    SlippageConfig,
    SlippageModel,
    SlippageModelType,
    SlippageResult,
    SymbolTier,
)
from .optimizer import OptimizationConfig, OptimizationMode, ParameterOptimizer, optimize_parameters
from .runner import PortfolioResult, RunConfig, load_configs_from_yaml, run_portfolio

__all__ = [
    # Experiments
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
    "PortfolioRunner",
    "RunConfig",
    # Optimizer
    "ParameterOptimizer",
    "OptimizationConfig",
    "OptimizationMode",
    "optimize_parameters",
    # Analyzer
    "ResultAnalyzer",
    "AnalysisReport",
    "analyze_result",
    # Execution Models
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
