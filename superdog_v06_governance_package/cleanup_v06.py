#!/usr/bin/env python3
"""
SuperDog v0.6 安全清理腳本

此腳本執行以下清理操作：
1. 備份和臨時檔案清理
2. 過時規格文檔歸檔
3. 空檔案處理
4. 版本一致性檢查

使用方式：
    python cleanup_v06.py --dry-run  # 預覽將要執行的操作
    python cleanup_v06.py --execute  # 實際執行清理

安全特性：
- 預設為 dry-run 模式
- 所有刪除操作先移動到 .trash/ 目錄
- 自動備份專案到 .backup/
- 詳細記錄所有操作
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


class SafeCleanup:
    """安全清理工具"""

    def __init__(self, root_dir: Path, dry_run: bool = True):
        self.root_dir = root_dir
        self.dry_run = dry_run
        self.trash_dir = root_dir / ".trash" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = root_dir / ".backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log = []

        if not dry_run:
            self.trash_dir.mkdir(parents=True, exist_ok=True)
            self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, action: str, path: str, reason: str = ""):
        """記錄操作"""
        entry = {
            "action": action,
            "path": path,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        self.log.append(entry)

        emoji = "🗑️" if action == "delete" else "📦" if action == "archive" else "✅"
        print(f"{emoji} {action.upper()}: {path}")
        if reason:
            print(f"   理由: {reason}")

    def safe_delete(self, file_path: Path, reason: str = ""):
        """安全刪除檔案（移動到 trash）"""
        if not file_path.exists():
            return

        self._log("delete", str(file_path.relative_to(self.root_dir)), reason)

        if not self.dry_run:
            target = self.trash_dir / file_path.relative_to(self.root_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(target))

    def safe_archive(self, source: Path, dest_relative: str, reason: str = ""):
        """安全歸檔（移動到 archive）"""
        if not source.exists():
            return

        self._log("archive", str(source.relative_to(self.root_dir)), reason)

        if not self.dry_run:
            dest = self.root_dir / dest_relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest))

    def backup_project(self):
        """備份整個專案"""
        print("\n📦 備份專案...")
        if not self.dry_run:
            # 只備份關鍵檔案和目錄
            important_items = [
                "strategies",
                "backtest",
                "execution_engine",
                "data",
                "risk_management",
                "cli",
                "tests",
                "README.md",
                "CHANGELOG.md",
                "requirements.txt",
            ]

            for item in important_items:
                source = self.root_dir / item
                if source.exists():
                    if source.is_file():
                        shutil.copy2(source, self.backup_dir / item)
                    else:
                        shutil.copytree(
                            source,
                            self.backup_dir / item,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                        )

            print(f"✅ 專案已備份到: {self.backup_dir}")

    def cleanup_backup_files(self):
        """清理備份和臨時檔案"""
        print("\n🗑️  清理備份和臨時檔案...")

        patterns = [
            ("data/storage.py.backup", "舊版備份檔案"),
            ("data/storage.txt", "臨時文本檔案"),
            ("data/fetcher.txt", "臨時文本檔案"),
            ("data/validator.txt", "臨時文本檔案"),
            ("data/新文字檔.txt", "中文臨時檔案（違反命名規範）"),
        ]

        for pattern, reason in patterns:
            file_path = self.root_dir / pattern
            if file_path.exists():
                self.safe_delete(file_path, reason)

    def archive_old_specs(self):
        """歸檔過時規格文檔"""
        print("\n📦 歸檔過時規格文檔...")

        archive_specs = [
            # v0.1-v0.2 implemented specs
            ("docs/specs/implemented/v0.1_mvp.md", "docs/archive/v0.1-v0.2/v0.1_mvp.md"),
            (
                "docs/specs/implemented/v0.2_risk_upgrade.md",
                "docs/archive/v0.1-v0.2/v0.2_risk_upgrade.md",
            ),
            ("docs/specs/implemented/data_v0.1.md", "docs/archive/v0.1-v0.2/data_v0.1.md"),
            # v0.3 planned specs
            ("docs/specs/planned/v0.3_SUMMARY.md", "docs/archive/v0.3/v0.3_SUMMARY.md"),
            ("docs/specs/planned/v0.3_architecture.md", "docs/archive/v0.3/v0.3_architecture.md"),
            ("docs/specs/planned/v0.3_cli_spec.md", "docs/archive/v0.3/v0.3_cli_spec.md"),
            (
                "docs/specs/planned/v0.3_multi_strategy_DRAFT.md",
                "docs/archive/v0.3/v0.3_multi_strategy_DRAFT.md",
            ),
            (
                "docs/specs/planned/v0.3_portfolio_runner_api.md",
                "docs/archive/v0.3/v0.3_portfolio_runner_api.md",
            ),
            (
                "docs/specs/planned/v0.3_short_leverage_spec.md",
                "docs/archive/v0.3/v0.3_short_leverage_spec.md",
            ),
            ("docs/specs/planned/v0.3_test_plan.md", "docs/archive/v0.3/v0.3_test_plan.md"),
            (
                "docs/specs/planned/v0.3_text_reporter_spec.md",
                "docs/archive/v0.3/v0.3_text_reporter_spec.md",
            ),
            # v0.4-v0.5 planned specs
            (
                "docs/specs/planned/v0.4_strategy_api_spec.md",
                "docs/archive/v0.4-v0.5/v0.4_strategy_api_spec.md",
            ),
            (
                "docs/specs/planned/v0.5_perpetual_data_ecosystem_spec.md",
                "docs/archive/v0.4-v0.5/v0.5_perpetual_data_ecosystem_spec.md",
            ),
        ]

        for source_path, dest_path in archive_specs:
            source = self.root_dir / source_path
            if source.exists():
                self.safe_archive(source, dest_path, f"過時規格（已被 v0.6 取代）")

    def check_and_delete_old_modules(self):
        """檢查並刪除舊模組（需要確認）"""
        print("\n⚠️  檢查舊模組...")

        # 檢查 risk/ 模組
        risk_dir = self.root_dir / "risk"
        if risk_dir.exists():
            # 檢查是否有任何檔案被 import
            import_found = self._check_imports(risk_dir, "from risk")

            if import_found:
                print(f"⚠️  警告: risk/ 模組仍被使用，跳過刪除")
                print(f"   找到以下 import: {import_found}")
            else:
                print(f"✅ risk/ 模組未被使用")
                for file in risk_dir.rglob("*.py"):
                    self.safe_delete(file, "舊版 risk 模組（已被 risk_management/ 取代）")

        # 檢查 utils/ 模組
        utils_dir = self.root_dir / "utils"
        if utils_dir.exists():
            import_found = self._check_imports(utils_dir, "from utils")

            if import_found:
                print(f"⚠️  警告: utils/ 模組仍被使用，跳過刪除")
                print(f"   找到以下 import: {import_found}")
            else:
                print(f"✅ utils/ 模組未被使用")
                for file in utils_dir.rglob("*.py"):
                    self.safe_delete(file, "未使用的 utils 模組")

    def cleanup_empty_strategy_files(self):
        """清理空的策略檔案"""
        print("\n🗑️  清理空策略檔案...")

        empty_strategies = [
            ("strategies/base.py", "空檔案（已被 api_v2.py 取代）"),
            ("strategies/indicators.py", "空檔案（未實作）"),
            ("strategies/mean_reversion.py", "空檔案（未實作）"),
            ("strategies/trend_follow.py", "空檔案（未實作）"),
        ]

        for file_path, reason in empty_strategies:
            file = self.root_dir / file_path
            if file.exists() and file.stat().st_size == 0:
                self.safe_delete(file, reason)

    def cleanup_empty_test_files(self):
        """清理空測試檔案"""
        print("\n🗑️  清理空測試檔案...")

        empty_tests = [
            ("tests/test_data.py", "空測試檔案"),
            ("tests/test_risk.py", "空測試檔案"),
            ("tests/test_strategies.py", "空測試檔案"),
        ]

        for file_path, reason in empty_tests:
            file = self.root_dir / file_path
            if file.exists() and file.stat().st_size == 0:
                self.safe_delete(file, reason)

    def _check_imports(self, module_dir: Path, import_pattern: str) -> list:
        """檢查是否有檔案 import 此模組"""
        imports_found = []

        # 搜索所有 Python 檔案
        for py_file in self.root_dir.rglob("*.py"):
            # 跳過模組自身和 __pycache__
            if module_dir in py_file.parents or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if import_pattern in content:
                        imports_found.append(str(py_file.relative_to(self.root_dir)))
            except:
                pass

        return imports_found

    def generate_report(self):
        """生成清理報告"""
        print("\n" + "=" * 60)
        print("📊 清理報告")
        print("=" * 60)

        # 統計操作
        deleted = [l for l in self.log if l["action"] == "delete"]
        archived = [l for l in self.log if l["action"] == "archive"]

        print(f"\n總操作數: {len(self.log)}")
        print(f"  • 刪除檔案: {len(deleted)}")
        print(f"  • 歸檔檔案: {len(archived)}")

        if self.dry_run:
            print("\n⚠️  這是預覽模式，未實際執行任何操作")
            print("   使用 --execute 參數執行實際清理")
        else:
            print(f"\n✅ 清理完成")
            print(f"   • 已刪除的檔案位於: {self.trash_dir}")
            print(f"   • 專案備份位於: {self.backup_dir}")

            # 保存日誌
            log_file = (
                self.root_dir / f"cleanup_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(self.log, f, indent=2, ensure_ascii=False)
            print(f"   • 操作日誌: {log_file}")

        print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="SuperDog v0.6 安全清理腳本")
    parser.add_argument("--execute", action="store_true", help="實際執行清理（預設為 dry-run 模式）")
    parser.add_argument("--root", type=str, default=".", help="專案根目錄路徑（預設為當前目錄）")

    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    dry_run = not args.execute

    print("=" * 60)
    print("🧹 SuperDog v0.6 安全清理工具")
    print("=" * 60)
    print(f"\n專案目錄: {root_dir}")
    print(f"模式: {'🔍 預覽模式 (DRY RUN)' if dry_run else '⚙️  執行模式 (EXECUTE)'}")

    if not dry_run:
        confirm = input("\n⚠️  確定要執行清理嗎？[y/N] ")
        if confirm.lower() != "y":
            print("❌ 已取消")
            return

    print("\n開始清理...\n")

    # 建立清理工具
    cleanup = SafeCleanup(root_dir, dry_run)

    # 執行清理步驟
    try:
        if not dry_run:
            cleanup.backup_project()

        cleanup.cleanup_backup_files()
        cleanup.archive_old_specs()
        cleanup.check_and_delete_old_modules()
        cleanup.cleanup_empty_strategy_files()
        cleanup.cleanup_empty_test_files()

        cleanup.generate_report()

    except Exception as e:
        print(f"\n❌ 清理過程發生錯誤: {e}")
        import traceback

        traceback.print_exc()

        if not dry_run:
            print(f"\n可以從備份恢復: {cleanup.backup_dir}")

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
