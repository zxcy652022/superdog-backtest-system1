"""
Walk-Forward Validator v1.0

Walk-Forward 驗證器 - 防止過擬合的核心工具

核心功能：
- 滾動窗口分割
- 訓練期參數優化
- 測試期驗證
- 穩健參數推薦
- 行情分類績效分析

Version: v1.0
Design Reference: docs/v1.0/DESIGN.md
"""

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from execution.runner import RunConfig, run_backtest, run_portfolio


@dataclass
class WFConfig:
    """Walk-Forward 配置"""

    train_months: int = 6  # 訓練期長度（月）
    test_months: int = 2  # 測試期長度（月）
    step_months: int = 2  # 滾動步長（月）

    # 優化配置
    optimize_metric: str = "sharpe_ratio"  # 優化目標指標
    maximize: bool = True  # True=最大化，False=最小化
    min_trades: int = 5  # 最少交易次數要求

    # 搜索配置
    max_combinations: int = 200  # 最大參數組合數（超過則隨機採樣）
    n_random_samples: int = 100  # 隨機搜索採樣數

    # 並行配置
    max_workers: int = 4


@dataclass
class WFWindow:
    """Walk-Forward 單一窗口"""

    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str

    # 優化結果
    best_params: Dict[str, Any] = field(default_factory=dict)
    train_metrics: Dict[str, float] = field(default_factory=dict)
    test_metrics: Dict[str, float] = field(default_factory=dict)

    # 狀態
    is_optimized: bool = False
    is_validated: bool = False


@dataclass
class WFResult:
    """Walk-Forward 驗證結果"""

    windows: List[WFWindow]
    config: WFConfig
    strategy_name: str
    symbols: List[str]
    timeframes: List[str]

    # 統計
    total_train_time: float = 0.0  # 總訓練時間（秒）
    total_test_time: float = 0.0  # 總測試時間（秒）

    def get_oos_metrics(self) -> pd.DataFrame:
        """獲取所有測試期（Out-of-Sample）績效

        Returns:
            pd.DataFrame: 各窗口的 OOS 績效
        """
        data = []
        for w in self.windows:
            if w.is_validated:
                row = {
                    "window": w.window_id,
                    "test_start": w.test_start,
                    "test_end": w.test_end,
                    **w.test_metrics,
                }
                data.append(row)
        return pd.DataFrame(data)

    def get_is_metrics(self) -> pd.DataFrame:
        """獲取所有訓練期（In-Sample）績效

        Returns:
            pd.DataFrame: 各窗口的 IS 績效
        """
        data = []
        for w in self.windows:
            if w.is_optimized:
                row = {
                    "window": w.window_id,
                    "train_start": w.train_start,
                    "train_end": w.train_end,
                    **w.train_metrics,
                }
                data.append(row)
        return pd.DataFrame(data)

    def get_param_stability(self) -> Dict[str, Dict[str, float]]:
        """分析每個參數在各窗口的穩定性

        Returns:
            Dict[str, Dict]: 參數名 -> {mean, std, cv}
        """
        if not self.windows:
            return {}

        # 收集各窗口的最佳參數
        param_values = {}
        for w in self.windows:
            if w.best_params:
                for name, value in w.best_params.items():
                    if name not in param_values:
                        param_values[name] = []
                    # 只處理數值型參數
                    if isinstance(value, (int, float)):
                        param_values[name].append(value)

        # 計算穩定性指標
        stability = {}
        for name, values in param_values.items():
            if len(values) > 1:
                mean = np.mean(values)
                std = np.std(values)
                cv = std / mean if mean != 0 else float("inf")
                stability[name] = {
                    "mean": mean,
                    "std": std,
                    "cv": cv,  # 變異係數，越小越穩定
                    "values": values,
                }

        return stability

    def get_robust_params(self) -> Dict[str, Any]:
        """獲取穩健參數推薦

        基於各窗口表現加權計算

        Returns:
            Dict[str, Any]: 推薦的參數組合
        """
        if not self.windows:
            return {}

        # 簡單策略：使用最後一個窗口的最佳參數
        # 或者使用各窗口表現最好的參數
        best_window = None
        best_score = float("-inf") if self.config.maximize else float("inf")

        for w in self.windows:
            if not w.is_validated:
                continue
            score = w.test_metrics.get(self.config.optimize_metric, 0)

            if self.config.maximize:
                if score > best_score:
                    best_score = score
                    best_window = w
            else:
                if score < best_score:
                    best_score = score
                    best_window = w

        return best_window.best_params if best_window else {}

    def get_robustness_score(self) -> float:
        """計算整體穩健度分數 (0-100)

        基於：
        - OOS 績效一致性
        - 參數穩定性
        - IS vs OOS 差異

        Returns:
            float: 穩健度分數
        """
        if not self.windows:
            return 0.0

        scores = []

        # 1. OOS 績效一致性 (40 分)
        oos_metrics = self.get_oos_metrics()
        if not oos_metrics.empty and self.config.optimize_metric in oos_metrics.columns:
            values = oos_metrics[self.config.optimize_metric].dropna()
            if len(values) > 1:
                # 正收益比例
                if self.config.maximize:
                    positive_ratio = (values > 0).mean()
                else:
                    positive_ratio = (values < 0).mean()
                scores.append(positive_ratio * 40)
            else:
                scores.append(20)  # 只有一個窗口給一半分

        # 2. IS vs OOS 差異 (30 分)
        is_metrics = self.get_is_metrics()
        if not oos_metrics.empty and not is_metrics.empty:
            metric = self.config.optimize_metric
            if metric in oos_metrics.columns and metric in is_metrics.columns:
                is_mean = is_metrics[metric].mean()
                oos_mean = oos_metrics[metric].mean()
                if is_mean != 0:
                    # 衰減率越小越好
                    decay = abs(is_mean - oos_mean) / abs(is_mean)
                    decay_score = max(0, 30 * (1 - decay))
                    scores.append(decay_score)
                else:
                    scores.append(15)

        # 3. 參數穩定性 (30 分)
        stability = self.get_param_stability()
        if stability:
            cv_values = [s["cv"] for s in stability.values() if s["cv"] != float("inf")]
            if cv_values:
                avg_cv = np.mean(cv_values)
                # CV < 0.3 視為穩定
                stability_score = max(0, 30 * (1 - min(avg_cv / 0.5, 1)))
                scores.append(stability_score)

        return sum(scores) if scores else 0.0

    def to_report(self) -> str:
        """生成文字報告"""
        lines = []
        lines.append("=" * 70)
        lines.append("           Walk-Forward 驗證報告")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"策略: {self.strategy_name}")
        lines.append(f"幣種: {len(self.symbols)} 個")
        lines.append(f"時間框架: {', '.join(self.timeframes)}")
        lines.append(f"窗口數: {len(self.windows)}")
        lines.append(f"訓練期: {self.config.train_months} 個月")
        lines.append(f"測試期: {self.config.test_months} 個月")
        lines.append(f"優化指標: {self.config.optimize_metric}")
        lines.append("")

        # 滾動窗口結果
        lines.append("-" * 70)
        lines.append("                    滾動窗口結果")
        lines.append("-" * 70)
        lines.append(f"{'窗口':^6} | {'訓練期':^21} | {'測試期':^21} | {'IS':^8} | {'OOS':^8}")
        lines.append("-" * 70)

        metric = self.config.optimize_metric
        for w in self.windows:
            is_val = w.train_metrics.get(metric, 0)
            oos_val = w.test_metrics.get(metric, 0)

            # 格式化數值
            if metric in ("total_return", "max_drawdown"):
                is_str = f"{is_val:+.1%}"
                oos_str = f"{oos_val:+.1%}"
            else:
                is_str = f"{is_val:.2f}"
                oos_str = f"{oos_val:.2f}"

            lines.append(
                f"  {w.window_id:^4} | {w.train_start}~{w.train_end} | "
                f"{w.test_start}~{w.test_end} | {is_str:^8} | {oos_str:^8}"
            )

        lines.append("")

        # OOS 統計
        oos_df = self.get_oos_metrics()
        if not oos_df.empty and metric in oos_df.columns:
            lines.append("-" * 70)
            lines.append("                    OOS 績效統計")
            lines.append("-" * 70)
            values = oos_df[metric].dropna()
            lines.append(f"  平均: {values.mean():.4f}")
            lines.append(f"  標準差: {values.std():.4f}")
            lines.append(f"  最大: {values.max():.4f}")
            lines.append(f"  最小: {values.min():.4f}")
            lines.append(f"  正收益窗口: {(values > 0).sum()}/{len(values)}")
            lines.append("")

        # 穩健參數
        robust_params = self.get_robust_params()
        if robust_params:
            lines.append("-" * 70)
            lines.append("                    穩健參數推薦")
            lines.append("-" * 70)
            for name, value in robust_params.items():
                lines.append(f"  {name}: {value}")
            lines.append("")

        # 穩健度分數
        score = self.get_robustness_score()
        lines.append("-" * 70)
        lines.append(f"整體穩健度分數: {score:.0f}/100")
        if score >= 70:
            lines.append("推薦使用: 是 (分數 >= 70)")
        else:
            lines.append("推薦使用: 否 (分數 < 70，建議調整策略)")
        lines.append("=" * 70)

        return "\n".join(lines)


class WalkForwardValidator:
    """Walk-Forward 驗證器

    執行滾動窗口的訓練-測試分割和參數優化

    Example:
        >>> validator = WalkForwardValidator(
        ...     strategy_cls=BiGeDualMAStrategy,
        ...     symbols=["BTCUSDT", "ETHUSDT"],
        ...     timeframes=["4h"],
        ...     start_date="2023-01-01",
        ...     end_date="2025-12-01",
        ... )
        >>> result = validator.run()
        >>> print(result.to_report())
    """

    def __init__(
        self,
        strategy_cls: type,
        symbols: List[str],
        timeframes: List[str],
        start_date: str,
        end_date: str,
        config: Optional[WFConfig] = None,
        universal_params: Optional[Dict[str, Any]] = None,
        param_names_to_optimize: Optional[List[str]] = None,
    ):
        """初始化 Walk-Forward 驗證器

        Args:
            strategy_cls: 策略類（需有 OPTIMIZABLE_PARAMS 或 get_default_parameters）
            symbols: 幣種列表
            timeframes: 時間框架列表
            start_date: 開始日期 (YYYY-MM-DD)
            end_date: 結束日期 (YYYY-MM-DD)
            config: WF 配置
            universal_params: 通用參數（leverage, initial_cash 等）
            param_names_to_optimize: 要優化的參數名列表（None=全部）
        """
        self.strategy_cls = strategy_cls
        self.strategy_name = strategy_cls.__name__
        self.symbols = symbols
        self.timeframes = timeframes
        self.start_date = start_date
        self.end_date = end_date
        self.config = config or WFConfig()
        self.universal_params = universal_params or {}
        self.param_names_to_optimize = param_names_to_optimize

        # 從策略提取參數空間
        self._setup_param_space()

    def _setup_param_space(self):
        """設置參數搜索空間"""
        from strategies.base import get_strategy_params

        all_params = get_strategy_params(self.strategy_cls)

        if self.param_names_to_optimize:
            self.param_space = {
                k: v for k, v in all_params.items() if k in self.param_names_to_optimize
            }
        else:
            self.param_space = all_params

        # 計算組合數
        from strategies.base import count_param_combinations

        self.total_combinations = count_param_combinations(self.param_space)

    def generate_windows(self) -> List[WFWindow]:
        """生成所有滾動窗口

        Returns:
            List[WFWindow]: 窗口列表
        """
        windows = []
        cfg = self.config

        start = datetime.strptime(self.start_date, "%Y-%m-%d")
        end = datetime.strptime(self.end_date, "%Y-%m-%d")

        train_delta = relativedelta(months=cfg.train_months)
        test_delta = relativedelta(months=cfg.test_months)
        step_delta = relativedelta(months=cfg.step_months)

        window_id = 0
        current_start = start

        while True:
            train_end = current_start + train_delta
            test_start = train_end
            test_end = test_start + test_delta

            # 檢查是否超出結束日期
            if test_end > end:
                break

            window = WFWindow(
                window_id=window_id,
                train_start=current_start.strftime("%Y-%m-%d"),
                train_end=train_end.strftime("%Y-%m-%d"),
                test_start=test_start.strftime("%Y-%m-%d"),
                test_end=test_end.strftime("%Y-%m-%d"),
            )
            windows.append(window)

            window_id += 1
            current_start += step_delta

        return windows

    def _generate_param_combinations(self) -> List[Dict[str, Any]]:
        """生成參數組合（網格或隨機採樣）"""
        import itertools

        # 獲取搜索空間
        search_space = {}
        for name, spec in self.param_space.items():
            param_type = spec.get("type", "float")
            default = spec.get("default")
            range_spec = spec.get("range")
            choices = spec.get("choices")
            step = spec.get("step", 1)

            if param_type == "int" and range_spec:
                search_space[name] = list(
                    range(int(range_spec[0]), int(range_spec[1]) + 1, int(step))
                )
            elif param_type == "float" and range_spec:
                values = []
                current = range_spec[0]
                while current <= range_spec[1]:
                    values.append(round(current, 6))
                    current += step
                search_space[name] = values
            elif param_type == "choice" and choices:
                search_space[name] = choices
            elif param_type == "bool":
                search_space[name] = [True, False]
            else:
                search_space[name] = [default]

        if not search_space:
            return [{}]

        # 計算總組合數
        total = 1
        for values in search_space.values():
            total *= len(values)

        # 如果組合數在限制內，使用網格搜索
        if total <= self.config.max_combinations:
            param_names = list(search_space.keys())
            values_lists = [search_space[name] for name in param_names]
            combinations = []
            for combo in itertools.product(*values_lists):
                combinations.append(dict(zip(param_names, combo)))
            return combinations

        # 否則使用隨機採樣
        combinations = []
        for _ in range(self.config.n_random_samples):
            params = {}
            for name, values in search_space.items():
                params[name] = random.choice(values)
            combinations.append(params)

        return combinations

    def optimize_window(
        self,
        window: WFWindow,
        verbose: bool = False,
    ) -> WFWindow:
        """對單一窗口執行參數優化

        Args:
            window: 要優化的窗口
            verbose: 是否顯示進度

        Returns:
            WFWindow: 更新後的窗口
        """
        if verbose:
            print(f"\n  優化窗口 {window.window_id}: {window.train_start} ~ {window.train_end}")

        combinations = self._generate_param_combinations()

        if verbose:
            print(f"  參數組合數: {len(combinations)}")

        best_score = float("-inf") if self.config.maximize else float("inf")
        best_params = {}
        best_metrics = {}

        # 獲取默認參數
        if hasattr(self.strategy_cls, "get_default_parameters"):
            default_params = self.strategy_cls.get_default_parameters()
        else:
            default_params = {}

        for i, params in enumerate(combinations):
            # 合併默認參數和優化參數
            full_params = {**default_params, **params, **self.universal_params}

            # 執行批量回測
            configs = []
            for symbol in self.symbols:
                for tf in self.timeframes:
                    config = RunConfig(
                        strategy=self.strategy_name.lower().replace("strategy", ""),
                        symbol=symbol,
                        timeframe=tf,
                        start=window.train_start,
                        end=window.train_end,
                        initial_cash=self.universal_params.get("initial_cash", 500),
                        fee_rate=self.universal_params.get("fee_rate", 0.0005),
                        strategy_params=full_params,
                    )
                    configs.append(config)

            try:
                result = run_portfolio(configs, verbose=False)
                df = result.to_dataframe()

                if df.empty:
                    continue

                # 計算聚合指標
                metric = self.config.optimize_metric
                if metric in df.columns:
                    score = df[metric].mean()
                elif metric == "sharpe_ratio":
                    # 嘗試從總收益計算
                    if "total_return" in df.columns:
                        returns = df["total_return"]
                        score = returns.mean() / (returns.std() + 1e-8)
                    else:
                        continue
                else:
                    continue

                # 檢查最少交易數
                if "num_trades" in df.columns:
                    if df["num_trades"].sum() < self.config.min_trades:
                        continue

                # 更新最佳
                is_better = score > best_score if self.config.maximize else score < best_score
                if is_better:
                    best_score = score
                    best_params = params
                    best_metrics = {
                        metric: score,
                        "total_return": df["total_return"].mean()
                        if "total_return" in df.columns
                        else 0,
                        "num_trades": df["num_trades"].sum() if "num_trades" in df.columns else 0,
                    }

            except Exception as e:
                if verbose:
                    print(f"    組合 {i} 失敗: {e}")
                continue

            if verbose and (i + 1) % 20 == 0:
                print(f"    進度: {i + 1}/{len(combinations)}, 當前最佳: {best_score:.4f}")

        window.best_params = best_params
        window.train_metrics = best_metrics
        window.is_optimized = True

        if verbose:
            print(f"  最佳參數: {best_params}")
            print(f"  訓練績效: {best_metrics}")

        return window

    def validate_window(
        self,
        window: WFWindow,
        verbose: bool = False,
    ) -> WFWindow:
        """使用最佳參數在測試期驗證

        Args:
            window: 已優化的窗口
            verbose: 是否顯示進度

        Returns:
            WFWindow: 更新後的窗口
        """
        if not window.is_optimized:
            raise ValueError("Window not optimized yet")

        if verbose:
            print(f"  驗證窗口 {window.window_id}: {window.test_start} ~ {window.test_end}")

        # 獲取默認參數
        if hasattr(self.strategy_cls, "get_default_parameters"):
            default_params = self.strategy_cls.get_default_parameters()
        else:
            default_params = {}

        # 使用最佳參數
        full_params = {
            **default_params,
            **window.best_params,
            **self.universal_params,
        }

        # 執行測試期回測
        configs = []
        for symbol in self.symbols:
            for tf in self.timeframes:
                config = RunConfig(
                    strategy=self.strategy_name.lower().replace("strategy", ""),
                    symbol=symbol,
                    timeframe=tf,
                    start=window.test_start,
                    end=window.test_end,
                    initial_cash=self.universal_params.get("initial_cash", 500),
                    fee_rate=self.universal_params.get("fee_rate", 0.0005),
                    strategy_params=full_params,
                )
                configs.append(config)

        try:
            result = run_portfolio(configs, verbose=False)
            df = result.to_dataframe()

            if not df.empty:
                metric = self.config.optimize_metric
                test_metrics = {}

                if metric in df.columns:
                    test_metrics[metric] = df[metric].mean()
                elif metric == "sharpe_ratio" and "total_return" in df.columns:
                    returns = df["total_return"]
                    test_metrics[metric] = returns.mean() / (returns.std() + 1e-8)

                if "total_return" in df.columns:
                    test_metrics["total_return"] = df["total_return"].mean()
                if "num_trades" in df.columns:
                    test_metrics["num_trades"] = df["num_trades"].sum()
                if "win_rate" in df.columns:
                    test_metrics["win_rate"] = df["win_rate"].mean()

                window.test_metrics = test_metrics

        except Exception as e:
            if verbose:
                print(f"  驗證失敗: {e}")
            window.test_metrics = {}

        window.is_validated = True

        if verbose:
            print(f"  測試績效: {window.test_metrics}")

        return window

    def run(self, verbose: bool = True) -> WFResult:
        """執行完整 Walk-Forward 驗證

        Args:
            verbose: 是否顯示進度

        Returns:
            WFResult: 驗證結果
        """
        import time

        if verbose:
            print("=" * 60)
            print("       Walk-Forward 驗證")
            print("=" * 60)
            print(f"策略: {self.strategy_name}")
            print(f"幣種: {len(self.symbols)} 個")
            print(f"期間: {self.start_date} ~ {self.end_date}")
            print(f"參數空間: {len(self.param_space)} 個參數")
            print(f"總組合數: {self.total_combinations:,}")

        windows = self.generate_windows()

        if verbose:
            print(f"窗口數: {len(windows)}")
            print("-" * 60)

        total_train_time = 0
        total_test_time = 0

        for window in windows:
            # 訓練
            t0 = time.time()
            self.optimize_window(window, verbose=verbose)
            total_train_time += time.time() - t0

            # 驗證
            t0 = time.time()
            self.validate_window(window, verbose=verbose)
            total_test_time += time.time() - t0

        result = WFResult(
            windows=windows,
            config=self.config,
            strategy_name=self.strategy_name,
            symbols=self.symbols,
            timeframes=self.timeframes,
            total_train_time=total_train_time,
            total_test_time=total_test_time,
        )

        if verbose:
            print("\n" + result.to_report())

        return result


# ===== 便捷函數 =====


def walk_forward_optimize(
    strategy_name: str,
    symbols: List[str],
    timeframes: List[str],
    start_date: str,
    end_date: str,
    train_months: int = 6,
    test_months: int = 2,
    leverage: int = 10,
    initial_cash: float = 500,
    verbose: bool = True,
) -> WFResult:
    """Walk-Forward 優化的便捷函數

    Args:
        strategy_name: 策略名稱
        symbols: 幣種列表
        timeframes: 時間框架列表
        start_date: 開始日期
        end_date: 結束日期
        train_months: 訓練期月數
        test_months: 測試期月數
        leverage: 槓桿倍數
        initial_cash: 初始資金
        verbose: 是否顯示進度

    Returns:
        WFResult: 驗證結果

    Example:
        >>> result = walk_forward_optimize(
        ...     strategy_name="bigedualma",
        ...     symbols=["BTCUSDT", "ETHUSDT"],
        ...     timeframes=["4h"],
        ...     start_date="2023-01-01",
        ...     end_date="2025-12-01",
        ... )
    """
    from strategies.registry import get_registry

    # 獲取策略類
    registry = get_registry()
    strategy_cls = registry.get_strategy(strategy_name)

    config = WFConfig(
        train_months=train_months,
        test_months=test_months,
    )

    universal_params = {
        "leverage": leverage,
        "initial_cash": initial_cash,
    }

    validator = WalkForwardValidator(
        strategy_cls=strategy_cls,
        symbols=symbols,
        timeframes=timeframes,
        start_date=start_date,
        end_date=end_date,
        config=config,
        universal_params=universal_params,
    )

    return validator.run(verbose=verbose)
