#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperDog Quant v1.0 - Walk-Forward Report Generator

WF 驗證報告生成器 - 生成多種格式的驗證報告

支援格式：
- 純文字報告 (TXT)
- Markdown 報告 (MD)
- JSON 資料 (JSON)

Features:
- 參數穩定性分析
- 行情分類績效
- 可視化圖表建議
- 綜合評分與建議

Usage:
    from cli.report_generator import WFReportGenerator
    from execution.walk_forward import WFResult

    generator = WFReportGenerator(wf_result)
    generator.save_all("output/wf_report")
"""

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from execution.walk_forward import WFResult

# 確保專案根目錄在 path 中
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class ReportSummary:
    """報告摘要"""

    strategy_name: str
    symbols_count: int
    total_windows: int
    train_months: int
    test_months: int
    optimize_metric: str

    # 績效統計
    avg_oos_return: float
    std_oos_return: float
    positive_windows: int
    best_oos_return: float
    worst_oos_return: float

    # 穩健度
    robustness_score: float
    is_oos_decay: float  # IS vs OOS 衰減率
    param_stability_cv: float  # 參數穩定性（平均 CV）

    # 推薦
    recommended: bool
    recommendation_text: str


class WFReportGenerator:
    """Walk-Forward 驗證報告生成器"""

    def __init__(self, wf_result: "WFResult"):
        """初始化報告生成器

        Args:
            wf_result: Walk-Forward 驗證結果
        """
        self.result = wf_result
        self._summary = None

    def get_summary(self) -> ReportSummary:
        """獲取報告摘要"""
        if self._summary is not None:
            return self._summary

        result = self.result
        config = result.config

        # OOS 績效統計
        oos_df = result.get_oos_metrics()
        metric = config.optimize_metric

        if not oos_df.empty and metric in oos_df.columns:
            values = oos_df[metric].dropna()
            avg_oos = values.mean() if len(values) > 0 else 0
            std_oos = values.std() if len(values) > 1 else 0
            positive = (values > 0).sum() if len(values) > 0 else 0
            best = values.max() if len(values) > 0 else 0
            worst = values.min() if len(values) > 0 else 0
        else:
            avg_oos = std_oos = positive = best = worst = 0

        # IS vs OOS 衰減
        is_df = result.get_is_metrics()
        if not is_df.empty and not oos_df.empty:
            if metric in is_df.columns and metric in oos_df.columns:
                is_mean = is_df[metric].mean()
                oos_mean = oos_df[metric].mean()
                if is_mean != 0:
                    decay = (is_mean - oos_mean) / abs(is_mean)
                else:
                    decay = 0
            else:
                decay = 0
        else:
            decay = 0

        # 參數穩定性
        stability = result.get_param_stability()
        if stability:
            cv_values = [s["cv"] for s in stability.values() if s["cv"] != float("inf")]
            avg_cv = sum(cv_values) / len(cv_values) if cv_values else 0
        else:
            avg_cv = 0

        # 穩健度分數
        robustness = result.get_robustness_score()

        # 推薦判定
        if robustness >= 70:
            recommended = True
            rec_text = "推薦使用：策略表現穩健，OOS 績效一致"
        elif robustness >= 50:
            recommended = False
            rec_text = "謹慎使用：策略表現尚可，建議進一步優化"
        else:
            recommended = False
            rec_text = "不建議使用：策略穩健性不足，存在過擬合風險"

        self._summary = ReportSummary(
            strategy_name=result.strategy_name,
            symbols_count=len(result.symbols),
            total_windows=len(result.windows),
            train_months=config.train_months,
            test_months=config.test_months,
            optimize_metric=metric,
            avg_oos_return=avg_oos,
            std_oos_return=std_oos,
            positive_windows=int(positive),
            best_oos_return=best,
            worst_oos_return=worst,
            robustness_score=robustness,
            is_oos_decay=decay,
            param_stability_cv=avg_cv,
            recommended=recommended,
            recommendation_text=rec_text,
        )

        return self._summary

    def to_json(self) -> Dict[str, Any]:
        """生成 JSON 格式報告

        Returns:
            Dict: 完整報告資料
        """
        result = self.result
        config = result.config
        summary = self.get_summary()

        # 窗口詳情
        windows_data = []
        for w in result.windows:
            window_data = {
                "window_id": w.window_id,
                "train_period": f"{w.train_start} ~ {w.train_end}",
                "test_period": f"{w.test_start} ~ {w.test_end}",
                "best_params": w.best_params,
                "train_metrics": w.train_metrics,
                "test_metrics": w.test_metrics,
            }
            windows_data.append(window_data)

        # 參數穩定性
        stability_data = {}
        stability = result.get_param_stability()
        for name, stats in stability.items():
            stability_data[name] = {
                "mean": stats["mean"],
                "std": stats["std"],
                "cv": stats["cv"] if stats["cv"] != float("inf") else None,
                "values": stats["values"],
            }

        # 穩健參數
        robust_params = result.get_robust_params()

        return {
            "meta": {
                "version": "1.0",
                "generated_at": datetime.now().isoformat(),
                "strategy": result.strategy_name,
            },
            "config": {
                "train_months": config.train_months,
                "test_months": config.test_months,
                "step_months": config.step_months,
                "optimize_metric": config.optimize_metric,
                "maximize": config.maximize,
                "max_combinations": config.max_combinations,
            },
            "summary": {
                "symbols_count": summary.symbols_count,
                "total_windows": summary.total_windows,
                "avg_oos_return": summary.avg_oos_return,
                "std_oos_return": summary.std_oos_return,
                "positive_windows": summary.positive_windows,
                "best_oos_return": summary.best_oos_return,
                "worst_oos_return": summary.worst_oos_return,
                "robustness_score": summary.robustness_score,
                "is_oos_decay": summary.is_oos_decay,
                "param_stability_cv": summary.param_stability_cv,
                "recommended": summary.recommended,
                "recommendation": summary.recommendation_text,
            },
            "windows": windows_data,
            "param_stability": stability_data,
            "robust_params": robust_params,
            "execution": {
                "total_train_time": result.total_train_time,
                "total_test_time": result.total_test_time,
                "symbols": result.symbols,
                "timeframes": result.timeframes,
            },
        }

    def to_markdown(self) -> str:
        """生成 Markdown 格式報告

        Returns:
            str: Markdown 文字
        """
        result = self.result
        config = result.config
        summary = self.get_summary()

        lines = []

        # 標題
        lines.append(f"# Walk-Forward 驗證報告")
        lines.append("")
        lines.append(f"**策略**: {result.strategy_name}")
        lines.append(f"**生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 配置摘要
        lines.append("## 驗證配置")
        lines.append("")
        lines.append(f"| 項目 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 幣種數量 | {summary.symbols_count} |")
        lines.append(f"| 訓練期 | {summary.train_months} 個月 |")
        lines.append(f"| 測試期 | {summary.test_months} 個月 |")
        lines.append(f"| 滾動步長 | {config.step_months} 個月 |")
        lines.append(f"| 優化指標 | {summary.optimize_metric} |")
        lines.append(f"| 窗口數量 | {summary.total_windows} |")
        lines.append("")

        # 績效摘要
        lines.append("## 績效摘要")
        lines.append("")

        # 評分表
        score = summary.robustness_score
        if score >= 70:
            score_emoji = "A"
            color = "green"
        elif score >= 50:
            score_emoji = "B"
            color = "yellow"
        else:
            score_emoji = "C"
            color = "red"

        lines.append(f"### 穩健度評分: {score:.0f}/100 ({score_emoji})")
        lines.append("")
        lines.append(f"> {summary.recommendation_text}")
        lines.append("")

        # OOS 績效
        lines.append("### Out-of-Sample 績效")
        lines.append("")
        lines.append(f"| 指標 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 平均 OOS {config.optimize_metric} | {summary.avg_oos_return:.4f} |")
        lines.append(f"| 標準差 | {summary.std_oos_return:.4f} |")
        lines.append(f"| 最佳 | {summary.best_oos_return:.4f} |")
        lines.append(f"| 最差 | {summary.worst_oos_return:.4f} |")
        lines.append(f"| 正收益窗口 | {summary.positive_windows}/{summary.total_windows} |")
        lines.append(f"| IS→OOS 衰減 | {summary.is_oos_decay:.1%} |")
        lines.append("")

        # 滾動窗口結果
        lines.append("## 滾動窗口詳情")
        lines.append("")

        metric = config.optimize_metric
        lines.append(f"| 窗口 | 訓練期 | 測試期 | IS {metric} | OOS {metric} |")
        lines.append(f"|------|--------|--------|------------|-------------|")

        for w in result.windows:
            is_val = w.train_metrics.get(metric, 0)
            oos_val = w.test_metrics.get(metric, 0)

            # 格式化
            if metric in ("total_return", "max_drawdown"):
                is_str = f"{is_val:+.2%}"
                oos_str = f"{oos_val:+.2%}"
            else:
                is_str = f"{is_val:.3f}"
                oos_str = f"{oos_val:.3f}"

            lines.append(
                f"| {w.window_id} | {w.train_start}~{w.train_end} | "
                f"{w.test_start}~{w.test_end} | {is_str} | {oos_str} |"
            )

        lines.append("")

        # 參數穩定性
        stability = result.get_param_stability()
        if stability:
            lines.append("## 參數穩定性分析")
            lines.append("")
            lines.append(f"| 參數 | 平均值 | 標準差 | CV (變異係數) | 評估 |")
            lines.append(f"|------|--------|--------|---------------|------|")

            for name, stats in stability.items():
                cv = stats["cv"]
                if cv == float("inf"):
                    cv_str = "N/A"
                    assess = "-"
                elif cv < 0.2:
                    cv_str = f"{cv:.3f}"
                    assess = "穩定"
                elif cv < 0.5:
                    cv_str = f"{cv:.3f}"
                    assess = "尚可"
                else:
                    cv_str = f"{cv:.3f}"
                    assess = "不穩定"

                lines.append(
                    f"| {name} | {stats['mean']:.3f} | {stats['std']:.3f} | {cv_str} | {assess} |"
                )

            lines.append("")

        # 穩健參數推薦
        robust_params = result.get_robust_params()
        if robust_params:
            lines.append("## 穩健參數推薦")
            lines.append("")
            lines.append("基於各窗口表現，推薦使用以下參數組合：")
            lines.append("")
            lines.append("```python")
            lines.append("params = {")
            for name, value in robust_params.items():
                if isinstance(value, str):
                    lines.append(f'    "{name}": "{value}",')
                else:
                    lines.append(f'    "{name}": {value},')
            lines.append("}")
            lines.append("```")
            lines.append("")

        # 執行資訊
        lines.append("## 執行資訊")
        lines.append("")
        lines.append(f"- 總訓練時間: {result.total_train_time:.1f} 秒")
        lines.append(f"- 總測試時間: {result.total_test_time:.1f} 秒")
        lines.append(
            f"- 幣種列表: {', '.join(result.symbols[:5])}{'...' if len(result.symbols) > 5 else ''}"
        )
        lines.append(f"- 時間框架: {', '.join(result.timeframes)}")
        lines.append("")

        # 頁腳
        lines.append("---")
        lines.append("*Generated by SuperDog Quant v1.0*")

        return "\n".join(lines)

    def to_text(self) -> str:
        """生成純文字報告（使用 WFResult 的內建方法）

        Returns:
            str: 純文字報告
        """
        return self.result.to_report()

    def save_json(self, filepath: str):
        """儲存 JSON 報告

        Args:
            filepath: 檔案路徑
        """
        data = self.to_json()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"JSON 報告已儲存: {filepath}")

    def save_markdown(self, filepath: str):
        """儲存 Markdown 報告

        Args:
            filepath: 檔案路徑
        """
        content = self.to_markdown()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Markdown 報告已儲存: {filepath}")

    def save_text(self, filepath: str):
        """儲存純文字報告

        Args:
            filepath: 檔案路徑
        """
        content = self.to_text()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"純文字報告已儲存: {filepath}")

    def save_all(self, base_path: str):
        """儲存所有格式的報告

        Args:
            base_path: 基礎路徑（不含副檔名）
        """
        # 確保目錄存在
        base = Path(base_path)
        base.parent.mkdir(parents=True, exist_ok=True)

        # 儲存各格式
        self.save_json(f"{base_path}.json")
        self.save_markdown(f"{base_path}.md")
        self.save_text(f"{base_path}.txt")

        print(f"\n所有報告已儲存至: {base.parent}")


def generate_wf_report(wf_result: "WFResult", output_dir: str = "reports") -> str:
    """生成 WF 驗證報告的便捷函數

    Args:
        wf_result: Walk-Forward 驗證結果
        output_dir: 輸出目錄

    Returns:
        str: 報告基礎路徑
    """
    # 生成報告名稱
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    strategy = wf_result.strategy_name.lower()
    base_name = f"wf_{strategy}_{timestamp}"

    # 輸出路徑
    output_path = Path(output_dir) / base_name

    # 生成報告
    generator = WFReportGenerator(wf_result)
    generator.save_all(str(output_path))

    return str(output_path)


# CLI 介面
def main():
    """主程式入口"""
    print("WF Report Generator - 示範模式")
    print()
    print("此模組用於生成 Walk-Forward 驗證報告。")
    print()
    print("使用方式：")
    print("  from cli.report_generator import WFReportGenerator, generate_wf_report")
    print("  from execution.walk_forward import walk_forward_optimize")
    print()
    print("  # 執行 WF 驗證")
    print("  result = walk_forward_optimize(...)")
    print()
    print("  # 生成報告")
    print("  generator = WFReportGenerator(result)")
    print("  generator.save_all('output/my_report')")
    print()
    print("  # 或使用便捷函數")
    print("  generate_wf_report(result, 'reports')")


if __name__ == "__main__":
    main()
