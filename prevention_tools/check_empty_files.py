#!/usr/bin/env python3
"""
檢查空 Python 檔案（除了 __init__.py）

Pre-commit hook 使用
"""
import sys
from pathlib import Path


def check_empty_files():
    """檢查 staged 的 Python 檔案是否為空"""
    import subprocess

    # 取得 staged 的檔案
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return 0

    files = result.stdout.strip().split("\n")
    empty_files = []

    for file in files:
        if not file.endswith(".py"):
            continue

        # __init__.py 可以是空的
        if file.endswith("__init__.py"):
            continue

        path = Path(file)
        if not path.exists():
            continue

        # 檢查檔案大小
        if path.stat().st_size == 0:
            empty_files.append(file)

        # 檢查是否只有註釋和空行
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            # 移除註釋和空行後檢查
            lines = [
                line.strip()
                for line in content.split("\n")
                if line.strip() and not line.strip().startswith("#")
            ]
            if not lines:
                empty_files.append(file)

    if empty_files:
        print("❌ 發現空檔案（或只有註釋的檔案）：")
        for f in empty_files:
            print(f"   - {f}")
        print("\n請添加實作或使用 NotImplementedError：")
        print('   raise NotImplementedError("TODO: Implement this module")')
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(check_empty_files())
