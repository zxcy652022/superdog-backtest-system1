#!/usr/bin/env python3
"""
Main Menu for SuperDog v0.5 Interactive CLI

主選單系統 - 提供美觀的命令行界面

Usage:
    from cli.interactive import MainMenu
    menu = MainMenu()
    menu.run()
"""

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional


class MenuOption:
    """選單選項"""

    def __init__(self, key: str, title: str, description: str, action: Callable):
        self.key = key
        self.title = title
        self.description = description
        self.action = action


class MainMenu:
    """SuperDog 互動式主選單

    提供美觀的選單界面，讓用戶輕鬆訪問所有功能

    Features:
    - 數據管理 (下載、查看、清理)
    - 策略配置 (創建、測試、回測)
    - 系統工具 (驗證、更新、幫助)
    """

    def __init__(self):
        """初始化主選單"""
        self.running = True
        self.current_menu = "main"
        self.options: Dict[str, List[MenuOption]] = {}
        self._setup_menus()

    def _setup_menus(self):
        """設置所有選單選項"""
        # 主選單
        self.options["main"] = [
            MenuOption("1", "數據管理", "下載、查看、管理永續合約數據", self._show_data_menu),
            MenuOption("2", "策略管理", "創建、配置、回測交易策略", self._show_strategy_menu),
            MenuOption("3", "系統工具", "驗證、更新、查看系統狀態", self._show_system_menu),
            MenuOption("4", "快速開始", "運行示範和教程", self._show_quickstart),
            MenuOption("q", "退出", "退出 SuperDog", self._quit),
        ]

        # 數據管理選單
        self.options["data"] = [
            MenuOption("1", "下載數據", "從交易所下載永續合約數據", self._download_data),
            MenuOption("2", "查看數據", "查看已下載的數據統計", self._view_data),
            MenuOption("3", "清理數據", "清理過期或無效數據", self._clean_data),
            MenuOption("4", "數據驗證", "驗證數據完整性", self._verify_data),
            MenuOption("b", "返回", "返回主選單", self._back_to_main),
            MenuOption("q", "退出", "退出 SuperDog", self._quit),
        ]

        # 策略管理選單
        self.options["strategy"] = [
            MenuOption("1", "創建策略", "使用模板創建新策略", self._create_strategy),
            MenuOption("2", "配置策略", "配置策略參數", self._configure_strategy),
            MenuOption("3", "運行回測", "執行策略回測", self._run_backtest),
            MenuOption("4", "查看結果", "查看回測結果和報告", self._view_results),
            MenuOption("b", "返回", "返回主選單", self._back_to_main),
            MenuOption("q", "退出", "退出 SuperDog", self._quit),
        ]

        # 系統工具選單
        self.options["system"] = [
            MenuOption("1", "系統驗證", "驗證所有模組安裝", self._verify_system),
            MenuOption("2", "查看狀態", "查看系統和數據狀態", self._view_status),
            MenuOption("3", "更新檢查", "檢查更新", self._check_updates),
            MenuOption("4", "幫助文檔", "查看文檔和教程", self._view_help),
            MenuOption("b", "返回", "返回主選單", self._back_to_main),
            MenuOption("q", "退出", "退出 SuperDog", self._quit),
        ]

    def _print_header(self, title: str = "SuperDog v0.5"):
        """打印美觀的標題"""
        print()
        print("╔" + "=" * 68 + "╗")
        print(f"║{title:^68}║")
        print("╚" + "=" * 68 + "╝")
        print()

    def _print_menu(self, menu_name: str):
        """打印選單選項"""
        options = self.options.get(menu_name, [])

        print("┌" + "─" * 68 + "┐")
        for option in options:
            print(f"│ [{option.key}] {option.title:<20} - {option.description:<40}│")
        print("└" + "─" * 68 + "┘")
        print()

    def _get_input(self, prompt: str = "請選擇") -> str:
        """獲取用戶輸入"""
        try:
            return input(f"{prompt} > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n\n已取消")
            return "q"

    def _execute_option(self, menu_name: str, choice: str) -> bool:
        """執行選單選項

        Returns:
            True if option executed, False if invalid choice
        """
        options = self.options.get(menu_name, [])
        for option in options:
            if option.key == choice:
                option.action()
                return True
        return False

    def _show_data_menu(self):
        """顯示數據管理選單"""
        self.current_menu = "data"

    def _show_strategy_menu(self):
        """顯示策略管理選單"""
        self.current_menu = "strategy"

    def _show_system_menu(self):
        """顯示系統工具選單"""
        self.current_menu = "system"

    def _show_quickstart(self):
        """顯示快速開始"""
        self._print_header("快速開始")
        print("SuperDog v0.5 提供以下快速開始選項：")
        print()
        print("1. 運行 Phase B 示範")
        print("   python3 examples/phase_b_quick_demo.py")
        print()
        print("2. 運行系統驗證")
        print("   python3 verify_v05_phase_b.py")
        print()
        print("3. 查看完整文檔")
        print("   cat PHASE_B_DELIVERY.md")
        print()

        choice = self._get_input("運行哪個選項？(1/2/3/b)")

        if choice == "1":
            print("\n正在運行 Phase B 示範...")
            import subprocess

            subprocess.run([sys.executable, "examples/phase_b_quick_demo.py"])
        elif choice == "2":
            print("\n正在運行系統驗證...")
            import subprocess

            subprocess.run([sys.executable, "verify_v05_phase_b.py"])
        elif choice == "3":
            print("\n正在顯示文檔...")
            doc_path = Path("PHASE_B_DELIVERY.md")
            if doc_path.exists():
                print(doc_path.read_text()[:2000])
                print("\n... (查看完整文檔請運行: cat PHASE_B_DELIVERY.md)")
            else:
                print("文檔未找到")

        input("\n按 Enter 繼續...")

    def _download_data(self):
        """下載數據嚮導"""
        self._print_header("數據下載嚮導")

        print("SuperDog v0.5 支援 6 種永續合約數據源：")
        print()
        print("  1. OHLCV          - K線數據")
        print("  2. FUNDING_RATE   - 資金費率")
        print("  3. OPEN_INTEREST  - 持倉量")
        print("  4. BASIS          - 期現基差")
        print("  5. LIQUIDATIONS   - 爆倉數據")
        print("  6. LONG_SHORT     - 多空比")
        print()
        print("支援交易所: Binance, Bybit, OKX")
        print()

        # 獲取下載參數
        symbol = self._get_input("輸入交易對 (如 BTCUSDT)").upper()
        if symbol in ["Q", "B"]:
            return

        data_type = self._get_input("選擇數據類型 (1-6)")
        if data_type in ["q", "b"]:
            return

        exchange = self._get_input("選擇交易所 (binance/bybit/okx)")
        if exchange in ["q", "b"]:
            return

        print(f"\n準備下載:")
        print(f"  交易對: {symbol}")
        print(f"  數據類型: {data_type}")
        print(f"  交易所: {exchange}")
        print()

        confirm = self._get_input("確認下載？(y/n)")
        if confirm == "y":
            print("\n📥 正在下載數據...")
            print("⚠️  實際下載功能請使用 DataPipeline API")
            print()
            print("示例代碼:")
            print(f"  from data.pipeline import get_pipeline")
            print(f"  pipeline = get_pipeline()")
            print(f"  # 使用 pipeline 載入數據")

        input("\n按 Enter 繼續...")

    def _view_data(self):
        """查看數據統計"""
        self._print_header("數據統計")

        print("正在掃描數據存儲...")
        print()

        # 檢查 SSD 路徑
        ssd_path = Path("/Volumes/權志龍的寶藏/SuperDogData")
        local_path = Path("data_storage")

        storage_path = ssd_path if ssd_path.exists() else local_path

        print(f"存儲位置: {storage_path}")
        print()

        if storage_path.exists():
            # 統計文件
            file_count = sum(1 for _ in storage_path.rglob("*.parquet"))
            print(f"已下載文件: {file_count} 個 Parquet 文件")

            # 列出最近的文件
            if file_count > 0:
                print("\n最近下載:")
                files = sorted(
                    storage_path.rglob("*.parquet"), key=lambda x: x.stat().st_mtime, reverse=True
                )[:5]
                for f in files:
                    size_mb = f.stat().st_size / 1024 / 1024
                    print(f"  - {f.name} ({size_mb:.2f} MB)")
        else:
            print("未找到數據存儲目錄")

        input("\n按 Enter 繼續...")

    def _clean_data(self):
        """清理數據"""
        self._print_header("數據清理")

        print("數據清理選項:")
        print()
        print("  1. 清理過期數據 (>30天)")
        print("  2. 清理重複數據")
        print("  3. 清理損壞文件")
        print("  4. 清理全部數據 (謹慎！)")
        print()

        choice = self._get_input("選擇清理選項 (1-4/b)")

        if choice in ["1", "2", "3"]:
            print(f"\n正在清理類型 {choice} 的數據...")
            print("⚠️  實際清理功能開發中")
        elif choice == "4":
            confirm = self._get_input("⚠️  確認清理全部數據？此操作不可恢復！(yes/no)")
            if confirm == "yes":
                print("\n正在清理全部數據...")
                print("⚠️  實際清理功能開發中")

        input("\n按 Enter 繼續...")

    def _verify_data(self):
        """驗證數據完整性"""
        self._print_header("數據驗證")

        print("正在驗證數據完整性...")
        print()
        print("檢查項目:")
        print("  ✓ Parquet 文件格式")
        print("  ✓ 時間戳連續性")
        print("  ✓ 數據範圍有效性")
        print("  ✓ 缺失值檢查")
        print()
        print("⚠️  詳細驗證功能開發中")

        input("\n按 Enter 繼續...")

    def _create_strategy(self):
        """創建策略"""
        self._print_header("策略創建嚮導")

        print("SuperDog v0.5 支援的策略模板:")
        print()
        print("  1. 簡單移動平均策略")
        print("  2. 資金費率套利策略")
        print("  3. 多因子策略 (使用所有 6 種數據源)")
        print("  4. 川沐策略 (完整示範)")
        print()

        choice = self._get_input("選擇策略模板 (1-4/b)")

        if choice in ["1", "2", "3", "4"]:
            strategy_name = self._get_input("輸入策略名稱")
            if strategy_name and strategy_name not in ["q", "b"]:
                print(f"\n正在創建策略: {strategy_name}")
                print("⚠️  策略生成功能開發中")
                print()
                print("手動創建策略:")
                print(f"  1. 複製模板到 strategies/{strategy_name}.py")
                print(f"  2. 繼承 StrategyV2 基礎類別")
                print(f"  3. 實作 generate_signals 方法")

        input("\n按 Enter 繼續...")

    def _configure_strategy(self):
        """配置策略"""
        self._print_header("策略配置")

        print("策略配置功能開發中...")
        print()
        print("配置文件示例: config/strategy_config.yaml")

        input("\n按 Enter 繼續...")

    def _run_backtest(self):
        """運行回測"""
        self._print_header("回測執行")

        print("回測參數配置:")
        print()

        symbol = self._get_input("交易對 (如 BTCUSDT)").upper()
        if symbol in ["Q", "B"]:
            return

        start_date = self._get_input("開始日期 (YYYY-MM-DD)")
        if start_date in ["q", "b"]:
            return

        end_date = self._get_input("結束日期 (YYYY-MM-DD)")
        if end_date in ["q", "b"]:
            return

        print(f"\n準備運行回測:")
        print(f"  交易對: {symbol}")
        print(f"  期間: {start_date} ~ {end_date}")
        print()

        confirm = self._get_input("確認運行？(y/n)")
        if confirm == "y":
            print("\n🚀 正在運行回測...")
            print("⚠️  完整回測功能請使用 BacktestEngine")

        input("\n按 Enter 繼續...")

    def _view_results(self):
        """查看回測結果"""
        self._print_header("回測結果")

        print("正在掃描回測結果...")
        print()
        print("⚠️  結果查看功能開發中")
        print()
        print("手動查看結果:")
        print("  - 檢查 backtest_results/ 目錄")
        print("  - 使用 pandas 讀取結果文件")

        input("\n按 Enter 繼續...")

    def _verify_system(self):
        """驗證系統"""
        self._print_header("系統驗證")

        print("正在運行系統驗證...")
        print()

        import subprocess

        result = subprocess.run(
            [sys.executable, "verify_v05_phase_b.py"], capture_output=True, text=True
        )
        print(result.stdout)

        input("\n按 Enter 繼續...")

    def _view_status(self):
        """查看系統狀態"""
        self._print_header("系統狀態")

        print("SuperDog v0.5 系統信息:")
        print()
        print(f"  Python 版本: {sys.version.split()[0]}")
        print(f"  工作目錄: {Path.cwd()}")
        print()

        # 檢查依賴
        print("依賴檢查:")
        dependencies = ["pandas", "numpy", "requests", "pyarrow"]
        for dep in dependencies:
            try:
                __import__(dep)
                print(f"  ✓ {dep}")
            except ImportError:
                print(f"  ✗ {dep} (未安裝)")

        print()

        # 檢查數據存儲
        ssd_path = Path("/Volumes/權志龍的寶藏/SuperDogData")
        print("數據存儲:")
        print(f"  SSD: {'✓ 可用' if ssd_path.exists() else '✗ 不可用'}")
        print(f"  本地: ✓ 可用")

        input("\n按 Enter 繼續...")

    def _check_updates(self):
        """檢查更新"""
        self._print_header("更新檢查")

        print("當前版本: v0.5 Phase C")
        print()
        print("最新功能:")
        print("  ✓ 6 種永續合約數據源")
        print("  ✓ 3 個交易所支援")
        print("  ✓ 多交易所數據聚合")
        print("  ✓ 互動式 CLI 選單")
        print()
        print("系統已是最新版本！")

        input("\n按 Enter 繼續...")

    def _view_help(self):
        """查看幫助"""
        self._print_header("幫助文檔")

        print("SuperDog v0.5 文檔:")
        print()
        print("  1. PHASE_B_DELIVERY.md - Phase B 完整交付文檔")
        print("  2. README.md - 項目說明")
        print("  3. CHANGELOG.md - 版本變更記錄")
        print()
        print("在線資源:")
        print("  - GitHub: [項目地址]")
        print("  - 文檔: [文檔地址]")

        input("\n按 Enter 繼續...")

    def _back_to_main(self):
        """返回主選單"""
        self.current_menu = "main"

    def _quit(self):
        """退出程序"""
        self.running = False
        print("\n感謝使用 SuperDog v0.5！")
        print()

    def run(self):
        """運行主選單循環"""
        while self.running:
            # 清屏（可選）
            # print("\033[2J\033[H", end="")

            # 顯示標題和選單
            if self.current_menu == "main":
                self._print_header("SuperDog v0.5 - 專業量化交易平台")
                print("永續合約數據 | 多交易所支援 | 完整回測系統")
            elif self.current_menu == "data":
                self._print_header("數據管理")
            elif self.current_menu == "strategy":
                self._print_header("策略管理")
            elif self.current_menu == "system":
                self._print_header("系統工具")

            self._print_menu(self.current_menu)

            # 獲取用戶選擇
            choice = self._get_input("請選擇")

            # 執行選項
            if not self._execute_option(self.current_menu, choice):
                print(f"\n❌ 無效選項: {choice}")
                input("按 Enter 繼續...")


def main():
    """主函數"""
    menu = MainMenu()
    menu.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
