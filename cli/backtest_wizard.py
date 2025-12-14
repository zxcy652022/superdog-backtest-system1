#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperDog Quant v1.0 - Backtest Configuration Wizard

互動式回測設定精靈，引導用戶完成回測配置

Features:
- Step-by-step 配置流程
- 策略參數自動載入
- 預設值與智能建議
- 配置驗證與確認

Usage:
    from cli.backtest_wizard import BacktestWizard
    wizard = BacktestWizard()
    config = wizard.run()
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 確保專案根目錄在 path 中
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class WizardConfig:
    """精靈生成的回測配置"""

    # 基本設定
    strategy: str = ""
    symbols: List[str] = field(default_factory=list)
    timeframe: str = "4h"
    start_date: str = ""
    end_date: str = ""

    # 資金設定
    initial_cash: float = 500.0
    leverage: int = 10
    fee_rate: float = 0.0005

    # v1.0 新增
    slippage_rate: Optional[float] = None
    maintenance_margin_rate: float = 0.005

    # 策略參數
    strategy_params: Dict[str, Any] = field(default_factory=dict)

    # 優化設定
    run_optimization: bool = False
    optimization_method: str = "walk_forward"  # walk_forward | grid
    train_months: int = 6
    test_months: int = 2

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "strategy": self.strategy,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "leverage": self.leverage,
            "fee_rate": self.fee_rate,
            "slippage_rate": self.slippage_rate,
            "maintenance_margin_rate": self.maintenance_margin_rate,
            "strategy_params": self.strategy_params,
            "run_optimization": self.run_optimization,
            "optimization_method": self.optimization_method,
            "train_months": self.train_months,
            "test_months": self.test_months,
        }


def clear_screen():
    """清除螢幕"""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str, width: int = 60):
    """打印標題"""
    print()
    print("=" * width)
    print(f"{title:^{width}}")
    print("=" * width)
    print()


def print_step(step: int, total: int, title: str):
    """打印步驟標題"""
    print()
    print(f"[步驟 {step}/{total}] {title}")
    print("-" * 40)


def get_input(prompt: str, default: str = "") -> str:
    """獲取用戶輸入"""
    if default:
        display = f"{prompt} [{default}]: "
    else:
        display = f"{prompt}: "

    try:
        value = input(display).strip()
        return value if value else default
    except (KeyboardInterrupt, EOFError):
        print("\n已取消")
        return ""


def get_number_input(
    prompt: str, default: float, min_val: float = None, max_val: float = None
) -> float:
    """獲取數字輸入"""
    while True:
        value_str = get_input(prompt, str(default))
        try:
            value = float(value_str)
            if min_val is not None and value < min_val:
                print(f"  數值不能小於 {min_val}")
                continue
            if max_val is not None and value > max_val:
                print(f"  數值不能大於 {max_val}")
                continue
            return value
        except ValueError:
            print("  請輸入有效數字")


def get_choice(options: List[Tuple[str, str]], prompt: str = "請選擇", default: str = "1") -> str:
    """獲取選項輸入

    Args:
        options: [(value, description), ...]
        prompt: 提示文字
        default: 預設選項編號

    Returns:
        選中的 value
    """
    for i, (value, desc) in enumerate(options, 1):
        print(f"  {i}. {desc}")
    print()

    while True:
        choice = get_input(prompt, default)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        print("  無效選項，請重新選擇")


class BacktestWizard:
    """回測設定精靈"""

    TOTAL_STEPS = 6

    # 預設幣種列表
    TOP_10_SYMBOLS = [
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

    TOP_20_SYMBOLS = TOP_10_SYMBOLS + [
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

    # 預設時間週期
    TIMEFRAMES = [
        ("1h", "1 小時"),
        ("4h", "4 小時 (推薦)"),
        ("1d", "1 天"),
    ]

    def __init__(self):
        """初始化精靈"""
        self.config = WizardConfig()
        self._available_strategies = None
        self._available_symbols = None

    def get_available_strategies(self) -> List[str]:
        """獲取可用策略列表"""
        if self._available_strategies is None:
            try:
                from strategies.registry import get_registry

                registry = get_registry()
                self._available_strategies = list(registry._strategies.keys())
            except Exception:
                self._available_strategies = ["bigedualma"]
        return self._available_strategies

    def get_available_symbols(self) -> List[str]:
        """獲取可用幣種列表（從數據目錄）"""
        if self._available_symbols is None:
            try:
                from data.paths import get_data_root

                data_root = get_data_root()
                ohlcv_path = data_root / "binance" / "4h"
                if ohlcv_path.exists():
                    self._available_symbols = sorted([f.stem for f in ohlcv_path.glob("*.parquet")])
            except Exception:
                pass

            if not self._available_symbols:
                self._available_symbols = self.TOP_20_SYMBOLS

        return self._available_symbols

    def get_strategy_params(self, strategy_name: str) -> Dict[str, Dict]:
        """獲取策略的可優化參數定義"""
        try:
            from strategies.registry import get_registry

            registry = get_registry()
            strategy_cls = registry.get_strategy(strategy_name)

            if hasattr(strategy_cls, "OPTIMIZABLE_PARAMS"):
                return strategy_cls.OPTIMIZABLE_PARAMS
        except Exception:
            pass
        return {}

    def run(self) -> Optional[WizardConfig]:
        """執行精靈"""
        clear_screen()
        print_header("SuperDog v1.0 - 回測設定精靈")

        print("歡迎使用回測設定精靈！")
        print("此精靈將引導您完成回測配置。")
        print()
        print("提示：")
        print("  - 按 Enter 使用預設值")
        print("  - 輸入 q 取消精靈")
        print()

        input("按 Enter 開始...")

        # Step 1: 選擇策略
        if not self._step_strategy():
            return None

        # Step 2: 選擇幣種
        if not self._step_symbols():
            return None

        # Step 3: 時間範圍
        if not self._step_time_range():
            return None

        # Step 4: 資金設定
        if not self._step_capital():
            return None

        # Step 5: 策略參數
        if not self._step_strategy_params():
            return None

        # Step 6: 優化設定
        if not self._step_optimization():
            return None

        # 確認設定
        if self._confirm_config():
            return self.config

        return None

    def _step_strategy(self) -> bool:
        """Step 1: 選擇策略"""
        clear_screen()
        print_header("回測設定精靈")
        print_step(1, self.TOTAL_STEPS, "選擇策略")

        strategies = self.get_available_strategies()

        if not strategies:
            print("錯誤：沒有可用的策略")
            return False

        options = [(s, s) for s in strategies]
        self.config.strategy = get_choice(options, "請選擇策略", "1")

        if self.config.strategy == "q":
            return False

        print(f"\n已選擇策略: {self.config.strategy}")
        input("\n按 Enter 繼續...")
        return True

    def _step_symbols(self) -> bool:
        """Step 2: 選擇幣種"""
        clear_screen()
        print_header("回測設定精靈")
        print_step(2, self.TOTAL_STEPS, "選擇幣種")

        options = [
            ("single", "單一幣種"),
            ("top10", "Top 10 幣種"),
            ("top20", "Top 20 幣種"),
            ("all", "所有可用幣種"),
            ("custom", "自訂幣種列表"),
        ]

        choice = get_choice(options, "請選擇", "1")

        if choice == "q":
            return False

        if choice == "single":
            symbol = get_input("請輸入幣種", "BTCUSDT").upper()
            if symbol == "Q":
                return False
            self.config.symbols = [symbol]

        elif choice == "top10":
            self.config.symbols = self.TOP_10_SYMBOLS.copy()

        elif choice == "top20":
            self.config.symbols = self.TOP_20_SYMBOLS.copy()

        elif choice == "all":
            self.config.symbols = self.get_available_symbols()

        elif choice == "custom":
            custom = get_input("請輸入幣種（逗號分隔）", "BTCUSDT,ETHUSDT")
            if custom.upper() == "Q":
                return False
            self.config.symbols = [s.strip().upper() for s in custom.split(",")]

        print(f"\n已選擇 {len(self.config.symbols)} 個幣種:")
        for i in range(0, len(self.config.symbols), 5):
            row = self.config.symbols[i : i + 5]
            print("  " + "  ".join(f"{s:<12}" for s in row))

        input("\n按 Enter 繼續...")
        return True

    def _step_time_range(self) -> bool:
        """Step 3: 時間範圍"""
        clear_screen()
        print_header("回測設定精靈")
        print_step(3, self.TOTAL_STEPS, "設定時間範圍")

        # 時間週期
        print("選擇時間週期:")
        self.config.timeframe = get_choice(self.TIMEFRAMES, "請選擇", "2")

        if self.config.timeframe == "q":
            return False

        print()

        # 預設日期範圍
        today = datetime.now().strftime("%Y-%m-%d")
        default_start = "2024-01-01"
        default_end = today

        # 快速選項
        print("選擇時間範圍:")
        range_options = [
            ("2024", "2024 年至今"),
            ("2023", "2023 年至今"),
            ("1year", "最近 1 年"),
            ("2year", "最近 2 年"),
            ("custom", "自訂日期"),
        ]

        range_choice = get_choice(range_options, "請選擇", "1")

        if range_choice == "q":
            return False

        if range_choice == "2024":
            self.config.start_date = "2024-01-01"
            self.config.end_date = today
        elif range_choice == "2023":
            self.config.start_date = "2023-01-01"
            self.config.end_date = today
        elif range_choice == "1year":
            from datetime import timedelta

            start = datetime.now() - timedelta(days=365)
            self.config.start_date = start.strftime("%Y-%m-%d")
            self.config.end_date = today
        elif range_choice == "2year":
            from datetime import timedelta

            start = datetime.now() - timedelta(days=730)
            self.config.start_date = start.strftime("%Y-%m-%d")
            self.config.end_date = today
        else:
            self.config.start_date = get_input("開始日期 (YYYY-MM-DD)", default_start)
            if self.config.start_date.upper() == "Q":
                return False
            self.config.end_date = get_input("結束日期 (YYYY-MM-DD)", default_end)
            if self.config.end_date.upper() == "Q":
                return False

        print(f"\n已設定時間範圍:")
        print(f"  時間週期: {self.config.timeframe}")
        print(f"  開始日期: {self.config.start_date}")
        print(f"  結束日期: {self.config.end_date}")

        input("\n按 Enter 繼續...")
        return True

    def _step_capital(self) -> bool:
        """Step 4: 資金設定"""
        clear_screen()
        print_header("回測設定精靈")
        print_step(4, self.TOTAL_STEPS, "設定資金與風險")

        # 初始資金
        print("設定初始資金:")
        cash_options = [
            ("100", "$100 (小額測試)"),
            ("500", "$500 (推薦)"),
            ("1000", "$1,000"),
            ("5000", "$5,000"),
            ("custom", "自訂金額"),
        ]

        cash_choice = get_choice(cash_options, "請選擇", "2")

        if cash_choice == "q":
            return False

        if cash_choice == "custom":
            self.config.initial_cash = get_number_input("初始資金 ($)", 500, min_val=10)
        else:
            self.config.initial_cash = float(cash_choice)

        print()

        # 槓桿
        print("設定槓桿倍數:")
        leverage_options = [
            ("5", "5x (保守)"),
            ("10", "10x (推薦)"),
            ("20", "20x (激進)"),
            ("custom", "自訂槓桿"),
        ]

        lev_choice = get_choice(leverage_options, "請選擇", "2")

        if lev_choice == "q":
            return False

        if lev_choice == "custom":
            self.config.leverage = int(get_number_input("槓桿倍數", 10, min_val=1, max_val=125))
        else:
            self.config.leverage = int(lev_choice)

        print()

        # 手續費率
        print("設定手續費率:")
        fee_options = [
            ("0.0004", "0.04% (VIP 費率)"),
            ("0.0005", "0.05% (一般費率)"),
            ("0.001", "0.10% (保守估計)"),
        ]

        fee_choice = get_choice(fee_options, "請選擇", "2")

        if fee_choice == "q":
            return False

        self.config.fee_rate = float(fee_choice)

        print()

        # v1.0 滑點設定
        print("設定滑點模型 (v1.0 新增):")
        slip_options = [
            ("none", "無滑點（理想化）"),
            ("0.001", "0.10% (輕微滑點)"),
            ("0.002", "0.20% (一般滑點)"),
            ("0.005", "0.50% (高滑點)"),
        ]

        slip_choice = get_choice(slip_options, "請選擇", "1")

        if slip_choice == "q":
            return False

        if slip_choice == "none":
            self.config.slippage_rate = None
        else:
            self.config.slippage_rate = float(slip_choice)

        print(f"\n已設定資金配置:")
        print(f"  初始資金: ${self.config.initial_cash:,.0f}")
        print(f"  槓桿倍數: {self.config.leverage}x")
        print(f"  手續費率: {self.config.fee_rate:.4%}")
        print(
            f"  滑點模型: {self.config.slippage_rate:.4%}" if self.config.slippage_rate else "  滑點模型: 無"
        )

        input("\n按 Enter 繼續...")
        return True

    def _step_strategy_params(self) -> bool:
        """Step 5: 策略參數"""
        clear_screen()
        print_header("回測設定精靈")
        print_step(5, self.TOTAL_STEPS, "設定策略參數")

        # 獲取策略的可優化參數
        params_def = self.get_strategy_params(self.config.strategy)

        if not params_def:
            print(f"策略 {self.config.strategy} 沒有定義可優化參數")
            print("將使用策略預設值")

            # 設定基本參數
            self.config.strategy_params = {
                "leverage": self.config.leverage,
            }

            input("\n按 Enter 繼續...")
            return True

        print(f"策略 {self.config.strategy} 的可配置參數:\n")

        # 選擇配置方式
        config_options = [
            ("default", "使用預設值"),
            ("custom", "自訂參數值"),
        ]

        config_choice = get_choice(config_options, "請選擇", "1")

        if config_choice == "q":
            return False

        # 初始化參數
        self.config.strategy_params = {"leverage": self.config.leverage}

        if config_choice == "default":
            # 使用預設值
            for name, spec in params_def.items():
                default = spec.get("default")
                if default is not None:
                    self.config.strategy_params[name] = default
        else:
            # 自訂參數
            print("\n請設定各參數值（按 Enter 使用預設值）:\n")

            for name, spec in params_def.items():
                param_type = spec.get("type", "float")
                default = spec.get("default", 0)
                range_spec = spec.get("range")
                description = spec.get("description", "")

                # 顯示參數資訊
                print(f"  {name}: {description}")
                if range_spec:
                    print(f"    範圍: {range_spec[0]} ~ {range_spec[1]}")

                # 獲取輸入
                if param_type == "int":
                    value = int(get_number_input(f"    {name}", default))
                elif param_type == "float":
                    value = get_number_input(f"    {name}", default)
                elif param_type == "choice":
                    choices = spec.get("choices", [])
                    if choices:
                        print(f"    選項: {', '.join(str(c) for c in choices)}")
                        value_str = get_input(f"    {name}", str(default))
                        value = value_str if value_str in [str(c) for c in choices] else default
                    else:
                        value = default
                else:
                    value = default

                self.config.strategy_params[name] = value
                print()

        print("\n已設定策略參數:")
        for name, value in self.config.strategy_params.items():
            print(f"  {name}: {value}")

        input("\n按 Enter 繼續...")
        return True

    def _step_optimization(self) -> bool:
        """Step 6: 優化設定"""
        clear_screen()
        print_header("回測設定精靈")
        print_step(6, self.TOTAL_STEPS, "優化設定 (可選)")

        print("是否執行參數優化？")
        print()

        opt_options = [
            ("no", "不優化，直接回測"),
            ("wf", "Walk-Forward 驗證 (推薦)"),
            ("grid", "網格搜索"),
        ]

        opt_choice = get_choice(opt_options, "請選擇", "1")

        if opt_choice == "q":
            return False

        if opt_choice == "no":
            self.config.run_optimization = False
        else:
            self.config.run_optimization = True
            self.config.optimization_method = "walk_forward" if opt_choice == "wf" else "grid"

            if opt_choice == "wf":
                print("\nWalk-Forward 驗證設定:")
                self.config.train_months = int(get_number_input("訓練期（月）", 6, min_val=1, max_val=24))
                self.config.test_months = int(get_number_input("測試期（月）", 2, min_val=1, max_val=12))

        print(f"\n已設定優化方式:")
        if self.config.run_optimization:
            print(f"  方法: {self.config.optimization_method}")
            if self.config.optimization_method == "walk_forward":
                print(f"  訓練期: {self.config.train_months} 個月")
                print(f"  測試期: {self.config.test_months} 個月")
        else:
            print("  不執行優化")

        input("\n按 Enter 繼續...")
        return True

    def _confirm_config(self) -> bool:
        """確認配置"""
        clear_screen()
        print_header("回測設定精靈 - 確認")

        print("請確認您的回測配置:\n")
        print("-" * 50)

        print(f"\n策略: {self.config.strategy}")
        print(f"幣種: {len(self.config.symbols)} 個")
        if len(self.config.symbols) <= 5:
            print(f"       {', '.join(self.config.symbols)}")
        else:
            print(f"       {', '.join(self.config.symbols[:3])}...")

        print(f"\n時間週期: {self.config.timeframe}")
        print(f"時間範圍: {self.config.start_date} ~ {self.config.end_date}")

        print(f"\n初始資金: ${self.config.initial_cash:,.0f}")
        print(f"槓桿倍數: {self.config.leverage}x")
        print(f"手續費率: {self.config.fee_rate:.4%}")
        if self.config.slippage_rate:
            print(f"滑點模型: {self.config.slippage_rate:.4%}")

        print(f"\n策略參數:")
        for name, value in self.config.strategy_params.items():
            print(f"  {name}: {value}")

        if self.config.run_optimization:
            print(f"\n優化方式: {self.config.optimization_method}")
            if self.config.optimization_method == "walk_forward":
                print(f"  訓練期: {self.config.train_months} 月")
                print(f"  測試期: {self.config.test_months} 月")

        print("\n" + "-" * 50)

        confirm = get_input("\n確認執行? [Y/n]", "y").lower()
        return confirm != "n"


def run_wizard() -> Optional[WizardConfig]:
    """執行回測設定精靈（便捷函數）"""
    wizard = BacktestWizard()
    return wizard.run()


def main():
    """主程式入口"""
    config = run_wizard()

    if config:
        print("\n配置完成！")
        print("生成的配置:")
        import json

        print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
        return 0
    else:
        print("\n已取消")
        return 1


if __name__ == "__main__":
    sys.exit(main())
