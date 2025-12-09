# 編碼問題指南

## 問題描述

在 2025-12-02 發現專案中的 Python 檔案出現中文亂碼問題。三個主要數據模組檔案的中文註解全部變成問號（?）：

- `data/fetcher.py` - 被儲存為 ASCII 編碼
- `data/validator.py` - 被儲存為 ASCII 編碼
- `data/storage.py` - 被儲存為 binary 編碼

## 根本原因

Python 原始碼檔案預設應該使用 **UTF-8 編碼**（根據 PEP 3120），但由於以下原因可能導致編碼問題：

1. **編輯器設定不當**：某些編輯器或 IDE 可能預設使用系統編碼（如 ASCII 或 Big5）
2. **缺少專案級編碼規範**：沒有 `.editorconfig` 或 VSCode 設定檔強制使用 UTF-8
3. **檔案建立方式**：透過某些工具或腳本建立檔案時未指定編碼

## 解決方案

### 1. 立即修正

已將三個檔案重新寫入並確保使用 UTF-8 編碼：

```bash
# 驗證編碼
file -I data/fetcher.py data/validator.py data/storage.py

# 結果應顯示：
# data/fetcher.py:   text/plain; charset=utf-8
# data/validator.py: text/plain; charset=utf-8
# data/storage.py:   text/plain; charset=utf-8
```

### 2. 預防措施

#### A. EditorConfig（跨編輯器通用）

已建立 `.editorconfig` 檔案，內容包含：

```ini
[*.py]
charset = utf-8
indent_style = space
indent_size = 4
```

這會被大多數現代編輯器支援（VSCode, PyCharm, Sublime Text 等）。

#### B. VSCode 專案設定

已建立 `.vscode/settings.json`，強制使用 UTF-8：

```json
{
  "files.encoding": "utf8",
  "files.autoGuessEncoding": false,
  "[python]": {
    "files.encoding": "utf8"
  }
}
```

#### C. Python 檔案標頭（可選）

對於特別重要的檔案，可以在檔案開頭加入編碼宣告：

```python
# -*- coding: utf-8 -*-
```

但在 Python 3 中這不是必須的，因為 UTF-8 已是預設值。

### 3. 檢查編碼的方法

使用以下命令檢查專案中所有 Python 檔案的編碼：

```bash
# 檢查單個檔案
file -I filename.py

# 檢查所有 Python 檔案
find . -name "*.py" -type f -exec file -I {} \;

# 或使用 chardet（需要安裝 chardet 套件）
python -c "import chardet; print(chardet.detect(open('filename.py', 'rb').read()))"
```

### 4. Git 設定

確保 Git 正確處理文字檔案編碼，在 `.gitattributes` 中設定：

```
*.py text eol=lf encoding=utf-8
*.md text eol=lf encoding=utf-8
```

## 最佳實踐

1. **始終使用 UTF-8**：所有文字檔案（Python、Markdown、配置檔等）都使用 UTF-8
2. **提交前檢查**：在 Git commit 前檢查檔案編碼
3. **使用 EditorConfig**：確保團隊成員的編輯器設定一致
4. **CI/CD 檢查**：可以在 CI 流程中加入編碼檢查腳本

## 相關資源

- [PEP 3120 -- Source Code Encoding](https://www.python.org/dev/peps/pep-3120/)
- [EditorConfig](https://editorconfig.org/)
- [VSCode Encoding Support](https://code.visualstudio.com/docs/editor/codebasics#_file-encoding-support)

## 檢查清單

建立新 Python 檔案時：

- [ ] 確認編輯器設定為 UTF-8
- [ ] 檔案包含中文時，儲存後用 `file -I` 驗證編碼
- [ ] 在 Git 提交前再次檢查
- [ ] 確保 `.editorconfig` 和 `.vscode/settings.json` 存在且正確

---

最後更新：2025-12-02
