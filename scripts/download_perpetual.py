#!/usr/bin/env python3
"""
衍生品數據批量下載腳本 - Funding Rate, Open Interest, Long/Short Ratio

功能:
- 資金費率 (Funding Rate)
- 持倉量 (Open Interest)
- 多空比 (Long/Short Ratio)

使用方式:
  # 下載 Top 100 幣種的衍生品數據
  python scripts/download_perpetual.py --top 100

  # 只下載特定數據類型
  python scripts/download_perpetual.py --top 50 --types funding,oi

  # 指定日期範圍
  python scripts/download_perpetual.py --top 100 --start 2024-01-01

  # 背景運行
  nohup python scripts/download_perpetual.py --top 100 > perpetual.log 2>&1 &

Version: v0.7
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# 添加項目路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests  # noqa: E402

from data.downloaders.top_symbols_fetcher import TopSymbolsFetcher  # noqa: E402
from data.perpetual.funding_rate import FundingRateData  # noqa: E402
from data.perpetual.open_interest import OpenInterestData  # noqa: E402


def get_futures_symbols(top_n: int = 300) -> List[str]:
    """獲取 Binance 永續合約幣種列表（只有這些才有 funding rate 和 OI）"""
    logger.info("獲取 Binance 永續合約幣種列表...")

    try:
        # 獲取所有永續合約交易對
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 過濾出 USDT 永續合約
        futures_symbols = []
        for symbol_info in data.get("symbols", []):
            symbol = symbol_info.get("symbol", "")
            status = symbol_info.get("status", "")
            contract_type = symbol_info.get("contractType", "")

            # 只要 USDT 永續合約且正在交易
            if symbol.endswith("USDT") and status == "TRADING" and contract_type == "PERPETUAL":
                futures_symbols.append(symbol)

        logger.info(f"找到 {len(futures_symbols)} 個 USDT 永續合約")

        # 如果需要 Top N，按交易量排序
        if top_n and top_n < len(futures_symbols):
            # 獲取 24h ticker 來排序
            ticker_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            ticker_response = requests.get(ticker_url, timeout=30)
            ticker_response.raise_for_status()
            tickers = ticker_response.json()

            # 建立交易量映射
            volume_map = {}
            for t in tickers:
                volume_map[t["symbol"]] = float(t.get("quoteVolume", 0))

            # 排序
            futures_symbols.sort(key=lambda s: volume_map.get(s, 0), reverse=True)
            futures_symbols = futures_symbols[:top_n]

            logger.info(f"按交易量排序後取 Top {top_n}")

        return futures_symbols

    except Exception as e:
        logger.error(f"獲取永續合約列表失敗: {e}")
        # 降級：使用現貨 Top N
        logger.info("降級使用現貨 Top N 幣種...")
        fetcher = TopSymbolsFetcher()
        return fetcher.get_top_symbols(n=top_n, min_volume=1_000_000)


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
        description="批量下載衍生品數據 (Funding Rate, Open Interest, Long/Short Ratio)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=100,
        help="下載 Top N 幣種 (默認: 100)",
    )
    parser.add_argument(
        "--types",
        type=str,
        default="funding,oi",
        help="數據類型，逗號分隔 (funding/oi/lsr，默認: funding,oi)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="起始日期 (默認: 1年前)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="結束日期 (默認: 今天)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="1h",
        help="OI 時間間隔 (5m/15m/30m/1h/4h/1d，默認: 1h)",
    )
    parser.add_argument(
        "--list-symbols",
        action="store_true",
        help="只列出幣種，不實際下載",
    )
    return parser.parse_args()


def download_funding_rate(
    symbols: List[str],
    start_time: datetime,
    end_time: datetime,
) -> dict:
    """下載資金費率數據"""
    logger.info(f"開始下載資金費率數據: {len(symbols)} 個幣種")

    fr = FundingRateData()
    results = {"success": 0, "failed": 0, "errors": []}

    for i, symbol in enumerate(symbols, 1):
        try:
            logger.info(f"[{i}/{len(symbols)}] 下載 {symbol} 資金費率...")
            df = fr.fetch(symbol, start_time, end_time, exchange="binance", use_cache=False)

            if not df.empty:
                fr.save(df, symbol, "binance")
                results["success"] += 1
                logger.info(f"  ✓ {symbol}: {len(df)} 筆記錄")
            else:
                results["failed"] += 1
                results["errors"].append({"symbol": symbol, "error": "No data"})
                logger.warning(f"  ✗ {symbol}: 無數據")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"symbol": symbol, "error": str(e)})
            logger.error(f"  ✗ {symbol}: {e}")

        # 速率控制
        time.sleep(0.5)

    return results


def download_open_interest(
    symbols: List[str],
    start_time: datetime,
    end_time: datetime,
    interval: str = "1h",
) -> dict:
    """下載持倉量數據"""
    logger.info(f"開始下載持倉量數據: {len(symbols)} 個幣種, 間隔: {interval}")

    oi = OpenInterestData()
    results = {"success": 0, "failed": 0, "errors": []}

    for i, symbol in enumerate(symbols, 1):
        try:
            logger.info(f"[{i}/{len(symbols)}] 下載 {symbol} 持倉量...")
            df = oi.fetch(
                symbol, start_time, end_time, interval=interval, exchange="binance", use_cache=False
            )

            if not df.empty:
                oi.save(df, symbol, "binance", interval=interval)
                results["success"] += 1
                logger.info(f"  ✓ {symbol}: {len(df)} 筆記錄")
            else:
                results["failed"] += 1
                results["errors"].append({"symbol": symbol, "error": "No data"})
                logger.warning(f"  ✗ {symbol}: 無數據")

        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"symbol": symbol, "error": str(e)})
            logger.error(f"  ✗ {symbol}: {e}")

        # 速率控制
        time.sleep(0.5)

    return results


def main():
    """主函數"""
    args = parse_args()

    print("=" * 60)
    print("🐕 SuperDog Quant - 衍生品數據下載器")
    print("=" * 60)

    # 解析數據類型
    data_types = [t.strip().lower() for t in args.types.split(",")]
    valid_types = {"funding", "oi", "lsr"}
    for t in data_types:
        if t not in valid_types:
            logger.error(f"無效的數據類型: {t} (可選: funding, oi, lsr)")
            return 1

    # 設置日期範圍
    end_time = datetime.now() if args.end is None else datetime.strptime(args.end, "%Y-%m-%d")
    start_time = (
        end_time - timedelta(days=365)
        if args.start is None
        else datetime.strptime(args.start, "%Y-%m-%d")
    )

    # 獲取永續合約幣種列表（關鍵修改：只下載有永續合約的幣種）
    symbols = get_futures_symbols(top_n=args.top)

    # 顯示配置
    print(f"\n📋 下載配置:")
    print(f"  幣種數量: {len(symbols)}")
    print(f"  數據類型: {', '.join(data_types)}")
    print(f"  日期範圍: {start_time.strftime('%Y-%m-%d')} ~ {end_time.strftime('%Y-%m-%d')}")
    if "oi" in data_types:
        print(f"  OI 間隔: {args.interval}")

    # 只列出幣種
    if args.list_symbols:
        print("\n📝 將下載的幣種:")
        for i, symbol in enumerate(symbols, 1):
            print(f"  {i:3d}. {symbol}")
        return 0

    # 開始下載
    print("\n" + "=" * 60)
    print("🚀 開始下載...")
    print("=" * 60)

    all_results = {}
    total_start = datetime.now()

    # 下載資金費率
    if "funding" in data_types:
        print("\n📊 [1] 資金費率 (Funding Rate)")
        print("-" * 40)
        all_results["funding"] = download_funding_rate(symbols, start_time, end_time)

    # 下載持倉量
    if "oi" in data_types:
        print("\n📊 [2] 持倉量 (Open Interest)")
        print("-" * 40)
        all_results["oi"] = download_open_interest(symbols, start_time, end_time, args.interval)

    # 下載多空比 (待實現)
    if "lsr" in data_types:
        print("\n⚠️  多空比 (Long/Short Ratio) 下載功能開發中...")

    # 顯示結果
    total_duration = (datetime.now() - total_start).total_seconds()

    print("\n" + "=" * 60)
    print("📊 下載完成!")
    print("=" * 60)
    print(f"  總耗時: {total_duration/60:.1f} 分鐘")

    for data_type, results in all_results.items():
        print(f"\n  {data_type.upper()}:")
        print(f"    成功: {results['success']}")
        print(f"    失敗: {results['failed']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
