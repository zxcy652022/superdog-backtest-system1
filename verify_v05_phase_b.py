#!/usr/bin/env python3
"""
SuperDog v0.5 Phase B 驗證腳本

驗證 Phase B 的所有模組和功能是否正確安裝

Usage:
    python3 verify_v05_phase_b.py
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent))


def print_header(title: str):
    """打印標題"""
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)
    print()


def verify_phase_b_modules():
    """驗證 Phase B 模組導入"""
    print_header("驗證 v0.5 Phase B 模組導入")

    tests_passed = 0
    tests_total = 0

    # 1. 驗證 Bybit 連接器
    print("1. Bybit 連接器...")
    tests_total += 1
    try:
        from data.exchanges import BybitConnector
        connector = BybitConnector()
        assert connector.name == 'bybit'
        print("   ✓ Bybit connector imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to import Bybit connector: {e}")

    # 2. 驗證 OKX 連接器
    print("2. OKX 連接器...")
    tests_total += 1
    try:
        from data.exchanges import OKXConnector
        connector = OKXConnector()
        assert connector.name == 'okx'
        print("   ✓ OKX connector imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to import OKX connector: {e}")

    # 3. 驗證期現基差模組
    print("3. 期現基差數據處理...")
    tests_total += 1
    try:
        from data.perpetual import BasisData, calculate_basis, find_arbitrage_opportunities
        basis = BasisData()
        print("   ✓ Basis data modules imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to import basis modules: {e}")

    # 4. 驗證爆倉數據模組
    print("4. 爆倉數據處理...")
    tests_total += 1
    try:
        from data.perpetual import LiquidationData, fetch_liquidations, calculate_panic_index
        liq = LiquidationData()
        print("   ✓ Liquidation data modules imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to import liquidation modules: {e}")

    # 5. 驗證多空持倉比模組
    print("5. 多空持倉比數據處理...")
    tests_total += 1
    try:
        from data.perpetual import LongShortRatioData, fetch_long_short_ratio, calculate_sentiment
        lsr = LongShortRatioData()
        print("   ✓ Long/short ratio modules imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to import long/short ratio modules: {e}")

    # 6. 驗證多交易所聚合
    print("6. 多交易所數據聚合...")
    tests_total += 1
    try:
        from data.aggregation import MultiExchangeAggregator, aggregate_funding_rates
        agg = MultiExchangeAggregator()
        assert len(agg.exchanges) > 0
        print("   ✓ Multi-exchange aggregation imported successfully")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to import aggregation modules: {e}")

    # 7. 驗證 DataPipeline v0.5 Phase B
    print("7. DataPipeline v0.5 Phase B...")
    tests_total += 1
    try:
        from data.pipeline import get_pipeline
        from strategies.api_v2 import DataSource

        pipeline = get_pipeline()

        # 檢查新增的數據處理器
        assert hasattr(pipeline, 'basis_data'), "Missing basis_data"
        assert hasattr(pipeline, 'liquidation_data'), "Missing liquidation_data"
        assert hasattr(pipeline, 'long_short_ratio_data'), "Missing long_short_ratio_data"

        # 檢查新增的 DataSource
        assert hasattr(DataSource, 'BASIS'), "Missing DataSource.BASIS"
        assert hasattr(DataSource, 'LIQUIDATIONS'), "Missing DataSource.LIQUIDATIONS"
        assert hasattr(DataSource, 'LONG_SHORT_RATIO'), "Missing DataSource.LONG_SHORT_RATIO"

        print("   ✓ DataPipeline v0.5 Phase B loaded successfully")
        print(f"   ✓ Has basis_data: True")
        print(f"   ✓ Has liquidation_data: True")
        print(f"   ✓ Has long_short_ratio_data: True")
        tests_passed += 1
    except Exception as e:
        print(f"   ✗ Failed to verify DataPipeline: {e}")

    return tests_passed, tests_total


def verify_file_structure():
    """驗證文件結構"""
    print_header("驗證 Phase B 文件結構")

    files = [
        "data/exchanges/bybit_connector.py",
        "data/exchanges/okx_connector.py",
        "data/perpetual/basis.py",
        "data/perpetual/liquidations.py",
        "data/perpetual/long_short_ratio.py",
        "data/aggregation/__init__.py",
        "data/aggregation/multi_exchange.py",
    ]

    files_found = 0
    for file in files:
        filepath = Path(file)
        if filepath.exists():
            print(f"   ✓ {file}")
            files_found += 1
        else:
            print(f"   ✗ {file} (NOT FOUND)")

    return files_found, len(files)


def print_summary(module_passed, module_total, files_found, files_total):
    """打印總結"""
    print()
    print("=" * 70)
    print("SuperDog v0.5 Phase B 驗證總結")
    print("=" * 70)
    print()
    print(f"模組導入: {module_passed}/{module_total} 通過")
    print(f"文件結構: {files_found}/{files_total} 存在")
    print()

    if module_passed == module_total and files_found == files_total:
        print("🎉 Phase B 驗證完全通過！")
        print()
        print("所有 Phase B 組件已正確安裝並可以使用。")
        print()
        print("下一步：")
        print("  - 使用新的數據源進行策略開發")
        print("  - 整合多交易所數據進行交叉驗證")
        print("  - 利用期現基差尋找套利機會")
        print("  - 監控爆倉數據識別市場恐慌")
        print("  - 使用多空比作為逆向指標")
        print()
        return True
    else:
        print("⚠️ 部分驗證未通過")
        print()
        print(f"模組導入失敗: {module_total - module_passed}")
        print(f"文件缺失: {files_total - files_found}")
        print()
        print("請檢查安裝或查看錯誤信息")
        print()
        return False


def main():
    """主函數"""
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 20 + "SuperDog v0.5 Phase B 驗證" + " " * 23 + "║")
    print("╚" + "=" * 68 + "╝")

    # 驗證模組
    module_passed, module_total = verify_phase_b_modules()

    # 驗證文件
    files_found, files_total = verify_file_structure()

    # 打印總結
    success = print_summary(module_passed, module_total, files_found, files_total)

    print("=" * 70)
    print()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
