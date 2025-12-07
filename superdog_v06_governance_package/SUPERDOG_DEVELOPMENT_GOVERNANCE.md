# SuperDog 開發維護規章
# Development & Maintenance Governance

**版本**: 1.0.0
**生效日期**: 2024-12-08
**適用範圍**: SuperDog v0.6+
**強制執行**: 所有開發者必須遵守

---

## 📜 目錄

1. [核心原則](#核心原則)
2. [版本管理規範](#版本管理規範)
3. [代碼規範](#代碼規範)
4. [文檔規範](#文檔規範)
5. [模組管理規範](#模組管理規範)
6. [測試規範](#測試規範)
7. [發布流程](#發布流程)
8. [問題處理流程](#問題處理流程)

---

## 🎯 核心原則

### 1. 可維護性優先 (Maintainability First)

```
質量 > 速度
清晰 > 聰明
簡單 > 複雜
```

**含義**:
- 代碼必須易於理解和修改
- 避免過度設計和過早優化
- 每個決策都考慮長期維護成本

### 2. 文檔即代碼 (Documentation as Code)

```
文檔與代碼必須同步更新
沒有文檔 = 功能不完整
```

**要求**:
- 每次 PR 必須包含相關文檔更新
- 文檔審查與代碼審查同等重要
- 文檔過期視為 Bug

### 3. 零容忍技術債 (Zero Technical Debt Tolerance)

```
發現問題 → 立即記錄 → 排期修復
不允許問題累積
```

**實施**:
- 每週 Technical Debt Review
- 優先修復架構問題
- 定期重構清理

### 4. 自動化一切 (Automate Everything)

```
能自動化的就不手動
能檢查的就不依賴記憶
```

**工具**:
- Pre-commit hooks
- CI/CD 自動測試
- 自動文檔生成
- 自動化清理腳本

---

## 📦 版本管理規範

### 版本號規則 (Semantic Versioning)

格式: `v{MAJOR}.{MINOR}.{PATCH}`

```
v0.6.0 → v0.6.1 (PATCH: Bug fix)
v0.6.1 → v0.7.0 (MINOR: New feature)
v0.9.9 → v1.0.0 (MAJOR: Breaking change)
```

**增加規則**:
- **PATCH**: Bug 修復、文檔更新、小改進
- **MINOR**: 新功能、向後兼容的變更
- **MAJOR**: 破壞性變更、架構重構

### 版本一致性檢查

**所有檔案必須版本同步**:

```bash
# 每次發布前執行
./scripts/check_version_consistency.sh

檢查項目：
□ README.md
□ CHANGELOG.md
□ pyproject.toml (如有)
□ __version__ 變數
□ 文檔中的版本引用
```

### 版本分支策略

```
main (v0.6.0-stable)
  ↓
develop (v0.7.0-dev)
  ↓
feature/universe-v2 (開發分支)
```

**規則**:
- `main`: 穩定版本，僅接受 hotfix
- `develop`: 開發版本，新功能在此集成
- `feature/*`: 功能分支，完成後 merge 到 develop

---

## 💻 代碼規範

### 1. Python 代碼風格

**遵循 PEP 8，使用工具強制執行**:

```bash
# 安裝工具
pip install black isort flake8 mypy

# 格式化
black .
isort .

# 檢查
flake8 .
mypy .
```

**配置** (pyproject.toml):
```toml
[tool.black]
line-length = 100
target-version = ['py39']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### 2. 命名規範

#### 檔案命名

```python
# ✅ 正確
universe_manager.py
dynamic_stops.py
support_resistance.py

# ❌ 錯誤
UniverseManager.py        # 不使用駝峰命名
universe-manager.py       # 不使用連字號
universeManager.py        # 不使用駝峰命名
新文字檔.txt              # 禁止中文檔名
```

#### 類別命名

```python
# ✅ 正確
class UniverseManager:
class BaseStrategy:
class DynamicStopManager:

# ❌ 錯誤
class universe_manager:   # 必須使用 PascalCase
class UNIVERSE_MANAGER:   # 不使用全大寫
```

#### 函式和變數命名

```python
# ✅ 正確
def calculate_sharpe_ratio():
def get_nearest_support():
max_drawdown = 0.15

# ❌ 錯誤
def CalculateSharpeRatio():   # 必須使用 snake_case
def get_nearest_Support():    # 不使用駝峰
MAX_DRAWDOWN = 0.15           # 變數不使用全大寫（除非是常數）
```

#### 常數命名

```python
# ✅ 正確
DEFAULT_LEVERAGE = 1.0
MAX_POSITION_SIZE = 0.1
API_VERSION = "v2"

# ❌ 錯誤
default_leverage = 1.0        # 常數必須全大寫
DefaultLeverage = 1.0         # 不使用駝峰
```

### 3. 類型註解要求

**所有公開 API 必須有類型註解**:

```python
# ✅ 正確
def calculate_position_size(
    capital: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float
) -> float:
    """計算倉位大小"""
    return capital * risk_pct / abs(entry_price - stop_loss)

# ❌ 錯誤
def calculate_position_size(capital, risk_pct, entry_price, stop_loss):
    """沒有類型註解"""
    return capital * risk_pct / abs(entry_price - stop_loss)
```

### 4. Docstring 要求

**所有公開函式和類別必須有 Docstring**:

```python
def detect_support_resistance(
    ohlcv: pd.DataFrame,
    window: int = 20,
    threshold: float = 0.02
) -> List[PriceLevel]:
    """
    檢測支撐壓力位。

    Args:
        ohlcv: OHLCV 數據，必須包含 ['high', 'low', 'close', 'volume']
        window: 局部極值檢測窗口（預設 20）
        threshold: 價格聚類閾值（預設 2%）

    Returns:
        List[PriceLevel]: 檢測到的支撐壓力位列表，按強度排序

    Raises:
        ValueError: 如果 ohlcv 缺少必要欄位

    Example:
        >>> ohlcv = fetch_ohlcv("BTCUSDT", "1h")
        >>> levels = detect_support_resistance(ohlcv)
        >>> print(f"Found {len(levels)} levels")
        Found 15 levels

    Note:
        此函式使用局部極值檢測和 K-means 聚類。
        對於高波動資產，建議增加 threshold。
    """
    pass
```

### 5. 禁止項目

```python
# ❌ 絕對禁止
import *                      # 禁止使用 import *
eval()                        # 禁止使用 eval
exec()                        # 禁止使用 exec

# ❌ 不建議
pass                          # 空實作應該用 NotImplementedError
print()                       # 應使用 logger
time.sleep() in production    # 使用異步或更好的方案

# ✅ 正確做法
from module import Class      # 明確 import
logger.info()                 # 使用 logger
raise NotImplementedError()   # 明確標記未實作
```

### 6. 空檔案處理

**規則**: 不允許完全空的 .py 檔案存在（除了 `__init__.py`）

```python
# ❌ 完全空的檔案（0 bytes）
# 不允許！

# ✅ 如果模組未實作，必須明確說明
"""
Indicators Module

TODO: This module will implement technical indicators.
Planned features:
- Moving averages (SMA, EMA, WMA)
- Oscillators (RSI, MACD, Stochastic)
- Volatility indicators (Bollinger Bands, ATR)

Planned for: v0.7.0
Issue: #123
"""

raise NotImplementedError(
    "Indicators module not yet implemented. "
    "Use strategies.api_v2.BaseStrategy for custom indicator logic."
)
```

---

## 📚 文檔規範

### 1. 文檔結構

```
docs/
├── README.md                    # 文檔索引
├── specs/                       # 規格文檔
│   ├── v0.6/                   # 當前版本
│   │   ├── README.md           # v0.6 規格索引
│   │   ├── strategy_api_spec.md
│   │   ├── universe_manager_spec.md
│   │   ├── execution_model_spec.md
│   │   └── risk_management_spec.md
│   └── v0.5/                   # 上一版本（僅保留一個版本）
├── archive/                     # 歷史版本歸檔
│   ├── v0.1-v0.4/              # 舊版本規格
│   └── deprecated/             # 已棄用的設計
├── architecture/               # 架構文檔
│   ├── overview.md
│   ├── data_pipeline.md
│   └── module_dependencies.md
├── guides/                     # 開發指南
│   ├── getting_started.md
│   ├── strategy_development.md
│   └── contribution_guide.md
└── api/                        # API 文檔（自動生成）
    └── index.html
```

### 2. Spec 文檔模板

**檔案命名**: `{module}_spec_v{X.Y}.md`

**內容結構**:
```markdown
# {模組名稱} 規格文檔

**版本**: v{X.Y}
**狀態**: ✅ 實作完成 / 🚧 開發中 / 📋 已規劃
**負責人**: @username
**最後更新**: YYYY-MM-DD

---

## 概述

[2-3 段落說明模組目的、適用場景、核心價值]

## 設計目標

- 🎯 目標 1：具體、可衡量
- 🎯 目標 2：具體、可衡量
- 🎯 目標 3：具體、可衡量

## 架構設計

### 模組關係圖

```
[Mermaid 或 ASCII 圖]
```

### 核心類別

#### Class: {ClassName}

**職責**: [說明此類別的職責]

**屬性**:
- `attr1: Type` - 說明
- `attr2: Type` - 說明

**方法**:
- `method1(arg: Type) -> ReturnType` - 說明

## API 規格

### 公開介面

\`\`\`python
class {ClassName}:
    def method(self, arg: Type) -> ReturnType:
        """詳細說明"""
        pass
\`\`\`

## 使用範例

### 基礎使用

\`\`\`python
# 可執行的完整範例
from module import Class

instance = Class()
result = instance.method()
print(result)
\`\`\`

### 進階使用

\`\`\`python
# 更複雜的場景
\`\`\`

## 測試需求

- [ ] 單元測試覆蓋率 ≥ 80%
- [ ] 整合測試場景 X 個
- [ ] 性能測試基準

## 依賴關係

- `module_a`: 用於 XXX
- `module_b`: 用於 YYY

## 限制與注意事項

- ⚠️ 限制 1
- ⚠️ 限制 2

## 未來規劃

- 🚀 v{X+1}: 計畫功能 1
- 🚀 v{X+2}: 計畫功能 2

## 變更歷史

- v{X.Y} (YYYY-MM-DD): 初始版本
- v{X.Y+1} (YYYY-MM-DD): 更新內容

## 參考資料

- [外部文檔鏈接]
- [相關論文]
```

### 3. README 更新規則

**每次發布新版本時，README 必須更新**:

```markdown
# SuperDog Backtest v{X.Y}

[版本描述]

## 新功能 (v{X.Y})

### 核心功能
- ✅ 功能 1 (說明)
- ✅ 功能 2 (說明)
- 🚧 功能 3 (開發中)

## 快速開始

### 安裝
[最新安裝步驟]

### 基礎使用
[可執行的範例，使用最新 API]

## 版本歷史

詳見 [CHANGELOG.md](CHANGELOG.md)
```

### 4. CHANGELOG 規範

**遵循 [Keep a Changelog](https://keepachangelog.com/)**:

```markdown
# Changelog

## [Unreleased]

### Added
- 新功能 1 (#issue-number)

### Changed
- 變更 1 (#issue-number)

### Fixed
- 修復 1 (#issue-number)

### Removed
- 移除 1 (#issue-number)

### Deprecated
- 棄用 1 (將在 v{X+1} 移除)

## [0.6.0] - 2024-12-07

### Added
- Phase 1: 幣種宇宙管理
- Phase 2: 策略實驗室
...
```

### 5. 文檔審查清單

**每次 PR 必須檢查**:

```bash
# 自動化檢查腳本
./scripts/check_docs.sh

檢查項目：
□ README 版本號已更新
□ CHANGELOG 已記錄變更
□ 新增功能有對應 spec
□ API 文檔已更新
□ 範例程式碼可執行
□ 連結無失效
□ 圖片正常顯示
□ Markdown 格式正確
```

---

## 🏗️ 模組管理規範

### 1. 新模組建立流程

```bash
# Step 1: 規劃階段
1. 建立 spec: docs/specs/v{X.Y}/{module}_spec.md
2. 架構審查（團隊討論）
3. 獲得批准

# Step 2: 實作階段
4. 建立模組目錄和 __init__.py
5. 實作核心功能
6. 撰寫測試
7. 撰寫 docstrings

# Step 3: 整合階段
8. 更新 README.md
9. 更新 CHANGELOG.md
10. 提交 PR
11. 代碼審查
12. 文檔審查
13. Merge

# Step 4: 發布階段
14. 更新版本號
15. 標記 Git tag
16. 發布 Release Notes
```

### 2. 模組淘汰流程

**當模組需要被取代時**:

```python
# Step 1: 標記棄用（保留一個版本）
# old_module.py (v0.6)

import warnings

warnings.warn(
    "old_module is deprecated and will be removed in v0.7. "
    "Use new_module instead. "
    "Migration guide: https://docs.superdog.com/migration/old-to-new",
    DeprecationWarning,
    stacklevel=2
)

# 原有功能保持可用
def old_function():
    """
    .. deprecated:: 0.6
       Use :func:`new_module.new_function` instead.
    """
    pass
```

```markdown
# Step 2: 文檔更新
在 CHANGELOG.md 中記錄：

## [0.6.0] - 2024-12-07

### Deprecated
- `old_module` 已棄用，請使用 `new_module` (將在 v0.7.0 移除)
  - 遷移指南: docs/migration/old_to_new.md

### Added
- `new_module` 新模組，取代 `old_module`
```

```bash
# Step 3: 下一版本移除（v0.7）
1. 刪除 old_module.py
2. 移動到 docs/archive/deprecated/
3. 更新所有 import 路徑
4. 更新測試
5. 更新文檔
```

### 3. 模組組織原則

```python
# ✅ 正確：按功能組織
strategies/
├── __init__.py
├── api_v2.py              # 策略 API
├── metadata.py            # 元數據定義
├── registry_v2.py         # 策略註冊
├── dependency_checker.py  # 依賴檢查
└── custom/               # 自訂策略
    └── my_strategy.py

# ❌ 錯誤：按版本組織
strategies/
├── v1/
├── v2/
└── v3/                   # 版本不應反映在目錄結構
```

### 4. __init__.py 規範

```python
# ✅ 正確：明確匯出公開 API
"""
Strategies Module

提供策略開發和管理功能。
"""

from .api_v2 import BaseStrategy, StrategyConfig
from .metadata import StrategyMetadata, StrategyCategory
from .registry_v2 import get_registry, register_strategy

__all__ = [
    # API
    "BaseStrategy",
    "StrategyConfig",
    # Metadata
    "StrategyMetadata",
    "StrategyCategory",
    # Registry
    "get_registry",
    "register_strategy",
]

__version__ = "0.6.0"

# ❌ 錯誤：空檔案或 import *
# 不明確匯出什麼
```

---

## 🧪 測試規範

### 1. 測試覆蓋率要求

```
核心模組：≥ 85% 覆蓋率
工具模組：≥ 70% 覆蓋率
整體專案：≥ 80% 覆蓋率
```

**檢查方式**:
```bash
pip install pytest pytest-cov

# 執行測試並生成覆蓋率報告
pytest --cov=. --cov-report=html --cov-report=term

# 查看報告
open htmlcov/index.html
```

### 2. 測試檔案命名

```python
# ✅ 正確
tests/
├── test_universe_manager.py
├── test_dynamic_stops.py
├── test_strategy_api_v2.py
└── test_integration_v06.py

# ❌ 錯誤
tests/
├── universe_test.py          # 必須以 test_ 開頭
├── TestDynamicStops.py       # 不使用駝峰
└── test_v02_universe.py      # 版本號不應在檔名中
```

### 3. 測試類別和函式命名

```python
# ✅ 正確
class TestUniverseManager:
    def test_create_universe_with_valid_params(self):
        pass

    def test_create_universe_with_invalid_params_raises_error(self):
        pass

    def test_update_universe_removes_delisted_symbols(self):
        pass

# ❌ 錯誤
class UniverseManagerTest:       # 必須以 Test 開頭
    def testCreate(self):         # 必須以 test_ 開頭
        pass

    def test_1(self):             # 名稱應該描述測試內容
        pass
```

### 4. 測試結構

```python
import pytest
from strategies import BaseStrategy

class TestBaseStrategy:
    """測試 BaseStrategy 類別"""

    # Fixtures
    @pytest.fixture
    def strategy(self):
        """提供測試用策略實例"""
        return BaseStrategy()

    @pytest.fixture
    def sample_data(self):
        """提供測試用數據"""
        return load_sample_ohlcv()

    # 正常情境測試
    def test_generate_signals_with_valid_data(self, strategy, sample_data):
        """測試：使用有效數據生成訊號"""
        # Arrange (準備)
        strategy.set_parameters(fast=10, slow=20)

        # Act (執行)
        signals = strategy.generate_signals(sample_data)

        # Assert (驗證)
        assert len(signals) == len(sample_data)
        assert all(s in ['long', 'short', 'flat'] for s in signals)

    # 邊界情境測試
    def test_generate_signals_with_empty_data_raises_error(self, strategy):
        """測試：空數據應拋出錯誤"""
        with pytest.raises(ValueError, match="Data cannot be empty"):
            strategy.generate_signals(pd.DataFrame())

    # 參數化測試
    @pytest.mark.parametrize("fast,slow,expected", [
        (5, 10, True),   # 正常參數
        (10, 5, False),  # fast > slow，應該失敗
        (0, 10, False),  # 負數參數
    ])
    def test_validate_parameters(self, strategy, fast, slow, expected):
        """測試：參數驗證"""
        is_valid = strategy.validate_parameters(fast=fast, slow=slow)
        assert is_valid == expected
```

### 5. 測試執行規範

```bash
# 執行所有測試
pytest

# 執行特定測試文件
pytest tests/test_universe_manager.py

# 執行特定測試類別
pytest tests/test_universe_manager.py::TestUniverseManager

# 執行特定測試函式
pytest tests/test_universe_manager.py::TestUniverseManager::test_create_universe

# 執行並顯示詳細輸出
pytest -v

# 執行並顯示 print 輸出
pytest -s

# 執行快速測試（跳過慢測試）
pytest -m "not slow"

# 執行失敗的測試
pytest --lf  # last failed
pytest --ff  # failed first
```

### 6. 測試標記 (Markers)

```python
import pytest

@pytest.mark.slow
def test_large_dataset_processing():
    """標記：慢測試"""
    pass

@pytest.mark.integration
def test_full_pipeline():
    """標記：整合測試"""
    pass

@pytest.mark.unit
def test_single_function():
    """標記：單元測試"""
    pass

@pytest.mark.skip(reason="Feature not yet implemented")
def test_future_feature():
    """標記：跳過測試"""
    pass

@pytest.mark.xfail(reason="Known issue #123")
def test_known_bug():
    """標記：預期失敗"""
    pass
```

### 7. Mock 和 Fixture 使用

```python
from unittest.mock import Mock, patch
import pytest

# Fixture 提供共用資源
@pytest.fixture
def mock_data_fetcher():
    """模擬數據獲取器"""
    fetcher = Mock()
    fetcher.fetch_ohlcv.return_value = pd.DataFrame(...)
    return fetcher

# 使用 patch 模擬外部依賴
def test_strategy_with_mocked_data():
    with patch('data.fetcher.DataFetcher') as MockFetcher:
        MockFetcher.return_value.fetch_ohlcv.return_value = pd.DataFrame(...)

        strategy = MyStrategy()
        result = strategy.backtest()

        assert result.total_return > 0
```

---

## 🚀 發布流程

### 1. 版本發布檢查清單

**Pre-release Checklist**:

```bash
# 1. 代碼質量檢查
□ 所有測試通過（pytest）
□ 代碼覆蓋率 ≥ 80%
□ 代碼格式化（black, isort）
□ 靜態檢查通過（flake8, mypy）
□ 無安全漏洞（bandit）

# 2. 文檔檢查
□ README.md 版本已更新
□ CHANGELOG.md 已記錄變更
□ API 文檔已更新
□ 所有範例可執行
□ 過時文檔已歸檔

# 3. 版本一致性
□ __version__ 已更新
□ pyproject.toml 版本已更新
□ Git tag 已創建
□ Release notes 已撰寫

# 4. 向後兼容性
□ 破壞性變更已記錄
□ 遷移指南已撰寫
□ 棄用警告已添加

# 5. 性能測試
□ 基準測試通過
□ 記憶體使用正常
□ 無明顯性能退化
```

### 2. 發布步驟

```bash
# Step 1: 準備發布分支
git checkout develop
git pull origin develop
git checkout -b release/v0.6.0

# Step 2: 更新版本號
# 更新所有相關文件的版本號
./scripts/bump_version.sh 0.6.0

# Step 3: 更新文檔
# 更新 README.md, CHANGELOG.md 等

# Step 4: 提交變更
git add .
git commit -m "Prepare release v0.6.0"

# Step 5: 合併到 main
git checkout main
git merge release/v0.6.0 --no-ff

# Step 6: 創建 tag
git tag -a v0.6.0 -m "Release version 0.6.0"

# Step 7: 推送
git push origin main
git push origin v0.6.0

# Step 8: 合併回 develop
git checkout develop
git merge main

# Step 9: 發布 Release Notes
# 在 GitHub Releases 創建新版本

# Step 10: 清理
git branch -d release/v0.6.0
```

### 3. Hotfix 流程

```bash
# 緊急修復流程（直接在 main 分支）

# Step 1: 創建 hotfix 分支
git checkout main
git checkout -b hotfix/critical-bug

# Step 2: 修復 bug
# ... 修復代碼 ...

# Step 3: 測試
pytest tests/

# Step 4: 更新版本號（PATCH）
./scripts/bump_version.sh 0.6.1

# Step 5: 提交
git commit -am "Fix critical bug in universe manager"

# Step 6: 合併到 main
git checkout main
git merge hotfix/critical-bug --no-ff

# Step 7: 標記
git tag -a v0.6.1 -m "Hotfix: Critical bug fix"

# Step 8: 合併到 develop
git checkout develop
git merge main

# Step 9: 推送
git push origin main develop
git push origin v0.6.1

# Step 10: 清理
git branch -d hotfix/critical-bug
```

---

## 🔧 問題處理流程

### 1. Bug 處理流程

```markdown
# Bug 報告模板

**Bug 描述**
[清楚描述問題]

**重現步驟**
1. 步驟 1
2. 步驟 2
3. 步驟 3

**預期行為**
[描述應該發生什麼]

**實際行為**
[描述實際發生什麼]

**環境**
- SuperDog 版本: v0.6.0
- Python 版本: 3.9.7
- 作業系統: macOS 12.5

**錯誤訊息**
\`\`\`
[完整錯誤訊息]
\`\`\`

**相關日誌**
\`\`\`
[相關日誌]
\`\`\`
```

**處理流程**:
```
1. 接收 Bug 報告
   ↓
2. 確認並分類
   - 嚴重度：Critical / High / Medium / Low
   - 類型：功能 / 性能 / 安全 / 文檔
   ↓
3. 排期修復
   - Critical: 立即修復（Hotfix）
   - High: 下一個 Patch 版本
   - Medium: 下一個 Minor 版本
   - Low: 待定
   ↓
4. 修復開發
   ↓
5. 測試驗證
   ↓
6. 文檔更新
   ↓
7. 發布修復
```

### 2. Feature Request 流程

```markdown
# 功能需求模板

**功能描述**
[清楚描述需要的功能]

**使用場景**
[為什麼需要這個功能？解決什麼問題？]

**建議實作**
[如果有想法，可以描述建議的實作方式]

**替代方案**
[是否有其他方法達到同樣目的？]

**優先級**
[High / Medium / Low]
```

**處理流程**:
```
1. 接收功能需求
   ↓
2. 評估可行性
   - 與現有架構是否衝突
   - 實作複雜度
   - 維護成本
   ↓
3. 決策
   - 接受：加入 Roadmap
   - 拒絕：說明理由
   - 延後：記錄並說明原因
   ↓
4. 設計階段
   - 撰寫 Spec
   - 架構審查
   ↓
5. 實作階段
   ↓
6. 測試驗證
   ↓
7. 文檔更新
   ↓
8. 發布
```

### 3. 技術債追蹤

**建立技術債追蹤文件**: `docs/TECHNICAL_DEBT.md`

```markdown
# 技術債追蹤

## 高優先級（必須在下一版本解決）

### 1. [模組名稱] - 問題描述
- **發現日期**: 2024-12-08
- **影響範圍**: backtest, execution_engine
- **嚴重度**: High
- **解決方案**: [建議的解決方案]
- **預計工作量**: 2 天
- **負責人**: @username
- **目標版本**: v0.7.0

## 中優先級（在未來 2-3 版本解決）

[...]

## 低優先級（長期改進）

[...]

## 已解決

[記錄已解決的技術債]
```

---

## 🛠️ 工具和自動化

### 1. Pre-commit Hooks

**安裝**:
```bash
pip install pre-commit
```

**配置** (`.pre-commit-config.yaml`):
```yaml
repos:
  # 代碼格式化
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.9

  # Import 排序
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort

  # 代碼檢查
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=100']

  # 類型檢查
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  # 安全檢查
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', '.bandit']

  # 基本檢查
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
```

**啟用**:
```bash
pre-commit install
```

### 2. CI/CD 配置

**GitHub Actions** (`.github/workflows/ci.yml`):
```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, "3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov black isort flake8 mypy

    - name: Code formatting check
      run: |
        black --check .
        isort --check-only .

    - name: Linting
      run: |
        flake8 .
        mypy .

    - name: Run tests
      run: |
        pytest --cov=. --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### 3. 自動化腳本

**版本檢查腳本** (`scripts/check_version.sh`):
```bash
#!/bin/bash
# 檢查版本一致性

echo "Checking version consistency..."

VERSION=$(grep "version" pyproject.toml | head -1 | cut -d'"' -f2)
README_VERSION=$(grep "# SuperDog Backtest" README.md | grep -oE "v[0-9]+\.[0-9]+\.[0-9]+")
CHANGELOG_VERSION=$(grep -m 1 "\[" CHANGELOG.md | grep -oE "[0-9]+\.[0-9]+\.[0-9]+")

echo "pyproject.toml: $VERSION"
echo "README.md: $README_VERSION"
echo "CHANGELOG.md: $CHANGELOG_VERSION"

if [ "$VERSION" != "${README_VERSION#v}" ] || [ "$VERSION" != "$CHANGELOG_VERSION" ]; then
    echo "❌ Version mismatch detected!"
    exit 1
else
    echo "✅ Version consistent across all files"
fi
```

**文檔檢查腳本** (`scripts/check_docs.sh`):
```bash
#!/bin/bash
# 檢查文檔完整性

echo "Checking documentation..."

# 檢查 broken links
find docs -name "*.md" -exec grep -Ho '\[.*\](http' {} \; | while read -r line; do
    url=$(echo "$line" | grep -oP 'http[^)]+')
    if ! curl -s --head "$url" | grep "200 OK" > /dev/null; then
        echo "❌ Broken link: $url in $line"
    fi
done

# 檢查 TODO markers
if grep -r "TODO" docs/ --include="*.md" | grep -v "^docs/archive"; then
    echo "⚠️  Found TODO items in docs"
fi

echo "✅ Documentation check complete"
```

---

## 📖 附錄

### A. 違規處罰措施

**輕度違規**（警告）:
- 忘記更新文檔
- 代碼格式不符
- 測試覆蓋率不足

**中度違規**（PR 被退回）:
- 提交空檔案
- 版本號不一致
- 測試未通過

**重度違規**（暫停 commit 權限）:
- 刪除重要模組導致系統崩潰
- 提交未經審查的破壞性變更
- 繞過 CI/CD 直接推送到 main

### B. 審查流程

**Code Review Checklist**:
```
功能性：
□ 功能符合需求
□ 邊界情況處理正確
□ 錯誤處理完善

代碼質量：
□ 命名清晰
□ 邏輯易懂
□ 無重複代碼
□ 符合 SOLID 原則

測試：
□ 測試覆蓋率足夠
□ 測試案例完整
□ 測試可維護

文檔：
□ Docstrings 完整
□ Spec 已更新
□ README 已更新
□ CHANGELOG 已記錄

安全性：
□ 無安全漏洞
□ 輸入驗證完善
□ 敏感資料處理正確
```

### C. 聯絡資訊

- **技術問題**: GitHub Issues
- **安全問題**: security@superdog.com
- **一般諮詢**: support@superdog.com

---

**文件版本**: 1.0.0
**生效日期**: 2024-12-08
**最後更新**: 2024-12-08
**下次審查**: 2025-03-08

---

**聲明**: 本規章為強制性文件，所有開發者必須遵守。違反規章將影響代碼合併和項目參與權限。
