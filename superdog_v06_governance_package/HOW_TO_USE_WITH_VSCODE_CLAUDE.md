# VS Code Claude 使用說明

## 📥 下載後的使用步驟

### Step 1: 解壓縮檔案
將 `superdog_v06_governance_package.zip` 解壓縮到你的 SuperDog 專案目錄中

### Step 2: 在 VS Code 中開啟專案
```bash
code /path/to/your/superdog/project
```

### Step 3: 與 VS Code Claude 互動

#### 方式 1: 直接請 Claude 執行清理

複製以下指令給 VS Code Claude：

```
請幫我執行 SuperDog v0.6 架構清理：

1. 先閱讀 00_START_HERE.md 了解整體架構
2. 閱讀 README_EXECUTION_GUIDE.md 了解執行步驟
3. 執行 `python cleanup_v06.py --dry-run` 預覽清理操作
4. 如果預覽結果正確，再執行 `python cleanup_v06.py --execute`
5. 清理完成後執行驗證測試

請一步步執行，並在每個步驟後告訴我結果。
```

#### 方式 2: 分步驟請 Claude 協助

**第一步：了解現狀**
```
請閱讀 SUPERDOG_V06_ARCHITECTURE_ANALYSIS.md，並總結：
1. 發現了哪些主要問題？
2. 哪些是高風險的清理操作？
3. 清理後預期的改善效果？
```

**第二步：預覽清理**
```
請執行 cleanup_v06.py --dry-run，並分析輸出結果：
1. 哪些檔案會被刪除？
2. 是否有誤刪風險？
3. 建議我執行嗎？
```

**第三步：執行清理**
```
請執行 cleanup_v06.py --execute，並在完成後：
1. 執行測試驗證
2. 檢查是否有 import 錯誤
3. 告訴我清理結果
```

**第四步：更新文檔**
```
請根據 README_EXECUTION_GUIDE.md 的指示：
1. 更新 README.md 到 v0.6
2. 更新 CHANGELOG.md
3. 建立 docs/specs/v0.6/README.md
```

#### 方式 3: 請 Claude 協助理解規範

```
我想了解 SuperDog 的開發規範，請閱讀 SUPERDOG_DEVELOPMENT_GOVERNANCE.md，並回答：

1. 代碼命名規範是什麼？
2. 如何處理空檔案？
3. 發布新版本時需要檢查什麼？
4. 如何設定 pre-commit hooks？

請給我具體的例子。
```

#### 方式 4: 請 Claude 協助開發策略

```
我想開發一個新的交易策略，請閱讀 SUPERDOG_UNIFIED_STRATEGY_API_SPEC_V06.md，然後：

1. 幫我建立一個基於 RSI 的策略模板
2. 確保符合統一 API 規範
3. 包含完整的參數定義和測試
4. 遵循所有最佳實踐
```

### Step 4: 重要文檔說明

| 文檔 | 用途 | 何時使用 |
|------|------|---------|
| **00_START_HERE.md** | 快速導航 | 第一次使用時 |
| **README_EXECUTION_GUIDE.md** | 執行手冊 | 執行清理時 |
| **SUPERDOG_V06_ARCHITECTURE_ANALYSIS.md** | 問題分析 | 了解為什麼要清理 |
| **SUPERDOG_DEVELOPMENT_GOVERNANCE.md** | 開發規範 | 日常開發參考 |
| **SUPERDOG_UNIFIED_STRATEGY_API_SPEC_V06.md** | 策略規範 | 開發策略時 |
| **cleanup_v06.py** | 清理工具 | 執行清理 |

### Step 5: 安全注意事項

⚠️ **在執行清理前**：

1. 確保已經提交所有變更到 Git
2. 先執行 `--dry-run` 預覽
3. 閱讀預覽輸出，確認沒有誤刪風險
4. 備份會自動創建在 `.backup/` 目錄

⚠️ **如果需要撤銷**：

```bash
# 從備份恢復
cp -r .backup/YYYYMMDD_HHMMSS/* .

# 或從垃圾桶恢復特定檔案
cp .trash/YYYYMMDD_HHMMSS/path/to/file original/path/
```

---

## 🎯 推薦的執行流程

### 快速流程（1小時）

1. **閱讀** 00_START_HERE.md（5分鐘）
2. **請 Claude 預覽清理** `python cleanup_v06.py --dry-run`（10分鐘）
3. **請 Claude 執行清理** `python cleanup_v06.py --execute`（20分鐘）
4. **請 Claude 驗證結果** 執行測試、檢查 import（20分鐘）
5. **請 Claude 更新文檔** README.md, CHANGELOG.md（5分鐘）

### 標準流程（3-4小時）

1. **請 Claude 分析架構** 閱讀 ARCHITECTURE_ANALYSIS.md（30分鐘）
2. **請 Claude 執行清理** 包含預覽、執行、驗證（1小時）
3. **請 Claude 學習規範** 閱讀 DEVELOPMENT_GOVERNANCE.md（1小時）
4. **請 Claude 更新文檔** 包含規格索引（1小時）
5. **請 Claude 設定工具** Pre-commit hooks, CI/CD（30分鐘）

### 完整流程（1-2天）

1. **第一天上午**：架構分析和清理執行
2. **第一天下午**：文檔更新和規範學習
3. **第二天上午**：策略 API 學習和範例開發
4. **第二天下午**：工具設定和團隊培訓準備

---

## 💡 與 Claude 互動技巧

### 好的提問方式

✅ **具體且有步驟**
```
請先閱讀 cleanup_v06.py 的代碼，了解它會做什麼，
然後執行 --dry-run 預覽，最後告訴我是否建議執行。
```

✅ **要求解釋**
```
ARCHITECTURE_ANALYSIS.md 中提到的「空檔案問題」，
請解釋為什麼這是個問題，以及清理後會如何改善。
```

✅ **請求驗證**
```
清理完成後，請幫我驗證：
1. 測試是否都通過
2. 是否有 import 錯誤
3. 範例程式是否正常運行
並給我一份驗證報告。
```

### 避免的提問方式

❌ **太籠統**
```
幫我清理專案
```

❌ **沒有上下文**
```
執行清理腳本
```
（應該說明是哪個腳本、要達成什麼目的）

❌ **跳過閱讀文檔**
```
直接幫我改
```
（應該先讓 Claude 閱讀相關文檔）

---

## 📚 常見場景

### 場景 1: 我想快速清理

```
請幫我快速執行 SuperDog v0.6 的架構清理：

1. 閱讀 README_EXECUTION_GUIDE.md 的「5分鐘快速開始」章節
2. 執行 cleanup_v06.py --dry-run
3. 如果看起來正常，執行 cleanup_v06.py --execute
4. 驗證清理結果
5. 給我一個簡短的清理報告

請開始執行。
```

### 場景 2: 我想了解規範

```
我想建立長期的開發規範，請幫我：

1. 閱讀 SUPERDOG_DEVELOPMENT_GOVERNANCE.md
2. 總結最重要的 5 條規範
3. 告訴我如何設定 pre-commit hooks
4. 提供一個完整的 .pre-commit-config.yaml 範例

請詳細說明。
```

### 場景 3: 我想開發策略

```
我想開發一個基於布林通道的策略，請幫我：

1. 閱讀 SUPERDOG_UNIFIED_STRATEGY_API_SPEC_V06.md
2. 根據統一 API 規範建立策略模板
3. 包含完整的參數定義、數據需求、信號計算
4. 添加完整的測試
5. 確保符合所有最佳實踐

請生成完整的策略代碼。
```

### 場景 4: 我遇到問題

```
清理後測試失敗了，請幫我：

1. 查看 cleanup_log_*.json 了解執行了哪些操作
2. 檢查錯誤訊息找出問題原因
3. 參考 README_EXECUTION_GUIDE.md 的「常見問題」章節
4. 提供解決方案
5. 如果需要，告訴我如何從備份恢復

請協助我解決問題。
```

---

## 🎉 開始使用

選擇一個場景，複製對應的提示詞給 VS Code Claude，開始你的清理之旅！

**祝順利！** 🚀

---

**提示**: VS Code Claude 可以直接讀取和執行這些文檔中的所有內容，充分利用它的能力！
