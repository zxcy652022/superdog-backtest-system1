# IMPORT_POLICY.md
# SuperDog-Quant — Import Path Policy

本文件定義 SuperDog-Quant 專案的模組匯入路徑政策，確保整體程式碼在任何執行環境下都能保持一致、乾淨且易於維護。

========================================
1. Library Modules（模組本體）禁止修改 sys.path
========================================

以下資料夾內所有 Python 程式碼不得加入任何與 sys.path 修改相關的程式碼：

- data/
- backtest/
- strategies/
- risk/
- utils/

以下程式碼在此類檔案中 **全面禁止**：

import sys
import os
sys.path.append(...)

原因：
- 保持模組乾淨，可移植性高
- 避免 namespace 汙染
- 避免不必要的依賴混亂
- 在 Docker、CI/CD、API 等環境中保持一致性
- 減少循環匯入 (circular import) 風險

所有 Library Code 須維持標準相對匯入，例如：

from data.fetcher import fetch_ohlcv
from backtest.engine import BacktestEngine

========================================
2. Runtime / Executable Scripts 必須加入 bootstrap
========================================

以下檔案（用來直接執行的 Python 程式碼）必須在檔案最上方加入 bootstrap：

- tests/*.py
- tools/*.py（若存在）
- cli/*.py（未來加入）
- notebooks/.ipynb（以 %run 執行 .py 時）

Bootstrap：

import sys, os
sys.path.append(os.path.abspath("."))

用途：
- 讓 Python 在任何執行路徑下都能找到 SuperDog-Quant 專案根目錄
- 減少因為執行位置不同導致的 import 錯誤

========================================
3. Bootstrap.py（未來選擇性加入）
========================================

未來可考慮加入：

bootstrap.py：

import sys, os
def setup_path():
    root = os.path.abspath(os.path.dirname(__file__))
    if root not in sys.path:
        sys.path.append(root)

執行端可用：

from bootstrap import setup_path
setup_path()

（目前 v0.1 不需加入此檔案）

========================================
4. 本政策適用範圍
========================================

此 Import Policy 適用於：

- 所有模組開發
- 所有測試流程
- 所有策略編寫
- 所有 CLI 或工具開發
- 未來的回測系統、自動交易系統

此政策為 SuperDog-Quant 專案長期維護的重要基礎。

========================================
5. 變更紀錄
========================================

v1.0 — 初版建立
