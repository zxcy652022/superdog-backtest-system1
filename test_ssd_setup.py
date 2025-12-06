#!/usr/bin/env python3
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
    print("\n📍 路徑測試:")
    print(f"專案根目錄: {config.project_root}")
    print(f"數據根目錄: {config.data_root}")
    print(f"歷史數據: {config.historical_data}")
    
    # 測試SSD可用性
    print("\n💾 SSD 狀態:")
    status = config.get_status()
    for key, value in status.items():
        print(f"{key}: {value}")
    
    # 測試目錄創建
    print("\n📁 目錄檢查:")
    dirs_to_check = [
        config.historical_data,
        config.backtest_results,
        config.cache_dir
    ]
    
    for dir_path in dirs_to_check:
        exists = dir_path.exists()
        print(f"{'✅' if exists else '❌'} {dir_path}")
    
    print("\n🎉 測試完成!")

if __name__ == "__main__":
    main()
