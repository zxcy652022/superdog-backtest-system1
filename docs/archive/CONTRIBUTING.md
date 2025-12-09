# 開發規範

本文件說明 SuperDog Backtest System 的開發流程與規範。

---

## 🔄 開發流程

### 新增功能

1. **規劃階段**
   - 在 VS Code 中使用 Claude Chat 模式討論需求
   - 確認技術設計與架構影響
   - 撰寫 spec 文件於 `docs/specs/planned/`

2. **實作階段**
   - 切換到 Agent 模式
   - Claude 直接修改檔案
   - 同步更新文件與測試

3. **驗證階段**
   ```bash
   pytest  # 執行所有測試
   python -m backtest ...  # 實際跑回測
   ```

4. **提交階段**
   ```bash
   git add .
   git commit -m "feat: 功能描述"
   git push
   ```

5. **文件更新**
   - 移動 spec 從 `planned/` 到 `implemented/`
   - 更新 CHANGELOG.md
   - 如有重大決策，新增 `docs/decisions/YYYY-MM-DD_topic.md`

---

## 📝 Commit Message 規範

使用 Conventional Commits 格式：

```
feat: 新增功能
fix: 修復 bug
docs: 文件更新
test: 測試相關
refactor: 重構
chore: 雜項（清理、設定等）
```

範例：
```
feat: add short position support in broker
fix: correct SL trigger logic for short positions
docs: update v0.3 architecture spec
test: add 15 test cases for short positions
refactor: merge duplicate position_sizer modules
chore: cleanup obsolete test files
```

---

## 🚫 禁止的行為

❌ **不允許**：
- Code 改了但文件沒改
- 建立「未實作」的資料夾或檔案佔位
- 重複的模組或功能
- 過期的 spec 檔案沒歸檔
- 測試沒通過就提交

✅ **必須做到**：
- 每個 commit 包含：code + 文件 + 測試
- 所有測試通過才能 push
- 重大設計決策記錄在 `docs/decisions/`
- Spec 與實際 code 保持一致

---

## 🧪 測試要求

### 必須通過的測試
```bash
# 單元測試
pytest

# 型別檢查（如果使用 mypy）
mypy backtest/ strategies/

# 程式碼風格（如果使用 black）
black --check .
```

### 測試涵蓋率目標
- 核心模組（backtest/）：> 80%
- 策略模組（strategies/）：> 70%
- 工具模組（utils/）：> 60%

---

## 📂 檔案組織規則

### Spec 檔案
- 規劃中 → `docs/specs/planned/vX.X_feature.md`
- 已實作 → `docs/specs/implemented/vX.X_feature.md`
- 不要留在根目錄

### 決策記錄
- 格式：`docs/decisions/YYYY-MM-DD_topic.md`
- 內容：背景、選項、決定、理由、後果

### 測試檔案
- 命名：`test_<module_name>.py`
- 不要有 `_old`、`_backup` 等後綴
- 過期的測試直接刪除，不要保留

---

## 🔍 每月檢查清單

在每個月最後一個工作日執行：

```bash
# 1. 執行完整測試
pytest --cov=backtest --cov=strategies

# 2. 檢查文件一致性
# - README.md 版本號是否最新
# - CHANGELOG.md 是否更新
# - docs/specs/ 是否有遺漏的檔案

# 3. 檢查技術債
# - TODO 註解
# - 暫時性的 workaround
# - 重複的程式碼

# 4. 生成健康報告
# （未來可自動化）
```

---

## 💡 最佳實踐

1. **小步快跑**：每個 PR 專注一個功能
2. **測試先行**：可能的話，先寫測試
3. **文件同步**：code 和 doc 在同一個 commit
4. **及時重構**：發現重複就立刻重構
5. **保持簡單**：能用簡單方法就不要複雜化

---

## 🆘 遇到問題時

1. 先查看 `docs/decisions/` 是否有相關決策
2. 檢查 `docs/specs/implemented/` 了解現有設計
3. 在 VS Code 中詢問 Claude
4. 如果是重大問題，記錄決策過程
