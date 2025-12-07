# Flake8 代碼質量修復計劃

**建立日期**: 2024-12-08
**總問題數**: 100+ 個
**預計修復時間**: 2-3 週 (分批進行)

---

## 📊 問題統計

### 按類型分類

| 錯誤代碼 | 描述 | 數量 | 優先級 | 預計時間 |
|---------|------|------|--------|---------|
| **F401** | 未使用的導入 | ~60 | 🟡 低 | 2 小時 |
| **F541** | f-string 無佔位符 | ~25 | 🟡 低 | 1 小時 |
| **E501** | 行太長 (>100字符) | ~10 | 🟡 低 | 1 小時 |
| **E402** | 模組導入位置錯誤 | ~8 | 🔴 高 | 1 小時 |
| **F841** | 未使用的變數 | ~5 | 🟢 中 | 30 分鐘 |
| **E722** | Bare except | 1 | 🔴 高 | 10 分鐘 |
| **F811** | 重複定義 | 1 | 🔴 高 | 10 分鐘 |
| **F821** | 未定義名稱 | 2 | 🔴 高 | 10 分鐘 |

### 按模組分類

| 模組 | 問題數 | 優先級 |
|------|--------|--------|
| `cli/main.py` | 20+ | 🔴 高 |
| `data/` 模組 | 40+ | 🟢 中 |
| `execution_engine/` | 15+ | 🟢 中 |
| `backtest/engine.py` | 10+ | 🟢 中 |
| `risk_management/` | 10+ | 🟡 低 |
| `tests/` | 5+ | 🟡 低 |

---

## 🎯 分批修復計劃

### Batch 1: 高優先級問題 (Week 1) 🔴

**目標**: 修復影響代碼正確性的問題
**預計時間**: 2 小時

#### Issue #1: 修復導入位置錯誤 (E402)
**受影響檔案** (8 個):
- [ ] `cli/main.py` - 5 處導入位置錯誤
- [ ] `tests/test_universe_v06.py` - 2 處
- [ ] 其他測試檔案

**修復方式**:
```python
# 錯誤: 導入在代碼後面
print("hello")
import os  # E402

# 正確: 所有導入在檔案開頭
import os
print("hello")
```

**預計時間**: 1 小時

---

#### Issue #2: 修復 Bare Except (E722)
**受影響檔案**:
- [ ] `cli/main.py:782` - 使用 bare except

**修復方式**:
```python
# 錯誤
try:
    something()
except:  # E722
    pass

# 正確
try:
    something()
except Exception as e:
    logger.error(f"Error: {e}")
```

**預計時間**: 10 分鐘

---

#### Issue #3: 修復重複定義 (F811)
**受影響檔案**:
- [ ] `data/universe_calculator.py:407` - timedelta 重複定義

**修復方式**:
```python
# 錯誤
from datetime import timedelta  # Line 19
# ... 代碼 ...
from datetime import timedelta  # Line 407 - F811

# 正確: 移除重複的導入
```

**預計時間**: 10 分鐘

---

#### Issue #4: 修復未定義名稱 (F821)
**受影響檔案**:
- [ ] `data_config.py:112` - 未定義的 `pd`
- [ ] `data_config.py:118` - 未定義的 `pd`

**修復方式**:
```python
# 添加缺失的導入
import pandas as pd
```

**預計時間**: 10 分鐘

---

### Batch 2: 中優先級問題 (Week 2) 🟢

**目標**: 清理未使用的代碼
**預計時間**: 3 小時

#### Issue #5: 移除未使用的導入 (F401)
**受影響檔案** (~30 個):

**高頻問題檔案**:
- [ ] `cli/main.py` - 10+ 個未使用導入
- [ ] `cli/dynamic_params.py`
- [ ] `cli/interactive/main_menu.py`
- [ ] `data/pipeline.py`
- [ ] `data/storage.py`
- [ ] `data/universe_manager.py`
- [ ] `execution_engine/` 模組 (多個檔案)
- [ ] `risk_management/` 模組 (多個檔案)
- [ ] `tests/` 模組 (多個檔案)

**修復方式**:
```python
# 錯誤
from typing import Optional, List, Dict  # F401 if not used
import numpy as np  # F401 if not used

# 正確: 只導入使用的
from typing import List  # 只保留用到的
```

**工具輔助**:
```bash
# 使用 autoflake 自動移除
pip install autoflake
autoflake --in-place --remove-unused-variables --remove-all-unused-imports cli/main.py
```

**預計時間**: 2 小時 (手動檢查 + 批量處理)

---

#### Issue #6: 移除未使用的變數 (F841)
**受影響檔案**:
- [ ] `backtest/engine.py:210` - `original_buy_all`
- [ ] `cli/main.py:368` - 變數 `e`
- [ ] `cli/main.py:374` - 變數 `e`
- [ ] `data/exchanges/binance_connector.py:92` - `estimated_records`
- [ ] `tests/test_risk_management_v06.py:445` - `stop_manager`

**修復方式**:
```python
# 錯誤
e = calculate()  # F841 - 未使用

# 正確 - 選項 1: 移除
# (刪除這行)

# 正確 - 選項 2: 重命名表示故意忽略
_ = calculate()  # 明確表示不使用返回值
```

**預計時間**: 30 分鐘

---

### Batch 3: 低優先級問題 (Week 3) 🟡

**目標**: 改善代碼風格
**預計時間**: 2 小時

#### Issue #7: 修復 f-string 無佔位符 (F541)
**受影響檔案** (~15 個):
- [ ] `backtest/engine.py` - 2 處
- [ ] `cli/interactive/main_menu.py` - 8 處
- [ ] `cli/main.py` - 10 處
- [ ] `data/fetcher.py` - 1 處
- [ ] `data/storage.py` - 1 處
- [ ] `verify_v06_phase2.py` - 4 處

**修復方式**:
```python
# 錯誤
print(f"Starting process...")  # F541 - 不需要 f-string

# 正確
print("Starting process...")  # 使用普通字串
```

**預計時間**: 1 小時

---

#### Issue #8: 修復過長的行 (E501)
**受影響檔案** (~8 個):
- [ ] `backtest/engine.py:4` - 101 字符
- [ ] `cli/main.py:588` - 112 字符
- [ ] `data/pipeline.py:216` - 101 字符
- [ ] `data/quality/controller.py:368` - 107 字符
- [ ] 其他檔案

**修復方式**:
```python
# 錯誤 - 超過 100 字符
result = some_very_long_function_name(parameter1, parameter2, parameter3, parameter4, parameter5)  # E501

# 正確 - 選項 1: 分行
result = some_very_long_function_name(
    parameter1, parameter2, parameter3,
    parameter4, parameter5
)

# 正確 - 選項 2: 如果無法分行,添加 noqa
result = some_very_long_function_name(parameter1, parameter2, parameter3, parameter4, parameter5)  # noqa: E501
```

**預計時間**: 1 小時

---

## 🛠️ 修復工具和命令

### 自動化工具

#### 1. autoflake - 移除未使用的導入和變數
```bash
pip install autoflake

# 單個檔案
autoflake --in-place --remove-unused-variables --remove-all-unused-imports file.py

# 整個專案
find . -name "*.py" -not -path "./.venv/*" -not -path "./.trash/*" | \
  xargs autoflake --in-place --remove-unused-variables --remove-all-unused-imports
```

#### 2. black - 自動格式化 (已配置)
```bash
black file.py
```

#### 3. isort - 排序導入 (已配置)
```bash
isort file.py
```

### 手動檢查命令

#### 只檢查特定錯誤
```bash
# 只檢查 E402 (導入位置)
flake8 --select=E402 .

# 只檢查 F401 (未使用導入)
flake8 --select=F401 .

# 檢查特定檔案
flake8 cli/main.py
```

#### 生成修復報告
```bash
# 輸出到檔案
flake8 . > flake8_report.txt

# 按檔案分組
flake8 --format='%(path)s:%(row)d:%(col)d: %(code)s %(text)s' . | \
  sort > flake8_sorted.txt
```

---

## 📋 執行檢查清單

### Week 1: 高優先級 (必須)
- [ ] Issue #1: 修復 E402 導入位置錯誤 (8 個檔案)
- [ ] Issue #2: 修復 E722 bare except (1 處)
- [ ] Issue #3: 修復 F811 重複定義 (1 處)
- [ ] Issue #4: 修復 F821 未定義名稱 (2 處)
- [ ] 執行測試驗證無破壞
- [ ] 提交: `fix: Resolve high-priority flake8 issues`

### Week 2: 中優先級 (推薦)
- [ ] Issue #5: 移除未使用的導入 F401 (~30 個檔案)
  - [ ] 使用 autoflake 批量處理
  - [ ] 手動檢查關鍵檔案
  - [ ] 執行測試驗證
- [ ] Issue #6: 移除未使用的變數 F841 (5 處)
- [ ] 執行完整測試套件
- [ ] 提交: `refactor: Remove unused imports and variables`

### Week 3: 低優先級 (可選)
- [ ] Issue #7: 修復 f-string 無佔位符 F541 (~15 個檔案)
- [ ] Issue #8: 修復過長的行 E501 (~8 個檔案)
- [ ] 執行測試驗證
- [ ] 提交: `style: Fix f-strings and long lines`

### 最終驗證
- [ ] 執行 `pre-commit run --all-files`
- [ ] 確認 flake8 全部通過
- [ ] 執行 `python3 superdog_v06_complete_validation.py`
- [ ] 確認 95.7% 測試通過率維持
- [ ] 更新 CHANGELOG.md
- [ ] 建立 Pull Request (如使用)

---

## 🎯 成功標準

### 最低要求 (Week 1 完成後)
- ✅ 無 E402, E722, F811, F821 錯誤
- ✅ 測試通過率 ≥ 95.7%
- ✅ 核心功能無破壞

### 理想狀態 (Week 3 完成後)
- ✅ Flake8 零錯誤
- ✅ 代碼風格一致
- ✅ Pre-commit hooks 全部通過
- ✅ 測試覆蓋率維持或提升

---

## 📝 暫時繞過方案 (開發期間)

如果需要在修復前繼續開發,可以暫時修改 `.pre-commit-config.yaml`:

```yaml
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        # 暫時只檢查高優先級錯誤
        args: ['--select=E402,E722,F811,F821']
        # 或者設為警告模式 (不阻止提交)
        # args: ['--exit-zero']
```

修改後重新安裝:
```bash
pre-commit install --overwrite
```

---

## 📊 進度追蹤

### 當前狀態: 🔴 未開始

| Batch | 狀態 | 完成日期 | 提交 Hash | 備註 |
|-------|------|---------|-----------|------|
| Batch 1 (高優先級) | ⏳ 待處理 | - | - | 必須完成 |
| Batch 2 (中優先級) | ⏳ 待處理 | - | - | 推薦完成 |
| Batch 3 (低優先級) | ⏳ 待處理 | - | - | 可選 |

### 更新記錄

| 日期 | 更新內容 |
|------|---------|
| 2024-12-08 | 建立修復計劃 |
| - | - |

---

## 💡 注意事項

### ⚠️ 修復時的注意事項

1. **每次修復後立即測試**
   ```bash
   python3 superdog_v06_complete_validation.py
   ```

2. **分批提交**
   - 不要一次修復所有問題
   - 每個 batch 完成後提交一次
   - 保持提交歷史清晰

3. **備份重要檔案**
   - 修復 `cli/main.py` 等關鍵檔案前先備份
   - 或使用 git stash

4. **使用工具但要驗證**
   - autoflake 等工具可能誤刪
   - 手動檢查自動修復的結果

### 🎓 學習資源

- [Flake8 錯誤代碼說明](https://flake8.pycqa.org/en/latest/user/error-codes.html)
- [PEP 8 風格指南](https://peps.python.org/pep-0008/)
- [Black 代碼格式化](https://black.readthedocs.io/)

---

**計劃版本**: 1.0.0
**建立時間**: 2024-12-08
**維護者**: Development Team

**下一步**: 開始 Batch 1 - 高優先級問題修復
