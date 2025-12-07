#!/bin/bash
# SuperDog v0.5 Phase A 安裝腳本
# 自動設置虛擬環境並安裝依賴

set -e  # 遇到錯誤立即退出

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║          SuperDog v0.5 Phase A - 自動安裝腳本                      ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# 檢查 Python 版本
echo "🔍 檢查 Python 版本..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "   ✓ $PYTHON_VERSION"

# 檢查是否已有虛擬環境
if [ -d "venv" ]; then
    echo ""
    echo "⚠️  虛擬環境已存在"
    read -p "是否要刪除並重建？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  刪除舊的虛擬環境..."
        rm -rf venv
        echo "   ✓ 刪除完成"
    else
        echo "   ✓ 使用現有虛擬環境"
    fi
fi

# 創建虛擬環境
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 創建虛擬環境..."
    python3 -m venv venv
    echo "   ✓ 虛擬環境創建成功"
fi

# 激活虛擬環境
echo ""
echo "🔌 激活虛擬環境..."
source venv/bin/activate
echo "   ✓ 虛擬環境已激活"

# 升級 pip
echo ""
echo "⬆️  升級 pip..."
pip install --upgrade pip -q
echo "   ✓ pip 已升級"

# 安裝依賴
echo ""
echo "📥 安裝 Python 依賴..."
echo "   - pandas"
echo "   - numpy"
echo "   - requests"
echo "   - pyarrow"
pip install -r requirements.txt -q
echo "   ✓ 依賴安裝完成"

# 驗證安裝
echo ""
echo "✅ 驗證安裝..."
echo ""
python3 verify_v05_phase_a.py

# 檢查驗證結果
VERIFY_RESULT=$?

if [ $VERIFY_RESULT -eq 0 ]; then
    # 完成
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                    🎉 安裝成功！                                   ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "🚀 立即體驗："
    echo ""
    echo "   # 測試永續數據功能（需要網絡）"
    echo "   python3 examples/test_perpetual_data.py"
    echo ""
    echo "📚 更多選項："
    echo ""
    echo "   # 運行單元測試"
    echo "   python3 tests/test_perpetual_v05.py"
    echo ""
    echo "   # Python 交互式測試"
    echo "   python3"
    echo "   >>> from data.perpetual import get_latest_funding_rate"
    echo "   >>> latest = get_latest_funding_rate('BTCUSDT')"
    echo ""
    echo "   # 閱讀快速指南"
    echo "   cat QUICKSTART.md"
    echo ""
    echo "💡 提示："
    echo "   每次使用前需要激活虛擬環境："
    echo "   source venv/bin/activate"
    echo ""
else
    echo ""
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                    ⚠️  驗證失敗                                   ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "可能的原因："
    echo "  - 某些依賴未正確安裝"
    echo "  - Python 版本過低（需要 3.8+）"
    echo ""
    echo "請查看上方的錯誤信息，或參考 SETUP.md 進行手動安裝"
    echo ""
    exit 1
fi
