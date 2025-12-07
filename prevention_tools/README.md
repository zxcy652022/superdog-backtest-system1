# SuperDog 防護工具包

這個工具包包含所有防止專案髒亂的自動化工具。

## 📦 包含內容

1. **PREVENTION_SYSTEM_GUIDE.md** - 完整防護系統指南
2. **.pre-commit-config.yaml** - Pre-commit hooks 配置
3. **check_empty_files.py** - 空檔案檢查腳本
4. **check_version.py** - 版本一致性檢查腳本
5. **monthly_cleanup.sh** - 每月清理檢查腳本

## 🚀 快速安裝

```bash
# 1. 複製所有檔案到專案根目錄
cp .pre-commit-config.yaml /path/to/superdog/
mkdir -p /path/to/superdog/scripts
cp check_*.py monthly_cleanup.sh /path/to/superdog/scripts/

# 2. 安裝 pre-commit
cd /path/to/superdog
pip install pre-commit

# 3. 安裝 hooks
pre-commit install

# 4. 測試
pre-commit run --all-files
```

## ✅ 效果

安裝後：
- ✅ 無法提交空檔案
- ✅ 無法提交備份檔案（.backup, .bak等）
- ✅ 自動檢查版本一致性
- ✅ 自動格式化代碼
- ✅ 防止提交到 main 分支

## 📚 詳細說明

請閱讀 **PREVENTION_SYSTEM_GUIDE.md** 了解：
- 為什麼需要這些工具
- 如何使用每個工具
- 如何養成好習慣
- 完整的實施計畫
