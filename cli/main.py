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

import sys
from pathlib import Path

import click

# 添加項目根目錄到 Python 路徑 (v0.5 修復)
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.engine import run_backtest  # noqa: E402

# v0.4 新增導入
from cli.dynamic_params import format_strategy_help  # noqa: E402
from data.storage import load_ohlcv  # noqa: E402
from execution_engine.portfolio_runner import (  # noqa: E402
    RunConfig,
    load_configs_from_yaml,
    run_portfolio,
)
from reports.text_reporter import render_portfolio, render_single  # noqa: E402
from strategies.registry_v2 import get_registry  # noqa: E402


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
def run_single(
    strategy, symbol, timeframe, cash, fee, leverage, stop_loss, take_profit, output, verbose
):
    """
    執行單個策略回測

    Example:
        superdog run -s simple_sma -m BTCUSDT -t 1h --sl 0.02 --tp 0.05
    """
    try:
        # 1. 獲取策略
        strategy_cls = get_registry().get_strategy(strategy)

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
            take_profit_pct=take_profit,
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
            take_profit_pct=take_profit,
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
    strategies = get_registry().list_strategies()

    click.echo("Available Strategies:")
    click.echo("=" * 60)

    for i, name in enumerate(strategies, 1):
        click.echo(f"{i}. {name}")

        if detailed:
            try:
                # 嘗試載入策略以獲取詳細信息
                strategy_cls = get_registry().get_strategy(name)

                # 檢查是否為 v2.0 策略
                try:
                    strategy_instance = strategy_cls()
                    if hasattr(strategy_instance, "get_parameters"):
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
        strategy_cls = get_registry().get_strategy(strategy)

        # 檢查是否為 v2.0 策略
        try:
            strategy_instance = strategy_cls()

            if hasattr(strategy_instance, "get_parameters"):
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
        available = ", ".join(sorted(get_registry().list_strategies()))
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
    驗證 SuperDog v0.6 安裝完整性

    檢查項目:
    - Phase 1-4 核心模組 (15+個模組)
    - 文件結構
    - 整合測試
    - CLI 命令
    - 依賴包

    Example:
        superdog verify
    """
    try:
        import subprocess

        # 優先使用完整驗證腳本
        if Path("superdog_v06_complete_validation.py").exists():
            script = "superdog_v06_complete_validation.py"
        elif Path("verify_v06_complete.py").exists():
            script = "verify_v06_complete.py"
        else:
            click.echo("❌ 驗證腳本未找到")
            raise click.Abort()

        result = subprocess.run([sys.executable, script], capture_output=True, text=True)
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
@click.option(
    "--type",
    "demo_type",
    type=click.Choice(["phase-b", "kawamoku", "all"]),
    default="phase-b",
    help="示範類型",
)
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
        "phase-b": "examples/phase_b_quick_demo.py",
        "kawamoku": "examples/kawamoku_complete_v05.py",
    }

    if demo_type == "all":
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
@click.option(
    "--type",
    "test_type",
    type=click.Choice(["integration", "all"]),
    default="integration",
    help="測試類型",
)
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

    if test_type == "integration":
        script = "tests/test_integration_v05.py"
        click.echo("運行整合測試...\n")
        try:
            subprocess.run([sys.executable, script], check=True)
        except subprocess.CalledProcessError:
            click.echo("測試失敗", err=True)
            raise click.Abort()
    elif test_type == "all":
        click.echo("運行所有測試...\n")
        # 未來可以添加更多測試
        try:
            subprocess.run([sys.executable, "tests/test_integration_v05.py"], check=True)
        except subprocess.CalledProcessError:
            click.echo("測試失敗", err=True)
            raise click.Abort()


# ===== Universe Management Commands (v0.6) =====


@cli.group(name="universe")
def universe_group():
    """
    幣種宇宙管理命令 (v0.6 Phase 1)

    構建、查看和匯出幣種宇宙分類

    Examples:
        superdog universe build
        superdog universe show large_cap
        superdog universe export --type yaml
    """


@universe_group.command(name="build")
@click.option("--exclude-stablecoins", is_flag=True, default=True, help="排除穩定幣 (默認: True)")
@click.option("--min-history-days", type=int, default=90, help="最小上市天數 (默認: 90)")
@click.option("--min-volume", type=float, default=1000000, help="最小30日平均成交額 (默認: $1M)")
@click.option("--parallel/--no-parallel", default=True, help="是否並行計算 (默認: True)")
@click.option("--max-workers", type=int, default=10, help="並行線程數 (默認: 10)")
@click.option("-v", "--verbose", is_flag=True, help="顯示詳細日誌")
def build_universe(
    exclude_stablecoins, min_history_days, min_volume, parallel, max_workers, verbose
):
    """
    構建幣種宇宙

    自動發現所有可用幣種，計算屬性並分類

    Example:
        superdog universe build
        superdog universe build --min-history-days 180 --parallel
    """
    import logging

    from data.universe_manager import get_universe_manager

    # 設定日誌級別
    if verbose:
        logging.getLogger("data.universe_manager").setLevel(logging.DEBUG)
        logging.getLogger("data.universe_calculator").setLevel(logging.DEBUG)

    try:
        click.echo("=" * 70)
        click.echo("SuperDog v0.6 - 幣種宇宙構建")
        click.echo("=" * 70)
        click.echo()

        # 創建管理器
        manager = get_universe_manager()

        # 構建宇宙
        click.echo(f"配置:")
        click.echo(f"  排除穩定幣: {exclude_stablecoins}")
        click.echo(f"  最小上市天數: {min_history_days}")
        click.echo(f"  最小成交額: ${min_volume:,.0f}")
        click.echo(f"  並行計算: {parallel} (線程數: {max_workers})")
        click.echo()

        universe = manager.build_universe(
            exclude_stablecoins=exclude_stablecoins,
            min_history_days=min_history_days,
            min_volume=min_volume,
            parallel=parallel,
            max_workers=max_workers,
        )

        # 保存快照
        saved_path = manager.save_universe(universe)

        # 顯示結果
        click.echo()
        click.echo("=" * 70)
        click.echo("宇宙構建完成")
        click.echo("=" * 70)
        click.echo()
        click.echo(f"日期: {universe.date}")
        click.echo(f"總幣種數: {universe.statistics['total']}")
        click.echo()
        click.echo("分類統計:")
        click.echo(f"  Large Cap (大盤):  {universe.statistics['large_cap']}")
        click.echo(f"  Mid Cap (中盤):    {universe.statistics['mid_cap']}")
        click.echo(f"  Small Cap (小盤):  {universe.statistics['small_cap']}")
        click.echo(f"  Micro Cap (微盤):  {universe.statistics['micro_cap']}")
        click.echo()
        click.echo(f"快照已保存到: {saved_path}")
        click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise click.Abort()


@universe_group.command(name="show")
@click.argument(
    "classification", type=click.Choice(["large_cap", "mid_cap", "small_cap", "micro_cap", "all"])
)
@click.option("--date", type=str, help="快照日期 (YYYY-MM-DD)，默認為最新")
@click.option("--top", type=int, help="只顯示前N個（按成交額排序）")
@click.option(
    "--format", type=click.Choice(["table", "list", "json"]), default="table", help="輸出格式"
)
def show_universe(classification, date, top, format):
    """
    顯示宇宙分類

    查看指定分類的幣種列表及其屬性

    Example:
        superdog universe show large_cap
        superdog universe show mid_cap --top 20
        superdog universe show all --format json
    """
    import json as json_module

    from data.universe_manager import get_universe_manager

    try:
        manager = get_universe_manager()

        # 獲取快照
        if date is None:
            dates = manager.get_available_dates()
            if not dates:
                click.echo("錯誤: 沒有找到宇宙快照，請先運行 'superdog universe build'", err=True)
                raise click.Abort()
            date = dates[0]  # 最新的

        universe = manager.load_universe(date)

        # 獲取指定分類的幣種
        if classification == "all":
            symbols_to_show = []
            for cat in ["large_cap", "mid_cap", "small_cap", "micro_cap"]:
                symbols_to_show.extend(universe.classification.get(cat, []))
        else:
            symbols_to_show = universe.classification.get(classification, [])

        if not symbols_to_show:
            click.echo(f"沒有找到 {classification} 分類的幣種")
            return

        # 按成交額排序
        sorted_symbols = sorted(
            symbols_to_show, key=lambda s: universe.symbols[s].volume_30d_usd, reverse=True
        )

        # 取前N個
        if top:
            sorted_symbols = sorted_symbols[:top]

        # 顯示結果
        click.echo()
        click.echo("=" * 100)
        click.echo(f"幣種宇宙 - {classification.upper()} ({date})")
        click.echo("=" * 100)
        click.echo()

        if format == "table":
            # 表格格式
            click.echo(
                f"{'#':<4} {'Symbol':<12} {'30d Volume':<15} {'History':<10} {'OI Trend':<10} {'Perpetual':<10}"
            )
            click.echo("-" * 100)
            for i, symbol in enumerate(sorted_symbols, 1):
                meta = universe.symbols[symbol]
                click.echo(
                    f"{i:<4} {symbol:<12} ${meta.volume_30d_usd:>13,.0f} "
                    f"{meta.history_days:>9}d {meta.oi_trend:>9.2f} "
                    f"{'✓' if meta.has_perpetual else '✗':>9}"
                )

        elif format == "list":
            # 列表格式
            for symbol in sorted_symbols:
                click.echo(symbol)

        elif format == "json":
            # JSON格式
            output = {
                "date": date,
                "classification": classification,
                "total": len(sorted_symbols),
                "symbols": [universe.symbols[s].to_dict() for s in sorted_symbols],
            }
            click.echo(json_module.dumps(output, indent=2, ensure_ascii=False))

        click.echo()
        click.echo(f"共 {len(sorted_symbols)} 個幣種")
        click.echo()

    except FileNotFoundError as e:
        click.echo(f"錯誤: {e}", err=True)
        click.echo("請先運行 'superdog universe build' 構建宇宙", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


@universe_group.command(name="export")
@click.option(
    "--type",
    "universe_type",
    type=click.Choice(["large_cap", "mid_cap", "small_cap", "micro_cap"]),
    default="large_cap",
    help="宇宙類型",
)
@click.option("--top", type=int, help="只匯出前N個（按成交額排序）")
@click.option("--format", type=click.Choice(["yaml", "json"]), default="yaml", help="輸出格式")
@click.option("--output", "-o", type=str, help="輸出文件路徑")
@click.option("--date", type=str, help="快照日期 (YYYY-MM-DD)，默認為最新")
def export_universe(universe_type, top, format, output, date):
    """
    匯出宇宙配置文件

    將指定分類的幣種匯出為YAML或JSON配置文件

    Example:
        superdog universe export --type large_cap --top 50
        superdog universe export --type mid_cap --format json -o config.json
    """
    from data.universe_manager import get_universe_manager

    try:
        manager = get_universe_manager()

        # 獲取快照
        if date is None:
            dates = manager.get_available_dates()
            if not dates:
                click.echo("錯誤: 沒有找到宇宙快照，請先運行 'superdog universe build'", err=True)
                raise click.Abort()
            date = dates[0]

        universe = manager.load_universe(date)

        # 匯出配置
        click.echo(f"正在匯出 {universe_type} 配置...")

        config_path = manager.export_config(
            universe, universe_type=universe_type, top_n=top, format=format, filename=output
        )

        click.echo()
        click.echo(f"✓ 配置文件已匯出到: {config_path}")
        click.echo()

    except FileNotFoundError as e:
        click.echo(f"錯誤: {e}", err=True)
        click.echo("請先運行 'superdog universe build' 構建宇宙", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


@universe_group.command(name="list")
def list_universes():
    """
    列出所有可用的宇宙快照

    Example:
        superdog universe list
    """
    from data.universe_manager import get_universe_manager

    try:
        manager = get_universe_manager()
        dates = manager.get_available_dates()

        if not dates:
            click.echo("沒有找到宇宙快照")
            click.echo()
            click.echo("請運行 'superdog universe build' 構建宇宙")
            return

        click.echo()
        click.echo("可用的宇宙快照:")
        click.echo()
        for i, date in enumerate(dates, 1):
            click.echo(f"  {i}. {date}")
        click.echo()
        click.echo(f"共 {len(dates)} 個快照")
        click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


# ===== v0.6 Experiment Commands =====


@cli.group(name="experiment")
def experiment_group():
    """
    實驗管理命令組 (v0.6 Strategy Lab)

    管理參數實驗、批量回測和結果分析

    子命令:
    - create    創建實驗配置
    - run       執行實驗
    - optimize  參數優化
    - list      列出實驗
    - show      顯示實驗詳情
    - analyze   分析實驗結果
    """


@experiment_group.command(name="create")
@click.option("--name", required=True, help="實驗名稱")
@click.option("-s", "--strategy", required=True, help="策略名稱")
@click.option("-m", "--symbols", required=True, help="幣種列表 (逗號分隔)")
@click.option("-t", "--timeframe", required=True, help="時間週期 (例如: 1h)")
@click.option("-o", "--output", help="輸出路徑 (默認: experiments/{name}.yaml)")
def create_experiment(name, strategy, symbols, timeframe, output):
    """
    創建實驗配置文件

    Example:
        superdog experiment create --name sma_test --strategy simple_sma \\
            --symbols BTCUSDT,ETHUSDT --timeframe 1h
    """
    try:
        from execution_engine import create_experiment_config

        # 解析幣種列表
        symbol_list = [s.strip() for s in symbols.split(",")]

        click.echo()
        click.echo(f"創建實驗配置: {name}")
        click.echo()

        # 交互式參數輸入
        click.echo("請定義參數範圍 (按 Ctrl+C 結束):")
        parameters = {}

        while True:
            try:
                param_name = click.prompt("參數名稱", default="")
                if not param_name:
                    break

                param_type = click.prompt(
                    "類型 (list/range)", type=click.Choice(["list", "range"]), default="list"
                )

                if param_type == "list":
                    values_str = click.prompt("值列表 (逗號分隔)")
                    # 嘗試轉換為數字
                    try:
                        values = [float(v.strip()) for v in values_str.split(",")]
                    except ValueError:
                        values = [v.strip() for v in values_str.split(",")]
                    parameters[param_name] = values
                else:
                    start = click.prompt("起始值", type=float)
                    stop = click.prompt("結束值", type=float)
                    step = click.prompt("步長", type=float)
                    parameters[param_name] = {"start": start, "stop": stop, "step": step}

            except click.Abort:
                break

        if not parameters:
            click.echo("錯誤: 必須至少定義一個參數", err=True)
            raise click.Abort()

        # 創建配置
        config = create_experiment_config(
            name=name,
            strategy=strategy,
            symbols=symbol_list,
            parameters=parameters,
            timeframe=timeframe,
        )

        # 保存配置
        if output is None:
            output = f"experiments/{name}.yaml"

        config.save(output)

        click.echo()
        click.echo(f"✓ 實驗配置已保存到: {output}")
        click.echo()
        click.echo(f"執行實驗:")
        click.echo(f"  superdog experiment run --config {output}")
        click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


@experiment_group.command(name="run")
@click.option("-c", "--config", required=True, help="實驗配置文件路徑")
@click.option("-w", "--workers", default=4, help="並行工作數 (默認: 4)")
@click.option("--no-retry", is_flag=True, help="失敗時不重試")
@click.option("--fail-fast", is_flag=True, help="遇到錯誤立即停止")
def run_experiment_cmd(config, workers, no_retry, fail_fast):
    """
    執行實驗

    Example:
        superdog experiment run --config experiments/sma_test.yaml --workers 8
    """
    try:
        from backtest.engine import run_backtest
        from data.pipeline import get_pipeline
        from execution_engine import ExperimentRunner, load_experiment_config

        # 加載配置
        click.echo()
        click.echo(f"加載實驗配置: {config}")
        exp_config = load_experiment_config(config)

        click.echo()
        click.echo(f"實驗名稱: {exp_config.name}")
        click.echo(f"策略: {exp_config.strategy}")
        click.echo(f"幣種數: {len(exp_config.symbols)}")
        click.echo()

        # 定義回測函數
        def backtest_func(symbol, timeframe, params, cfg):
            """回測執行函數"""
            from strategies.registry_v2 import get_registry

            # 載入策略
            strategy_cls = get_registry().get_strategy(cfg.strategy)

            # 載入數據
            pipeline = get_pipeline()
            strategy_instance = strategy_cls()
            result = pipeline.load_strategy_data(
                strategy_instance,
                symbol,
                timeframe,
                start_date=cfg.start_date,
                end_date=cfg.end_date,
            )

            if not result.success:
                raise ValueError(f"數據載入失敗: {result.error}")

            # 運行回測
            backtest_result = run_backtest(
                strategy_cls,
                result.data["ohlcv"],
                initial_cash=cfg.initial_cash,
                fee_rate=cfg.fee_rate,
                leverage=cfg.leverage,
                stop_loss_pct=cfg.stop_loss_pct,
                take_profit_pct=cfg.take_profit_pct,
                params=params,
            )

            # 提取指標
            return {
                "total_return": backtest_result.total_return,
                "max_drawdown": backtest_result.max_drawdown,
                "sharpe_ratio": backtest_result.sharpe_ratio,
                "num_trades": backtest_result.num_trades,
                "win_rate": backtest_result.win_rate,
                "profit_factor": backtest_result.profit_factor,
            }

        # 執行實驗
        runner = ExperimentRunner(
            max_workers=workers, retry_failed=not no_retry, fail_fast=fail_fast
        )

        result = runner.run_experiment(exp_config, backtest_func)

        # 保存結果
        runner.save_result(result)

        # 顯示摘要
        click.echo()
        click.echo("=" * 60)
        click.echo("實驗完成摘要")
        click.echo("=" * 60)
        click.echo()

        if result.best_run:
            click.echo("最佳結果:")
            click.echo(f"  Symbol: {result.best_run.symbol}")
            click.echo(f"  Return: {result.best_run.total_return:.2%}")
            click.echo(f"  Sharpe: {result.best_run.sharpe_ratio:.2f}")
            click.echo(f"  Max DD: {result.best_run.max_drawdown:.2%}")
            click.echo()
            click.echo("  最佳參數:")
            for k, v in result.best_run.parameters.items():
                click.echo(f"    {k}: {v}")

        click.echo()
        click.echo(f"分析結果:")
        click.echo(f"  superdog experiment analyze --id {result.experiment_id}")
        click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        import traceback

        if click.get_current_context().obj and click.get_current_context().obj.get("verbose"):
            traceback.print_exc()
        raise click.Abort()


@experiment_group.command(name="optimize")
@click.option("-c", "--config", required=True, help="實驗配置文件路徑")
@click.option(
    "-m", "--mode", type=click.Choice(["grid", "random", "bayesian"]), default="grid", help="優化模式"
)
@click.option("--metric", default="sharpe_ratio", help="優化指標")
@click.option("-w", "--workers", default=4, help="並行工作數")
@click.option("--early-stopping", is_flag=True, help="啟用早停")
def optimize_experiment(config, mode, metric, workers, early_stopping):
    """
    參數優化

    Example:
        superdog experiment optimize --config experiments/sma_test.yaml \\
            --mode bayesian --metric sharpe_ratio --early-stopping
    """
    try:
        from backtest.engine import run_backtest
        from data.pipeline import get_pipeline
        from execution_engine import (
            OptimizationConfig,
            OptimizationMode,
            ParameterOptimizer,
            load_experiment_config,
        )

        # 加載配置
        click.echo()
        click.echo(f"加載實驗配置: {config}")
        exp_config = load_experiment_config(config)

        click.echo()
        click.echo(f"優化模式: {mode}")
        click.echo(f"優化指標: {metric}")
        click.echo()

        # 定義回測函數
        def backtest_func(symbol, timeframe, params, cfg):
            strategy_cls = get_registry().get_strategy(cfg.strategy)
            pipeline = get_pipeline()
            strategy_instance = strategy_cls()

            result = pipeline.load_strategy_data(
                strategy_instance,
                symbol,
                timeframe,
                start_date=cfg.start_date,
                end_date=cfg.end_date,
            )

            if not result.success:
                raise ValueError(f"數據載入失敗: {result.error}")

            backtest_result = run_backtest(
                strategy_cls,
                result.data["ohlcv"],
                initial_cash=cfg.initial_cash,
                fee_rate=cfg.fee_rate,
                leverage=cfg.leverage,
                params=params,
            )

            return {
                "total_return": backtest_result.total_return,
                "sharpe_ratio": backtest_result.sharpe_ratio,
                "max_drawdown": backtest_result.max_drawdown,
                "num_trades": backtest_result.num_trades,
                "win_rate": backtest_result.win_rate,
                "profit_factor": backtest_result.profit_factor,
            }

        # 配置優化器
        opt_config = OptimizationConfig(
            mode=OptimizationMode(mode),
            metric=metric,
            maximize=True,
            early_stopping=early_stopping,
            max_workers=workers,
        )

        optimizer = ParameterOptimizer(exp_config, backtest_func, opt_config)
        result = optimizer.optimize()

        # 顯示結果
        click.echo()
        click.echo("=" * 60)
        click.echo("優化完成")
        click.echo("=" * 60)
        click.echo()

        if result.best_run:
            click.echo("最佳參數組合:")
            for k, v in result.best_run.parameters.items():
                click.echo(f"  {k}: {v}")
            click.echo()
            click.echo(f"最佳 {metric}: {getattr(result.best_run, metric):.4f}")

        # 參數重要性分析
        importance = optimizer.analyze_parameter_importance(result)
        if importance:
            click.echo()
            click.echo("參數重要性:")
            for param, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
                click.echo(f"  {param}: {score:.2%}")

        click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


@experiment_group.command(name="list")
def list_experiments():
    """
    列出所有實驗

    Example:
        superdog experiment list
    """
    try:
        import json
        from pathlib import Path

        results_dir = Path("data/experiments/results")

        if not results_dir.exists():
            click.echo("沒有找到實驗結果")
            return

        experiments = []
        for exp_dir in results_dir.iterdir():
            if exp_dir.is_dir():
                summary_file = exp_dir / "summary.json"
                if summary_file.exists():
                    with open(summary_file) as f:
                        data = json.load(f)
                        experiments.append(
                            {
                                "id": exp_dir.name,
                                "name": data["config"]["name"],
                                "completed": data.get("completed_runs", 0),
                                "total": data.get("total_runs", 0),
                                "date": data.get("started_at", "")[:10],
                            }
                        )

        if not experiments:
            click.echo("沒有找到實驗結果")
            return

        click.echo()
        click.echo(f"{'ID':<40} {'名稱':<20} {'完成/總數':<12} {'日期':<12}")
        click.echo("-" * 90)

        for exp in sorted(experiments, key=lambda x: x["date"], reverse=True):
            click.echo(
                f"{exp['id']:<40} {exp['name']:<20} "
                f"{exp['completed']}/{exp['total']:<10} {exp['date']:<12}"
            )

        click.echo()
        click.echo(f"共 {len(experiments)} 個實驗")
        click.echo()

    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


@experiment_group.command(name="analyze")
@click.option("--id", "experiment_id", required=True, help="實驗ID")
@click.option("-o", "--output", help="輸出報告路徑")
@click.option(
    "--format", type=click.Choice(["markdown", "json", "html"]), default="markdown", help="報告格式"
)
@click.option("--top", default=10, help="Top N 結果數量")
def analyze_experiment(experiment_id, output, format, top):
    """
    分析實驗結果

    Example:
        superdog experiment analyze --id sma_test_abc123 --output report.md
    """
    try:
        from execution_engine import ExperimentRunner, ResultAnalyzer

        # 加載結果
        click.echo()
        click.echo(f"加載實驗結果: {experiment_id}")

        runner = ExperimentRunner()
        result = runner.load_result(experiment_id)

        # 生成分析
        analyzer = ResultAnalyzer(result)
        report = analyzer.generate_report(top_n=top)

        # 顯示摘要
        click.echo()
        click.echo(f"實驗名稱: {report.experiment_name}")
        click.echo(f"總運行數: {report.total_runs}")
        click.echo(f"成功運行: {report.completed_runs}")
        click.echo()

        if report.best_run:
            click.echo("最佳結果:")
            click.echo(f"  Total Return: {report.best_run.total_return:.2%}")
            click.echo(f"  Sharpe Ratio: {report.best_run.sharpe_ratio:.2f}")
            click.echo()

        # 保存報告
        if output:
            analyzer.save_report(report, output, format=format)
        else:
            # 默認輸出路徑
            default_output = f"data/experiments/results/{experiment_id}/report.{format}"
            analyzer.save_report(report, default_output, format=format)

        click.echo()

    except FileNotFoundError:
        click.echo(f"錯誤: 找不到實驗 {experiment_id}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"錯誤: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    cli()
