"""
SuperDog Backtest CLI v0.3

Command-line interface for running single or portfolio backtests and printing
plain-text reports.

Design Reference: docs/specs/planned/v0.3_cli_spec.md
"""

import click

from execution_engine.portfolio_runner import RunConfig, run_portfolio, load_configs_from_yaml
from reports.text_reporter import render_single, render_portfolio
from data.storage import load_ohlcv
from strategies.registry import get_strategy, list_strategies
from backtest.engine import run_backtest


@click.group()
@click.version_option(version="0.3.0", prog_name="SuperDog Backtest")
def cli():
    """
    SuperDog Backtest CLI v0.3

    量化交易回測引擎命令行工具
    """
    pass


@cli.command(name="run")
@click.option("-s", "--strategy", required=True, help="策略名稱")
@click.option("-m", "--symbol", required=True, help="交易對 (例如: BTCUSDT)")
@click.option("-t", "--timeframe", required=True, help="時間週期 (例如: 1h, 4h, 1d)")
@click.option("-c", "--cash", default=10000.0, help="初始資金 (默認: 10000)")
@click.option("--fee", default=0.0005, help="手續費率 (默認: 0.0005)")
@click.option("--leverage", default=1.0, help="槓桿倍數 (默認: 1.0)")
@click.option("--sl", "stop_loss", type=float, help="止損百分比 (例如: 0.02)")
@click.option("--tp", "take_profit", type=float, help="止盈百分比 (例如: 0.05)")
@click.option("-o", "--output", help="輸出報表到檔案")
@click.option("-v", "--verbose", is_flag=True, help="顯示詳細日誌")
def run_single(strategy, symbol, timeframe, cash, fee, leverage, stop_loss, take_profit, output, verbose):
    """
    執行單個策略回測

    Example:
        superdog run -s simple_sma -m BTCUSDT -t 1h --sl 0.02 --tp 0.05
    """
    try:
        # 1. 獲取策略
        strategy_cls = get_strategy(strategy)

        # 2. 載入數據
        data_file = f"data/raw/{symbol}_{timeframe}.csv"
        data = load_ohlcv(data_file)

        # 3. 執行回測
        result = run_backtest(
            data=data,
            strategy_cls=strategy_cls,
            initial_cash=cash,
            fee_rate=fee,
            leverage=leverage,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit
        )

        # 4. 生成報表
        config = RunConfig(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            initial_cash=cash,
            fee_rate=fee,
            leverage=leverage,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit
        )
        report = render_single(result, config=config)

        # 5. 輸出
        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(report)
            click.echo(f"Report saved to {output}")
        else:
            click.echo(report)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command(name="portfolio")
@click.option("-c", "--config", "config_file", required=True, help="YAML 配置檔案路徑")
@click.option("-o", "--output", help="輸出報表到檔案")
@click.option("-v", "--verbose", is_flag=True, help="顯示詳細日誌")
@click.option("--fail-fast", is_flag=True, help="遇錯立即停止")
def run_portfolio_cmd(config_file, output, verbose, fail_fast):
    """
    執行批量回測（從 YAML 配置）

    Example:
        superdog portfolio -c configs/multi_strategy.yml -o report.txt
    """
    try:
        configs = load_configs_from_yaml(config_file)
        result = run_portfolio(configs, verbose=verbose, fail_fast=fail_fast)
        report = render_portfolio(result)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(report)
            click.echo(f"Report saved to {output}")
        else:
            click.echo(report)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command(name="list")
def list_strategies_cmd():
    """
    列出所有可用策略

    Example:
        superdog list
    """
    strategies = list_strategies()

    click.echo("Available Strategies:")
    click.echo("=" * 40)
    for i, name in enumerate(strategies, 1):
        click.echo(f"  {i}. {name}")
    click.echo("=" * 40)
    click.echo(f"Total: {len(strategies)} strategies")


if __name__ == "__main__":
    cli()
