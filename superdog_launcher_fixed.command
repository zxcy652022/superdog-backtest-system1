#!/bin/bash
# SuperDog v0.5 修復版啟動器
# 自動找到專案根目錄並啟動

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 找到專案根目錄
find_project_root() {
    # 方法1: 檢查當前目錄
    if [ -f "cli/main.py" ] && [ -f "requirements.txt" ]; then
        echo "$(pwd)"
        return 0
    fi

    # 方法2: 檢查腳本所在目錄
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -f "$script_dir/cli/main.py" ] && [ -f "$script_dir/requirements.txt" ]; then
        echo "$script_dir"
        return 0
    fi

    # 方法3: 搜尋用戶目錄下的superdog-quant
    possible_paths=(
        "$HOME/Projects/superdog-quant"
        "$HOME/Documents/superdog-quant"
        "$HOME/Desktop/superdog-quant"
        "$HOME/superdog-quant"
    )

    for path in "${possible_paths[@]}"; do
        if [ -f "$path/cli/main.py" ] && [ -f "$path/requirements.txt" ]; then
            echo "$path"
            return 0
        fi
    done

    return 1
}

# 清屏函數
clear_screen() {
    clear
}

# 顯示標題
show_header() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                    ${WHITE}SuperDog v0.5${CYAN}                           ║${NC}"
    echo -e "${CYAN}║                ${YELLOW}永續合約量化交易平台${CYAN}                      ║${NC}"
    echo -e "${CYAN}╠════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  狀態: Production Ready  │  數據源: 6種  │  交易所: 3個     ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}專案路徑: $PROJECT_ROOT${NC}"
    echo ""
}

# 顯示主選單
show_menu() {
    echo -e "${WHITE}請選擇功能：${NC}"
    echo -e "${YELLOW}═════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  1.${NC} 📋 查看系統狀態 (verify)"
    echo -e "${GREEN}  2.${NC} 📊 查看所有策略 (list)"
    echo -e "${GREEN}  3.${NC} 📈 查看策略詳情 (info)"
    echo -e "${GREEN}  4.${NC} 🎮 川沐策略示範 (kawamoku demo)"
    echo -e "${GREEN}  5.${NC} 🚀 完整功能示範 (all demo)"
    echo -e "${GREEN}  6.${NC} 🧪 運行系統測試 (test)"
    echo -e "${GREEN}  7.${NC} ❓ 查看CLI幫助 (help)"
    echo -e "${GREEN}  8.${NC} 💻 執行自訂命令 (custom)"
    echo -e "${RED}  0.${NC} 🚪 退出程式"
    echo -e "${YELLOW}═════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# 等待用戶按鍵
wait_for_key() {
    echo ""
    echo -e "${CYAN}按任意鍵返回主選單...${NC}"
    read -n 1 -s
}

# 執行命令並顯示結果
run_command() {
    local cmd="$1"
    local desc="$2"

    echo -e "${BLUE}正在執行: ${desc}${NC}"
    echo -e "${YELLOW}命令: python3 cli/main.py $cmd${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"

    # 切換到專案目錄並激活虛擬環境
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    python3 cli/main.py $cmd

    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    wait_for_key
}

# 策略信息查詢
strategy_info() {
    clear_screen
    show_header
    echo -e "${WHITE}策略信息查詢${NC}"
    echo -e "${YELLOW}─────────────────────────────────────────────────────────────────${NC}"

    # 先顯示可用策略
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    echo -e "${GREEN}可用策略列表：${NC}"
    python3 cli/main.py list

    echo ""
    echo -e "${CYAN}請輸入策略名稱 (或按 Enter 返回): ${NC}"
    read strategy_name

    if [ -n "$strategy_name" ]; then
        echo -e "${BLUE}查詢策略: $strategy_name${NC}"
        echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
        python3 cli/main.py info -s "$strategy_name"
        echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    fi

    wait_for_key
}

# 自訂命令
custom_command() {
    clear_screen
    show_header
    echo -e "${WHITE}自訂命令執行${NC}"
    echo -e "${YELLOW}─────────────────────────────────────────────────────────────────${NC}"
    echo -e "${GREEN}可用命令範例：${NC}"
    echo -e "${CYAN}  • run -s simple_sma -m BTCUSDT -t 1h${NC}"
    echo -e "${CYAN}  • portfolio -c configs/test.yml${NC}"
    echo -e "${CYAN}  • demo --type phase-b${NC}"
    echo ""

    echo -e "${CYAN}請輸入CLI命令參數 (或按 Enter 返回): ${NC}"
    read custom_params

    if [ -n "$custom_params" ]; then
        echo -e "${BLUE}執行自訂命令: $custom_params${NC}"
        echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
        cd "$PROJECT_ROOT"
        source .venv/bin/activate
        python3 cli/main.py $custom_params
        echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    fi

    wait_for_key
}

# 主程式邏輯
main() {
    # 找到專案根目錄
    PROJECT_ROOT=$(find_project_root)

    if [ $? -ne 0 ] || [ -z "$PROJECT_ROOT" ]; then
        echo -e "${RED}錯誤: 無法找到 SuperDog 專案目錄${NC}"
        echo -e "${YELLOW}請確保以下檔案存在：${NC}"
        echo -e "${CYAN}  • cli/main.py${NC}"
        echo -e "${CYAN}  • requirements.txt${NC}"
        echo ""
        echo -e "${YELLOW}可能的專案位置：${NC}"
        echo -e "${CYAN}  • $HOME/Projects/superdog-quant${NC}"
        echo -e "${CYAN}  • $HOME/Documents/superdog-quant${NC}"
        echo -e "${CYAN}  • $HOME/Desktop/superdog-quant${NC}"
        echo ""
        read -p "按任意鍵退出..." -n 1
        exit 1
    fi

    # 檢查虛擬環境
    if [ ! -d "$PROJECT_ROOT/.venv" ]; then
        echo -e "${RED}錯誤: 找不到虛擬環境 .venv${NC}"
        echo -e "${YELLOW}專案路徑: $PROJECT_ROOT${NC}"
        echo -e "${CYAN}請執行: cd '$PROJECT_ROOT' && python3 -m venv .venv${NC}"
        read -p "按任意鍵退出..." -n 1
        exit 1
    fi

    while true; do
        clear_screen
        show_header
        show_menu

        echo -n -e "${WHITE}請輸入選項 (0-8): ${NC}"
        read choice

        case $choice in
            1)
                clear_screen
                show_header
                run_command "verify" "系統狀態驗證"
                ;;
            2)
                clear_screen
                show_header
                run_command "list --detailed" "查看所有策略 (詳細)"
                ;;
            3)
                strategy_info
                ;;
            4)
                clear_screen
                show_header
                run_command "demo --type kawamoku" "川沐策略示範"
                ;;
            5)
                clear_screen
                show_header
                run_command "demo --type all" "完整功能示範"
                ;;
            6)
                clear_screen
                show_header
                run_command "test --type integration" "系統整合測試"
                ;;
            7)
                clear_screen
                show_header
                run_command "--help" "CLI幫助信息"
                ;;
            8)
                custom_command
                ;;
            0)
                clear_screen
                echo -e "${GREEN}感謝使用 SuperDog v0.5！${NC}"
                echo -e "${CYAN}專業級永續合約量化交易平台${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo -e "${RED}無效選項，請輸入 0-8${NC}"
                sleep 1
                ;;
        esac
    done
}

# 啟動主程式
main
