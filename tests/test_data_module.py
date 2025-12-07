# 測試 Data Module v0.1

import os
import sys

sys.path.append(os.path.abspath("."))

from data.fetcher import download_btcusdt_1h  # noqa: E402
from data.validator import validate_ohlcv_csv  # noqa: E402


def test_fetch_and_validate():
    """
    測試流程：
    1. 下載 1h BTCUSDT
    2. 驗證 CSV
    3. 印出檢查結果
    """

    print("\n=== Step 1：下載 BTCUSDT 1h ===")
    csv_path = download_btcusdt_1h(
        start_date="2023-01-01", end_date="2023-02-01", save_path="data/raw/BTCUSDT_1h_test.csv"
    )

    print(f"CSV 下載完成：{csv_path}")
    assert os.path.exists(csv_path), "CSV 檔案不存在！"

    print("\n=== Step 2：驗證 CSV ===")
    report = validate_ohlcv_csv(csv_path, timeframe="1h")
    print(report)

    print("\n=== Step 3：基礎驗收 ===")
    assert report["ok"], "驗證未通過！"
    assert report["total_rows"] > 0, "數據列數為 0！"

    print("\n🎉 測試通過！")


if __name__ == "__main__":
    test_fetch_and_validate()
