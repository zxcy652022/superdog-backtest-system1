"""
下載 Top 10 主流幣種 1h 數據
用於 DualMA v2.0 回測
"""

import sys
from datetime import datetime, timedelta

# 添加項目路徑
sys.path.insert(0, ".")

from data.downloaders.multi_tf_downloader import MultiTimeframeDownloader  # noqa: E402
from data.paths import get_raw_data_dir  # noqa: E402


def main():
    """下載 Top 10 幣種 1h 數據"""

    # Top 10 幣種
    symbols = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "SOLUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "AVAXUSDT",
        "DOTUSDT",
        "LINKUSDT",
    ]

    # 下載 1 年數據
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400)  # 多下載一點 buffer

    output_dir = get_raw_data_dir("binance")
    print(f"輸出目錄: {output_dir}")

    downloader = MultiTimeframeDownloader(output_dir=str(output_dir))

    print(f"\n開始下載 {len(symbols)} 個幣種的 1h 數據...")
    print(f"日期範圍: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")

    results = downloader.download_multi_timeframe(
        symbols=symbols,
        timeframes=["1h"],
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )

    # 統計結果
    success = sum(1 for r in results if r.get("status") == "success")
    failed = len(results) - success

    print(f"\n下載完成!")
    print(f"  成功: {success}")
    print(f"  失敗: {failed}")

    return results


if __name__ == "__main__":
    main()
