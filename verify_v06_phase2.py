"""
SuperDog v0.6 Phase 2 驗證腳本

驗證 Strategy Lab System 的安裝和基本功能

Author: SuperDog Development Team
Version: v0.6.0-phase2
"""

import sys
from pathlib import Path

# 確保可以導入專案模組
sys.path.insert(0, str(Path(__file__).parent))


def verify_imports():
    """驗證所有模組可以正確導入"""
    print("=" * 70)
    print("驗證模組導入")
    print("=" * 70)
    print()

    modules_to_test = [
        "execution_engine.experiments",
        "execution_engine.experiment_runner",
        "execution_engine.parameter_optimizer",
        "execution_engine.result_analyzer"
    ]

    passed = 0
    failed = 0

    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✓ {module_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {module_name}: {e}")
            failed += 1

    print()
    print(f"導入測試: {passed}/{len(modules_to_test)} 通過")
    print()

    return failed == 0


def verify_classes():
    """驗證核心類可以實例化"""
    print("=" * 70)
    print("驗證核心類")
    print("=" * 70)
    print()

    from execution_engine import (
        create_experiment_config,
        ExperimentRunner,
        ParameterOptimizer,
        ResultAnalyzer,
        OptimizationConfig,
        OptimizationMode
    )

    tests = []

    # 測試 1: 創建實驗配置
    try:
        config = create_experiment_config(
            name="Verify_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10, 20]},
            timeframe="1h"
        )
        print(f"✓ ExperimentConfig 創建成功")
        print(f"  - 實驗ID: {config.get_experiment_id()}")
        tests.append(True)
    except Exception as e:
        print(f"✗ ExperimentConfig 創建失敗: {e}")
        tests.append(False)

    # 測試 2: 實例化 ExperimentRunner
    try:
        runner = ExperimentRunner(max_workers=2)
        print(f"✓ ExperimentRunner 實例化成功")
        print(f"  - Max workers: {runner.max_workers}")
        tests.append(True)
    except Exception as e:
        print(f"✗ ExperimentRunner 實例化失敗: {e}")
        tests.append(False)

    # 測試 3: 實例化 ParameterOptimizer
    try:
        def mock_backtest(symbol, timeframe, params, config):
            return {'sharpe_ratio': 1.0}

        opt_config = OptimizationConfig(
            mode=OptimizationMode.GRID,
            metric="sharpe_ratio"
        )
        optimizer = ParameterOptimizer(config, mock_backtest, opt_config)
        print(f"✓ ParameterOptimizer 實例化成功")
        print(f"  - 優化模式: {optimizer.opt_config.mode.value}")
        tests.append(True)
    except Exception as e:
        print(f"✗ ParameterOptimizer 實例化失敗: {e}")
        tests.append(False)

    # 測試 4: 創建 mock 結果並分析
    try:
        from execution_engine import ExperimentResult, ExperimentRun, ExperimentStatus

        runs = [
            ExperimentRun(
                experiment_id="test",
                run_id="run_001",
                symbol="BTCUSDT",
                parameters={"period": 10},
                status=ExperimentStatus.COMPLETED,
                sharpe_ratio=1.5,
                total_return=0.15
            )
        ]

        result = ExperimentResult(
            experiment_id="test",
            config=config,
            runs=runs,
            total_runs=1,
            completed_runs=1,
            failed_runs=0
        )

        analyzer = ResultAnalyzer(result)
        print(f"✓ ResultAnalyzer 實例化成功")
        print(f"  - 分析運行數: {len(analyzer.df)}")
        tests.append(True)
    except Exception as e:
        print(f"✗ ResultAnalyzer 實例化失敗: {e}")
        tests.append(False)

    print()
    print(f"類測試: {sum(tests)}/{len(tests)} 通過")
    print()

    return all(tests)


def verify_file_structure():
    """驗證文件結構"""
    print("=" * 70)
    print("驗證文件結構")
    print("=" * 70)
    print()

    required_files = [
        "execution_engine/__init__.py",
        "execution_engine/experiments.py",
        "execution_engine/experiment_runner.py",
        "execution_engine/parameter_optimizer.py",
        "execution_engine/result_analyzer.py",
        "cli/main.py",
        "tests/test_experiments_v06.py",
        "V06_PHASE2_STRATEGY_LAB.md",
        "CHANGELOG.md"
    ]

    passed = 0
    failed = 0

    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"✓ {file_path}")
            passed += 1
        else:
            print(f"✗ {file_path} (不存在)")
            failed += 1

    print()
    print(f"文件檢查: {passed}/{len(required_files)} 存在")
    print()

    return failed == 0


def verify_cli_commands():
    """驗證 CLI 命令可用"""
    print("=" * 70)
    print("驗證 CLI 命令")
    print("=" * 70)
    print()

    try:
        from cli.main import cli
        from click.testing import CliRunner

        runner = CliRunner()

        # 測試 help
        result = runner.invoke(cli, ['experiment', '--help'])
        if result.exit_code == 0 and 'experiment' in result.output:
            print("✓ superdog experiment --help")
        else:
            print(f"✗ superdog experiment --help (exit code: {result.exit_code})")
            return False

        # 檢查子命令
        commands = ['create', 'run', 'optimize', 'list', 'analyze']
        for cmd in commands:
            if cmd in result.output:
                print(f"✓ superdog experiment {cmd} (可用)")
            else:
                print(f"✗ superdog experiment {cmd} (不可用)")

        print()
        print("CLI 命令: 可用")
        print()
        return True

    except Exception as e:
        print(f"✗ CLI 測試失敗: {e}")
        print()
        return False


def main():
    """主驗證流程"""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "SuperDog v0.6 Phase 2 驗證" + " " * 26 + "║")
    print("║" + " " * 15 + "Strategy Lab System" + " " * 31 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    results = {
        "模組導入": verify_imports(),
        "核心類": verify_classes(),
        "文件結構": verify_file_structure(),
        "CLI 命令": verify_cli_commands()
    }

    # 總結
    print("=" * 70)
    print("驗證總結")
    print("=" * 70)
    print()

    for name, passed in results.items():
        status = "✅ 通過" if passed else "❌ 失敗"
        print(f"{name}: {status}")

    print()

    if all(results.values()):
        print("🎉 Phase 2 驗證完全通過！")
        print()
        print("下一步:")
        print("  1. 運行測試: python3 tests/test_experiments_v06.py")
        print("  2. 查看文檔: cat V06_PHASE2_STRATEGY_LAB.md")
        print("  3. 試用 CLI: python3 cli/main.py experiment --help")
        print()
        return 0
    else:
        print("⚠️  部分驗證失敗，請檢查上述錯誤")
        print()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
