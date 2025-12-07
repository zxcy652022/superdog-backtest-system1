"""
SuperDog Backtest CLI v0.5

Command-line interface for running single or portfolio backtests and printing
plain-text reports.

v0.5 新增:
- 永續合約數據支援 (6種數據源)
- 多交易所支援 (Binance, Bybit, OKX)
- 互動式選單系統
- Phase A/B/C 完整功能

v0.4 特性:
- 動態策略參數支援
- 策略信息查詢命令
- v2.0 Strategy API 整合

Design Reference:
- v0.3: docs/specs/planned/v0.3_cli_spec.md
- v0.4: docs/specs/planned/v0.4_strategy_api_spec.md
- v0.5: PHASE_B_DELIVERY.md, V05_FINAL_SUMMARY.md
"""

import click
import sys
from pathlib import Path
from typing import Dict, Any

# 添加項目根目錄到 Python 路徑 (v0.5 修復)
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution_engine.portfolio_runner import RunConfig, run_portfolio, load_configs_from_yaml
from reports.text_reporter import render_single, render_portfolio
from data.storage import load_ohlcv
from strategies.registry import get_strategy, list_strategies
from backtest.engine import run_backtest

# v0.4 新增導入
from cli.dynamic_params import (
    DynamicCLI,
    extract_strategy_params,
    validate_and_convert_params,
    format_strategy_help
)
from cli.parameter_validator import ParameterValidator, BacktestConfigValidator


@click.group()
@click.version_option(version="0.5.0", prog_name="SuperDog Backtest")
def cli():
    """
    SuperDog Backtest CLI v0.5

    專業量化交易回測引擎命令行工具

    v0.5 新特性:
    - 永續合約數據生態系統 (6種數據源)
    - 多交易所支援 (Binance, Bybit, OKX)
    - 互動式選單系統 (使用 'interactive' 命令)
    - 完整驗證工具 (使用 'verify' 命令)

    v0.4 特性:
    - 動態策略參數支援
    - 使用 'info' 命令查看策略詳細信息
    - 使用 'list' 命令查看所有可用策略

    快速開始:
    - superdog interactive    # 啟動互動式選單
    - superdog verify         # 驗證 v0.5 安裝
    - superdog list           # 列出所有策略
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
@click.option("--detailed", is_flag=True, help="顯示詳細信息（包含參數）")
def list_strategies_cmd(detailed):
    """
    列出所有可用策略

    Example:
        superdog list
        superdog list --detailed
    """
    strategies = list_strategies()

    click.echo("Available Strategies:")
    click.echo("=" * 60)

    for i, name in enumerate(strategies, 1):
        click.echo(f"{i}. {name}")

        if detailed:
            try:
                # 嘗試載入策略以獲取詳細信息
                strategy_cls = get_strategy(name)

                # 檢查是否為 v2.0 策略
                try:
                    strategy_instance = strategy_cls()
                    if hasattr(strategy_instance, 'get_parameters'):
                        # v2.0 策略
                        params = strategy_instance.get_parameters()
                        click.echo(f"   Description: {strategy_instance.description or 'N/A'}")
                        click.echo(f"   Parameters: {len(params)} configurable")
                        if params:
                            click.echo(f"   Available params: {', '.join(params.keys())}")
                    else:
                        # v0.3 策略
                        click.echo(f"   Type: v0.3 strategy (legacy)")
                except Exception:
                    click.echo(f"   Type: v0.3 strategy (legacy)")

                click.echo("")  # 空行分隔

            except Exception as e:
                click.echo(f"   (Error loading strategy info: {e})")
                click.echo("")

    click.echo("=" * 60)
    click.echo(f"Total: {len(strategies)} strategies")
    click.echo("\nTip: Use 'superdog info -s <strategy>' for detailed parameter information")


@cli.command(name="info")
@click.option("-s", "--strategy", required=True, help="策略名稱")
def strategy_info_cmd(strategy):
    """
    顯示策略詳細信息和參數列表

    Example:
        superdog info -s simple_sma
        superdog info -s kawamoku_demo
    """
    try:
        # 載入策略
        strategy_cls = get_strategy(strategy)

        # 檢查是否為 v2.0 策略
        try:
            strategy_instance = strategy_cls()

            if hasattr(strategy_instance, 'get_parameters'):
                # v2.0 策略 - 使用動態幫助格式化
                help_text = format_strategy_help(strategy_instance)
                click.echo(help_text)
            else:
                # v0.3 策略 - 顯示基本信息
                click.echo(f"Strategy: {strategy}")
                click.echo(f"Type: v0.3 (legacy)")
                click.echo(f"Class: {strategy_cls.__name__}")
                click.echo("\nThis is a legacy v0.3 strategy.")
                click.echo("It does not support dynamic parameters.")
                click.echo("\nUsage:")
                click.echo(f"  superdog run -s {strategy} -m BTCUSDT -t 1h")

        except Exception as e:
            click.echo(f"Error loading strategy: {e}", err=True)
            raise click.Abort()

    except KeyError:
        available = ", ".join(sorted(list_strategies()))
        click.echo(f"Error: Strategy '{strategy}' not found.", err=True)
        click.echo(f"Available strategies: {available}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@cli.command(name="interactive")
def interactive_menu():
    """
    啟動 SuperDog v0.5 互動式選單系統

    提供美觀的終端界面，包含:
    - 數據管理 (下載/查看/清理)
    - 策略管理 (創建/配置/回測)
    - 系統工具 (驗證/更新/幫助)
    - 快速開始嚮導

    Example:
        superdog interactive
    """
    try:
        from cli.interactive import MainMenu
        menu = MainMenu()
        menu.run()
    except KeyboardInterrupt:
        click.echo("\n\n已取消")
    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


@cli.command(name="verify")
def verify_installation():
    """
    驗證 SuperDog v0.5 安裝完整性

    檢查項目:
    - Phase A/B 模組導入 (7個模組)
    - 文件結構 (7個文件)
    - DataPipeline 集成
    - 依賴包

    Example:
        superdog verify
    """
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "verify_v05_phase_b.py"],
            capture_output=True,
            text=True
        )
        click.echo(result.stdout)
        if result.returncode != 0:
            click.echo(result.stderr, err=True)
            raise click.Abort()
    except FileNotFoundError:
        click.echo("錯誤: verify_v05_phase_b.py 未找到", err=True)
        click.echo("請確保在項目根目錄運行此命令", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


@cli.command(name="demo")
@click.option("--type", "demo_type",
              type=click.Choice(['phase-b', 'kawamoku', 'all']),
              default='phase-b',
              help="示範類型")
def run_demo(demo_type):
    """
    運行 SuperDog v0.5 示範腳本

    示範類型:
    - phase-b: Phase B 快速示範 (8個功能模組)
    - kawamoku: 川沐多因子策略示範
    - all: 運行所有示範

    Example:
        superdog demo --type phase-b
        superdog demo --type kawamoku
    """
    import subprocess

    demos = {
        'phase-b': 'examples/phase_b_quick_demo.py',
        'kawamoku': 'examples/kawamoku_complete_v05.py'
    }

    if demo_type == 'all':
        for name, script in demos.items():
            click.echo(f"\n{'='*60}")
            click.echo(f"運行 {name} 示範...")
            click.echo(f"{'='*60}\n")
            try:
                subprocess.run([sys.executable, script], check=True)
            except subprocess.CalledProcessError as e:
                click.echo(f"錯誤: {name} 示範失敗", err=True)
    else:
        script = demos[demo_type]
        try:
            subprocess.run([sys.executable, script], check=True)
        except subprocess.CalledProcessError as e:
            click.echo(f"錯誤: 示範失敗", err=True)
            raise click.Abort()


@cli.command(name="test")
@click.option("--type", "test_type",
              type=click.Choice(['integration', 'all']),
              default='integration',
              help="測試類型")
def run_tests(test_type):
    """
    運行 SuperDog v0.5 測試套件

    測試類型:
    - integration: 端到端整合測試 (17個測試)
    - all: 運行所有測試

    Example:
        superdog test --type integration
    """
    import subprocess

    if test_type == 'integration':
        script = 'tests/test_integration_v05.py'
        click.echo("運行整合測試...\n")
        try:
            subprocess.run([sys.executable, script], check=True)
        except subprocess.CalledProcessError:
            click.echo("測試失敗", err=True)
            raise click.Abort()
    elif test_type == 'all':
        click.echo("運行所有測試...\n")
        # 未來可以添加更多測試
        try:
            subprocess.run([sys.executable, 'tests/test_integration_v05.py'], check=True)
        except subprocess.CalledProcessError:
            click.echo("測試失敗", err=True)
            raise click.Abort()


if __name__ == "__main__":
    cli()
