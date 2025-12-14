#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperDog Quant v1.0 - CLI 主入口

量化回測系統互動式命令行介面

功能：
- 數據管理（下載、檢查）
- 快速回測
- 參數優化（Walk-Forward 驗證）
- 查看報告

Usage:
    python superdog.py

Design Reference: docs/v1.0/DESIGN.md
"""

import os
import sys
from datetime import datetime
from typing import List, Optional

# 確保專案根目錄在 path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def clear_screen():
    """清除螢幕"""
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    """顯示主選單橫幅"""
    print()
    print("=" * 64)
    print("         SuperDog Quant v1.0 - 量化回測系統")
    print("=" * 64)
    print()


def print_main_menu():
    """顯示主選單"""
    print("  1. 數據管理")
    print("     - 下載歷史數據")
    print("     - 檢查數據完整性")
    print()
    print("  2. 快速回測")
    print("     - 單策略回測")
    print()
    print("  3. 參數優化")
    print("     - Walk-Forward 驗證")
    print("     - 網格搜索")
    print()
    print("  4. 查看報告")
    print("     - 最近回測結果")
    print()
    print("  5. 系統設定")
    print()
    print("  0. 退出")
    print()
    print("-" * 64)


def get_available_strategies() -> List[str]:
    """獲取可用策略列表"""
    try:
        from strategies.registry import get_registry

        registry = get_registry()
        return list(registry._strategies.keys())
    except Exception:
        return ["bigedualma"]


def get_available_symbols() -> List[str]:
    """獲取可用幣種列表"""
    try:
        from data.paths import get_data_root

        data_root = get_data_root()
        ohlcv_path = data_root / "binance" / "4h"
        if ohlcv_path.exists():
            symbols = [f.stem for f in ohlcv_path.glob("*.parquet")]
            return sorted(symbols)
    except Exception:
        pass
    # 預設幣種列表
    return [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "DOTUSDT",
        "LTCUSDT",
        "ATOMUSDT",
        "UNIUSDT",
        "ETCUSDT",
        "XLMUSDT",
        "FILUSDT",
        "AAVEUSDT",
        "NEARUSDT",
        "APTUSDT",
        "OPUSDT",
    ]


# ===== 1. 數據管理 =====


def menu_data_management():
    """數據管理子選單"""
    while True:
        clear_screen()
        print("\n" + "=" * 50)
        print("        數據管理")
        print("=" * 50)
        print()
        print("  1. 下載歷史數據")
        print("  2. 檢查數據完整性")
        print("  3. 查看可用數據")
        print()
        print("  0. 返回主選單")
        print()

        choice = input("請選擇 [0-3]: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            download_data()
        elif choice == "2":
            check_data_integrity()
        elif choice == "3":
            show_available_data()
        else:
            print("無效選項，請重新選擇")
            input("按 Enter 繼續...")


def download_data():
    """下載歷史數據"""
    print("\n=== 下載歷史數據 ===\n")
    print("此功能將調用現有的數據下載腳本。")
    print()

    # 顯示可用選項
    print("可用時間週期: 1h, 4h, 1d")
    timeframe = input("請選擇時間週期 [4h]: ").strip() or "4h"

    # 幣種選擇
    print("\n幣種選擇:")
    print("  1. Top 10 幣種")
    print("  2. Top 20 幣種")
    print("  3. 全部主流幣種")
    print("  4. 自訂（輸入幣種代碼）")

    symbol_choice = input("請選擇 [2]: ").strip() or "2"

    top_10 = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "DOTUSDT",
    ]
    top_20 = top_10 + [
        "LTCUSDT",
        "ATOMUSDT",
        "UNIUSDT",
        "ETCUSDT",
        "XLMUSDT",
        "FILUSDT",
        "AAVEUSDT",
        "NEARUSDT",
        "APTUSDT",
        "OPUSDT",
    ]

    if symbol_choice == "1":
        symbols = top_10
    elif symbol_choice == "2":
        symbols = top_20
    elif symbol_choice == "3":
        symbols = top_20  # 可擴展
    elif symbol_choice == "4":
        custom = input("請輸入幣種代碼（逗號分隔）: ")
        symbols = [s.strip().upper() for s in custom.split(",")]
    else:
        symbols = top_20

    print(f"\n將下載 {len(symbols)} 個幣種的 {timeframe} 數據")
    confirm = input("確認? [Y/n]: ").strip().lower()

    if confirm != "n":
        print("\n開始下載...")
        try:
            from data.download import download_symbols

            download_symbols(symbols, timeframe)
            print("\n下載完成！")
        except ImportError:
            print("\n找不到下載模組，請手動執行數據下載腳本。")
        except Exception as e:
            print(f"\n下載失敗: {e}")

    input("\n按 Enter 繼續...")


def check_data_integrity():
    """檢查數據完整性"""
    print("\n=== 檢查數據完整性 ===\n")

    try:
        from data.paths import get_data_root

        data_root = get_data_root()

        # 檢查各時間週期的數據
        for tf in ["1h", "4h", "1d"]:
            ohlcv_path = data_root / "binance" / tf
            if ohlcv_path.exists():
                files = list(ohlcv_path.glob("*.parquet"))
                print(f"  {tf}: {len(files)} 個幣種")
            else:
                print(f"  {tf}: 無數據")

    except Exception as e:
        print(f"檢查失敗: {e}")

    input("\n按 Enter 繼續...")


def show_available_data():
    """顯示可用數據"""
    print("\n=== 可用數據 ===\n")

    symbols = get_available_symbols()
    print(f"共 {len(symbols)} 個幣種:\n")

    # 每行顯示 5 個
    for i in range(0, len(symbols), 5):
        row = symbols[i : i + 5]
        print("  " + "  ".join(f"{s:<12}" for s in row))

    input("\n按 Enter 繼續...")


# ===== 2. 快速回測 =====


def menu_quick_backtest():
    """快速回測"""
    clear_screen()
    print("\n" + "=" * 50)
    print("        快速回測")
    print("=" * 50)
    print()

    # Step 1: 選擇策略
    strategies = get_available_strategies()
    print("[步驟 1/4] 選擇策略")
    print("-" * 30)
    for i, s in enumerate(strategies, 1):
        print(f"  {i}. {s}")
    print()

    try:
        choice = int(input(f"請選擇 [1-{len(strategies)}]: ").strip() or "1")
        strategy = strategies[choice - 1]
    except (ValueError, IndexError):
        strategy = strategies[0]

    # Step 2: 選擇幣種
    print(f"\n[步驟 2/4] 選擇幣種（已選策略: {strategy}）")
    print("-" * 30)
    print("  1. 單一幣種")
    print("  2. Top 10 幣種")
    print("  3. Top 20 幣種")
    print()

    symbol_choice = input("請選擇 [1]: ").strip() or "1"

    if symbol_choice == "1":
        symbol = input("請輸入幣種 [BTCUSDT]: ").strip().upper() or "BTCUSDT"
        symbols = [symbol]
    elif symbol_choice == "2":
        symbols = get_available_symbols()[:10]
    else:
        symbols = get_available_symbols()[:20]

    # Step 3: 時間範圍
    print(f"\n[步驟 3/4] 設定時間範圍")
    print("-" * 30)
    start = input("開始日期 [2024-01-01]: ").strip() or "2024-01-01"
    end = input("結束日期 [2025-12-01]: ").strip() or "2025-12-01"

    # Step 4: 回測參數
    print(f"\n[步驟 4/4] 設定回測參數")
    print("-" * 30)
    leverage = input("槓桿倍數 [10]: ").strip() or "10"
    initial_cash = input("初始資金 [500]: ").strip() or "500"

    try:
        leverage = int(leverage)
        initial_cash = float(initial_cash)
    except ValueError:
        leverage = 10
        initial_cash = 500

    # 確認
    print(f"\n=== 確認設定 ===")
    print(f"  策略: {strategy}")
    print(f"  幣種: {len(symbols)} 個")
    print(f"  時間: {start} ~ {end}")
    print(f"  槓桿: {leverage}x")
    print(f"  資金: {initial_cash}")

    confirm = input("\n開始執行? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    # 執行回測
    print("\n" + "=" * 50)
    print("開始回測...")
    print("=" * 50 + "\n")

    try:
        from execution.runner import RunConfig, run_portfolio

        configs = []
        for symbol in symbols:
            config = RunConfig(
                strategy=strategy,
                symbol=symbol,
                timeframe="4h",
                start=start,
                end=end,
                initial_cash=initial_cash,
                leverage=leverage,
                fee_rate=0.0005,
                strategy_params={"leverage": leverage},
            )
            configs.append(config)

        result = run_portfolio(configs, verbose=True)

        # 顯示結果摘要
        print("\n" + "=" * 50)
        print("回測結果摘要")
        print("=" * 50)
        print(result.summary())

        # 顯示排行榜
        df = result.to_dataframe()
        if not df.empty:
            print("\n=== 收益排行榜 (Top 10) ===\n")
            df_sorted = df.sort_values("total_return", ascending=False).head(10)
            for _, row in df_sorted.iterrows():
                ret = row.get("total_return", 0)
                if ret is not None:
                    print(f"  {row['symbol']}: {ret:+.2%}")

    except Exception as e:
        print(f"\n回測失敗: {e}")
        import traceback

        traceback.print_exc()

    input("\n按 Enter 繼續...")


# ===== 3. 參數優化 =====


def menu_optimization():
    """參數優化子選單"""
    while True:
        clear_screen()
        print("\n" + "=" * 50)
        print("        參數優化")
        print("=" * 50)
        print()
        print("  1. Walk-Forward 驗證 (推薦)")
        print("  2. 網格搜索")
        print("  3. 查看可優化參數")
        print()
        print("  0. 返回主選單")
        print()

        choice = input("請選擇 [0-3]: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            run_walk_forward()
        elif choice == "2":
            run_grid_search()
        elif choice == "3":
            show_optimizable_params()
        else:
            print("無效選項，請重新選擇")
            input("按 Enter 繼續...")


def run_walk_forward():
    """執行 Walk-Forward 驗證"""
    print("\n=== Walk-Forward 驗證 ===\n")

    # 選擇策略
    strategies = get_available_strategies()
    print("可用策略:")
    for i, s in enumerate(strategies, 1):
        print(f"  {i}. {s}")

    try:
        choice = int(input(f"\n請選擇策略 [1]: ").strip() or "1")
        strategy = strategies[choice - 1]
    except (ValueError, IndexError):
        strategy = strategies[0]

    # 選擇幣種
    symbol = input("選擇幣種 [BTCUSDT]: ").strip().upper() or "BTCUSDT"

    # 時間設定
    start = input("開始日期 [2023-01-01]: ").strip() or "2023-01-01"
    end = input("結束日期 [2025-12-01]: ").strip() or "2025-12-01"

    # WF 參數
    train_months = input("訓練期（月）[6]: ").strip() or "6"
    test_months = input("測試期（月）[2]: ").strip() or "2"

    try:
        train_months = int(train_months)
        test_months = int(test_months)
    except ValueError:
        train_months = 6
        test_months = 2

    print(f"\n設定:")
    print(f"  策略: {strategy}")
    print(f"  幣種: {symbol}")
    print(f"  時間: {start} ~ {end}")
    print(f"  訓練期: {train_months} 個月")
    print(f"  測試期: {test_months} 個月")

    confirm = input("\n開始執行? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    print("\n執行中，請稍候...\n")

    try:
        from execution.walk_forward import WalkForwardValidator, WFConfig

        config = WFConfig(
            train_months=train_months,
            test_months=test_months,
            metric="total_return",
            max_combinations=100,
        )

        validator = WalkForwardValidator(strategy, config)
        result = validator.run(symbol, "4h", start, end)

        # 顯示結果
        print("\n" + "=" * 50)
        print("Walk-Forward 驗證結果")
        print("=" * 50)
        print(result.to_report())

    except Exception as e:
        print(f"\n執行失敗: {e}")
        import traceback

        traceback.print_exc()

    input("\n按 Enter 繼續...")


def run_grid_search():
    """執行網格搜索"""
    print("\n=== 網格搜索 ===\n")
    print("此功能開發中...")
    input("\n按 Enter 繼續...")


def show_optimizable_params():
    """顯示可優化參數"""
    print("\n=== 可優化參數 ===\n")

    strategies = get_available_strategies()
    print("可用策略:")
    for i, s in enumerate(strategies, 1):
        print(f"  {i}. {s}")

    try:
        choice = int(input(f"\n請選擇策略 [1]: ").strip() or "1")
        strategy_name = strategies[choice - 1]
    except (ValueError, IndexError):
        strategy_name = strategies[0]

    try:
        from strategies.base import OptimizableStrategyMixin
        from strategies.registry import get_registry

        registry = get_registry()
        strategy_cls = registry.get_strategy(strategy_name)

        if hasattr(strategy_cls, "get_params_summary"):
            print()
            print(strategy_cls.get_params_summary())
        elif hasattr(strategy_cls, "OPTIMIZABLE_PARAMS"):
            print(f"\n{strategy_name} 的可優化參數:\n")
            for name, spec in strategy_cls.OPTIMIZABLE_PARAMS.items():
                default = spec.get("default", "N/A")
                desc = spec.get("description", "")
                range_spec = spec.get("range")
                if range_spec:
                    print(f"  {name}: {default} ({range_spec[0]}~{range_spec[1]}) - {desc}")
                else:
                    print(f"  {name}: {default} - {desc}")
        else:
            print(f"\n{strategy_name} 沒有定義可優化參數")

    except Exception as e:
        print(f"\n獲取參數失敗: {e}")

    input("\n按 Enter 繼續...")


# ===== 4. 查看報告 =====


def menu_reports():
    """查看報告子選單"""
    clear_screen()
    print("\n" + "=" * 50)
    print("        查看報告")
    print("=" * 50)
    print()
    print("此功能開發中...")
    print()
    print("未來將支援:")
    print("  - 最近回測結果查看")
    print("  - 歷史優化報告")
    print("  - 性能對比分析")
    print()

    input("按 Enter 返回主選單...")


# ===== 5. 系統設定 =====


def menu_settings():
    """系統設定子選單"""
    clear_screen()
    print("\n" + "=" * 50)
    print("        系統設定")
    print("=" * 50)
    print()

    try:
        from data.paths import get_data_root

        data_root = get_data_root()
        print(f"  數據路徑: {data_root}")
    except Exception:
        print("  數據路徑: 未設定")

    print(f"  Python: {sys.version.split()[0]}")
    print(f"  專案路徑: {PROJECT_ROOT}")
    print()

    input("按 Enter 返回主選單...")


# ===== 主程式 =====


def main():
    """主程式入口"""
    while True:
        clear_screen()
        print_banner()
        print_main_menu()

        choice = input("請選擇 [0-5]: ").strip()

        if choice == "0":
            print("\n感謝使用 SuperDog Quant，再見！\n")
            break
        elif choice == "1":
            menu_data_management()
        elif choice == "2":
            menu_quick_backtest()
        elif choice == "3":
            menu_optimization()
        elif choice == "4":
            menu_reports()
        elif choice == "5":
            menu_settings()
        else:
            print("無效選項，請重新選擇")
            input("按 Enter 繼續...")


if __name__ == "__main__":
    main()
