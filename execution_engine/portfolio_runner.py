# -*- coding: utf-8 -*-
"""
Portfolio Runner v0.3

批量回測執行器，負責執行多個回測任務並聚合結果。

Features:
- 序列執行多個回測任務
- 錯誤處理（單個失敗不影響其他）
- 結果聚合和查詢
- 支援從 YAML 載入配置

Design Reference: docs/specs/planned/v0.3_portfolio_runner_api.md
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import time
import pandas as pd

# Backtest engine imports
from backtest.engine import run_backtest, BacktestResult
from backtest.position_sizer import AllInSizer, FixedCashSizer, PercentOfEquitySizer
from data.storage import load_ohlcv
from strategies.registry import get_strategy


@dataclass
class RunConfig:
    """
    單次回測任務配置

    每個 RunConfig 對應一次 run_backtest() 調用
    """
    # 必填字段
    strategy: str          # 策略名稱（在 registry 中查找）
    symbol: str            # 交易對（例如: "BTCUSDT"）
    timeframe: str         # 時間周期（例如: "1h", "4h", "1d"）

    # 可選字段（時間範圍）
    start: Optional[str] = None    # 開始日期（YYYY-MM-DD 格式）
    end: Optional[str] = None      # 結束日期（YYYY-MM-DD 格式）

    # 可選字段（回測參數）
    initial_cash: float = 10000.0
    fee_rate: float = 0.0005
    leverage: float = 1.0

    # 可選字段（Position Sizer）
    position_sizer: Optional[Dict[str, Any]] = None
    # 例如: {"type": "PercentOfEquitySizer", "percent": 0.5}

    # 可選字段（SL/TP）
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None

    # 可選字段（策略參數）
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    # 例如: {"fast_period": 5, "slow_period": 20}

    def __post_init__(self):
        """驗證配置"""
        if not self.strategy:
            raise ValueError("strategy is required")
        if not self.symbol:
            raise ValueError("symbol is required")
        if not self.timeframe:
            raise ValueError("timeframe is required")

        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.fee_rate < 0 or self.fee_rate > 0.1:
            raise ValueError("fee_rate must be between 0 and 0.1")
        if self.leverage < 1 or self.leverage > 100:
            raise ValueError("leverage must be between 1 and 100")

    def to_dict(self) -> dict:
        """轉換為字典（用於序列化）"""
        return {
            "strategy": self.strategy,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start": self.start,
            "end": self.end,
            "initial_cash": self.initial_cash,
            "fee_rate": self.fee_rate,
            "leverage": self.leverage,
            "position_sizer": self.position_sizer,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "strategy_params": self.strategy_params
        }


@dataclass
class SingleRunResult:
    """
    單次回測任務的執行結果

    無論成功或失敗，都會創建一個 SingleRunResult 對象
    """
    # 配置信息（方便追溯）
    strategy: str
    symbol: str
    timeframe: str
    config: RunConfig

    # 執行結果
    success: bool                                # 是否成功
    backtest_result: Optional[BacktestResult] = None  # 成功時有值
    error: Optional[str] = None                  # 失敗時記錄錯誤

    # 元數據
    execution_time: float = 0.0                  # 執行耗時（秒）
    timestamp: datetime = field(default_factory=datetime.now)

    def get_metrics(self) -> Dict[str, float]:
        """獲取 metrics（如果成功）"""
        if self.success and self.backtest_result:
            return self.backtest_result.metrics
        else:
            return {}

    def get_metric(self, name: str, default=None):
        """獲取單個 metric"""
        return self.get_metrics().get(name, default)

    def __repr__(self) -> str:
        if self.success:
            total_return = self.get_metric('total_return', 0)
            return f"<SingleRunResult: {self.strategy}@{self.symbol} [{self.timeframe}] ✓ {total_return:.2%}>"
        else:
            return f"<SingleRunResult: {self.strategy}@{self.symbol} [{self.timeframe}] ✗ {self.error}>"


@dataclass
class PortfolioResult:
    """
    批量回測的聚合結果

    包含多個 SingleRunResult，並提供查詢、過濾、排序等功能
    """
    runs: List[SingleRunResult]
    total_time: float = 0.0  # 總耗時（秒）

    def __len__(self) -> int:
        """返回回測任務數量"""
        return len(self.runs)

    def __getitem__(self, index: int) -> SingleRunResult:
        """支持索引訪問"""
        return self.runs[index]

    def __iter__(self):
        """支持迭代"""
        return iter(self.runs)

    # === 查詢方法 ===

    def get_successful_runs(self) -> List[SingleRunResult]:
        """獲取所有成功的回測"""
        return [run for run in self.runs if run.success]

    def get_failed_runs(self) -> List[SingleRunResult]:
        """獲取所有失敗的回測"""
        return [run for run in self.runs if not run.success]

    def get_by_strategy(self, strategy_name: str) -> List[SingleRunResult]:
        """獲取特定策略的所有回測"""
        return [run for run in self.runs if run.strategy == strategy_name]

    def get_by_symbol(self, symbol: str) -> List[SingleRunResult]:
        """獲取特定交易對的所有回測"""
        return [run for run in self.runs if run.symbol == symbol]

    def filter(self, predicate: Callable[[SingleRunResult], bool]) -> List[SingleRunResult]:
        """自定義過濾"""
        return [run for run in self.runs if predicate(run)]

    # === 排序方法 ===

    def get_best_by(self, metric: str, top_n: int = 1) -> List[SingleRunResult]:
        """
        按某個 metric 排序，返回最好的 N 個

        Args:
            metric: 指標名稱（例如: "total_return", "profit_factor"）
            top_n: 返回前 N 個

        Returns:
            排序後的列表（降序）
        """
        successful = self.get_successful_runs()
        if not successful:
            return []

        # 按 metric 降序排序
        sorted_runs = sorted(
            successful,
            key=lambda r: r.get_metric(metric, float('-inf')),
            reverse=True
        )
        return sorted_runs[:top_n]

    def get_worst_by(self, metric: str, bottom_n: int = 1) -> List[SingleRunResult]:
        """按某個 metric 排序，返回最差的 N 個"""
        successful = self.get_successful_runs()
        if not successful:
            return []

        sorted_runs = sorted(
            successful,
            key=lambda r: r.get_metric(metric, float('inf')),
            reverse=False
        )
        return sorted_runs[:bottom_n]

    # === 統計方法 ===

    def count_successful(self) -> int:
        """成功的回測數量"""
        return len(self.get_successful_runs())

    def count_failed(self) -> int:
        """失敗的回測數量"""
        return len(self.get_failed_runs())

    def success_rate(self) -> float:
        """成功率"""
        if len(self.runs) == 0:
            return 0.0
        return self.count_successful() / len(self.runs)

    # === DataFrame 轉換 ===

    def to_dataframe(self, include_failed: bool = False) -> pd.DataFrame:
        """
        轉換為 DataFrame（排行表）

        Args:
            include_failed: 是否包含失敗的回測

        Returns:
            DataFrame with columns:
                - strategy: 策略名稱
                - symbol: 交易對
                - timeframe: 時間周期
                - total_return: 總收益率
                - max_drawdown: 最大回撤
                - profit_factor: 盈虧比
                - num_trades: 交易次數
                - win_rate: 勝率
                - execution_time: 執行耗時
                - status: 成功/失敗
                - error: 錯誤信息（僅失敗時）
        """
        records = []

        for run in self.runs:
            if not run.success and not include_failed:
                continue

            record = {
                "strategy": run.strategy,
                "symbol": run.symbol,
                "timeframe": run.timeframe,
                "status": "✓" if run.success else "✗",
            }

            if run.success:
                metrics = run.get_metrics()
                record.update({
                    "total_return": metrics.get("total_return", 0),
                    "max_drawdown": metrics.get("max_drawdown", 0),
                    "profit_factor": metrics.get("profit_factor", 0),
                    "num_trades": metrics.get("num_trades", 0),
                    "win_rate": metrics.get("win_rate", 0),
                    "expectancy": metrics.get("expectancy", 0),
                    "execution_time": run.execution_time,
                    "error": ""
                })
            else:
                record.update({
                    "total_return": None,
                    "max_drawdown": None,
                    "profit_factor": None,
                    "num_trades": None,
                    "win_rate": None,
                    "expectancy": None,
                    "execution_time": run.execution_time,
                    "error": run.error or ""
                })

            records.append(record)

        return pd.DataFrame(records)

    # === 輔助方法 ===

    def summary(self) -> str:
        """生成簡短摘要"""
        total = len(self.runs)
        success = self.count_successful()
        failed = self.count_failed()

        return (
            f"Portfolio Summary:\n"
            f"  Total runs: {total}\n"
            f"  Successful: {success}\n"
            f"  Failed: {failed}\n"
            f"  Success rate: {self.success_rate():.1%}\n"
            f"  Total time: {self.total_time:.2f}s"
        )

    def __repr__(self) -> str:
        return f"<PortfolioResult: {len(self.runs)} runs, {self.count_successful()} successful>"


# === 核心函數：run_portfolio ===

def run_portfolio(
    configs: List[RunConfig],
    verbose: bool = False,
    fail_fast: bool = False
) -> PortfolioResult:
    """
    批量執行回測任務

    Args:
        configs: 回測配置列表
        verbose: 是否輸出詳細日誌
        fail_fast: 遇到錯誤時是否立即停止（默認 False，繼續執行）

    Returns:
        PortfolioResult: 聚合結果

    Raises:
        ValueError: 如果 configs 為空
    """

    if not configs:
        raise ValueError("configs cannot be empty")

    results: List[SingleRunResult] = []
    start_time = time.time()

    for i, config in enumerate(configs, 1):
        if verbose:
            print(f"[{i}/{len(configs)}] Running: {config.strategy} on {config.symbol} ({config.timeframe})...")

        # 執行單次回測
        run_result = _run_single_backtest(config, verbose=verbose)
        results.append(run_result)

        # 失敗處理
        if not run_result.success:
            if verbose:
                print(f"  ✗ Failed: {run_result.error}")

            if fail_fast:
                # 立即停止
                if verbose:
                    print(f"Stopping due to error (fail_fast=True)")
                break
        else:
            if verbose:
                total_return = run_result.get_metric('total_return', 0)
                print(f"  ✓ Success: {total_return:.2%}")

    total_time = time.time() - start_time

    if verbose:
        print(f"\nCompleted {len(results)} runs in {total_time:.2f}s")
        print(f"  Successful: {sum(1 for r in results if r.success)}")
        print(f"  Failed: {sum(1 for r in results if not r.success)}")

    return PortfolioResult(runs=results, total_time=total_time)


def _run_single_backtest(config: RunConfig, verbose: bool = False) -> SingleRunResult:
    """
    執行單次回測（內部函數）

    捕獲所有異常，確保不會中斷批量執行
    """
    start_time = time.time()

    try:
        # Step 1: 獲取策略類
        try:
            strategy_cls = get_strategy(config.strategy)
        except Exception as e:
            raise ValueError(f"Strategy not found: {config.strategy}") from e

        # Step 2: 加載數據
        data_file = f"data/raw/{config.symbol}_{config.timeframe}.csv"
        try:
            data = load_ohlcv(data_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Data file not found: {data_file}")
        except Exception as e:
            raise ValueError(f"Failed to load data: {e}") from e

        # Step 3: 過濾時間範圍
        if config.start or config.end:
            data = _filter_date_range(data, config.start, config.end)

        if len(data) == 0:
            raise ValueError("No data after date filtering")

        # Step 4: 構建 Position Sizer
        position_sizer = _build_position_sizer(config)

        # Step 5: 執行回測
        backtest_result = run_backtest(
            data=data,
            strategy_cls=strategy_cls,
            initial_cash=config.initial_cash,
            fee_rate=config.fee_rate,
            position_sizer=position_sizer,
            stop_loss_pct=config.stop_loss_pct,
            take_profit_pct=config.take_profit_pct,
            leverage=config.leverage
        )

        execution_time = time.time() - start_time

        # 返回成功結果
        return SingleRunResult(
            strategy=config.strategy,
            symbol=config.symbol,
            timeframe=config.timeframe,
            config=config,
            success=True,
            backtest_result=backtest_result,
            error=None,
            execution_time=execution_time
        )

    except Exception as e:
        # 捕獲所有錯誤
        execution_time = time.time() - start_time

        if verbose:
            import traceback
            traceback.print_exc()

        return SingleRunResult(
            strategy=config.strategy,
            symbol=config.symbol,
            timeframe=config.timeframe,
            config=config,
            success=False,
            backtest_result=None,
            error=str(e),
            execution_time=execution_time
        )


def _filter_date_range(
    data: pd.DataFrame,
    start: Optional[str],
    end: Optional[str]
) -> pd.DataFrame:
    """過濾日期範圍"""
    if start:
        data = data[data.index >= pd.Timestamp(start)]
    if end:
        data = data[data.index <= pd.Timestamp(end)]
    return data


def _build_position_sizer(config: RunConfig):
    """根據配置構建 Position Sizer"""
    if config.position_sizer is None:
        # 默認使用 AllInSizer
        return AllInSizer(fee_rate=config.fee_rate)

    ps_type = config.position_sizer.get("type")

    if ps_type == "AllInSizer":
        return AllInSizer(fee_rate=config.fee_rate)

    elif ps_type == "FixedCashSizer":
        cash_amount = config.position_sizer.get("cash_amount", 1000)
        return FixedCashSizer(cash_amount=cash_amount, fee_rate=config.fee_rate)

    elif ps_type == "PercentOfEquitySizer":
        percent = config.position_sizer.get("percent", 0.5)
        return PercentOfEquitySizer(percent=percent, fee_rate=config.fee_rate)

    else:
        raise ValueError(f"Unknown position sizer type: {ps_type}")


# === YAML 配置支援（可選功能） ===

def load_configs_from_yaml(yaml_path: str) -> List[RunConfig]:
    """
    從 YAML 文件加載配置

    Args:
        yaml_path: YAML 文件路徑

    Returns:
        List[RunConfig]

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 配置格式錯誤
    """
    import yaml

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("YAML root must be a dict")

    runs = data.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError("'runs' must be a list")

    configs = []
    for i, run_dict in enumerate(runs):
        try:
            config = RunConfig(**run_dict)
            configs.append(config)
        except Exception as e:
            raise ValueError(f"Invalid config at index {i}: {e}") from e

    return configs
