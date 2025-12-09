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

```python
# ✅ 正確：策略只負責計算進出場信號
class MyStrategy(BaseStrategy):
    def get_parameters(self) -> Dict[str, ParameterSpec]:
        return {
            'ma_short': int_param(20, "短均線週期", 5, 100),
            'ma_long': int_param(60, "長均線週期", 20, 200),
        }

    def compute_signals(self, data, params) -> pd.Series:
        close = data['ohlcv']['close']
        ma_short = close.rolling(params['ma_short']).mean()
        ma_long = close.rolling(params['ma_long']).mean()

        signals = pd.Series(0, index=close.index)
        signals[ma_short > ma_long] = 1   # 買入信號
        signals[ma_short < ma_long] = -1  # 賣出信號
        return signals
```

### 2.2 禁止在策略中包含的內容

| 類別 | 禁止內容 | 正確處理方式 |
|-----|---------|-------------|
| 執行參數 | leverage, position_size | 傳給 `run_backtest()` |
| 風控參數 | stop_loss_pct, take_profit_pct | 傳給 `run_backtest()` 或 broker |
| 倉位管理 | 加倉邏輯、減倉邏輯 | 使用 `PositionSizer` 模組 |
| 資金管理 | 計算下單數量 | 使用 `PositionSizer` 模組 |

### 2.3 策略參數 vs 執行參數

```python
# 策略參數：只影響信號計算
strategy_params = {
    'ma_short': 20,         # 影響信號
    'ma_long': 60,          # 影響信號
    'entry_threshold': 0.01 # 影響信號
}

# 執行參數：控制回測行為
result = run_backtest(
    data=df,
    strategy_cls=MyStrategy,
    strategy_params=strategy_params,  # 策略參數
    # --- 以下是執行參數 ---
    initial_cash=10000,
    leverage=10,
    stop_loss_pct=0.02,
    take_profit_pct=0.04,
    fee_rate=0.001,
    position_sizer=PercentOfEquitySizer(0.5),
)
```

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
