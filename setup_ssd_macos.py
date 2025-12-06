#!/usr/bin/env python3
"""
SuperDog SSD 環境設置腳本 (macOS 版)

針對 MacBook Air M1 和「權志龍的寶藏」SSD 的專用設置
"""

import shutil
import sys
import os
from pathlib import Path
import pandas as pd


def setup_data_config():
    """設置數據配置模組"""
    print("🚀 SuperDog SSD 環境設置 (macOS)")
    print("=" * 60)
    
    # 檢查SSD是否掛載
    ssd_volume = Path("/Volumes/權志龍的寶藏")
    if not ssd_volume.exists():
        print("❌ SSD「權志龍的寶藏」未偵測到")
        print("請確認:")
        print("  1. SSD已正確連接")
        print("  2. SSD已正確掛載在 /Volumes/權志龍的寶藏")
        return False
    
    print(f"✅ SSD 已偵測到: {ssd_volume}")
    
    # 創建數據目錄
    data_root = ssd_volume / "SuperDogData"
    data_root.mkdir(exist_ok=True)
    
    directories = [
        "historical/binance",
        "historical/bybit", 
        "historical/coinbase",
        "backtest_results/single_runs",
        "backtest_results/portfolio_runs",
        "cache",
        "models",
        "exports"
    ]
    
    for dir_path in directories:
        full_path = data_root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"  📁 {dir_path}")
    
    print(f"✅ 數據目錄結構已建立: {data_root}")
    return True


def migrate_historical_data():
    """遷移現有歷史數據"""
    print("\n🔄 遷移歷史數據...")
    
    source_dir = Path("data/raw")
    target_dir = Path("/Volumes/權志龍的寶藏/SuperDogData/historical/binance")
    
    if not source_dir.exists():
        print("ℹ️  未找到 data/raw 目錄，跳過遷移")
        return
    
    csv_files = list(source_dir.glob("*.csv"))
    if not csv_files:
        print("ℹ️  data/raw 目錄為空，跳過遷移")
        return
    
    migrated_count = 0
    for csv_file in csv_files:
        target_file = target_dir / csv_file.name
        if not target_file.exists():
            try:
                shutil.copy2(csv_file, target_file)
                file_size = csv_file.stat().st_size / (1024 * 1024)  # MB
                print(f"  📊 {csv_file.name} ({file_size:.1f}MB)")
                migrated_count += 1
            except Exception as e:
                print(f"  ❌ 遷移失敗 {csv_file.name}: {e}")
        else:
            print(f"  ⏭️  已存在 {csv_file.name}")
    
    print(f"✅ 遷移完成: {migrated_count} 個新檔案")


def update_storage_module():
    """更新 data/storage.py 以支援SSD路徑"""
    print("\n🔧 更新 storage 模組...")
    
    storage_file = Path("data/storage.py")
    
    if not storage_file.exists():
        print("❌ data/storage.py 不存在")
        return
    
    # 備份原檔案
    backup_file = storage_file.with_suffix(".py.backup")
    shutil.copy2(storage_file, backup_file)
    print(f"  💾 已備份至: {backup_file}")
    
    # 讀取原始內容
    content = storage_file.read_text()
    
    # 添加SSD配置支援（在檔案開頭添加導入）
    if "from data_config import config" not in content:
        lines = content.split('\n')
        import_index = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_index = i + 1
        
        lines.insert(import_index, "\n# SSD 配置支援 (v0.4)")
        lines.insert(import_index + 1, "from data_config import config")
        content = '\n'.join(lines)
        
        storage_file.write_text(content)
        print("  ✅ 已添加 SSD 配置導入")
    else:
        print("  ✅ SSD 配置已存在")


def create_symlinks():
    """創建符號鏈接以便快速訪問"""
    print("\n🔗 創建符號鏈接...")
    
    try:
        # 創建 data/ssd -> SSD數據目錄的鏈接
        link_path = Path("data/ssd")
        target_path = Path("/Volumes/權志龍的寶藏/SuperDogData")
        
        if link_path.exists():
            print(f"  ⏭️  符號鏈接已存在: {link_path}")
        else:
            link_path.symlink_to(target_path)
            print(f"  ✅ 符號鏈接已創建: {link_path} -> {target_path}")
    
    except OSError as e:
        print(f"  ⚠️  無法創建符號鏈接: {e}")


def update_gitignore():
    """更新 .gitignore"""
    print("\n📝 更新 .gitignore...")
    
    gitignore_entries = [
        "\n# SSD 數據配置 (v0.4)\n",
        "data/ssd/\n",
        "local_data/\n", 
        "*.pkl\n",
        "*.backup\n",
        "backtest_results/\n",
        "\n# macOS\n",
        ".DS_Store\n",
        "__MACOSX/\n"
    ]
    
    gitignore_path = Path(".gitignore")
    
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if "# SSD 數據配置" not in content:
            with open(gitignore_path, 'a') as f:
                f.writelines(gitignore_entries)
            print("  ✅ .gitignore 已更新")
        else:
            print("  ✅ .gitignore 已是最新")
    else:
        gitignore_path.write_text(''.join(gitignore_entries))
        print("  ✅ .gitignore 已創建")


def create_test_script():
    """創建測試腳本"""
    print("\n🧪 創建測試腳本...")
    
    test_script = Path("test_ssd_setup.py")
    test_content = '''#!/usr/bin/env python3
"""
測試 SSD 配置是否正常運作
"""

from data_config import config, setup_data_environment

def main():
    print("🧪 測試 SSD 配置...")
    print("=" * 40)
    
    # 初始化環境
    setup_data_environment()
    
    # 測試路徑
    print("\\n📍 路徑測試:")
    print(f"專案根目錄: {config.project_root}")
    print(f"數據根目錄: {config.data_root}")
    print(f"歷史數據: {config.historical_data}")
    
    # 測試SSD可用性
    print("\\n💾 SSD 狀態:")
    status = config.get_status()
    for key, value in status.items():
        print(f"{key}: {value}")
    
    # 測試目錄創建
    print("\\n📁 目錄檢查:")
    dirs_to_check = [
        config.historical_data,
        config.backtest_results,
        config.cache_dir
    ]
    
    for dir_path in dirs_to_check:
        exists = dir_path.exists()
        print(f"{'✅' if exists else '❌'} {dir_path}")
    
    print("\\n🎉 測試完成!")

if __name__ == "__main__":
    main()
'''
    
    test_script.write_text(test_content)
    print(f"  ✅ 測試腳本已創建: {test_script}")


def show_completion_info():
    """顯示完成資訊和下一步操作"""
    print("\n" + "=" * 60)
    print("🎉 SuperDog SSD 環境設置完成!")
    print("=" * 60)
    
    # 檢查SSD狀態
    ssd_volume = Path("/Volumes/權志龍的寶藏")
    if ssd_volume.exists():
        total, used, free = shutil.disk_usage(ssd_volume)
        free_gb = free / (1024**3)
        total_gb = total / (1024**3)
        print(f"💾 SSD 狀態: {free_gb:.1f}GB 可用 / {total_gb:.1f}GB 總容量")
    
    print(f"📍 數據目錄: /Volumes/權志龍的寶藏/SuperDogData")
    print(f"🔗 本地鏈接: data/ssd/")
    
    print("\n📋 下一步操作:")
    print("1. 🧪 測試配置: python test_ssd_setup.py")
    print("2. 🎨 開啟 VS Code: code superdog-quant.code-workspace") 
    print("3. 🚀 開始 v0.4 開發!")
    
    print("\n💡 提示:")
    print("- 數據文件將自動存儲到 SSD")
    print("- VS Code 可以同時看到專案代碼和 SSD 數據")
    print("- SSD 斷線時會自動回退到本地存儲")


def main():
    """主要設置流程"""
    try:
        # 1. 設置數據目錄
        if not setup_data_config():
            return
        
        # 2. 遷移歷史數據
        migrate_historical_data()
        
        # 3. 更新 storage 模組
        update_storage_module()
        
        # 4. 創建符號鏈接
        create_symlinks()
        
        # 5. 更新 .gitignore
        update_gitignore()
        
        # 6. 創建測試腳本
        create_test_script()
        
        # 7. 顯示完成資訊
        show_completion_info()
        
    except Exception as e:
        print(f"\n❌ 設置過程出現錯誤: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
