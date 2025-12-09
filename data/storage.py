"""
Data Storage Module v0.4

負責讀取和處理 OHLCV CSV 數據。
將 CSV 轉換為 pandas DataFrame，並進行必要的格式化。

v0.4 Updates:
- 整合 TimeframeManager 和 SymbolManager
- 支援多時間週期和多交易對
- 與 DataPipeline 無縫整合
- 增強的數據驗證和清理
- SSD 環境支援

Version: v0.4
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# SSD 配置支援 (v0.4)
from data.config import config

# v0.4: 新增管理器
from data.timeframe_manager import TimeframeManager
from data.universe.symbols import SymbolManager

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OHLCVStorage:
    """OHLCV 數據儲存與讀取器

    v0.4 Updates:
    - 整合 TimeframeManager 和 SymbolManager
    - 支援多時間週期和多交易對載入
    - 自動數據驗證和清理
    - SSD 環境整合
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """初始化儲存器

        Args:
            data_dir: 數據目錄路徑（默認使用 SSD 配置）
        """
        self.data_dir = data_dir or config.data_root
        self.timeframe_manager = TimeframeManager()
        self.symbol_manager = SymbolManager()

    def load_ohlcv(
        self,
        file_path: str,
        convert_to_datetime: bool = True,
        set_datetime_index: bool = True,
        timezone: str = "UTC",
    ) -> pd.DataFrame:
        """
        載入 OHLCV CSV 為 DataFrame

        Args:
            file_path: CSV 檔案路徑
            convert_to_datetime: 是否將 timestamp 轉換為 datetime
            set_datetime_index: 是否將 datetime 設為索引
            timezone: 時區，預設為 UTC

        Returns:
            pd.DataFrame: OHLCV 數據

        Raises:
            FileNotFoundError: 當檔案不存在時
            Exception: 當讀取或轉換失敗時
        """
        logger.info(f"載入 OHLCV 數據: {file_path}")

        try:
            # 讀取 CSV
            df = pd.read_csv(file_path)

            # 驗證必要欄位
            required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
            missing_columns = set(required_columns) - set(df.columns)
            if missing_columns:
                raise Exception(f"CSV 缺少必要欄位: {missing_columns}")

            # 確保數據類型正確
            df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
            df["open"] = pd.to_numeric(df["open"], errors="coerce")
            df["high"] = pd.to_numeric(df["high"], errors="coerce")
            df["low"] = pd.to_numeric(df["low"], errors="coerce")
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

            # 移除包含 NaN 的行（轉換失敗的數據）
            original_len = len(df)
            df = df.dropna()
            if len(df) < original_len:
                logger.warning(f"移除了 {original_len - len(df)} 筆包含無效數據的行")

            # 轉換時間戳為 datetime
            if convert_to_datetime:
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

                # 設定時區
                if timezone != "UTC":
                    df["datetime"] = df["datetime"].dt.tz_convert(timezone)

                # 設定 datetime 為索引
                if set_datetime_index:
                    df = df.set_index("datetime")
                    # 保留 timestamp 欄位以便需要時使用
                    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                else:
                    # 調整欄位順序
                    df = df[["datetime", "timestamp", "open", "high", "low", "close", "volume"]]
            else:
                # 不轉換時，確保欄位順序
                df = df[["timestamp", "open", "high", "low", "close", "volume"]]

            # 排序
            if set_datetime_index and convert_to_datetime:
                df = df.sort_index()
            else:
                df = df.sort_values("timestamp")

            logger.info(f"成功載入 {len(df)} 筆數據")
            if convert_to_datetime and len(df) > 0:
                if set_datetime_index:
                    logger.info(f"期間: {df.index[0]} ~ {df.index[-1]}")
                else:
                    logger.info(f"期間: {df['datetime'].iloc[0]} ~ {df['datetime'].iloc[-1]}")

            return df

        except FileNotFoundError:
            error_msg = f"找不到檔案: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        except Exception as e:
            error_msg = f"載入 OHLCV 數據失敗: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def load_symbol_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        v0.4: 載入指定交易對和時間週期的數據

        Args:
            symbol: 交易對（如 BTCUSDT）
            timeframe: 時間週期（如 1h）
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）

        Returns:
            pd.DataFrame: OHLCV 數據

        Raises:
            ValueError: 當交易對或時間週期無效時
            FileNotFoundError: 當數據文件不存在時

        Example:
            >>> storage = OHLCVStorage()
            >>> df = storage.load_symbol_data("BTCUSDT", "1h")
        """
        # 驗證交易對
        if not self.symbol_manager.validate_symbol(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")

        # 驗證時間週期
        if not self.timeframe_manager.validate_timeframe(timeframe):
            raise ValueError(f"Invalid timeframe: {timeframe}")

        # 構建文件路徑
        # 檢查歷史數據目錄（binance）
        file_path = self.data_dir / "historical" / "binance" / f"{symbol}_{timeframe}.csv"

        # 如果不存在，嘗試 raw 目錄（向後兼容）
        if not file_path.exists():
            file_path = self.data_dir / "raw" / f"{symbol}_{timeframe}.csv"

        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        # 載入數據
        df = self.load_ohlcv(str(file_path))

        # 過濾日期範圍
        if start_date:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df.index <= pd.Timestamp(end_date)]

        logger.info(f"Loaded {len(df)} bars for {symbol} ({timeframe})")

        return df

    def load_multiple_symbols(
        self,
        symbols: List[str],
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        v0.4: 載入多個交易對的數據

        Args:
            symbols: 交易對列表
            timeframe: 時間週期
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）

        Returns:
            字典，鍵為交易對，值為 DataFrame

        Example:
            >>> storage = OHLCVStorage()
            >>> symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
            >>> data = storage.load_multiple_symbols(symbols, "1h")
            >>> print(f"Loaded {len(data)} symbols")
        """
        result = {}

        for symbol in symbols:
            try:
                df = self.load_symbol_data(symbol, timeframe, start_date, end_date)
                result[symbol] = df
            except Exception as e:
                logger.warning(f"Failed to load {symbol}: {e}")

        logger.info(f"Successfully loaded {len(result)}/{len(symbols)} symbols")

        return result

    def load_multiple_timeframes(
        self,
        symbol: str,
        timeframes: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        v0.4: 載入單一交易對的多個時間週期數據

        Args:
            symbol: 交易對
            timeframes: 時間週期列表
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）

        Returns:
            字典，鍵為時間週期，值為 DataFrame

        Example:
            >>> storage = OHLCVStorage()
            >>> timeframes = ["1h", "4h", "1d"]
            >>> data = storage.load_multiple_timeframes("BTCUSDT", timeframes)
            >>> print(f"Loaded {len(data)} timeframes")
        """
        result = {}

        for timeframe in timeframes:
            try:
                df = self.load_symbol_data(symbol, timeframe, start_date, end_date)
                result[timeframe] = df
            except Exception as e:
                logger.warning(f"Failed to load {symbol} {timeframe}: {e}")

        logger.info(f"Successfully loaded {len(result)}/{len(timeframes)} timeframes for {symbol}")

        return result

    def list_available_data(self) -> List[Dict[str, str]]:
        """
        v0.4: 列出所有可用的數據文件

        Returns:
            可用數據文件的列表，每個元素包含 symbol 和 timeframe

        Example:
            >>> storage = OHLCVStorage()
            >>> available = storage.list_available_data()
            >>> for item in available:
            ...     print(f"{item['symbol']} - {item['timeframe']}")
        """
        # 檢查多個可能的數據目錄
        search_dirs = [self.data_dir / "historical" / "binance", self.data_dir / "raw"]

        available = []

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for file_path in search_dir.glob("*_*.csv"):
                # 解析文件名（格式：SYMBOL_TIMEFRAME.csv）
                file_name = file_path.stem
                parts = file_name.rsplit("_", 1)

                if len(parts) == 2:
                    symbol, timeframe = parts

                    # 驗證
                    if self.symbol_manager.validate_symbol(
                        symbol
                    ) and self.timeframe_manager.validate_timeframe(timeframe):
                        # 避免重複
                        if not any(
                            item["symbol"] == symbol and item["timeframe"] == timeframe
                            for item in available
                        ):
                            available.append(
                                {
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "file_path": str(file_path),
                                }
                            )

        logger.info(f"Found {len(available)} available data files")
        return available

    def save_ohlcv(self, df: pd.DataFrame, file_path: str, include_datetime: bool = False) -> str:
        """
        儲存 DataFrame 為 CSV

        Args:
            df: OHLCV DataFrame
            file_path: 儲存路徑
            include_datetime: 是否包含 datetime 欄位

        Returns:
            str: 檔案路徑

        Raises:
            Exception: 當儲存失敗時
        """
        logger.info(f"儲存 OHLCV 數據至: {file_path}")

        try:
            # 準備儲存的資料
            df_to_save = df.copy()

            # 如果 index 是 datetime，重置索引
            if isinstance(df_to_save.index, pd.DatetimeIndex):
                df_to_save = df_to_save.reset_index()

            # 選擇要儲存的欄位
            if include_datetime and "datetime" in df_to_save.columns:
                columns = ["datetime", "timestamp", "open", "high", "low", "close", "volume"]
            else:
                columns = ["timestamp", "open", "high", "low", "close", "volume"]

            # 確保所有必要欄位都存在
            available_columns = [col for col in columns if col in df_to_save.columns]
            df_to_save = df_to_save[available_columns]

            # 儲存
            df_to_save.to_csv(file_path, index=False)
            logger.info(f"成功儲存 {len(df_to_save)} 筆數據")

            return file_path

        except Exception as e:
            error_msg = f"儲存 OHLCV 數據失敗: {e}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def get_ohlcv_info(self, df: pd.DataFrame) -> dict:
        """
        取得 OHLCV DataFrame 的摘要資訊

        Args:
            df: OHLCV DataFrame

        Returns:
            dict: 摘要資訊
        """
        info = {
            "total_rows": len(df),
            "columns": list(df.columns),
            "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
        }

        # 如果有 datetime index 或欄位
        if isinstance(df.index, pd.DatetimeIndex):
            info["start_date"] = str(df.index[0])
            info["end_date"] = str(df.index[-1])
            info["duration_days"] = (df.index[-1] - df.index[0]).days
        elif "datetime" in df.columns:
            info["start_date"] = str(df["datetime"].iloc[0])
            info["end_date"] = str(df["datetime"].iloc[-1])
            info["duration_days"] = (df["datetime"].iloc[-1] - df["datetime"].iloc[0]).days

        # 價格統計
        if "close" in df.columns:
            info["price_stats"] = {
                "min": float(df["close"].min()),
                "max": float(df["close"].max()),
                "mean": float(df["close"].mean()),
                "std": float(df["close"].std()),
            }

        # 成交量統計
        if "volume" in df.columns:
            info["volume_stats"] = {
                "min": float(df["volume"].min()),
                "max": float(df["volume"].max()),
                "mean": float(df["volume"].mean()),
                "total": float(df["volume"].sum()),
            }

        return info


def load_ohlcv(
    file_path: str,
    convert_to_datetime: bool = True,
    set_datetime_index: bool = True,
    timezone: str = "UTC",
) -> pd.DataFrame:
    """
    便捷函數：載入 OHLCV CSV 為 DataFrame

    Args:
        file_path: CSV 檔案路徑
        convert_to_datetime: 是否將 timestamp 轉換為 datetime
        set_datetime_index: 是否將 datetime 設為索引
        timezone: 時區，預設為 UTC

    Returns:
        pd.DataFrame: OHLCV 數據
    """
    storage = OHLCVStorage()
    return storage.load_ohlcv(
        file_path=file_path,
        convert_to_datetime=convert_to_datetime,
        set_datetime_index=set_datetime_index,
        timezone=timezone,
    )


if __name__ == "__main__":
    # 測試載入
    import sys

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = "data/raw/BTCUSDT_1h.csv"

    try:
        # 載入數據
        df = load_ohlcv(csv_path)

        print("\n=== OHLCV 數據載入成功 ===")
        print(f"\n數據形狀: {df.shape}")
        print(f"\n欄位: {list(df.columns)}")
        print(f"\n索引類型: {type(df.index).__name__}")

        print("\n前 5 筆數據:")
        print(df.head())

        print("\n後 5 筆數據:")
        print(df.tail())

        # 顯示摘要資訊
        storage = OHLCVStorage()
        info = storage.get_ohlcv_info(df)

        print("\n=== 數據摘要 ===")
        print(f"總筆數: {info['total_rows']}")
        print(f"期間: {info.get('start_date', 'N/A')} ~ {info.get('end_date', 'N/A')}")
        if "duration_days" in info:
            print(f"持續天數: {info['duration_days']}")
        if "price_stats" in info:
            print(f"\n價格統計:")
            print(f"  最低: {info['price_stats']['min']:.2f}")
            print(f"  最高: {info['price_stats']['max']:.2f}")
            print(f"  平均: {info['price_stats']['mean']:.2f}")
        print(f"\n記憶體使用: {info['memory_usage_mb']:.2f} MB")

    except Exception as e:
        print(f"載入失敗: {e}")
        sys.exit(1)
