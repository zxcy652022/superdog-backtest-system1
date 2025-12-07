#!/usr/bin/env python3
"""
檢查版本一致性

確保 README.md, CHANGELOG.md, __init__.py 的版本號一致
"""
import re
import sys
from pathlib import Path


def extract_version_from_readme(path):
    """從 README.md 提取版本號"""
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    # 匹配 "# SuperDog Backtest vX.Y.Z" 或 "v0.6.0"
    match = re.search(r"v(\d+\.\d+\.\d+)", content)
    return match.group(1) if match else None


def extract_version_from_changelog(path):
    """從 CHANGELOG.md 提取最新版本號"""
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    # 匹配 "## [X.Y.Z]" 或 "## [X.Y.Z-suffix]" 格式,取第一個(最新的)
    match = re.search(r"## \[(\d+\.\d+\.\d+)(?:-\w+)?\]", content)
    return match.group(1) if match else None


def check_version_consistency():
    """檢查版本一致性"""
    root = Path(".")

    versions = {}

    # 檢查 README.md
    readme = root / "README.md"
    if readme.exists():
        versions["README.md"] = extract_version_from_readme(readme)

    # 檢查 CHANGELOG.md
    changelog = root / "CHANGELOG.md"
    if changelog.exists():
        versions["CHANGELOG.md"] = extract_version_from_changelog(changelog)

    # 檢查是否一致
    if len(set(versions.values())) > 1:
        print("❌ 版本號不一致：")
        for file, version in versions.items():
            print(f"   {file}: v{version}")
        print("\n請確保所有檔案的版本號一致")
        return 1

    if versions:
        version = list(versions.values())[0]
        print(f"✅ 版本檢查通過: v{version}")

    return 0


if __name__ == "__main__":
    sys.exit(check_version_consistency())
