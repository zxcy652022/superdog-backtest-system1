"""
Text Reporter v0.3

Generate plain-text reports for single backtests and portfolio runs.

v0.3 新增：
- 單策略詳細報表 render_single()
- 多策略排行表 render_portfolio()
- ASCII 表格渲染（box-drawing characters）

Design Reference: docs/specs/planned/v0.3_text_reporter_spec.md
"""

from typing import List, Optional

import numpy as np
import pandas as pd

from backtest.engine import BacktestResult
from execution_engine.portfolio_runner import PortfolioResult, RunConfig


def render_single(
    result: BacktestResult, config: Optional[RunConfig] = None, show_recent_trades: int = 5
) -> str:
    """
    生成單策略詳細報表

    Args:
        result: 回測結果
        config: 回測配置（可選，用於顯示配置信息）
        show_recent_trades: 顯示最近 N 筆交易（默認 5）

    Returns:
        str: 格式化的報表文本
    """
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(" " * 24 + "BACKTEST REPORT")
    lines.append("=" * 80)
    lines.append("")

    metrics = result.metrics
    equity_curve = result.equity_curve

    # === CONFIGURATION ===
    lines.append("CONFIGURATION")
    if config:
        lines.append(f"  Strategy          : {config.strategy}")
        lines.append(f"  Symbol            : {config.symbol}")
        lines.append(f"  Timeframe         : {config.timeframe}")
        period = _format_period(equity_curve)
        if period:
            lines.append(f"  Period            : {period}")
        lines.append(f"  Initial Cash      : {config.initial_cash:,.2f} USDT")
        lines.append(f"  Fee Rate          : {config.fee_rate * 100:.2f}%")
        if config.stop_loss_pct is not None:
            lines.append(f"  Stop Loss         : {config.stop_loss_pct * 100:.2f}%")
        if config.take_profit_pct is not None:
            lines.append(f"  Take Profit       : {config.take_profit_pct * 100:.2f}%")
    lines.append("")

    # === PERFORMANCE SUMMARY ===
    lines.append("PERFORMANCE SUMMARY")
    if len(equity_curve) > 0:
        lines.append(f"  Starting Equity   : {equity_curve.iloc[0]:,.2f} USDT")
    if len(equity_curve) > 0:
        lines.append(f"  Final Equity      : {equity_curve.iloc[-1]:,.2f} USDT")
    else:
        lines.append("  Final Equity      : N/A")
    lines.append(f"  Total Return      : {_fmt_pct(metrics.get('total_return'))}")
    lines.append(f"  Max Drawdown      : {_fmt_pct(metrics.get('max_drawdown'))}")
    lines.append("")

    # === TRADE STATISTICS ===
    lines.append("TRADE STATISTICS")
    num_trades = int(metrics.get("num_trades", 0))
    win_rate = metrics.get("win_rate", 0.0)
    win_trades = int(round(num_trades * win_rate))
    lose_trades = num_trades - win_trades

    lines.append(f"  Total Trades      : {num_trades}")
    lines.append(f"  Winning Trades    : {win_trades} ({win_rate:.2%})")
    lines.append(f"  Losing Trades     : {lose_trades} ({(1 - win_rate):.2%})")
    lines.append(f"  Avg Win           : {_fmt_currency(metrics.get('avg_win'))}")
    lines.append(f"  Avg Loss          : {_fmt_currency(metrics.get('avg_loss'))}")
    lines.append(f"  Win/Loss Ratio    : {_fmt_number(metrics.get('win_loss_ratio'))}")
    lines.append("")

    # === RISK METRICS ===
    lines.append("RISK METRICS")
    lines.append(f"  Profit Factor     : {_fmt_profit_factor(metrics.get('profit_factor'))}")
    lines.append(f"  Expectancy        : {_fmt_currency(metrics.get('expectancy'))}")
    lines.append(f"  Max Consecutive W : {int(metrics.get('max_consecutive_win', 0))}")
    lines.append(f"  Max Consecutive L : {int(metrics.get('max_consecutive_loss', 0))}")
    lines.append("")

    # === RECENT TRADES ===
    if result.trade_log is not None and len(result.trade_log) > 0:
        lines.append(f"RECENT TRADES (Last {show_recent_trades})")
        trade_log = result.trade_log.tail(show_recent_trades)
        total_trades = len(result.trade_log)

        for idx, (_, row) in enumerate(trade_log.iterrows(), 1):
            entry_time = (
                row["entry_time"].strftime("%Y-%m-%d") if pd.notna(row["entry_time"]) else "N/A"
            )
            exit_time = (
                row["exit_time"].strftime("%Y-%m-%d") if pd.notna(row["exit_time"]) else "N/A"
            )
            entry_price = row.get("entry_price", 0)
            exit_price = row.get("exit_price", 0)
            pnl_pct = row.get("pnl_pct", 0)
            exit_reason = _format_exit_reason(str(row.get("exit_reason", "")))

            trade_index = total_trades - len(trade_log) + idx
            line = (
                f"  #{trade_index:>3}  "
                f"{entry_time} → {exit_time}  |  "
                f"Entry: {entry_price:>7,.0f}  Exit: {exit_price:>7,.0f}  |  "
                f"{pnl_pct:+.2%}  |  {exit_reason}"
            )
            lines.append(line)
        lines.append("")

    # === ASSESSMENT ===
    assessment = _generate_assessment(metrics)
    lines.append("ASSESSMENT")
    for line in assessment:
        lines.append(f"  {line}")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def render_portfolio(
    portfolio_result: PortfolioResult,
    sort_by: str = "total_return",
    show_failed: bool = True,
    top_n: Optional[int] = None,
) -> str:
    """
    生成多策略對比排行表

    Args:
        portfolio_result: Portfolio 結果對象
        sort_by: 排序字段（默認 total_return）
        show_failed: 是否顯示失敗的回測
        top_n: 只顯示前 N 個（None 表示全部）

    Returns:
        str: 格式化的排行表文本
    """
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(" " * 21 + "PORTFOLIO BACKTEST REPORT")
    lines.append("=" * 80)
    lines.append("")

    total = len(portfolio_result.runs)
    success = portfolio_result.count_successful()
    failed = portfolio_result.count_failed()
    lines.append(
        f"Summary: {total} runs completed "
        f"({success} successful, {failed} failed) in {portfolio_result.total_time:.2f}s"
    )
    lines.append("")

    df = portfolio_result.to_dataframe(include_failed=show_failed)
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False, na_position="last")

    if top_n:
        df = df.head(top_n)

    lines.append(f"RANKING TABLE (Sorted by {sort_by.replace('_', ' ').title()})")
    lines.append(_render_table(df))
    lines.append("")

    if show_failed and failed > 0:
        lines.append("FAILED RUNS")
        for i, run in enumerate(portfolio_result.get_failed_runs(), 1):
            lines.append(f"  [{i}] {run.strategy} @ {run.symbol} ({run.timeframe}): {run.error}")
        lines.append("")

    if success > 0:
        lines.append("TOP PERFORMERS")
        best_return = portfolio_result.get_best_by("total_return", top_n=1)
        if best_return:
            r = best_return[0]
            lines.append(
                f"  Best Return:  {r.strategy} @ {r.symbol} ({r.timeframe}) "
                f"→ {r.get_metric('total_return', 0):+.2%}"
            )

        best_pf = portfolio_result.get_best_by("profit_factor", top_n=1)
        if best_pf:
            r = best_pf[0]
            lines.append(
                f"  Best PF:      {r.strategy} @ {r.symbol} ({r.timeframe}) "
                f"→ {_fmt_profit_factor(r.get_metric('profit_factor'))}"
            )

        lowest_dd = portfolio_result.get_worst_by("max_drawdown", bottom_n=1)
        if lowest_dd:
            r = lowest_dd[0]
            lines.append(
                f"  Lowest DD:    {r.strategy} @ {r.symbol} ({r.timeframe}) "
                f"→ {_fmt_pct(r.get_metric('max_drawdown', 0))}"
            )
        lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)


def _format_exit_reason(reason: str) -> str:
    """格式化退出原因"""
    mapping = {"stop_loss": "SL", "take_profit": "TP", "strategy_signal": "Signal"}
    return mapping.get(reason, reason)


def _generate_assessment(metrics: dict) -> list:
    """
    生成簡短評估

    Returns:
        List of assessment lines
    """
    lines: List[str] = []

    wl_ratio = metrics.get("win_loss_ratio", 0) or 0
    max_dd = abs(metrics.get("max_drawdown", 0) or 0)

    if wl_ratio > 1.5 and max_dd < 0.1:
        rr = "Good (W/L Ratio > 1.5, Max DD < 10%)"
    elif wl_ratio > 1.0 and max_dd < 0.15:
        rr = "Fair (W/L Ratio > 1.0, Max DD < 15%)"
    else:
        rr = "Poor (Low W/L Ratio or High DD)"
    lines.append(f"Risk-Reward: {rr}")

    num_trades = metrics.get("num_trades", 0) or 0
    if num_trades > 50:
        freq = f"High ({num_trades} trades)"
    elif num_trades > 20:
        freq = f"Moderate ({num_trades} trades)"
    else:
        freq = f"Low ({num_trades} trades)"
    lines.append(f"Trade Frequency: {freq}")

    win_rate = metrics.get("win_rate", 0.0) or 0.0
    if win_rate > 0.6:
        cons = f"Good ({win_rate:.2%} win rate)"
    elif win_rate > 0.5:
        cons = f"Fair ({win_rate:.2%} win rate)"
    else:
        cons = f"Poor ({win_rate:.2%} win rate)"
    lines.append(f"Consistency: {cons}")

    return lines


def _render_table(df: pd.DataFrame) -> str:
    """
    渲染 ASCII 表格

    使用 box-drawing characters: ┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ │ ─
    """
    col_widths = {
        "#": 4,
        "strategy": 18,
        "symbol": 9,
        "timeframe": 4,
        "total_return": 14,
        "max_drawdown": 10,
        "profit_factor": 6,
        "num_trades": 8,
        "win_rate": 9,
        "status": 8,
    }

    header = "┌" + "┬".join("─" * col_widths[col] for col in col_widths.keys()) + "┐"
    col_names = (
        "│ "
        + " │ ".join(
            [
                "#".ljust(col_widths["#"]),
                "Strategy".ljust(col_widths["strategy"]),
                "Symbol".ljust(col_widths["symbol"]),
                "TF".ljust(col_widths["timeframe"]),
                "Total Return".rjust(col_widths["total_return"]),
                "Max DD".rjust(col_widths["max_drawdown"]),
                "PF".rjust(col_widths["profit_factor"]),
                "Trades".rjust(col_widths["num_trades"]),
                "Win%".rjust(col_widths["win_rate"]),
                "Status".rjust(col_widths["status"]),
            ]
        )
        + " │"
    )
    separator = "├" + "┼".join("─" * col_widths[col] for col in col_widths.keys()) + "┤"

    rows: List[str] = []
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        status = row.get("status", "")
        if status == "✓":
            total_return = _fmt_pct(row.get("total_return"))
            max_dd = _fmt_pct(row.get("max_drawdown"))
            pf = _fmt_profit_factor(row.get("profit_factor"))
            trades = _fmt_int(row.get("num_trades"))
            win_rate = _fmt_pct(row.get("win_rate"))
        else:
            total_return = "N/A"
            max_dd = "N/A"
            pf = "N/A"
            trades = "N/A"
            win_rate = "N/A"

        row_str = (
            "│ "
            + " │ ".join(
                [
                    str(idx).ljust(col_widths["#"]),
                    str(row.get("strategy", ""))[:16].ljust(col_widths["strategy"]),
                    str(row.get("symbol", ""))[:7].ljust(col_widths["symbol"]),
                    str(row.get("timeframe", "")).ljust(col_widths["timeframe"]),
                    total_return.rjust(col_widths["total_return"]),
                    max_dd.rjust(col_widths["max_drawdown"]),
                    pf.rjust(col_widths["profit_factor"]),
                    str(trades).rjust(col_widths["num_trades"]),
                    win_rate.rjust(col_widths["win_rate"]),
                    str(status).rjust(col_widths["status"]),
                ]
            )
            + " │"
        )
        rows.append(row_str)

    footer = "└" + "┴".join("─" * col_widths[col] for col in col_widths.keys()) + "┘"
    table = [header, col_names, separator] + rows + [footer]
    return "\n".join(table)


def _fmt_pct(value) -> str:
    """格式化百分比"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    return f"{value:+.2%}"


def _fmt_currency(value) -> str:
    """格式化貨幣"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    return f"{value:,.2f} USDT"


def _fmt_number(value) -> str:
    """格式化數字"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    if value == float("inf"):
        return "∞"
    return f"{value:.2f}"


def _fmt_profit_factor(value) -> str:
    """專用 PF 格式"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    if np.isinf(value):
        return "∞"
    return f"{value:.2f}"


def _fmt_int(value) -> str:
    """格式化整數，允許 NaN"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    return f"{int(value)}"


def _format_period(equity_curve: pd.Series) -> str:
    """格式化期間"""
    if len(equity_curve.index) == 0 or not isinstance(equity_curve.index, pd.DatetimeIndex):
        return ""
    start = equity_curve.index[0].strftime("%Y-%m-%d")
    end = equity_curve.index[-1].strftime("%Y-%m-%d")
    return f"{start} ~ {end}"
