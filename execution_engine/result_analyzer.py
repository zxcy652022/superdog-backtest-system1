"""
Result Analyzer v0.6

結果分析器 - 可視化、報告生成、性能排名

核心功能:
- 結果統計分析
- 參數相關性分析
- 性能排名和篩選
- 可視化圖表（績效分布、參數影響等）
- 報告生成（Markdown/HTML）

Version: v0.6 Phase 2
Design Reference: docs/specs/v0.6/superdog_v06_strategy_lab_spec.md
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime

from .experiments import ExperimentResult, ExperimentRun, ExperimentStatus


@dataclass
class AnalysisReport:
    """分析報告"""
    experiment_id: str
    experiment_name: str

    # 統計摘要
    total_runs: int
    completed_runs: int
    failed_runs: int

    # 最佳結果
    best_run: Optional[ExperimentRun]
    best_parameters: Optional[Dict[str, Any]]

    # Top N 結果
    top_runs: List[ExperimentRun]

    # 統計指標
    statistics: Dict[str, Any]

    # 參數分析
    parameter_importance: Dict[str, float]
    parameter_correlations: Dict[str, float]

    # 生成時間
    generated_at: str

    def to_dict(self) -> Dict:
        """轉換為字典"""
        return {
            'experiment_id': self.experiment_id,
            'experiment_name': self.experiment_name,
            'total_runs': self.total_runs,
            'completed_runs': self.completed_runs,
            'failed_runs': self.failed_runs,
            'best_run': self.best_run.to_dict() if self.best_run else None,
            'best_parameters': self.best_parameters,
            'top_runs': [r.to_dict() for r in self.top_runs],
            'statistics': self.statistics,
            'parameter_importance': self.parameter_importance,
            'parameter_correlations': self.parameter_correlations,
            'generated_at': self.generated_at
        }


class ResultAnalyzer:
    """結果分析器

    提供實驗結果的深度分析功能

    Example:
        >>> analyzer = ResultAnalyzer(experiment_result)
        >>> report = analyzer.generate_report()
        >>> analyzer.save_report(report, "output/analysis.md")
    """

    def __init__(self, result: ExperimentResult):
        """初始化

        Args:
            result: 實驗結果
        """
        self.result = result
        self.df = self._create_dataframe()

    def _create_dataframe(self) -> pd.DataFrame:
        """將結果轉換為 DataFrame

        Returns:
            pd.DataFrame: 結果數據框
        """
        data = []

        for run in self.result.runs:
            if run.status == ExperimentStatus.COMPLETED:
                row = {
                    'run_id': run.run_id,
                    'symbol': run.symbol,
                    'status': run.status.value,
                    'total_return': run.total_return,
                    'max_drawdown': run.max_drawdown,
                    'sharpe_ratio': run.sharpe_ratio,
                    'num_trades': run.num_trades,
                    'win_rate': run.win_rate,
                    'profit_factor': run.profit_factor,
                }

                # 添加參數
                for k, v in run.parameters.items():
                    row[f'param_{k}'] = v

                # 添加額外指標
                for k, v in run.metrics.items():
                    row[f'metric_{k}'] = v

                data.append(row)

        return pd.DataFrame(data)

    def generate_report(
        self,
        top_n: int = 10,
        metric: str = "sharpe_ratio"
    ) -> AnalysisReport:
        """生成分析報告

        Args:
            top_n: Top N 結果數量
            metric: 排名指標

        Returns:
            AnalysisReport: 分析報告
        """
        print(f"📊 生成分析報告...")

        # 獲取最佳結果
        best_run = self.result.get_best_run(metric=metric, ascending=False)
        best_params = best_run.parameters if best_run else None

        # 獲取 Top N
        top_runs = self.get_top_runs(top_n=top_n, metric=metric)

        # 統計分析
        statistics = self.result.get_statistics()

        # 參數重要性
        param_importance = self.analyze_parameter_importance(metric=metric)

        # 參數相關性
        param_correlations = self.analyze_parameter_correlations(metric=metric)

        report = AnalysisReport(
            experiment_id=self.result.experiment_id,
            experiment_name=self.result.config.name,
            total_runs=self.result.total_runs,
            completed_runs=self.result.completed_runs,
            failed_runs=self.result.failed_runs,
            best_run=best_run,
            best_parameters=best_params,
            top_runs=top_runs,
            statistics=statistics,
            parameter_importance=param_importance,
            parameter_correlations=param_correlations,
            generated_at=datetime.now().isoformat()
        )

        print(f"✅ 報告生成完成")
        return report

    def get_top_runs(
        self,
        top_n: int = 10,
        metric: str = "sharpe_ratio",
        ascending: bool = False
    ) -> List[ExperimentRun]:
        """獲取 Top N 結果

        Args:
            top_n: 返回數量
            metric: 排名指標
            ascending: 是否升序

        Returns:
            List[ExperimentRun]: Top N 運行記錄
        """
        completed = [r for r in self.result.runs if r.status == ExperimentStatus.COMPLETED]

        # 按指標排序
        sorted_runs = sorted(
            completed,
            key=lambda r: getattr(r, metric, None) or r.metrics.get(metric, float('-inf')),
            reverse=not ascending
        )

        return sorted_runs[:top_n]

    def analyze_parameter_importance(
        self,
        metric: str = "sharpe_ratio"
    ) -> Dict[str, float]:
        """分析參數重要性

        使用方差分析評估每個參數的影響

        Args:
            metric: 分析指標

        Returns:
            Dict[str, float]: 參數重要性分數
        """
        if self.df.empty:
            return {}

        # 獲取參數列
        param_cols = [c for c in self.df.columns if c.startswith('param_')]

        importance = {}
        total_variance = self.df[metric].var()

        if total_variance == 0:
            return {col.replace('param_', ''): 0.0 for col in param_cols}

        for col in param_cols:
            # 計算分組內方差
            try:
                grouped_var = self.df.groupby(col)[metric].var().mean()
                # 方差比例（越大說明該參數影響越大）
                importance[col.replace('param_', '')] = 1 - (grouped_var / total_variance)
            except:
                importance[col.replace('param_', '')] = 0.0

        # 歸一化
        total = sum(importance.values())
        if total > 0:
            importance = {k: v/total for k, v in importance.items()}

        return importance

    def analyze_parameter_correlations(
        self,
        metric: str = "sharpe_ratio"
    ) -> Dict[str, float]:
        """分析參數與結果的相關性

        Args:
            metric: 分析指標

        Returns:
            Dict[str, float]: 參數相關系數
        """
        if self.df.empty:
            return {}

        param_cols = [c for c in self.df.columns if c.startswith('param_')]

        correlations = {}
        for col in param_cols:
            try:
                # 計算 Pearson 相關係數
                corr = self.df[col].corr(self.df[metric])
                correlations[col.replace('param_', '')] = corr if not np.isnan(corr) else 0.0
            except:
                correlations[col.replace('param_', '')] = 0.0

        return correlations

    def get_metric_distribution(
        self,
        metric: str = "sharpe_ratio",
        bins: int = 20
    ) -> Tuple[np.ndarray, np.ndarray]:
        """獲取指標分布

        Args:
            metric: 指標名稱
            bins: 分箱數量

        Returns:
            Tuple[np.ndarray, np.ndarray]: (counts, bin_edges)
        """
        if self.df.empty:
            return np.array([]), np.array([])

        values = self.df[metric].dropna()
        return np.histogram(values, bins=bins)

    def get_parameter_impact(
        self,
        parameter: str,
        metric: str = "sharpe_ratio"
    ) -> pd.DataFrame:
        """獲取單個參數的影響分析

        Args:
            parameter: 參數名稱
            metric: 分析指標

        Returns:
            pd.DataFrame: 參數值與指標的關係
        """
        if self.df.empty:
            return pd.DataFrame()

        param_col = f'param_{parameter}'
        if param_col not in self.df.columns:
            return pd.DataFrame()

        # 分組統計
        grouped = self.df.groupby(param_col)[metric].agg(['mean', 'std', 'count'])
        grouped = grouped.reset_index()
        grouped.columns = ['parameter_value', 'mean', 'std', 'count']

        return grouped

    def save_report(
        self,
        report: AnalysisReport,
        output_path: str,
        format: str = "markdown"
    ):
        """保存報告

        Args:
            report: 分析報告
            output_path: 輸出路徑
            format: 格式（markdown/json/html）
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        elif format == "markdown":
            md_content = self._generate_markdown(report)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(md_content)

        elif format == "html":
            html_content = self._generate_html(report)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)

        else:
            raise ValueError(f"不支援的格式: {format}")

        print(f"💾 報告已保存: {output_file}")

    def _generate_markdown(self, report: AnalysisReport) -> str:
        """生成 Markdown 報告

        Args:
            report: 分析報告

        Returns:
            str: Markdown 內容
        """
        lines = [
            f"# 實驗分析報告: {report.experiment_name}",
            "",
            f"**實驗ID:** `{report.experiment_id}`  ",
            f"**生成時間:** {report.generated_at}  ",
            "",
            "---",
            "",
            "## 📊 執行摘要",
            "",
            f"- **總運行數:** {report.total_runs}",
            f"- **成功運行:** {report.completed_runs}",
            f"- **失敗運行:** {report.failed_runs}",
            f"- **成功率:** {report.completed_runs/report.total_runs*100:.1f}%",
            "",
            "## 🏆 最佳結果",
            ""
        ]

        if report.best_run:
            lines.extend([
                f"- **Symbol:** {report.best_run.symbol}",
                f"- **Total Return:** {report.best_run.total_return:.2%}" if report.best_run.total_return else "",
                f"- **Sharpe Ratio:** {report.best_run.sharpe_ratio:.2f}" if report.best_run.sharpe_ratio else "",
                f"- **Max Drawdown:** {report.best_run.max_drawdown:.2%}" if report.best_run.max_drawdown else "",
                f"- **Win Rate:** {report.best_run.win_rate:.2%}" if report.best_run.win_rate else "",
                "",
                "### 最佳參數",
                "",
                "```json",
                json.dumps(report.best_parameters, indent=2, ensure_ascii=False),
                "```",
                ""
            ])

        # 統計指標
        lines.extend([
            "## 📈 統計指標",
            "",
            "| 指標 | 值 |",
            "|------|-----|"
        ])

        for key, value in report.statistics.items():
            if isinstance(value, float):
                lines.append(f"| {key} | {value:.4f} |")
            else:
                lines.append(f"| {key} | {value} |")

        lines.append("")

        # Top 10
        lines.extend([
            f"## 🔝 Top {len(report.top_runs)} 結果",
            "",
            "| Rank | Symbol | Total Return | Sharpe | Max DD | Win Rate |",
            "|------|--------|-------------|--------|--------|----------|"
        ])

        for i, run in enumerate(report.top_runs, 1):
            lines.append(
                f"| {i} | {run.symbol} | "
                f"{run.total_return:.2%} | "
                f"{run.sharpe_ratio:.2f} | "
                f"{run.max_drawdown:.2%} | "
                f"{run.win_rate:.2%} |"
            )

        lines.append("")

        # 參數重要性
        if report.parameter_importance:
            lines.extend([
                "## 🎯 參數重要性",
                "",
                "| 參數 | 重要性 |",
                "|------|--------|"
            ])

            sorted_params = sorted(
                report.parameter_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )

            for param, importance in sorted_params:
                lines.append(f"| {param} | {importance:.2%} |")

            lines.append("")

        # 參數相關性
        if report.parameter_correlations:
            lines.extend([
                "## 🔗 參數相關性",
                "",
                "| 參數 | 相關係數 |",
                "|------|----------|"
            ])

            for param, corr in report.parameter_correlations.items():
                lines.append(f"| {param} | {corr:.4f} |")

            lines.append("")

        lines.extend([
            "---",
            "",
            f"*報告由 SuperDog v0.6 Strategy Lab 生成*"
        ])

        return '\n'.join(lines)

    def _generate_html(self, report: AnalysisReport) -> str:
        """生成 HTML 報告

        Args:
            report: 分析報告

        Returns:
            str: HTML 內容
        """
        # 簡化版 HTML 模板
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>實驗分析報告: {report.experiment_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>實驗分析報告: {report.experiment_name}</h1>
    <div class="summary">
        <p><strong>實驗ID:</strong> {report.experiment_id}</p>
        <p><strong>生成時間:</strong> {report.generated_at}</p>
    </div>

    <h2>執行摘要</h2>
    <ul>
        <li>總運行數: {report.total_runs}</li>
        <li>成功運行: {report.completed_runs}</li>
        <li>失敗運行: {report.failed_runs}</li>
        <li>成功率: {report.completed_runs/report.total_runs*100:.1f}%</li>
    </ul>

    <h2>最佳結果</h2>
    {self._format_best_run_html(report.best_run, report.best_parameters)}

    <h2>Top {len(report.top_runs)} 結果</h2>
    {self._format_top_runs_html(report.top_runs)}

    <footer>
        <p><em>報告由 SuperDog v0.6 Strategy Lab 生成</em></p>
    </footer>
</body>
</html>
"""
        return html

    def _format_best_run_html(self, run: Optional[ExperimentRun], params: Optional[Dict]) -> str:
        """格式化最佳運行為 HTML"""
        if not run:
            return "<p>無可用結果</p>"

        return f"""
        <ul>
            <li>Symbol: {run.symbol}</li>
            <li>Total Return: {run.total_return:.2%}</li>
            <li>Sharpe Ratio: {run.sharpe_ratio:.2f}</li>
            <li>Max Drawdown: {run.max_drawdown:.2%}</li>
        </ul>
        <h3>最佳參數</h3>
        <pre>{json.dumps(params, indent=2, ensure_ascii=False)}</pre>
        """

    def _format_top_runs_html(self, runs: List[ExperimentRun]) -> str:
        """格式化 Top 運行為 HTML 表格"""
        rows = []
        for i, run in enumerate(runs, 1):
            rows.append(f"""
            <tr>
                <td>{i}</td>
                <td>{run.symbol}</td>
                <td>{run.total_return:.2%}</td>
                <td>{run.sharpe_ratio:.2f}</td>
                <td>{run.max_drawdown:.2%}</td>
                <td>{run.win_rate:.2%}</td>
            </tr>
            """)

        return f"""
        <table>
            <tr>
                <th>Rank</th>
                <th>Symbol</th>
                <th>Total Return</th>
                <th>Sharpe</th>
                <th>Max DD</th>
                <th>Win Rate</th>
            </tr>
            {''.join(rows)}
        </table>
        """


# ===== 便捷函數 =====

def analyze_result(
    result: ExperimentResult,
    output_path: Optional[str] = None,
    format: str = "markdown"
) -> AnalysisReport:
    """分析實驗結果的便捷函數

    Args:
        result: 實驗結果
        output_path: 輸出路徑（可選）
        format: 輸出格式

    Returns:
        AnalysisReport: 分析報告

    Example:
        >>> report = analyze_result(my_result, "output/report.md")
    """
    analyzer = ResultAnalyzer(result)
    report = analyzer.generate_report()

    if output_path:
        analyzer.save_report(report, output_path, format=format)

    return report
