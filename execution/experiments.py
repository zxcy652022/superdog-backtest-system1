"""
Experiment Management System v0.6

實驗管理核心模組 - 定義實驗配置、數據結構和管理接口

核心功能:
- 實驗配置定義（YAML/JSON）
- 參數展開邏輯（網格、隨機）
- 實驗元數據管理
- 實驗狀態追蹤

Version: v0.6 Phase 2
Design Reference: docs/specs/v0.6/superdog_v06_implementation_guide.md
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class ExperimentStatus(Enum):
    """實驗狀態"""

    PENDING = "pending"  # 待執行
    RUNNING = "running"  # 執行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失敗
    CANCELLED = "cancelled"  # 已取消


class ParameterExpansionMode(Enum):
    """參數展開模式"""

    GRID = "grid"  # 網格搜索（全組合）
    RANDOM = "random"  # 隨機採樣
    LIST = "list"  # 列表（指定組合）


@dataclass
class ParameterRange:
    """參數範圍定義

    支援多種定義方式:
    - 列表: [1, 2, 3, 5, 10]
    - 範圍: {"start": 10, "stop": 100, "step": 10}
    - 對數範圍: {"start": 0.001, "stop": 1, "num": 10, "log": True}
    """

    name: str  # 參數名稱
    values: Optional[List[Any]] = None  # 離散值列表
    start: Optional[float] = None  # 範圍起始
    stop: Optional[float] = None  # 範圍結束
    step: Optional[float] = None  # 範圍步長
    num: Optional[int] = None  # 數量（用於對數）
    log_scale: bool = False  # 是否對數刻度

    def expand(self) -> List[Any]:
        """展開參數範圍為具體值列表

        Returns:
            List[Any]: 參數值列表

        Example:
            >>> param = ParameterRange("period", start=10, stop=50, step=10)
            >>> param.expand()
            [10, 20, 30, 40, 50]
        """
        if self.values is not None:
            return self.values

        if self.start is not None and self.stop is not None:
            if self.log_scale:
                # 對數刻度
                import numpy as np

                num = self.num or 10
                return list(np.logspace(np.log10(self.start), np.log10(self.stop), num=num))
            else:
                # 線性刻度
                if self.step is not None:
                    # 使用step
                    import numpy as np

                    return list(np.arange(self.start, self.stop + self.step, self.step))
                elif self.num is not None:
                    # 使用num
                    import numpy as np

                    return list(np.linspace(self.start, self.stop, num=self.num))

        raise ValueError(f"Invalid parameter range definition for {self.name}")


@dataclass
class ExperimentConfig:
    """實驗配置

    Example YAML:
        name: SMA_Optimization
        strategy: simple_sma
        symbols:
          - BTCUSDT
          - ETHUSDT
        timeframe: 1h
        parameters:
          sma_short:
            start: 5
            stop: 20
            step: 5
          sma_long:
            start: 20
            stop: 100
            step: 10
        expansion_mode: grid
        max_combinations: 1000
    """

    name: str  # 實驗名稱
    strategy: str  # 策略名稱
    symbols: List[str]  # 幣種列表
    timeframe: str  # 時間週期
    parameters: Dict[str, ParameterRange]  # 參數範圍

    # 可選配置
    expansion_mode: ParameterExpansionMode = ParameterExpansionMode.GRID
    max_combinations: Optional[int] = None  # 最大組合數（防止爆炸）
    sample_size: Optional[int] = None  # 隨機採樣大小
    start_date: Optional[str] = None  # 回測起始日期
    end_date: Optional[str] = None  # 回測結束日期
    initial_cash: float = 10000  # 初始資金
    fee_rate: float = 0.0005  # 手續費率
    leverage: float = 1.0  # 槓桿
    stop_loss_pct: Optional[float] = None  # 止損
    take_profit_pct: Optional[float] = None  # 止盈

    # 實驗元數據
    description: str = ""  # 實驗描述
    tags: List[str] = field(default_factory=list)  # 標籤
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """初始化後處理"""
        # 轉換參數為ParameterRange對象
        if isinstance(self.parameters, dict):
            new_params = {}
            for name, spec in self.parameters.items():
                if isinstance(spec, ParameterRange):
                    new_params[name] = spec
                elif isinstance(spec, dict):
                    # 如果 dict 已經包含 name，移除以避免重複
                    spec_copy = spec.copy()
                    spec_copy.pop("name", None)
                    new_params[name] = ParameterRange(name=name, **spec_copy)
                elif isinstance(spec, list):
                    new_params[name] = ParameterRange(name=name, values=spec)
                else:
                    raise ValueError(f"Invalid parameter spec for {name}")
            self.parameters = new_params

        # 轉換expansion_mode為枚舉
        if isinstance(self.expansion_mode, str):
            self.expansion_mode = ParameterExpansionMode(self.expansion_mode)

    def get_experiment_id(self) -> str:
        """生成實驗唯一ID

        基於配置內容的哈希值

        Returns:
            str: 實驗ID
        """
        # 創建配置的穩定表示
        config_str = json.dumps(
            {
                "name": self.name,
                "strategy": self.strategy,
                "symbols": sorted(self.symbols),
                "timeframe": self.timeframe,
                "parameters": {k: v.__dict__ for k, v in self.parameters.items()},
                "expansion_mode": self.expansion_mode.value,
            },
            sort_keys=True,
        )

        # 生成哈希
        hash_obj = hashlib.md5(config_str.encode())
        return f"{self.name}_{hash_obj.hexdigest()[:8]}"

    def to_dict(self) -> Dict:
        """轉換為字典"""
        result = asdict(self)
        result["expansion_mode"] = self.expansion_mode.value
        return result

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "ExperimentConfig":
        """從YAML文件加載配置

        Args:
            yaml_path: YAML文件路徑

        Returns:
            ExperimentConfig: 配置對象
        """
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_path: str) -> "ExperimentConfig":
        """從JSON文件加載配置

        Args:
            json_path: JSON文件路徑

        Returns:
            ExperimentConfig: 配置對象
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict) -> "ExperimentConfig":
        """從字典創建配置

        Args:
            data: 配置字典

        Returns:
            ExperimentConfig: 配置對象
        """
        # 移除created_at以使用默認值
        if "created_at" in data:
            del data["created_at"]

        return cls(**data)

    def save(self, output_path: str):
        """保存配置到文件

        Args:
            output_path: 輸出文件路徑（.yaml或.json）
        """
        path = Path(output_path)

        if path.suffix == ".yaml" or path.suffix == ".yml":
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


@dataclass
class ExperimentRun:
    """單次實驗執行記錄"""

    experiment_id: str  # 實驗ID
    run_id: str  # 執行ID
    symbol: str  # 幣種
    parameters: Dict[str, Any]  # 參數組合

    # 執行狀態
    status: ExperimentStatus = ExperimentStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    # 回測結果
    total_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    num_trades: Optional[int] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None

    # 其他指標
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """轉換為字典"""
        result = asdict(self)
        result["status"] = self.status.value
        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "ExperimentRun":
        """從字典創建"""
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ExperimentStatus(data["status"])
        return cls(**data)


@dataclass
class ExperimentResult:
    """實驗結果匯總"""

    experiment_id: str
    config: ExperimentConfig
    runs: List[ExperimentRun]

    # 統計信息
    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0

    # 最佳結果
    best_run: Optional[ExperimentRun] = None
    best_metric: str = "sharpe_ratio"

    # 時間信息
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None

    def get_best_run(
        self, metric: str = "sharpe_ratio", ascending: bool = False
    ) -> Optional[ExperimentRun]:
        """獲取最佳執行

        Args:
            metric: 評估指標
            ascending: 是否升序（True=越小越好，False=越大越好）

        Returns:
            Optional[ExperimentRun]: 最佳執行記錄
        """
        completed = [r for r in self.runs if r.status == ExperimentStatus.COMPLETED]

        if not completed:
            return None

        # 篩選有該指標的執行
        valid_runs = []
        for run in completed:
            value = getattr(run, metric, None)
            if value is None:
                value = run.metrics.get(metric)

            if value is not None and not (isinstance(value, float) and value != value):  # 排除NaN
                valid_runs.append((run, value))

        if not valid_runs:
            return None

        # 排序並返回最佳
        valid_runs.sort(key=lambda x: x[1], reverse=not ascending)
        return valid_runs[0][0]

    def get_statistics(self) -> Dict[str, Any]:
        """獲取統計信息

        Returns:
            Dict: 統計字典
        """
        completed = [r for r in self.runs if r.status == ExperimentStatus.COMPLETED]

        if not completed:
            return {}

        import numpy as np

        # 收集各項指標
        returns = [r.total_return for r in completed if r.total_return is not None]
        drawdowns = [r.max_drawdown for r in completed if r.max_drawdown is not None]
        sharpes = [r.sharpe_ratio for r in completed if r.sharpe_ratio is not None]

        return {
            "total_runs": len(self.runs),
            "completed": len(completed),
            "failed": len([r for r in self.runs if r.status == ExperimentStatus.FAILED]),
            "avg_return": np.mean(returns) if returns else None,
            "avg_drawdown": np.mean(drawdowns) if drawdowns else None,
            "avg_sharpe": np.mean(sharpes) if sharpes else None,
            "best_return": max(returns) if returns else None,
            "worst_return": min(returns) if returns else None,
            "best_sharpe": max(sharpes) if sharpes else None,
        }

    def to_dict(self) -> Dict:
        """轉換為字典"""
        return {
            "experiment_id": self.experiment_id,
            "config": self.config.to_dict(),
            "runs": [r.to_dict() for r in self.runs],
            "total_runs": self.total_runs,
            "completed_runs": self.completed_runs,
            "failed_runs": self.failed_runs,
            "best_run": self.best_run.to_dict() if self.best_run else None,
            "best_metric": self.best_metric,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "statistics": self.get_statistics(),
        }


# ===== 便捷函數 =====


def create_experiment_config(
    name: str, strategy: str, symbols: List[str], parameters: Dict[str, Union[List, Dict]], **kwargs
) -> ExperimentConfig:
    """創建實驗配置的便捷函數

    Args:
        name: 實驗名稱
        strategy: 策略名稱
        symbols: 幣種列表
        parameters: 參數定義
        **kwargs: 其他配置

    Returns:
        ExperimentConfig: 配置對象

    Example:
        >>> config = create_experiment_config(
        ...     name="SMA_Test",
        ...     strategy="simple_sma",
        ...     symbols=["BTCUSDT"],
        ...     parameters={
        ...         "sma_short": [5, 10, 15],
        ...         "sma_long": {"start": 20, "stop": 100, "step": 20}
        ...     },
        ...     timeframe="1h"
        ... )
    """
    return ExperimentConfig(
        name=name, strategy=strategy, symbols=symbols, parameters=parameters, **kwargs
    )


def load_experiment_config(config_path: str) -> ExperimentConfig:
    """加載實驗配置

    自動檢測文件格式（YAML或JSON）

    Args:
        config_path: 配置文件路徑

    Returns:
        ExperimentConfig: 配置對象
    """
    path = Path(config_path)

    if path.suffix in [".yaml", ".yml"]:
        return ExperimentConfig.from_yaml(config_path)
    elif path.suffix == ".json":
        return ExperimentConfig.from_json(config_path)
    else:
        raise ValueError(f"Unsupported config file format: {path.suffix}")
