"""
抓取擴展數據
- 幣種: TOP30
- 時間: 2018-01-01 ~ 2025-12-31
- 時間框架: 4H
- 存儲位置: /Volumes/權志龍的寶藏/SuperDogData/binance_4h/
"""

import sys
import time
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import requests

DATA_DIR = Path("/Volumes/權志龍的寶藏/SuperDogData/binance_4h")

# TOP30 幣種 (按市值排序，排除穩定幣)
TOP30_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "SOLUSDT",
    "DOTUSDT",
    "LTCUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "ATOMUSDT",
    "UNIUSDT",
    "ETCUSDT",
    "XLMUSDT",
    "NEARUSDT",
    "APTUSDT",
    "FILUSDT",
    "ARBUSDT",
    "MATICUSDT",
    "TRXUSDT",
    "SHIBUSDT",
    "ICPUSDT",
    "VETUSDT",
    "HBARUSDT",
    "INJUSDT",
    "OPUSDT",
    "IMXUSDT",
    "RNDRUSDT",
    "SUIUSDT",
]


def fetch_klines(
    symbol: str,
    interval: str = "4h",
    start_time: int = None,
    end_time: int = None,
    limit: int = 1000,
) -> list:
    """從 Binance API 獲取K線數據"""
    url = "https://api.binance.com/api/v3/klines"

    params = {"symbol": symbol, "interval": interval, "limit": limit}

    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"    Error fetching {symbol}: {e}")
        return []


def fetch_all_klines(
    symbol: str, start_date: str, end_date: str, interval: str = "4h"
) -> pd.DataFrame:
    """獲取完整時間範圍的K線數據"""
    start_ts = int(pd.Timestamp(start_date).timestamp() * 1000)
    end_ts = int(pd.Timestamp(end_date).timestamp() * 1000)

    all_klines = []
    current_start = start_ts

    while current_start < end_ts:
        klines = fetch_klines(symbol, interval, current_start, end_ts, 1000)

        if not klines:
            break

        all_klines.extend(klines)

        # 下一批從最後一條之後開始
        last_ts = klines[-1][0]
        if last_ts <= current_start:
            break
        current_start = last_ts + 1

        # 避免請求過快
        time.sleep(0.1)

    if not all_klines:
        return pd.DataFrame()

    # 轉換為DataFrame
    df = pd.DataFrame(
        all_klines,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )

    # 轉換數據類型
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["timestamp"] = pd.to_numeric(df["timestamp"])

    # 去重
    df = df.drop_duplicates(subset=["timestamp"])
    df = df.sort_values("timestamp")

    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def main():
    print("=" * 80)
    print("抓取擴展數據 (TOP30, 2018-2025)")
    print("=" * 80)

    # 確保目錄存在
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    start_date = "2018-01-01"
    end_date = "2025-12-31"

    successful = []
    failed = []

    for i, symbol in enumerate(TOP30_SYMBOLS):
        print(f"\n[{i+1}/{len(TOP30_SYMBOLS)}] {symbol}")

        # 檢查是否已存在
        existing_files = list(DATA_DIR.glob(f"{symbol}_*.parquet"))
        if existing_files:
            # 讀取現有文件檢查時間範圍
            existing_df = pd.read_parquet(existing_files[0])
            if "timestamp" in existing_df.columns:
                existing_df["timestamp"] = pd.to_datetime(existing_df["timestamp"], unit="ms")
                min_date = existing_df["timestamp"].min()
                max_date = existing_df["timestamp"].max()
                print(f"  已有數據: {min_date.date()} ~ {max_date.date()}")

                # 如果已經有足夠數據，跳過
                if min_date <= pd.Timestamp("2018-06-01") and max_date >= pd.Timestamp(
                    "2025-01-01"
                ):
                    print(f"  ✓ 數據充足，跳過")
                    successful.append(symbol)
                    continue

        # 抓取數據
        print(f"  抓取 {start_date} ~ {end_date}...")
        df = fetch_all_klines(symbol, start_date, end_date)

        if df.empty:
            print(f"  ✗ 無數據")
            failed.append(symbol)
            continue

        # 檢查數據範圍
        df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
        min_date = df["dt"].min()
        max_date = df["dt"].max()
        print(f"  獲取數據: {min_date.date()} ~ {max_date.date()}, {len(df)} 條")

        # 保存
        output_file = DATA_DIR / f"{symbol}_4h.parquet"
        df[["timestamp", "open", "high", "low", "close", "volume"]].to_parquet(output_file)
        print(f"  ✓ 已保存至 {output_file.name}")

        successful.append(symbol)

        # 避免請求過快
        time.sleep(0.5)

    # 摘要
    print(f"\n{'='*80}")
    print("摘要")
    print("=" * 80)
    print(f"成功: {len(successful)}/{len(TOP30_SYMBOLS)}")
    print(f"失敗: {len(failed)}")
    if failed:
        print(f"失敗幣種: {', '.join(failed)}")

    # 檢查最終可用數據
    print(f"\n可用數據檢查:")
    valid_symbols = []
    for symbol in successful:
        files = list(DATA_DIR.glob(f"{symbol}_*.parquet"))
        if files:
            df = pd.read_parquet(files[0])
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                min_date = df["timestamp"].min()

                # 檢查是否有足夠早的數據 (至少2019年)
                if min_date <= pd.Timestamp("2019-01-01"):
                    valid_symbols.append(symbol)
                    print(f"  ✓ {symbol}: {min_date.date()} 起")
                else:
                    print(f"  ⚠ {symbol}: 僅從 {min_date.date()} 起")

    print(f"\n有效幣種 (2019年前有數據): {len(valid_symbols)}")
    print(valid_symbols)


if __name__ == "__main__":
    main()
