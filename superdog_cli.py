#!/usr/bin/env python3
"""
SuperDog v0.5 Interactive CLI Entry Point

互動式命令行界面入口

Usage:
    python3 superdog_cli.py
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent))

from cli.interactive import MainMenu


def main():
    """主函數"""
    try:
        menu = MainMenu()
        menu.run()
        return 0
    except KeyboardInterrupt:
        print("\n\n已取消")
        return 0
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
