# SuperDog 開發規範 v1.0

> 本文檔定義專案的開發規則，確保代碼一致性與架構完整性。

---

## 1. 專案結構規範

### 1.1 目錄職責

| 目錄 | 職責 | 可放內容 |
|-----|------|---------|
| `core/` | 核心引擎，不可或缺的基礎功能 | backtest, data, strategies API |
| `modules/` | 可選功能模組，可獨立啟用/停用 | execution, risk, universe |
| `cli/` | 命令行介面 | CLI 命令、互動模式 |
| `tests/` | 測試代碼 | unit/, integration/ |
| `examples/` | 使用範例 | 完整可執行的範例腳本 |
| `scripts/` | 維護腳本 | 下載、清理、部署腳本 |
| `docs/` | 文檔 | 架構、API、指南、版本文檔 |
| `data/` | 數據存放 (gitignored) | raw/, processed/, experiments/ |

### 1.2 檔案命名規則

```
# Python 模組
snake_case.py              # 例: dual_ma.py, position_sizer.py

# 測試檔案
test_{模組名}.py           # 例: test_backtest.py, test_broker.py

# 文檔
UPPER_CASE.md              # 頂層文檔: README.md, CHANGELOG.md
lower_case.md              # 子目錄文檔: overview.md, api.md

# 配置
.{name}                    # 隱藏配置: .env, .gitignore
{name}.yaml/.json          # 配置檔案: config.yaml
```

### 1.3 禁止事項

- ❌ 根目錄放置 `test_*.py` 檔案 → 移到 `tests/` 或 `examples/`
- ❌ 根目錄放置 `verify_*.py` 檔案 → 驗證後刪除或移到 `scripts/`
- ❌ 根目錄放置版本特定文檔 (如 `V06_*.md`) → 移到 `docs/releases/`
- ❌ 建立空的 placeholder 模組 → 需要時再建立
- ❌ 重複功能模組 (如 `risk/` 和 `risk_management/`) → 整合為一個

---

## 2. 策略開發規範

### 2.1 核心原則：策略只產生信號

> ⚠️ **強制規範**：這是不可違反的架構原則。所有策略必須遵守此規範。

**廚師與食譜模式**：
- 策略 = 食譜（Recipe）：定義需要什麼配置，產生進出場信號
- 引擎 = 廚師（Chef）：理解所有執行技巧，根據食譜執行

```python
# ✅ 正確：策略只負責計算進出場信號，通過 ExecutionConfig 告訴引擎需要什麼
class MyStrategy(BaseStrategy):
    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """食譜：告訴引擎需要什麼執行配置"""
        return ExecutionConfig(
            stop_config=StopConfig(type="confirmed", confirm_bars=10),
            add_position_config=AddPositionConfig(enabled=True, max_count=3),
            leverage=7.0,
        )

    def on_bar(self, i: int, row: pd.Series):
        """只產生進場信號，不處理止損/加倉"""
        if self._entry_condition(row):
            self.broker.buy_all(row["close"], row.name)
```

### 2.2 禁止在策略中包含的內容

> ⚠️ **絕對禁止**：違反此規範會導致多路徑執行差異，造成回測與實盤結果不一致。

| 類別 | 禁止內容 | 正確處理方式 |
|-----|---------|-------------|
| 執行參數 | leverage, position_size | `ExecutionConfig` → 引擎處理 |
| 風控邏輯 | 止損檢查、止盈檢查 | `StopConfig` → `StopManager` 處理 |
| 倉位管理 | 加倉邏輯、減倉邏輯 | `AddPositionConfig` → `AddPositionManager` 處理 |
| 資金管理 | 計算下單數量 | `PositionSizingConfig` → `PositionSizer` 處理 |

**禁止的代碼模式**：
```python
# ❌ 絕對禁止：策略內部處理止損
def on_bar(self, i, row):
    if self.broker.has_position:
        if row["close"] < self.stop_loss_price:  # 錯！
            self.broker.close_all(row["close"])  # 錯！

# ❌ 絕對禁止：策略內部處理加倉
def on_bar(self, i, row):
    if self._should_add_position():  # 錯！
        self.broker.buy(...)  # 錯！

# ✅ 正確：策略只產生進場信號，執行邏輯由引擎統一處理
def on_bar(self, i, row):
    if self.broker.has_position:
        return  # 有倉位時不做任何事，讓引擎處理
    if self._entry_condition(row):
        self.broker.buy_all(row["close"], row.name)
```

### 2.3 ExecutionConfig 架構（v2.4+）

所有策略必須通過 `get_execution_config()` 提供執行配置：

```python
from backtest.strategy_config import (
    ExecutionConfig,
    StopConfig,
    AddPositionConfig,
    PositionSizingConfig,
)

class MyStrategy(BaseStrategy):
    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        return ExecutionConfig(
            # 止損配置
            stop_config=StopConfig(
                type="confirmed",        # 確認式止損
                confirm_bars=10,         # 連續 N 根確認
                trailing=True,           # 追蹤止損
                trailing_ma_key="avg20", # 追蹤哪條均線
                trailing_buffer=0.02,    # 緩衝百分比
                emergency_atr_mult=3.5,  # 緊急止損 ATR 倍數
                fixed_stop_pct=0.03,     # 最大止損百分比
            ),
            # 加倉配置
            add_position_config=AddPositionConfig(
                enabled=True,
                max_count=3,             # 最多加倉次數
                size_pct=0.5,            # 每次加倉比例
                min_interval=6,          # 最小間隔 K 線數
                min_profit=0.03,         # 最低盈利門檻
                pullback_tolerance=0.018,# 回踩容許範圍
                pullback_ma_key="avg20", # 回踩參考均線
            ),
            # 倉位配置
            position_sizing_config=PositionSizingConfig(
                type="percent_of_equity",
                percent=0.15,            # 權益百分比
            ),
            # 其他
            take_profit_pct=0.10,        # 止盈百分比
            leverage=7.0,                # 槓桿
            fee_rate=0.0005,             # 手續費率
        )
```

### 2.4 策略參數 vs 執行參數

```python
# 策略參數：只影響信號計算（在策略內部）
strategy_params = {
    'ma_short': 20,           # 影響信號
    'ma_long': 60,            # 影響信號
    'cluster_threshold': 0.03 # 影響信號
}

# 執行參數：控制回測行為（通過 ExecutionConfig）
# 這些參數由策略的 get_execution_config() 提供
# 引擎自動讀取並配置 StopManager, AddPositionManager, PositionSizer
result = run_backtest(
    data=df,
    strategy_cls=MyStrategy,
    strategy_params=strategy_params,
    initial_cash=500,
    # ExecutionConfig 由策略提供，無需手動傳入
)

---

## 3. 模組依賴規範

### 3.1 依賴方向

```
cli/ → 可依賴 → core/, modules/
modules/ → 可依賴 → core/
core/ → 不可依賴 → modules/, cli/
tests/ → 可依賴 → 所有
```

### 3.2 核心模組不可依賴可選模組

```python
# ❌ 錯誤：core 依賴 modules
# 在 core/backtest/engine.py 中
from modules.risk.dynamic_stops import DynamicStopLoss  # 錯！

# ✅ 正確：使用依賴注入
def run_backtest(
    ...,
    stop_loss_handler=None,  # 可選注入
):
    if stop_loss_handler:
        stop_loss_handler.check(...)
```

---

## 4. 導入規範

### 4.1 導入順序

```python
# 1. 標準庫
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# 2. 第三方庫
import pandas as pd
import numpy as np

# 3. 本專案模組 (絕對導入)
from core.backtest.engine import run_backtest
from core.strategies.api import BaseStrategy
from modules.risk.position_sizer import PercentOfEquitySizer
```

### 4.2 禁止相對導入跨層級

```python
# ❌ 錯誤
from ...core.backtest import engine

# ✅ 正確
from core.backtest import engine
```

---

## 5. 測試規範

### 5.1 測試檔案位置

```
tests/
├── unit/                    # 單元測試
│   ├── test_broker.py
│   ├── test_engine.py
│   └── test_metrics.py
├── integration/             # 整合測試
│   ├── test_backtest_flow.py
│   └── test_cli_commands.py
└── conftest.py              # pytest fixtures
```

### 5.2 測試命名

```python
# 測試函數命名：test_{功能}_{場景}_{預期結果}
def test_broker_open_long_position_success():
    ...

def test_broker_open_position_with_zero_equity_fails():
    ...
```

---

## 6. Git 規範

### 6.1 Commit 訊息格式

```
<type>: <subject>

<body>

<footer>
```

**類型 (type):**
- `feat`: 新功能
- `fix`: 修復 bug
- `refactor`: 重構
- `docs`: 文檔更新
- `test`: 測試相關
- `chore`: 雜項

**範例:**
```
feat: Add ATR-based dynamic stop loss

- Implement ATRStopLoss class in modules/risk/
- Support trailing stop based on ATR multiplier
- Add unit tests for edge cases

Closes #123
```

### 6.2 分支命名

```
feature/{功能名}      # 新功能
fix/{bug描述}         # 修復
refactor/{重構描述}   # 重構
cleanup/{清理描述}    # 清理
```

---

## 7. 文檔規範

### 7.1 必要文檔

| 文檔 | 位置 | 內容 |
|-----|------|------|
| README.md | 根目錄 | 專案介紹、快速開始 |
| CHANGELOG.md | 根目錄 | 版本變更記錄 |
| docs/api/strategy_api.md | docs/api/ | 策略 API 完整規範 |
| docs/guides/CONTRIBUTING.md | docs/guides/ | 貢獻指南 |

### 7.2 版本文檔

每個主要版本的設計文檔放在 `docs/releases/v{X.Y}/`:
```
docs/releases/v0.6/
├── design.md           # 設計規格
├── implementation.md   # 實作指南
└── migration.md        # 升級指南
```

---

## 8. 代碼風格

### 8.1 工具配置

- **格式化**: black
- **導入排序**: isort
- **Linting**: flake8
- **類型檢查**: mypy (建議)

### 8.2 pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    hooks:
      - id: flake8
```

---

## 9. 快速檢查清單

開發新功能前，確認：

- [ ] 功能屬於哪個層級？(core/modules/cli)
- [ ] 依賴方向正確嗎？
- [ ] 策略只產生信號嗎？
- [ ] 測試檔案放在正確位置嗎？
- [ ] 有更新 CHANGELOG 嗎？

---

## 10. 架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI                                  │
│                    (User Interface)                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      MODULES                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Execution  │  │    Risk     │  │  Universe   │          │
│  │   Engine    │  │ Management  │  │  Manager    │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
└─────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                        CORE                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Backtest   │  │    Data     │  │ Strategies  │          │
│  │   Engine    │  │   Layer     │  │    API      │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

**版本**: 1.0
**最後更新**: 2025-12-09
**維護者**: DDragon
