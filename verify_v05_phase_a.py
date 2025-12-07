#!/usr/bin/env python3
"""
SuperDog v0.5 Phase A 驗證腳本

快速驗證所有 Phase A 組件是否正確安裝和可用

Usage:
    python3 verify_v05_phase_a.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def verify_imports():
    """驗證所有模組可以正確導入"""
    print("=" * 70)
    print("驗證 v0.5 Phase A 模組導入")
    print("=" * 70)

    tests = []

    # 1. Exchange Connectors
    print("\n1. Exchange Connectors...")
    try:
        from data.exchanges.base_connector import ExchangeConnector
        from data.exchanges.binance_connector import BinanceConnector, BinanceAPIError
        print("   ✓ Exchange connectors imported successfully")
        tests.append(("Exchange Connectors", True, None))
    except Exception as e:
        print(f"   ✗ Failed to import exchange connectors: {e}")
        tests.append(("Exchange Connectors", False, str(e)))

    # 2. Perpetual Data
    print("\n2. Perpetual Data Processing...")
    try:
        from data.perpetual import (
            FundingRateData,
            OpenInterestData,
            fetch_funding_rate,
            fetch_open_interest,
            get_latest_funding_rate,
            analyze_oi_trend
        )
        print("   ✓ Perpetual data modules imported successfully")
        tests.append(("Perpetual Data", True, None))
    except Exception as e:
        print(f"   ✗ Failed to import perpetual data: {e}")
        tests.append(("Perpetual Data", False, str(e)))

    # 3. Quality Control
    print("\n3. Quality Control...")
    try:
        from data.quality import (
            DataQualityController,
            QualityCheckResult,
            QualityIssue
        )
        print("   ✓ Quality control modules imported successfully")
        tests.append(("Quality Control", True, None))
    except Exception as e:
        print(f"   ✗ Failed to import quality control: {e}")
        tests.append(("Quality Control", False, str(e)))

    # 4. DataPipeline v0.5
    print("\n4. DataPipeline v0.5...")
    try:
        from data.pipeline import DataPipeline, get_pipeline
        pipeline = get_pipeline()

        # 驗證 v0.5 組件
        assert hasattr(pipeline, 'funding_rate_data'), "Missing funding_rate_data"
        assert hasattr(pipeline, 'open_interest_data'), "Missing open_interest_data"
        assert hasattr(pipeline, 'quality_controller'), "Missing quality_controller"
        assert hasattr(pipeline, '_load_funding_rate'), "Missing _load_funding_rate method"
        assert hasattr(pipeline, '_load_open_interest'), "Missing _load_open_interest method"

        print("   ✓ DataPipeline v0.5 loaded successfully")
        print(f"   ✓ Has funding_rate_data: {pipeline.funding_rate_data is not None}")
        print(f"   ✓ Has open_interest_data: {pipeline.open_interest_data is not None}")
        print(f"   ✓ Has quality_controller: {pipeline.quality_controller is not None}")
        tests.append(("DataPipeline v0.5", True, None))
    except Exception as e:
        print(f"   ✗ Failed to verify DataPipeline v0.5: {e}")
        tests.append(("DataPipeline v0.5", False, str(e)))

    return tests


def verify_functionality():
    """驗證基本功能"""
    print("\n" + "=" * 70)
    print("驗證基本功能")
    print("=" * 70)

    tests = []

    # 1. Binance Connector Initialization
    print("\n1. Binance Connector 初始化...")
    try:
        from data.exchanges.binance_connector import BinanceConnector

        connector = BinanceConnector()
        assert connector.name == 'binance'
        assert connector.base_url == 'https://fapi.binance.com'
        assert connector.session is not None

        print("   ✓ Binance connector initialized")
        print(f"     - Name: {connector.name}")
        print(f"     - Base URL: {connector.base_url}")
        print(f"     - Rate limit: {connector.max_requests_per_interval} req/{connector.rate_limit_interval}s")
        tests.append(("Binance Connector Init", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("Binance Connector Init", False, str(e)))

    # 2. Funding Rate Data Initialization
    print("\n2. Funding Rate Data 初始化...")
    try:
        from data.perpetual import FundingRateData

        fr = FundingRateData()
        assert fr.connectors is not None
        assert 'binance' in fr.connectors

        print("   ✓ Funding rate data initialized")
        print(f"     - Storage path: {fr.storage_path}")
        print(f"     - Available exchanges: {list(fr.connectors.keys())}")
        tests.append(("Funding Rate Init", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("Funding Rate Init", False, str(e)))

    # 3. Open Interest Data Initialization
    print("\n3. Open Interest Data 初始化...")
    try:
        from data.perpetual import OpenInterestData

        oi = OpenInterestData()
        assert oi.connectors is not None
        assert 'binance' in oi.connectors

        print("   ✓ Open interest data initialized")
        print(f"     - Storage path: {oi.storage_path}")
        print(f"     - Available exchanges: {list(oi.connectors.keys())}")
        tests.append(("Open Interest Init", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("Open Interest Init", False, str(e)))

    # 4. Quality Controller Initialization
    print("\n4. Quality Controller 初始化...")
    try:
        from data.quality import DataQualityController

        qc = DataQualityController(strict_mode=False)
        assert qc.strict_mode == False
        assert hasattr(qc, 'check_ohlcv')
        assert hasattr(qc, 'check_funding_rate')
        assert hasattr(qc, 'check_open_interest')
        assert hasattr(qc, 'clean_ohlcv')

        print("   ✓ Quality controller initialized")
        print(f"     - Strict mode: {qc.strict_mode}")
        print(f"     - Check methods: check_ohlcv, check_funding_rate, check_open_interest")
        tests.append(("Quality Controller Init", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("Quality Controller Init", False, str(e)))

    # 5. Quality Check with Test Data
    print("\n5. Quality Check 測試數據...")
    try:
        import pandas as pd
        import numpy as np
        from data.quality import DataQualityController

        # 創建測試 OHLCV 數據
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
        test_df = pd.DataFrame({
            'open': np.random.randn(100).cumsum() + 50000,
            'high': np.random.randn(100).cumsum() + 50100,
            'low': np.random.randn(100).cumsum() + 49900,
            'close': np.random.randn(100).cumsum() + 50000,
            'volume': np.random.randint(1000, 10000, 100)
        }, index=dates)

        # 確保價格邏輯正確
        test_df['high'] = test_df[['open', 'close']].max(axis=1) + 100
        test_df['low'] = test_df[['open', 'close']].min(axis=1) - 100

        qc = DataQualityController()
        result = qc.check_ohlcv(test_df)

        print("   ✓ Quality check executed")
        print(f"     - Passed: {result.passed}")
        print(f"     - Critical issues: {result.critical_count}")
        print(f"     - Warnings: {result.warning_count}")
        print(f"     - Info: {result.info_count}")
        tests.append(("Quality Check Test", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        tests.append(("Quality Check Test", False, str(e)))

    return tests


def verify_file_structure():
    """驗證文件結構"""
    print("\n" + "=" * 70)
    print("驗證文件結構")
    print("=" * 70)

    expected_files = [
        # Exchange Connectors
        "data/exchanges/__init__.py",
        "data/exchanges/base_connector.py",
        "data/exchanges/binance_connector.py",

        # Perpetual Data
        "data/perpetual/__init__.py",
        "data/perpetual/funding_rate.py",
        "data/perpetual/open_interest.py",

        # Quality Control
        "data/quality/__init__.py",
        "data/quality/controller.py",

        # Tests
        "tests/test_perpetual_v05.py",
        "examples/test_perpetual_data.py",

        # Documentation
        "docs/v0.5_phase_a_completion.md"
    ]

    missing_files = []
    existing_files = []

    for file_path in expected_files:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            existing_files.append(file_path)
            print(f"   ✓ {file_path}")
        else:
            missing_files.append(file_path)
            print(f"   ✗ {file_path} (MISSING)")

    return existing_files, missing_files


def print_summary(import_tests, func_tests, existing_files, missing_files):
    """打印總結"""
    print("\n" + "=" * 70)
    print("SuperDog v0.5 Phase A 驗證總結")
    print("=" * 70)

    # Import tests
    import_passed = sum(1 for _, passed, _ in import_tests if passed)
    print(f"\n模組導入: {import_passed}/{len(import_tests)} 通過")
    for name, passed, error in import_tests:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if error:
            print(f"      錯誤: {error}")

    # Functionality tests
    func_passed = sum(1 for _, passed, _ in func_tests if passed)
    print(f"\n功能測試: {func_passed}/{len(func_tests)} 通過")
    for name, passed, error in func_tests:
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if error:
            print(f"      錯誤: {error}")

    # File structure
    print(f"\n文件結構: {len(existing_files)}/{len(existing_files) + len(missing_files)} 存在")
    if missing_files:
        print(f"  缺少的文件:")
        for file in missing_files:
            print(f"    - {file}")

    # Overall status
    all_imports_passed = import_passed == len(import_tests)
    all_funcs_passed = func_passed == len(func_tests)
    all_files_exist = len(missing_files) == 0

    print("\n" + "=" * 70)
    if all_imports_passed and all_funcs_passed and all_files_exist:
        print("🎉 Phase A 驗證完全通過！")
        print("\n所有組件已正確安裝並可以使用。")
        print("準備好進入實際測試或 Phase B 開發！")
        return 0
    else:
        print("⚠️  Phase A 驗證部分失敗")
        if not all_imports_passed:
            print("  - 某些模組無法導入")
        if not all_funcs_passed:
            print("  - 某些功能測試失敗")
        if not all_files_exist:
            print("  - 某些文件缺失")
        return 1


def main():
    """主函數"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "SuperDog v0.5 Phase A 驗證" + " " * 27 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")

    # Run all verifications
    import_tests = verify_imports()
    func_tests = verify_functionality()
    existing_files, missing_files = verify_file_structure()

    # Print summary
    exit_code = print_summary(import_tests, func_tests, existing_files, missing_files)

    print("\n" + "=" * 70)
    print()

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
