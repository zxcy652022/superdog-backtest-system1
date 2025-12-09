"""
Multi-Timeframe Downloader v0.7

多時間週期並行下載器 - 支援同時下載多個時間週期的數據

功能:
- 並行下載多個幣種和時間週期
- 優先級調度（1h/1d 優先）
- 斷點續傳支援
- 進度追蹤

Version: v0.7
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import pandas as pd

from data.downloaders.rate_limiter import RateLimiter
from data.downloaders.symbol_mapper import SymbolMapper
from data.fetcher import OHLCVFetcher
from data.paths import get_raw_data_dir

logger = logging.getLogger(__name__)


def _get_default_output_dir() -> str:
    """獲取默認輸出目錄 (從 SSD 或本地)"""
    return str(get_raw_data_dir("binance"))


@dataclass
class DownloadTask:
    """下載任務"""

    symbol: str
    timeframe: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    priority: int = 0  # 數字越小優先級越高


@dataclass
class DownloadResult:
    """下載結果"""

    symbol: str
    timeframe: str
    success: bool
    rows: int = 0
    file_path: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0


@dataclass
class DownloadProgress:
    """下載進度"""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    current_symbol: str = ""
    current_timeframe: str = ""
    start_time: float = field(default_factory=time.time)

    @property
    def percent(self) -> float:
        """完成百分比"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def elapsed_time(self) -> float:
        """已用時間（秒）"""
        return time.time() - self.start_time

    @property
    def eta(self) -> Optional[float]:
        """預估剩餘時間（秒）"""
        if self.completed_tasks == 0:
            return None
        avg_time = self.elapsed_time / self.completed_tasks
        remaining = self.total_tasks - self.completed_tasks
        return avg_time * remaining


class MultiTimeframeDownloader:
    """多時間週期並行下載器"""

    # 時間週期優先級（數字越小越優先）
    TIMEFRAME_PRIORITY = {
        "1h": 1,
        "1d": 1,
        "4h": 2,
        "15m": 3,
        "5m": 4,
        "1m": 5,
    }

    def __init__(
        self,
        output_dir: Optional[str] = None,
        max_workers: int = 5,
        rate_limiter: Optional[RateLimiter] = None,
        checkpoint_file: Optional[str] = None,
    ):
        """初始化下載器"""
        # 使用 SSD 路徑作為默認值
        self.output_dir = Path(output_dir if output_dir else _get_default_output_dir())
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.max_workers = max_workers
        self.rate_limiter = rate_limiter or RateLimiter(requests_per_minute=1100, name="downloader")

        self.checkpoint_file = checkpoint_file or str(self.output_dir / ".download_checkpoint.json")
        self.completed_tasks: set = set()
        self._load_checkpoint()

        self.progress = DownloadProgress()
        self._progress_callback: Optional[Callable[[DownloadProgress], None]] = None

        logger.info(f"下載器初始化: output_dir={output_dir}, workers={max_workers}")

    def download_multi_timeframe(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        resume: bool = True,
    ) -> List[DownloadResult]:
        """下載多個幣種的多個時間週期"""
        tasks = self._create_tasks(symbols, timeframes, start_date, end_date)

        if resume:
            tasks = self._filter_completed_tasks(tasks)

        if not tasks:
            logger.info("所有任務已完成，無需下載")
            return []

        tasks.sort(key=lambda t: t.priority)

        logger.info(f"開始下載 {len(tasks)} 個任務")
        self.progress = DownloadProgress(total_tasks=len(tasks))

        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {executor.submit(self._download_single, task): task for task in tasks}

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)

                    if result.success:
                        self.progress.completed_tasks += 1
                        self._mark_completed(task)
                    else:
                        self.progress.failed_tasks += 1

                    self._notify_progress()

                except Exception as e:
                    logger.error(f"任務執行異常: {task.symbol}/{task.timeframe}: {e}")
                    self.progress.failed_tasks += 1
                    results.append(
                        DownloadResult(
                            symbol=task.symbol,
                            timeframe=task.timeframe,
                            success=False,
                            error=str(e),
                        )
                    )

        self._save_checkpoint()
        logger.info(
            f"下載完成: 成功={self.progress.completed_tasks}, " f"失敗={self.progress.failed_tasks}"
        )

        return results

    def _create_tasks(
        self,
        symbols: List[str],
        timeframes: List[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> List[DownloadTask]:
        """創建下載任務列表"""
        tasks = []
        for symbol in symbols:
            for tf in timeframes:
                priority = self.TIMEFRAME_PRIORITY.get(tf, 10)
                task = DownloadTask(
                    symbol=symbol,
                    timeframe=tf,
                    start_date=start_date,
                    end_date=end_date,
                    priority=priority,
                )
                tasks.append(task)
        return tasks

    def _filter_completed_tasks(self, tasks: List[DownloadTask]) -> List[DownloadTask]:
        """過濾已完成的任務"""
        remaining = []
        for task in tasks:
            task_key = f"{task.symbol}_{task.timeframe}"
            if task_key not in self.completed_tasks:
                remaining.append(task)
        logger.info(f"過濾完成: {len(tasks)} -> {len(remaining)} 個待下載")
        return remaining

    def _download_single(self, task: DownloadTask) -> DownloadResult:
        """下載單個任務"""
        start_time = time.time()

        self.progress.current_symbol = task.symbol
        self.progress.current_timeframe = task.timeframe

        try:
            self.rate_limiter.acquire()

            # 準備保存路徑
            file_path = self._get_file_path(task.symbol, task.timeframe)

            # 轉換符號格式為 CCXT 格式 (BTC/USDT)
            mapper = SymbolMapper()
            ccxt_symbol = mapper.to_ccxt(task.symbol) or task.symbol

            # 使用 OHLCVFetcher 下載數據
            fetcher = OHLCVFetcher()

            # 設置默認日期範圍
            start_date = task.start_date or "2020-01-01"
            end_date = task.end_date or datetime.now().strftime("%Y-%m-%d")

            saved_path = fetcher.fetch_ohlcv(
                symbol=ccxt_symbol,
                timeframe=task.timeframe,
                start_date=start_date,
                end_date=end_date,
                save_path=str(file_path),
            )

            # 讀取保存的數據以獲取行數
            if os.path.exists(saved_path):
                df = pd.read_csv(saved_path)
                rows = len(df)
            else:
                return DownloadResult(
                    symbol=task.symbol,
                    timeframe=task.timeframe,
                    success=False,
                    error="No data returned",
                    duration=time.time() - start_time,
                )

            duration = time.time() - start_time
            logger.debug(f"下載成功: {task.symbol}/{task.timeframe} - " f"{rows} 行, {duration:.2f}s")

            return DownloadResult(
                symbol=task.symbol,
                timeframe=task.timeframe,
                success=True,
                rows=rows,
                file_path=saved_path,
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"下載失敗: {task.symbol}/{task.timeframe}: {e}")
            return DownloadResult(
                symbol=task.symbol,
                timeframe=task.timeframe,
                success=False,
                error=str(e),
                duration=duration,
            )

    def _get_file_path(self, symbol: str, timeframe: str) -> Path:
        """獲取文件保存路徑"""
        # 創建時間週期目錄
        tf_dir = self.output_dir / timeframe
        tf_dir.mkdir(parents=True, exist_ok=True)

        # 文件名格式: BTCUSDT_1h.csv
        return tf_dir / f"{symbol}_{timeframe}.csv"

    def _save_data(self, symbol: str, timeframe: str, df) -> Path:
        """保存數據到文件"""
        file_path = self._get_file_path(symbol, timeframe)
        df.to_csv(file_path, index=True)
        return file_path

    def _mark_completed(self, task: DownloadTask):
        """標記任務為已完成"""
        task_key = f"{task.symbol}_{task.timeframe}"
        self.completed_tasks.add(task_key)

    def _load_checkpoint(self):
        """載入檢查點"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r") as f:
                    data = json.load(f)
                    self.completed_tasks = set(data.get("completed", []))
                logger.info(f"載入檢查點: {len(self.completed_tasks)} 個已完成任務")
            except Exception as e:
                logger.warning(f"載入檢查點失敗: {e}")
                self.completed_tasks = set()

    def _save_checkpoint(self):
        """保存檢查點"""
        try:
            data = {
                "completed": list(self.completed_tasks),
                "last_update": datetime.now().isoformat(),
            }
            with open(self.checkpoint_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("檢查點已保存")
        except Exception as e:
            logger.warning(f"保存檢查點失敗: {e}")

    def clear_checkpoint(self):
        """清除檢查點"""
        self.completed_tasks = set()
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
        logger.info("檢查點已清除")

    def set_progress_callback(self, callback: Callable[[DownloadProgress], None]):
        """設置進度回調"""
        self._progress_callback = callback

    def _notify_progress(self):
        """通知進度更新"""
        if self._progress_callback:
            self._progress_callback(self.progress)

    def get_progress(self) -> DownloadProgress:
        """獲取當前進度"""
        return self.progress

    def get_completed_count(self) -> int:
        """獲取已完成任務數"""
        return len(self.completed_tasks)


# ===== 便捷函數 =====


def download_symbols_multi_tf(
    symbols: List[str],
    timeframes: List[str] = None,
    output_dir: Optional[str] = None,
    max_workers: int = 5,
) -> List[DownloadResult]:
    """下載多個幣種的多個時間週期（便捷函數）"""
    if timeframes is None:
        timeframes = ["1h", "4h", "1d"]

    downloader = MultiTimeframeDownloader(
        output_dir=output_dir,
        max_workers=max_workers,
    )

    return downloader.download_multi_timeframe(
        symbols=symbols,
        timeframes=timeframes,
    )
