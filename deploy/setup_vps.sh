#!/bin/bash
# =============================================================================
# SuperDog 量化系統 - VPS 一鍵部署腳本
# 適用於：Ubuntu 22.04 LTS
# =============================================================================

set -e

echo "=========================================="
echo "SuperDog 量化系統 - VPS 部署"
echo "=========================================="

# 1. 系統更新
echo "[1/6] 更新系統..."
apt update && apt upgrade -y

# 2. 安裝 Python 和依賴
echo "[2/6] 安裝 Python..."
apt install -y python3 python3-pip python3-venv git screen

# 3. 創建專案目錄
echo "[3/6] 創建專案目錄..."
mkdir -p /opt/superdog
cd /opt/superdog

# 4. 創建虛擬環境
echo "[4/6] 創建 Python 虛擬環境..."
python3 -m venv venv
source venv/bin/activate

# 5. 安裝 Python 依賴
echo "[5/6] 安裝依賴..."
pip install --upgrade pip
pip install requests python-dotenv pandas numpy

# 6. 完成
echo "[6/6] 基礎環境安裝完成！"

echo ""
echo "=========================================="
echo "接下來請手動執行："
echo "=========================================="
echo ""
echo "1. 上傳程式碼到 /opt/superdog/"
echo "   scp -r live/ config/ strategies/ backtest/ root@你的IP:/opt/superdog/"
echo ""
echo "2. 創建 .env 檔案："
echo "   nano /opt/superdog/.env"
echo "   貼上你的 API 密鑰"
echo ""
echo "3. 啟動交易系統（用 screen 背景執行）："
echo "   cd /opt/superdog"
echo "   screen -S trading"
echo "   source venv/bin/activate"
echo "   python3 live/runner.py"
echo ""
echo "4. 離開 screen（程式繼續跑）："
echo "   按 Ctrl+A 然後按 D"
echo ""
echo "5. 重新連接 screen："
echo "   screen -r trading"
echo ""
echo "=========================================="
