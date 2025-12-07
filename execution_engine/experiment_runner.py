"""
Experiment Runner v0.6

批量實驗執行引擎 - 並行執行、記憶體管理、失敗容錯

核心功能:
- 並行任務執行（ThreadPoolExecutor）
- 內存管理和結果流式寫入
- 失敗容錯和重試機制
- 進度追蹤和狀態更新
- 結果收集和存儲

Version: v0.6 Phase 2
Design Reference: docs/specs/v0.6/superdog_v06_strategy_lab_spec.md
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import itertools
import json
import hashlib
import time
from tqdm import tqdm

from .experiments import (
    ExperimentConfig,
    ExperimentRun,
    ExperimentResult,
    ExperimentStatus,
    ParameterRange
)


class ParameterExpander:
    """參數組合展開器

    負責將參數範圍展開為具體的參數組合
    支援網格搜索和隨機採樣
    """

    def __init__(self, config: ExperimentConfig):
        """初始化

        Args:
            config: 實驗配置
        """
        self.config = config

    def expand_combinations(self) -> List[Dict[str, Any]]:
        """展開所有參數組合

        Returns:
            List[Dict]: 參數組合列表

        Example:
            >>> expander = ParameterExpander(config)
            >>> combinations = expander.expand_combinations()
            >>> len(combinations)
            100
        """
        # 展開每個參數的值列表
        param_values = {}
        for name, param_range in self.config.parameters.items():
            param_values[name] = param_range.expand()

        # 生成所有組合
        param_names = list(param_values.keys())
        value_lists = [param_values[name] for name in param_names]

        combinations = []
        for values in itertools.product(*value_lists):
            combo = dict(zip(param_names, values))
            combinations.append(combo)

        # 應用採樣策略
        if self.config.expansion_mode.value == "random":
            combinations = self._random_sample(combinations)
        elif self.config.max_combinations and len(combinations) > self.config.max_combinations:
            # 網格模式但超過限制，進行採樣
            combinations = self._grid_sample(combinations)

        return combinations

    def _random_sample(self, combinations: List[Dict]) -> List[Dict]:
        """隨機採樣

        Args:
            combinations: 所有組合

        Returns:
            List[Dict]: 採樣後的組合
        """
        import random

        sample_size = self.config.sample_size or self.config.max_combinations
        if sample_size and len(combinations) > sample_size:
            return random.sample(combinations, sample_size)
        return combinations

    def _grid_sample(self, combinations: List[Dict]) -> List[Dict]:
        """網格採樣（均勻採樣）

        Args:
            combinations: 所有組合

        Returns:
            List[Dict]: 採樣後的組合
        """
        max_count = self.config.max_combinations
        if not max_count or len(combinations) <= max_count:
            return combinations

        # 均勻採樣
        step = len(combinations) // max_count
        return combinations[::step][:max_count]

    def expand_tasks(self) -> List[Dict[str, Any]]:
        """展開所有實驗任務（symbol × parameter combinations）

        Returns:
            List[Dict]: 任務列表，每個任務包含 symbol 和 parameters
        """
        combinations = self.expand_combinations()

        tasks = []
        for symbol in self.config.symbols:
            for params in combinations:
                tasks.append({
                    'symbol': symbol,
                    'parameters': params
                })

        return tasks


class ExperimentRunner:
    """實驗批量執行引擎

    核心功能:
    1. 並行執行實驗任務
    2. 內存管理（流式寫入結果）
    3. 失敗容錯和重試
    4. 進度追蹤
    """

    def __init__(
        self,
        max_workers: int = 4,
        retry_failed: bool = True,
        max_retries: int = 2,
        fail_fast: bool = False,
        progress_callback: Optional[Callable] = None
    ):
        """初始化

        Args:
            max_workers: 最大並行任務數
            retry_failed: 是否重試失敗任務
            max_retries: 最大重試次數
            fail_fast: 遇到錯誤立即停止
            progress_callback: 進度回調函數
        """
        self.max_workers = max_workers
        self.retry_failed = retry_failed
        self.max_retries = max_retries
        self.fail_fast = fail_fast
        self.progress_callback = progress_callback

    def run_experiment(
        self,
        config: ExperimentConfig,
        backtest_func: Callable[[str, str, Dict, ExperimentConfig], Dict]
    ) -> ExperimentResult:
        """執行完整實驗

        Args:
            config: 實驗配置
            backtest_func: 回測函數，簽名為 (symbol, timeframe, params, config) -> metrics_dict

        Returns:
            ExperimentResult: 實驗結果

        Example:
            >>> def my_backtest(symbol, timeframe, params, config):
            ...     # 運行回測
            ...     return {'total_return': 0.15, 'sharpe_ratio': 1.5, ...}
            >>>
            >>> runner = ExperimentRunner(max_workers=4)
            >>> result = runner.run_experiment(config, my_backtest)
        """
        experiment_id = config.get_experiment_id()

        print(f"🚀 開始實驗: {config.name}")
        print(f"📋 實驗ID: {experiment_id}")

        # 展開任務
        expander = ParameterExpander(config)
        tasks = expander.expand_tasks()

        total_tasks = len(tasks)
        print(f"📊 總任務數: {total_tasks}")
        print(f"💰 幣種數: {len(config.symbols)}")
        print(f"⚙️  參數組合數: {len(expander.expand_combinations())}")
        print(f"👷 並行工作數: {self.max_workers}")

        # 初始化結果
        runs: List[ExperimentRun] = []
        started_at = datetime.now().isoformat()

        # 並行執行
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任務
            future_to_task = {}
            for i, task in enumerate(tasks):
                run_id = f"{experiment_id}_run_{i:06d}"
                future = executor.submit(
                    self._execute_single_run,
                    run_id=run_id,
                    experiment_id=experiment_id,
                    symbol=task['symbol'],
                    parameters=task['parameters'],
                    config=config,
                    backtest_func=backtest_func
                )
                future_to_task[future] = task

            # 收集結果（帶進度條）
            completed = 0
            failed_count = 0

            with tqdm(total=total_tasks, desc="執行進度") as pbar:
                for future in as_completed(future_to_task):
                    try:
                        run = future.result()
                        runs.append(run)

                        if run.status == ExperimentStatus.FAILED:
                            failed_count += 1
                            if self.fail_fast:
                                print(f"\n❌ 任務失敗（fail_fast 模式），停止執行")
                                executor.shutdown(wait=False, cancel_futures=True)
                                break

                        # 流式寫入結果（節省內存）
                        if completed % 10 == 0:
                            self._flush_results(experiment_id, runs[-10:])

                    except Exception as e:
                        failed_count += 1
                        print(f"\n⚠️  任務執行異常: {e}")
                        if self.fail_fast:
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

                    completed += 1
                    pbar.update(1)

                    if self.progress_callback:
                        self.progress_callback(completed, total_tasks, failed_count)

        completed_at = datetime.now().isoformat()
        duration = (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds()

        # 統計結果
        completed_runs = len([r for r in runs if r.status == ExperimentStatus.COMPLETED])
        failed_runs = len([r for r in runs if r.status == ExperimentStatus.FAILED])

        print(f"\n✅ 實驗完成！")
        print(f"⏱️  執行時間: {duration:.1f} 秒")
        print(f"✅ 成功: {completed_runs}/{total_tasks}")
        print(f"❌ 失敗: {failed_runs}/{total_tasks}")

        # 創建結果對象
        result = ExperimentResult(
            experiment_id=experiment_id,
            config=config,
            runs=runs,
            total_runs=total_tasks,
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration
        )

        # 找出最佳執行
        result.best_run = result.get_best_run(metric=config.tags[0] if config.tags else "sharpe_ratio")

        return result

    def _execute_single_run(
        self,
        run_id: str,
        experiment_id: str,
        symbol: str,
        parameters: Dict[str, Any],
        config: ExperimentConfig,
        backtest_func: Callable
    ) -> ExperimentRun:
        """執行單個實驗運行

        包含重試邏輯和錯誤處理

        Args:
            run_id: 運行ID
            experiment_id: 實驗ID
            symbol: 交易對
            parameters: 參數組合
            config: 實驗配置
            backtest_func: 回測函數

        Returns:
            ExperimentRun: 運行記錄
        """
        run = ExperimentRun(
            experiment_id=experiment_id,
            run_id=run_id,
            symbol=symbol,
            parameters=parameters,
            status=ExperimentStatus.PENDING
        )

        retries = 0
        while retries <= self.max_retries:
            try:
                # 標記為運行中
                run.status = ExperimentStatus.RUNNING
                run.started_at = datetime.now().isoformat()

                # 執行回測
                metrics = backtest_func(symbol, config.timeframe, parameters, config)

                # 記錄結果
                run.total_return = metrics.get('total_return')
                run.max_drawdown = metrics.get('max_drawdown')
                run.sharpe_ratio = metrics.get('sharpe_ratio')
                run.num_trades = metrics.get('num_trades')
                run.win_rate = metrics.get('win_rate')
                run.profit_factor = metrics.get('profit_factor')

                # 保存額外指標
                run.metrics = {k: v for k, v in metrics.items()
                              if k not in ['total_return', 'max_drawdown', 'sharpe_ratio',
                                          'num_trades', 'win_rate', 'profit_factor']}

                # 標記完成
                run.status = ExperimentStatus.COMPLETED
                run.completed_at = datetime.now().isoformat()

                return run

            except Exception as e:
                retries += 1
                error_msg = f"{type(e).__name__}: {str(e)}"

                if retries > self.max_retries or not self.retry_failed:
                    # 標記失敗
                    run.status = ExperimentStatus.FAILED
                    run.error_message = error_msg
                    run.completed_at = datetime.now().isoformat()
                    return run
                else:
                    # 等待後重試
                    time.sleep(0.5 * retries)

        return run

    def _flush_results(self, experiment_id: str, runs: List[ExperimentRun]):
        """流式寫入結果到磁盤（節省內存）

        Args:
            experiment_id: 實驗ID
            runs: 運行記錄列表
        """
        output_dir = Path("data/experiments/results") / experiment_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # 追加模式寫入
        output_file = output_dir / "runs.jsonl"
        with open(output_file, 'a') as f:
            for run in runs:
                f.write(json.dumps(run.to_dict()) + '\n')

    def save_result(self, result: ExperimentResult, output_path: Optional[str] = None):
        """保存完整實驗結果

        Args:
            result: 實驗結果
            output_path: 輸出路徑（默認為 data/experiments/results/{experiment_id}/）
        """
        if output_path is None:
            output_dir = Path("data/experiments/results") / result.experiment_id
        else:
            output_dir = Path(output_path)

        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存摘要
        summary_file = output_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

        # 保存配置
        config_file = output_dir / "config.json"
        result.config.save(str(config_file))

        # 保存所有運行記錄（如果還沒寫入）
        runs_file = output_dir / "runs.jsonl"
        if not runs_file.exists():
            with open(runs_file, 'w') as f:
                for run in result.runs:
                    f.write(json.dumps(run.to_dict()) + '\n')

        print(f"💾 結果已保存: {output_dir}")

    def load_result(self, experiment_id: str) -> ExperimentResult:
        """加載實驗結果

        Args:
            experiment_id: 實驗ID

        Returns:
            ExperimentResult: 實驗結果
        """
        result_dir = Path("data/experiments/results") / experiment_id

        # 加載摘要
        summary_file = result_dir / "summary.json"
        with open(summary_file, 'r') as f:
            data = json.load(f)

        # 重建對象
        config = ExperimentConfig.from_dict(data['config'])

        runs = []
        for run_data in data['runs']:
            runs.append(ExperimentRun.from_dict(run_data))

        result = ExperimentResult(
            experiment_id=data['experiment_id'],
            config=config,
            runs=runs,
            total_runs=data['total_runs'],
            completed_runs=data['completed_runs'],
            failed_runs=data['failed_runs'],
            started_at=data['started_at'],
            completed_at=data['completed_at'],
            duration_seconds=data['duration_seconds']
        )

        if data['best_run']:
            result.best_run = ExperimentRun.from_dict(data['best_run'])

        return result


# ===== 便捷函數 =====

def run_experiment(
    config: ExperimentConfig,
    backtest_func: Callable,
    max_workers: int = 4,
    **runner_kwargs
) -> ExperimentResult:
    """運行實驗的便捷函數

    Args:
        config: 實驗配置
        backtest_func: 回測函數
        max_workers: 最大並行數
        **runner_kwargs: 傳遞給 ExperimentRunner 的其他參數

    Returns:
        ExperimentResult: 實驗結果

    Example:
        >>> def my_backtest(symbol, timeframe, params, config):
        ...     # 執行回測
        ...     return metrics
        >>>
        >>> config = create_experiment_config(...)
        >>> result = run_experiment(config, my_backtest, max_workers=8)
    """
    runner = ExperimentRunner(max_workers=max_workers, **runner_kwargs)
    result = runner.run_experiment(config, backtest_func)
    runner.save_result(result)
    return result
