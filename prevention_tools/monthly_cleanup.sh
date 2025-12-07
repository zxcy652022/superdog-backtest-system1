#!/bin/bash
# SuperDog 每月清理檢查腳本

echo "🧹 SuperDog 每月清理檢查"
echo "================================"
echo ""

# 1. 檢查空檔案
echo "📋 1. 檢查空 Python 檔案（除了 __init__.py）..."
EMPTY_FILES=$(find . -type f -name "*.py" -size 0 -not -path "*/__pycache__/*" -not -name "__init__.py" 2>/dev/null)
if [ -z "$EMPTY_FILES" ]; then
    echo "   ✅ 沒有發現空檔案"
else
    echo "   ⚠️  發現以下空檔案："
    echo "$EMPTY_FILES" | sed 's/^/      /'
fi
echo ""

# 2. 檢查備份檔案
echo "📋 2. 檢查備份和臨時檔案..."
BACKUP_FILES=$(find . -type f \( -name "*.backup" -o -name "*.bak" -o -name "*.tmp" -o -name "*.old" \) -not -path "*/.trash/*" -not -path "*/.backup/*" 2>/dev/null)
if [ -z "$BACKUP_FILES" ]; then
    echo "   ✅ 沒有發現備份檔案"
else
    echo "   ⚠️  發現以下備份檔案："
    echo "$BACKUP_FILES" | sed 's/^/      /'
fi
echo ""

# 3. 檢查大於 3 個月未修改的 TODO 檔案
echo "📋 3. 檢查過期 TODO 檔案（超過 90 天未修改）..."
TODO_FILES=$(find . -type f -name "*TODO*" -o -name "*todo*" 2>/dev/null | while read f; do
    if [ $(( ($(date +%s) - $(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null)) / 86400 )) -gt 90 ]; then
        echo "$f"
    fi
done)
if [ -z "$TODO_FILES" ]; then
    echo "   ✅ 沒有發現過期 TODO"
else
    echo "   ⚠️  發現以下過期 TODO："
    echo "$TODO_FILES" | sed 's/^/      /'
fi
echo ""

# 4. 檢查版本一致性
echo "📋 4. 檢查版本一致性..."
if [ -f "scripts/check_version.py" ]; then
    python scripts/check_version.py
else
    echo "   ⚠️  找不到 check_version.py"
fi
echo ""

# 5. 檢查過時的規格文檔
echo "📋 5. 檢查未歸檔的舊版規格（v0.0-v0.5）..."
OLD_SPECS=$(find docs/specs -name "*.md" 2>/dev/null | grep -E "v0\.[0-5]" | grep -v archive)
if [ -z "$OLD_SPECS" ]; then
    echo "   ✅ 沒有發現未歸檔的舊規格"
else
    echo "   ⚠️  發現以下未歸檔的舊規格："
    echo "$OLD_SPECS" | sed 's/^/      /'
    echo "   建議移到 docs/archive/"
fi
echo ""

# 6. 檢查大檔案
echo "📋 6. 檢查大檔案（>1MB）..."
LARGE_FILES=$(find . -type f -size +1M -not -path "*/.git/*" -not -path "*/__pycache__/*" -not -path "*/node_modules/*" 2>/dev/null)
if [ -z "$LARGE_FILES" ]; then
    echo "   ✅ 沒有發現大檔案"
else
    echo "   ⚠️  發現以下大檔案："
    echo "$LARGE_FILES" | while read f; do
        size=$(du -h "$f" | cut -f1)
        echo "      $f ($size)"
    done
fi
echo ""

# 總結
echo "================================"
echo "✅ 每月清理檢查完成"
echo ""
echo "建議操作："
echo "  1. 檢查並處理上述發現的問題"
echo "  2. 執行 'python cleanup_v06.py --dry-run' 預覽清理"
echo "  3. 更新 TECHNICAL_DEBT.md 記錄技術債"
echo ""
