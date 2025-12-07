"""
Parameter Optimizer v0.6

參數優化器 - 智能搜索、貝葉斯優化、早停策略

核心功能:
- 網格搜索（Grid Search）
- 隨機搜索（Random Search）
- 貝葉斯優化（Bayesian Optimization）
- 早停策略（Early Stopping）
- 參數重要性分析

Version: v0.6 Phase 2
Design Reference: docs/specs/v0.6/superdog_v06_strategy_lab_spec.md
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .experiment_runner import ExperimentRunner, ParameterExpander
from .experiments import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentRun,
    ExperimentStatus,
    ParameterRange,
)


class OptimizationMode(Enum):
    """優化模式"""

    GRID = "grid"  # 網格搜索
    RANDOM = "random"  # 隨機搜索
    BAYESIAN = "bayesian"  # 貝葉斯優化
    GENETIC = "genetic"  # 遺傳算法（未實現）


@dataclass
class OptimizationConfig:
    """優化配置"""

    mode: OptimizationMode = OptimizationMode.GRID
    metric: str = "sharpe_ratio"  # 優化目標指標
    maximize: bool = True  # True=最大化，False=最小化

    # 早停配置
    early_stopping: bool = False  # 是否啟用早停
    patience: int = 10  # 容忍輪數
    min_improvement: float = 0.01  # 最小改進幅度

    # 貝葉斯優化配置
    n_initial_points: int = 10  # 初始隨機點數
    acquisition_function: str = "EI"  # Expected Improvement

    # 並行配置
    max_workers: int = 4


class ParameterOptimizer:
    """參數優化器

    提供多種優化策略，找出最佳參數組合

    Example:
        >>> optimizer = ParameterOptimizer(
        ...     config=experiment_config,
        ...     backtest_func=my_backtest,
        ...     opt_config=OptimizationConfig(mode=OptimizationMode.BAYESIAN)
        ... )
        >>> result = optimizer.optimize()
        >>> print(f"最佳參數: {result.best_run.parameters}")
    """

    def __init__(
        self,
        config: ExperimentConfig,
        backtest_func: Callable,
        opt_config: Optional[OptimizationConfig] = None,
    ):
        """初始化

        Args:
            config: 實驗配置
            backtest_func: 回測函數
            opt_config: 優化配置（默認為網格搜索）
        """
        self.config = config
        self.backtest_func = backtest_func
        self.opt_config = opt_config or OptimizationConfig()

        self.runner = ExperimentRunner(max_workers=self.opt_config.max_workers)

        # 優化狀態
        self.best_score = float("-inf") if self.opt_config.maximize else float("inf")
        self.no_improvement_count = 0
        self.iteration = 0

    def optimize(self) -> ExperimentResult:
        """執行優化

        Returns:
            ExperimentResult: 優化結果
        """
        print(f"🎯 開始參數優化: {self.opt_config.mode.value}")
        print(f"📊 優化指標: {self.opt_config.metric} ({'最大化' if self.opt_config.maximize else '最小化'})")

        if self.opt_config.mode == OptimizationMode.GRID:
            return self._grid_search()
        elif self.opt_config.mode == OptimizationMode.RANDOM:
            return self._random_search()
        elif self.opt_config.mode == OptimizationMode.BAYESIAN:
            return self._bayesian_optimization()
        else:
            raise ValueError(f"不支援的優化模式: {self.opt_config.mode}")

    def _grid_search(self) -> ExperimentResult:
        """網格搜索

        遍歷所有參數組合

        Returns:
            ExperimentResult: 優化結果
        """
        # 使用標準 ExperimentRunner
        result = self.runner.run_experiment(self.config, self.backtest_func)

        # 早停檢查（不適用於網格搜索，因為是一次性執行）
        return result

    def _random_search(self) -> ExperimentResult:
        """隨機搜索

        隨機採樣參數空間，支援早停

        Returns:
            ExperimentResult: 優化結果
        """
        # 設置為隨機模式
        from .experiments import ParameterExpansionMode

        original_mode = self.config.expansion_mode
        self.config.expansion_mode = ParameterExpansionMode.RANDOM

        if self.opt_config.early_stopping:
            result = self._random_search_with_early_stopping()
        else:
            result = self.runner.run_experiment(self.config, self.backtest_func)

        # 恢復原模式
        self.config.expansion_mode = original_mode

        return result

    def _random_search_with_early_stopping(self) -> ExperimentResult:
        """帶早停的隨機搜索

        Returns:
            ExperimentResult: 優化結果
        """
        expander = ParameterExpander(self.config)
        all_tasks = expander.expand_tasks()

        # 分批執行
        batch_size = 20
        all_runs = []
        experiment_id = self.config.get_experiment_id()

        for i in range(0, len(all_tasks), batch_size):
            batch_tasks = all_tasks[i : i + batch_size]
            print(f"\n📦 批次 {i//batch_size + 1}/{(len(all_tasks)-1)//batch_size + 1}")

            # 執行批次
            batch_runs = self._execute_batch(batch_tasks, experiment_id)
            all_runs.extend(batch_runs)

            # 檢查早停
            if self._should_stop_early(all_runs):
                print(f"⏹️  早停觸發，已執行 {len(all_runs)}/{len(all_tasks)} 個任務")
                break

        # 創建結果
        return self._create_result(experiment_id, all_runs)

    def _bayesian_optimization(self) -> ExperimentResult:
        """貝葉斯優化

        使用高斯過程進行智能搜索

        Returns:
            ExperimentResult: 優化結果
        """
        print("⚠️  貝葉斯優化需要安裝 scikit-optimize")
        print("    使用隨機搜索替代...")

        try:
            from skopt import gp_minimize
            from skopt.space import Categorical, Integer, Real
            from skopt.utils import use_named_args
        except ImportError:
            print("❌ scikit-optimize 未安裝，回退到隨機搜索")
            return self._random_search()

        # 定義搜索空間
        search_space = self._create_search_space()
        param_names = list(self.config.parameters.keys())

        # 定義目標函數
        @use_named_args(search_space)
        def objective(**params):
            # 執行回測
            symbol = self.config.symbols[0]  # 貝葉斯優化時通常用單個symbol
            metrics = self.backtest_func(symbol, self.config.timeframe, params, self.config)

            # 返回負數（因為 gp_minimize 是最小化）
            score = metrics.get(self.opt_config.metric, 0)
            return -score if self.opt_config.maximize else score

        # 執行優化
        print(f"🔍 開始貝葉斯搜索...")
        n_calls = self.config.max_combinations or 100

        result_bo = gp_minimize(
            objective,
            search_space,
            n_calls=n_calls,
            n_initial_points=self.opt_config.n_initial_points,
            acq_func=self.opt_config.acquisition_function,
            random_state=42,
            verbose=True,
        )

        # 轉換為 ExperimentResult
        return self._convert_bayesian_result(result_bo, param_names)

    def _create_search_space(self) -> List:
        """創建 scikit-optimize 搜索空間

        Returns:
            List: 搜索空間定義
        """
        from skopt.space import Integer, Real

        space = []
        for name, param_range in self.config.parameters.items():
            if param_range.values is not None:
                # 離散值
                values = param_range.values
                if all(isinstance(v, int) for v in values):
                    space.append(Integer(min(values), max(values), name=name))
                else:
                    space.append(Real(min(values), max(values), name=name))
            else:
                # 連續範圍
                if param_range.log_scale:
                    space.append(
                        Real(param_range.start, param_range.stop, prior="log-uniform", name=name)
                    )
                else:
                    space.append(Real(param_range.start, param_range.stop, name=name))

        return space

    def _execute_batch(self, tasks: List[Dict], experiment_id: str) -> List[ExperimentRun]:
        """執行一批任務

        Args:
            tasks: 任務列表
            experiment_id: 實驗ID

        Returns:
            List[ExperimentRun]: 運行記錄
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        runs = []
        with ThreadPoolExecutor(max_workers=self.opt_config.max_workers) as executor:
            futures = []
            for i, task in enumerate(tasks):
                run_id = f"{experiment_id}_run_{self.iteration:06d}"
                self.iteration += 1

                future = executor.submit(
                    self.runner._execute_single_run,
                    run_id=run_id,
                    experiment_id=experiment_id,
                    symbol=task["symbol"],
                    parameters=task["parameters"],
                    config=self.config,
                    backtest_func=self.backtest_func,
                )
                futures.append(future)

            for future in as_completed(futures):
                run = future.result()
                runs.append(run)

        return runs

    def _should_stop_early(self, runs: List[ExperimentRun]) -> bool:
        """檢查是否應該早停

        Args:
            runs: 所有運行記錄

        Returns:
            bool: True=應該停止
        """
        if not self.opt_config.early_stopping:
            return False

        # 找出完成的運行
        completed = [r for r in runs if r.status == ExperimentStatus.COMPLETED]
        if len(completed) < 2:
            return False

        # 獲取當前批次的最佳分數
        current_best = self._get_best_score(completed)

        # 檢查是否有改進
        if self.opt_config.maximize:
            improvement = current_best - self.best_score
        else:
            improvement = self.best_score - current_best

        if improvement > self.opt_config.min_improvement:
            # 有改進，重置計數
            self.best_score = current_best
            self.no_improvement_count = 0
            print(f"✨ 找到更好的參數，{self.opt_config.metric} = {current_best:.4f}")
        else:
            # 無改進，增加計數
            self.no_improvement_count += 1

        # 檢查是否達到容忍度
        return self.no_improvement_count >= self.opt_config.patience

    def _get_best_score(self, runs: List[ExperimentRun]) -> float:
        """獲取最佳分數

        Args:
            runs: 運行記錄

        Returns:
            float: 最佳分數
        """
        scores = []
        for run in runs:
            score = getattr(run, self.opt_config.metric, None)
            if score is None:
                score = run.metrics.get(self.opt_config.metric)
            if score is not None:
                scores.append(score)

        if not scores:
            return float("-inf") if self.opt_config.maximize else float("inf")

        return max(scores) if self.opt_config.maximize else min(scores)

    def _create_result(self, experiment_id: str, runs: List[ExperimentRun]) -> ExperimentResult:
        """創建實驗結果

        Args:
            experiment_id: 實驗ID
            runs: 運行記錄

        Returns:
            ExperimentResult: 實驗結果
        """
        completed = [r for r in runs if r.status == ExperimentStatus.COMPLETED]
        failed = [r for r in runs if r.status == ExperimentStatus.FAILED]

        result = ExperimentResult(
            experiment_id=experiment_id,
            config=self.config,
            runs=runs,
            total_runs=len(runs),
            completed_runs=len(completed),
            failed_runs=len(failed),
            best_metric=self.opt_config.metric,
        )

        result.best_run = result.get_best_run(
            metric=self.opt_config.metric, ascending=not self.opt_config.maximize
        )

        return result

    def _convert_bayesian_result(self, result_bo: Any, param_names: List[str]) -> ExperimentResult:
        """轉換貝葉斯優化結果

        Args:
            result_bo: scikit-optimize 結果
            param_names: 參數名稱列表

        Returns:
            ExperimentResult: 實驗結果
        """
        # 創建運行記錄
        runs = []
        for i, (x, y) in enumerate(zip(result_bo.x_iters, result_bo.func_vals)):
            params = dict(zip(param_names, x))

            # 反轉分數（之前為了最小化取了負數）
            score = -y if self.opt_config.maximize else y

            run = ExperimentRun(
                experiment_id=self.config.get_experiment_id(),
                run_id=f"bayesian_run_{i:04d}",
                symbol=self.config.symbols[0],
                parameters=params,
                status=ExperimentStatus.COMPLETED,
            )

            # 設置指標
            setattr(run, self.opt_config.metric, score)

            runs.append(run)

        # 創建結果
        return self._create_result(self.config.get_experiment_id(), runs)

    def analyze_parameter_importance(self, result: ExperimentResult) -> Dict[str, float]:
        """分析參數重要性

        使用方差分析來評估每個參數對結果的影響

        Args:
            result: 實驗結果

        Returns:
            Dict[str, float]: 參數重要性分數（0-1）
        """
        import pandas as pd

        # 提取數據
        data = []
        for run in result.runs:
            if run.status == ExperimentStatus.COMPLETED:
                row = run.parameters.copy()
                row["_metric"] = getattr(run, self.opt_config.metric, None)
                if row["_metric"] is not None:
                    data.append(row)

        if not data:
            return {}

        df = pd.DataFrame(data)

        # 計算每個參數的方差貢獻
        importance = {}
        total_variance = df["_metric"].var()

        for param in [c for c in df.columns if c != "_metric"]:
            # 計算分組方差
            grouped = df.groupby(param)["_metric"].var()
            param_variance = grouped.mean()

            # 方差比例
            importance[param] = param_variance / total_variance if total_variance > 0 else 0

        # 歸一化
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}

        return importance


# ===== 便捷函數 =====


def optimize_parameters(
    config: ExperimentConfig,
    backtest_func: Callable,
    mode: str = "grid",
    metric: str = "sharpe_ratio",
    **kwargs,
) -> ExperimentResult:
    """優化參數的便捷函數

    Args:
        config: 實驗配置
        backtest_func: 回測函數
        mode: 優化模式（grid/random/bayesian）
        metric: 優化指標
        **kwargs: 其他優化配置

    Returns:
        ExperimentResult: 優化結果

    Example:
        >>> result = optimize_parameters(
        ...     config=my_config,
        ...     backtest_func=my_backtest,
        ...     mode="bayesian",
        ...     metric="sharpe_ratio"
        ... )
    """
    opt_config = OptimizationConfig(mode=OptimizationMode(mode), metric=metric, **kwargs)

    optimizer = ParameterOptimizer(config, backtest_func, opt_config)
    return optimizer.optimize()
