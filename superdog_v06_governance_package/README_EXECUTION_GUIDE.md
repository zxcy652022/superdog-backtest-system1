# SuperDog v0.6 架構清理與治理 - 執行指南

**生成日期**: 2024-12-08
**目標版本**: v0.6.1 (清理後)
**預計清理時間**: 2-4 小時

---

## 📦 交付內容總覽

本次交付包含以下文檔和工具：

### 1. 核心文檔 (3 份)

#### 📄 SUPERDOG_V06_ARCHITECTURE_ANALYSIS.md
**完整架構分析報告**
- 專案現狀統計
- 發現的 21 個空檔案
- 13 個過時規格文檔
- 5 個備份/臨時檔案
- 版本不一致問題
- 詳細的清理執行方案
- 預期成果與改善指標

#### 📘 SUPERDOG_DEVELOPMENT_GOVERNANCE.md
**開發維護規章（長期規範）**
- 核心開發原則
- 版本管理規範
- 代碼規範（命名、類型註解、Docstring）
- 文檔規範（結構、模板、更新規則）
- 模組管理規範（建立、淘汰、組織）
- 測試規範（覆蓋率、命名、結構）
- 發布流程（Pre-release checklist）
- 問題處理流程

#### 📗 SUPERDOG_UNIFIED_STRATEGY_API_SPEC_V06.md
**統一策略 API 規格（v0.6 標準）**
- BaseStrategy 完整規格
- ParameterSpec 參數系統
- DataRequirement 數據聲明
- StrategyMetadata 元數據
- 完整策略模板（可直接使用）
- 測試規範
- 最佳實踐和常見問題

### 2. 工具腳本 (1 個)

#### 🔧 cleanup_v06.py
**安全清理執行腳本**
- 自動備份專案
- 安全刪除（移動到 .trash/）
- 過時規格歸檔
- 空檔案清理
- 舊模組檢查
- Dry-run 預覽模式
- 詳細操作日誌

---

## 🚀 立即執行步驟

### Step 1: 預覽清理操作（必須先執行）

```bash
# 進入專案根目錄
cd /path/to/superdog

# 複製清理腳本到專案根目錄
cp cleanup_v06.py .

# 執行預覽（不會實際修改任何檔案）
python cleanup_v06.py --dry-run
```

**檢查輸出**:
- 確認要刪除的檔案都是正確的
- 檢查是否有誤刪的風險
- 查看歸檔路徑是否正確

### Step 2: 手動確認關鍵檔案

在執行清理前，手動檢查以下項目：

```bash
# 1. 確認 risk/ 模組未被使用
grep -r "from risk\." . --include="*.py" | grep -v "__pycache__"

# 2. 確認 utils/ 模組未被使用
grep -r "from utils" . --include="*.py" | grep -v "__pycache__"

# 3. 確認空策略檔案未被 import
grep -r "from strategies.base" . --include="*.py"
grep -r "from strategies.indicators" . --include="*.py"
```

**預期結果**: 應該沒有任何輸出（表示未被使用）

### Step 3: 執行實際清理

```bash
# ⚠️  確認無誤後執行
python cleanup_v06.py --execute

# 腳本會要求二次確認，輸入 y 繼續
```

**執行過程**:
1. 備份專案到 `.backup/YYYYMMDD_HHMMSS/`
2. 刪除檔案移動到 `.trash/YYYYMMDD_HHMMSS/`
3. 歸檔過時規格到 `docs/archive/`
4. 生成操作日誌 `cleanup_log_YYYYMMDD_HHMMSS.json`

### Step 4: 驗證清理結果

```bash
# 1. 檢查是否有空檔案殘留
find . -type f -name "*.py" -size 0 | grep -v __pycache__ | grep -v ".trash"

# 2. 執行完整測試套件
python superdog_v06_complete_validation.py

# 3. 檢查 import 錯誤
python -m pytest tests/ --collect-only

# 4. 執行簡單回測驗證
python examples/kawamoku_complete_v05.py
```

**預期結果**:
- 測試成功率應該維持或提升（≥95%）
- 無 import 錯誤
- 範例程式正常執行

### Step 5: 更新文檔

#### 5.1 更新 README.md

```bash
# 手動編輯或使用以下命令替換版本號
sed -i 's/v0.3/v0.6/g' README.md
```

**主要更新內容**:
```markdown
# SuperDog Backtest v0.6.0

企業級加密貨幣量化回測引擎。v0.6 實現四大核心系統：
- 幣種宇宙管理 (Universe Manager)
- 策略實驗室 (Strategy Lab)
- 真實執行模型 (Execution Model)
- 動態風控系統 (Risk Management)

## 快速開始

### 單策略回測（v0.6 API）
\`\`\`python
from execution_engine.portfolio_runner import PortfolioRunner
from strategies.registry_v2 import get_registry

registry = get_registry()
strategy_class = registry.get_strategy("simple_sma")

runner = PortfolioRunner(
    strategy=strategy_class,
    symbols=["BTCUSDT"],
    timeframe="1h"
)
result = runner.run()
\`\`\`
```

#### 5.2 建立規格索引

在 `docs/specs/v0.6/README.md`:

```markdown
# SuperDog v0.6 規格索引

## 當前有效規格（v0.6）

### 核心系統
- [統一策略 API](UNIFIED_STRATEGY_API.md) - 所有策略必須遵循
- [幣種宇宙管理](superdog_v06_universe_manager_spec.md)
- [策略實驗室](superdog_v06_strategy_lab_spec.md)
- [執行模型](superdog_v06_execution_model_spec.md)
- [風控系統](../../V06_PHASE4_RISK_MANAGEMENT.md)

### 開發規範
- [開發維護規章](../../DEVELOPMENT_GOVERNANCE.md)
- [貢獻指南](../../CONTRIBUTING.md)

## 歷史版本

舊版本規格已歸檔至 `docs/archive/`
```

#### 5.3 更新 CHANGELOG.md

```markdown
## [0.6.1] - 2024-12-08

### Changed - 架構清理
- 🧹 清理 21 個空檔案
- 📦 歸檔 13 個過時規格文檔
- 🗑️  刪除 5 個備份/臨時檔案
- 📝 更新 README 到 v0.6
- 📘 建立統一策略 API 規格
- 📗 建立開發維護規章

### Removed
- risk/ 模組（已被 risk_management/ 完全取代）
- utils/ 模組（未使用）
- strategies/base.py（已被 api_v2.py 取代）
- strategies/indicators.py（未實作）
- strategies/mean_reversion.py（未實作）
- strategies/trend_follow.py（未實作）

### Documentation
- 新增：統一策略 API 規格 v0.6
- 新增：開發維護規章
- 新增：架構分析報告
```

### Step 6: Git 提交

```bash
# 1. 查看變更
git status

# 2. 添加所有變更
git add .

# 3. 提交（包含詳細說明）
git commit -m "refactor: Architecture cleanup v0.6.1

- Remove 21 empty files
- Archive 13 outdated spec docs
- Delete 5 backup/temp files
- Remove deprecated risk/ and utils/ modules
- Update README to v0.6
- Add unified strategy API spec
- Add development governance

BREAKING CHANGE: Removed risk/ module (use risk_management/ instead)

Refs: #cleanup, #v0.6.1"

# 4. 創建標籤
git tag -a v0.6.1 -m "Release v0.6.1: Architecture cleanup"

# 5. 推送
git push origin main
git push origin v0.6.1
```

### Step 7: 驗證最終結果

```bash
# 1. 檢查專案結構
tree -L 2 -I '__pycache__|*.pyc|.trash|.backup'

# 2. 統計代碼行數
find . -name "*.py" -not -path "*/.trash/*" -not -path "*/.backup/*" \
  -not -path "*/__pycache__/*" | xargs wc -l | tail -1

# 3. 檢查文檔完整性
ls -lh docs/specs/v0.6/
ls -lh docs/archive/

# 4. 最終測試
python superdog_v06_complete_validation.py
```

---

## 📋 清理檢查清單

使用以下檢查清單確保所有步驟完成：

### 清理前準備
- [ ] 已閱讀架構分析報告
- [ ] 已閱讀開發維護規章
- [ ] 已執行 dry-run 預覽
- [ ] 已手動確認關鍵檔案未被使用
- [ ] 已通知團隊成員（如有）

### 執行清理
- [ ] 執行 `cleanup_v06.py --execute`
- [ ] 確認備份已創建
- [ ] 確認操作日誌已生成
- [ ] 檢查 .trash/ 目錄內容

### 清理後驗證
- [ ] 無空檔案殘留
- [ ] 測試套件通過（≥95%）
- [ ] 無 import 錯誤
- [ ] 範例程式正常執行

### 文檔更新
- [ ] README.md 已更新到 v0.6
- [ ] CHANGELOG.md 已記錄變更
- [ ] 建立 docs/specs/v0.6/README.md
- [ ] 複製統一策略 API 規格到 docs/specs/v0.6/
- [ ] 複製開發規章到 docs/

### Git 管理
- [ ] 提交清理變更
- [ ] 創建 v0.6.1 標籤
- [ ] 推送到遠端

### 長期維護
- [ ] 設定 pre-commit hooks（可選）
- [ ] 建立定期清理流程（每月/季度）
- [ ] 團隊培訓開發規章

---

## ⚠️ 常見問題與解決

### Q1: 執行清理後測試失敗？

**可能原因**:
- 刪除了仍在使用的檔案
- import 路徑錯誤

**解決方案**:
```bash
# 1. 從備份恢復
cp -r .backup/YYYYMMDD_HHMMSS/* .

# 2. 檢查具體錯誤
python -m pytest tests/ -v

# 3. 手動修復 import 路徑
```

### Q2: 如何撤銷清理？

```bash
# 完全恢復（如果在執行清理的同一天）
rm -rf backtest cli data execution_engine risk_management strategies tests
cp -r .backup/YYYYMMDD_HHMMSS/* .

# 或從 .trash/ 恢復特定檔案
cp .trash/YYYYMMDD_HHMMSS/path/to/file original/path/
```

### Q3: 清理後專案大小變化？

**預期變化**:
- 檔案數量: ↓ ~30 個
- 代碼行數: 不變（只刪除空檔案和文檔）
- 專案大小: ↓ ~100-200KB（主要是文檔）

### Q4: 發現遺漏的空檔案？

```bash
# 手動查找並刪除
find . -type f -name "*.py" -size 0 -not -path "*/.trash/*" -not -path "*/__pycache__/*"

# 確認未被使用後刪除
rm path/to/empty/file.py
```

---

## 📊 預期成果

### 量化指標改善

| 指標 | 清理前 | 清理後 | 改善 |
|------|--------|--------|------|
| 空檔案數量 | 21 | 3 | ↓ 86% |
| 過時規格文檔 | 13 | 0 | ↓ 100% |
| 備份/臨時檔案 | 5 | 0 | ↓ 100% |
| 版本不一致 | 1 | 0 | ✅ 修復 |
| 文檔覆蓋率 | ~60% | ~95% | ↑ 35% |
| 冗餘模組 | 2 (risk, utils) | 0 | ↓ 100% |

### 質量改善

**架構清晰度**: ⭐⭐⭐ → ⭐⭐⭐⭐⭐
- 移除混淆的舊模組
- 統一的策略 API
- 清晰的文檔結構

**可維護性**: ⭐⭐⭐ → ⭐⭐⭐⭐⭐
- 建立開發規章
- 自動化清理工具
- 完整的測試覆蓋

**新人友善度**: ⭐⭐ → ⭐⭐⭐⭐
- 清晰的快速開始指南
- 完整的 API 規格
- 豐富的範例程式碼

---

## 🎯 下一步建議

### 短期（1-2 週）
1. **實施 pre-commit hooks**: 防止空檔案和格式問題
2. **建立 CI/CD 自動測試**: 每次 commit 自動驗證
3. **撰寫貢獻指南**: 方便外部貢獻者

### 中期（1-2 個月）
1. **完善策略範例**: 至少 5 個不同類型的策略
2. **建立策略市場**: 社群分享和評價策略
3. **性能優化**: 提升回測速度 2-3 倍

### 長期（3-6 個月）
1. **Web UI**: 視覺化回測介面
2. **自動報告生成**: PDF/HTML 格式
3. **實盤交易整合**: 從回測到實盤的完整流程

---

## 📞 支援與回饋

如果在清理過程中遇到任何問題：

1. **查看操作日誌**: `cleanup_log_YYYYMMDD_HHMMSS.json`
2. **檢查備份**: `.backup/YYYYMMDD_HHMMSS/`
3. **查看垃圾桶**: `.trash/YYYYMMDD_HHMMSS/`
4. **參考文檔**: 三份核心文檔提供詳細說明

**祝清理順利！** 🎉

---

**文件版本**: 1.0.0
**最後更新**: 2024-12-08
**維護者**: Architecture Team
