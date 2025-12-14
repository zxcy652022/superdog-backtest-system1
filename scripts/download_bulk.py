#!/usr/bin/env python3
"""
批量下載腳本 - Top 200-300 幣種歷史數據

功能:
- 支援 YAML 配置檔
- 可選擇 Top N 數量
- 進度追蹤與斷點續傳
- 可在背景運行

使用方式:
  # 使用預設配置 (Top 300)
  python scripts/download_bulk.py

  # 指定 Top N 數量
  python scripts/download_bulk.py --top 200

  # 指定配置檔
  python scripts/download_bulk.py --config configs/download_top300.yaml

  # 只下載特定時間週期
  python scripts/download_bulk.py --top 100 --timeframes 1h,4h

  # 背景運行 (nohup)
  nohup python scripts/download_bulk.py --top 300 > download.log 2>&1 &

Version: v0.7
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加項目路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.downloaders.robust_downloader import DownloadConfig, RobustDownloader  # noqa: E402
from data.downloaders.top_symbols_fetcher import TopSymbolsFetcher  # noqa: E402

# 設置 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行參數"""
    parser = argparse.ArgumentParser(
        description="批量下載 Top N 幣種歷史數據",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python scripts/download_bulk.py --top 200
  python scripts/download_bulk.py --config configs/download_top300.yaml
  python scripts/download_bulk.py --top 100 --timeframes 1h,4h
        """,
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="下載 Top N 幣種 (默認: 使用配置檔或 300)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/download_top300.yaml",
        help="YAML 配置檔路徑",
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default=None,
        help="時間週期，逗號分隔 (例: 15m,1h,4h,1d)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="起始日期 (例: 2023-01-01)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="結束日期 (例: 2025-12-01)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="並行工作數 (建議 3-5)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="不使用斷點續傳，重新下載全部",
    )
    parser.add_argument(
        "--list-symbols",
        action="store_true",
        help="只列出將下載的幣種，不實際下載",
    )
    return parser.parse_args()


def main():
    """主函數"""
    args = parse_args()

    print("=" * 60)
    print("🐕 SuperDog Quant - 批量數據下載器")
    print("=" * 60)

    # 載入配置
    config_path = Path(args.config)
    if config_path.exists():
        logger.info(f"載入配置檔: {config_path}")
        config = DownloadConfig.from_yaml(str(config_path))
    else:
        logger.info("使用默認配置")
        config = DownloadConfig()

    # 覆蓋配置（命令行參數優先）
    if args.top:
        config.symbols_count = args.top
    if args.timeframes:
        config.timeframes = [tf.strip() for tf in args.timeframes.split(",")]
    if args.start:
        config.start_date = args.start
    if args.end:
        config.end_date = args.end
    if args.workers:
        config.parallel_workers = args.workers

    # 獲取幣種列表
    logger.info(f"獲取 Top {config.symbols_count} 幣種...")
    fetcher = TopSymbolsFetcher()
    symbols = fetcher.get_top_symbols(
        n=config.symbols_count,
        min_volume=config.min_volume_24h,
        exclude_stablecoins=config.exclude_stablecoins,
        exclude_leveraged=config.exclude_leveraged,
    )

    # 顯示配置摘要
    print("\n📋 下載配置:")
    print(f"  幣種數量: {len(symbols)}")
    print(f"  時間週期: {', '.join(config.timeframes)}")
    print(f"  日期範圍: {config.start_date or '最早'} ~ {config.end_date or '今天'}")
    print(f"  並行數: {config.parallel_workers}")
    print(f"  輸出目錄: {config.output_dir}")

    total_tasks = len(symbols) * len(config.timeframes)
    estimated_time = total_tasks * 3 / 60  # 每任務約 3 秒
    print(f"\n📊 預估:")
    print(f"  總任務數: {total_tasks}")
    print(f"  預估時間: {estimated_time:.1f} 分鐘")

    # 只列出幣種
    if args.list_symbols:
        print("\n📝 將下載的幣種:")
        for i, symbol in enumerate(symbols, 1):
            print(f"  {i:3d}. {symbol}")
        return

    # 確認開始
    print("\n" + "=" * 60)
    print("🚀 開始下載...")
    print("=" * 60)
    start_time = datetime.now()

    # 執行下載
    downloader = RobustDownloader(config=config)
    report = downloader.download_all(
        symbols=symbols,
        timeframes=config.timeframes,
        resume=not args.no_resume,
    )

    # 顯示結果
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 60)
    print("📊 下載完成!")
    print("=" * 60)
    print(f"  開始時間: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  結束時間: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  總耗時: {duration/60:.1f} 分鐘")
    print(f"\n  成功: {report.successful_tasks}")
    print(f"  失敗: {report.failed_tasks}")
    print(f"  總行數: {report.total_rows:,}")

    if report.failed_items:
        print(f"\n⚠️  失敗項目 ({len(report.failed_items)}):")
        for item in report.failed_items[:10]:  # 只顯示前 10 個
            print(f"    - {item['symbol']} {item['timeframe']}: {item['error']}")
        if len(report.failed_items) > 10:
            print(f"    ... 還有 {len(report.failed_items) - 10} 個")

    print(f"\n📁 報告已保存: {config.output_dir}/download_report.json")

    # 返回狀態碼
    return 0 if report.failed_tasks == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
