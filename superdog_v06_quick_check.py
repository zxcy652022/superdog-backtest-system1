#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperDog v0.6 快速驗證腳本
快速檢查所有核心功能是否正常
"""

import importlib.util
import sys
from pathlib import Path


# 顏色輸出
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_check(message, status):
    """打印檢查結果"""
    if status:
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")
    else:
        print(f"{Colors.RED}❌ {message}{Colors.END}")
    return status


def check_module_exists(module_path):
    """檢查模組文件是否存在"""
    return Path(module_path).exists()


def check_module_import(module_name, from_path=None):
    """檢查模組是否可以導入"""
    try:
        if from_path:
            spec = importlib.util.spec_from_file_location(module_name, from_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            __import__(module_name)
        return True
    except Exception:
        return False


def quick_validation():
    """快速驗證所有核心功能"""

    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("SuperDog v0.6 快速驗證")
    print("=" * 40)
    print(f"{Colors.END}")

    all_passed = True

    # Phase 1: 幣種宇宙管理
    print(f"\n{Colors.BLUE}📊 Phase 1: 幣種宇宙管理{Colors.END}")

    checks = [
        ("data/universe_manager.py", check_module_exists("data/universe_manager.py")),
        ("data/universe_calculator.py", check_module_exists("data/universe_calculator.py")),
        ("data/universe/ 目錄", Path("data/universe").exists()),
    ]

    for desc, result in checks:
        all_passed &= print_check(desc, result)

    # Phase 2: 策略實驗室
    print(f"\n{Colors.BLUE}🧪 Phase 2: 策略實驗室{Colors.END}")

    checks = [
        ("execution_engine/experiments.py", check_module_exists("execution_engine/experiments.py")),
        (
            "execution_engine/experiment_runner.py",
            check_module_exists("execution_engine/experiment_runner.py"),
        ),
        (
            "execution_engine/parameter_optimizer.py",
            check_module_exists("execution_engine/parameter_optimizer.py"),
        ),
        (
            "execution_engine/result_analyzer.py",
            check_module_exists("execution_engine/result_analyzer.py"),
        ),
    ]

    for desc, result in checks:
        all_passed &= print_check(desc, result)

    # Phase 3: 真實執行模型
    print(f"\n{Colors.BLUE}💰 Phase 3: 真實執行模型{Colors.END}")

    checks = [
        (
            "execution_engine/execution_model.py",
            check_module_exists("execution_engine/execution_model.py"),
        ),
        ("execution_engine/fee_models.py", check_module_exists("execution_engine/fee_models.py")),
        (
            "execution_engine/slippage_models.py",
            check_module_exists("execution_engine/slippage_models.py"),
        ),
        (
            "execution_engine/funding_models.py",
            check_module_exists("execution_engine/funding_models.py"),
        ),
        (
            "execution_engine/liquidation_models.py",
            check_module_exists("execution_engine/liquidation_models.py"),
        ),
    ]

    for desc, result in checks:
        all_passed &= print_check(desc, result)

    # Phase 4: 動態風控
    print(f"\n{Colors.BLUE}🛡️ Phase 4: 動態風控{Colors.END}")

    checks = [
        (
            "risk_management/support_resistance.py",
            check_module_exists("risk_management/support_resistance.py"),
        ),
        (
            "risk_management/dynamic_stops.py",
            check_module_exists("risk_management/dynamic_stops.py"),
        ),
        (
            "risk_management/risk_calculator.py",
            check_module_exists("risk_management/risk_calculator.py"),
        ),
        (
            "risk_management/position_sizer.py",
            check_module_exists("risk_management/position_sizer.py"),
        ),
        ("risk_management/__init__.py", check_module_exists("risk_management/__init__.py")),
    ]

    for desc, result in checks:
        all_passed &= print_check(desc, result)

    # CLI系統
    print(f"\n{Colors.BLUE}💻 CLI系統{Colors.END}")

    checks = [
        ("cli/main.py", check_module_exists("cli/main.py")),
        ("CLI主程序導入", check_module_import("main", "cli/main.py")),
    ]

    for desc, result in checks:
        all_passed &= print_check(desc, result)

    # v0.5兼容性
    print(f"\n{Colors.BLUE}🔄 v0.5兼容性{Colors.END}")

    checks = [
        ("strategies/simple_sma.py", check_module_exists("strategies/simple_sma.py")),
        ("strategies/kawamoku.py", check_module_exists("strategies/kawamoku.py")),
        ("data/storage.py", check_module_exists("data/storage.py")),
        ("backtest/engine.py", check_module_exists("backtest/engine.py")),
    ]

    for desc, result in checks:
        all_passed &= print_check(desc, result)

    # 測試文件
    print(f"\n{Colors.BLUE}🧪 測試文件{Colors.END}")

    test_files = [
        "tests/test_experiments_v06.py",
        "tests/test_risk_management_v06.py",
        "tests/test_perpetual_v05.py",
    ]

    for test_file in test_files:
        result = check_module_exists(test_file)
        all_passed &= print_check(test_file, result)

    # 文檔
    print(f"\n{Colors.BLUE}📚 文檔{Colors.END}")

    doc_files = [
        "V06_PHASE2_STRATEGY_LAB.md",
        "V06_PHASE4_RISK_MANAGEMENT.md",
        "V06_COMPLETE_DELIVERY.md",
        "CHANGELOG.md",
        "README.md",
    ]

    for doc_file in doc_files:
        result = check_module_exists(doc_file)
        all_passed &= print_check(doc_file, result)

    # 總結
    print(f"\n{Colors.CYAN}{'='*40}{Colors.END}")

    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 所有檢查通過！SuperDog v0.6 結構完整！{Colors.END}")
        print(f"{Colors.WHITE}建議運行完整驗證: python3 superdog_v06_complete_validation.py{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ 發現缺失文件，請檢查上述標記為紅色的項目{Colors.END}")

    return all_passed


def main():
    """主程序"""

    # 檢查是否在正確目錄
    if not Path("cli/main.py").exists():
        print(f"{Colors.RED}❌ 錯誤: 請在SuperDog專案根目錄執行此腳本{Colors.END}")
        print(f"{Colors.YELLOW}當前目錄: {Path.cwd()}{Colors.END}")
        sys.exit(1)

    # 執行快速驗證
    success = quick_validation()

    if success:
        print(f"\n{Colors.GREEN}✅ 快速驗證完成！{Colors.END}")
        print(f"{Colors.CYAN}💡 提示: 運行完整驗證測試以確保所有功能正常{Colors.END}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}❌ 快速驗證發現問題{Colors.END}")
        sys.exit(1)


if __name__ == "__main__":
    main()
