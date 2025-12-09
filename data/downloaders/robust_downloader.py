"""
Robust Downloader v0.7

健壯下載器 - 主入口點，整合所有下載功能

功能:
- YAML 配置檔支援
- 自動獲取 Top N 幣種
- 完整的錯誤處理和重試
- 下載報告生成

Version: v0.7
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from data.downloaders.multi_tf_downloader import MultiTimeframeDownloader
from data.downloaders.rate_limiter import RateLimiter
from data.downloaders.top_symbols_fetcher import TopSymbolsFetcher
from data.paths import get_raw_data_dir

logger = logging.getLogger(__name__)


def _get_default_output_dir() -> str:
    """獲取默認輸出目錄 (從 SSD 或本地)"""
    return str(get_raw_data_dir("binance"))


@dataclass
class DownloadConfig:
    """下載配置"""

    # 幣種設置
    symbols_source: str = "binance_top"
    symbols_count: int = 100
    symbols_list: List[str] = field(default_factory=list)
    exclude_stablecoins: bool = True
    exclude_leveraged: bool = True
    min_volume_24h: float = 1_000_000

    # 時間週期
    timeframes: List[str] = field(default_factory=lambda: ["1d", "4h", "1h", "15m"])

    # 日期範圍
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # 下載設置
    parallel_workers: int = 5
    checkpoint_enabled: bool = True
    retry_failed: bool = True
    max_retries: int = 3

    # 速率限制
    requests_per_minute: int = 1100

    # 存儲設置 (默認使用 SSD)
    output_dir: str = field(default_factory=_get_default_output_dir)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "DownloadConfig":
        """從 YAML 文件載入配置"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        config = cls()

        # 解析 symbols 配置
        symbols_config = data.get("symbols", {})
        config.symbols_source = symbols_config.get("source", "binance_top")
        config.symbols_count = symbols_config.get("count", 100)
        config.symbols_list = symbols_config.get("list", [])

        filters = symbols_config.get("filters", {})
        config.exclude_stablecoins = filters.get("exclude_stablecoins", True)
        config.exclude_leveraged = filters.get("exclude_leveraged", True)
        config.min_volume_24h = filters.get("min_volume_24h", 1_000_000)

        # 解析 timeframes 配置
        tf_config = data.get("timeframes", {})
        config.timeframes = tf_config.get("enabled", ["1d", "4h", "1h", "15m"])

        # 解析日期配置
        date_config = data.get("date_range", {})
        config.start_date = date_config.get("start")
        config.end_date = date_config.get("end")

        # 解析下載配置
        dl_config = data.get("download", {})
        config.parallel_workers = dl_config.get("parallel_workers", 5)
        config.checkpoint_enabled = dl_config.get("checkpoint_enabled", True)
        config.retry_failed = dl_config.get("retry_failed", True)
        config.max_retries = dl_config.get("max_retries", 3)

        # 解析速率限制
        rate_config = data.get("rate_limiting", {})
        config.requests_per_minute = rate_config.get("requests_per_minute", 1100)

        # 解析存儲配置 (默認使用 SSD)
        storage_config = data.get("storage", {})
        config.output_dir = storage_config.get("base_path", _get_default_output_dir())

        return config


@dataclass
class DownloadReport:
    """下載報告"""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_symbols: int = 0
    total_timeframes: int = 0
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_rows: int = 0
    total_duration: float = 0.0
    failed_items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_symbols": self.total_symbols,
            "total_timeframes": self.total_timeframes,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": (
                f"{(self.successful_tasks / self.total_tasks * 100):.1f}%"
                if self.total_tasks > 0
                else "N/A"
            ),
            "total_rows": self.total_rows,
            "total_duration": f"{self.total_duration:.2f}s",
            "failed_items": self.failed_items,
        }

    def save(self, path: str):
        """保存報告"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class RobustDownloader:
    """健壯下載器 - 主入口"""

    DEFAULT_CONFIG_PATH = "config/data_download.yaml"

    def __init__(
        self,
        config: Optional[DownloadConfig] = None,
        config_path: Optional[str] = None,
    ):
        """初始化下載器"""
        if config:
            self.config = config
        elif config_path and os.path.exists(config_path):
            self.config = DownloadConfig.from_yaml(config_path)
        elif os.path.exists(self.DEFAULT_CONFIG_PATH):
            self.config = DownloadConfig.from_yaml(self.DEFAULT_CONFIG_PATH)
        else:
            self.config = DownloadConfig()

        self.rate_limiter = RateLimiter(
            requests_per_minute=self.config.requests_per_minute,
            name="robust_downloader",
        )

        self.downloader = MultiTimeframeDownloader(
            output_dir=self.config.output_dir,
            max_workers=self.config.parallel_workers,
            rate_limiter=self.rate_limiter,
        )

        self.fetcher = TopSymbolsFetcher()

        logger.info("RobustDownloader 初始化完成")

    def get_symbols(self) -> List[str]:
        """獲取要下載的幣種列表"""
        if self.config.symbols_list:
            logger.info(f"使用指定幣種列表: {len(self.config.symbols_list)} 個")
            return self.config.symbols_list

        if self.config.symbols_source == "binance_top":
            logger.info(f"從 Binance 獲取 Top {self.config.symbols_count} 幣種")
            return self.fetcher.get_top_symbols(
                n=self.config.symbols_count,
                min_volume=self.config.min_volume_24h,
                exclude_stablecoins=self.config.exclude_stablecoins,
                exclude_leveraged=self.config.exclude_leveraged,
            )

        logger.warning(f"未知的幣種來源: {self.config.symbols_source}")
        return []

    def download_all(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        resume: bool = True,
    ) -> DownloadReport:
        """執行完整下載"""
        report = DownloadReport()
        report.start_time = datetime.now()

        # 獲取幣種列表
        if symbols is None:
            symbols = self.get_symbols()
        report.total_symbols = len(symbols)

        # 獲取時間週期
        if timeframes is None:
            timeframes = self.config.timeframes
        report.total_timeframes = len(timeframes)

        report.total_tasks = report.total_symbols * report.total_timeframes

        if not symbols:
            logger.warning("沒有幣種可下載")
            report.end_time = datetime.now()
            return report

        logger.info(
            f"開始下載: {len(symbols)} 幣種 x {len(timeframes)} 時間週期 = " f"{report.total_tasks} 個任務"
        )

        # 執行下載
        results = self.downloader.download_multi_timeframe(
            symbols=symbols,
            timeframes=timeframes,
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            resume=resume,
        )

        # 統計結果
        for result in results:
            if result.success:
                report.successful_tasks += 1
                report.total_rows += result.rows
            else:
                report.failed_tasks += 1
                report.failed_items.append(
                    {
                        "symbol": result.symbol,
                        "timeframe": result.timeframe,
                        "error": result.error,
                    }
                )
            report.total_duration += result.duration

        report.end_time = datetime.now()

        # 重試失敗的任務
        if self.config.retry_failed and report.failed_items:
            self._retry_failed(report)

        # 保存報告
        report_path = Path(self.config.output_dir) / "download_report.json"
        report.save(str(report_path))
        logger.info(f"下載報告已保存: {report_path}")

        return report

    def _retry_failed(self, report: DownloadReport):
        """重試失敗的任務"""
        failed = report.failed_items.copy()
        if not failed:
            return

        logger.info(f"重試 {len(failed)} 個失敗任務")

        for attempt in range(self.config.max_retries):
            if not failed:
                break

            logger.info(f"重試第 {attempt + 1} 次")
            time.sleep(5)  # 等待一下再重試

            still_failed = []
            for item in failed:
                results = self.downloader.download_multi_timeframe(
                    symbols=[item["symbol"]],
                    timeframes=[item["timeframe"]],
                    resume=False,
                )

                if results and results[0].success:
                    report.successful_tasks += 1
                    report.failed_tasks -= 1
                    report.total_rows += results[0].rows
                else:
                    still_failed.append(item)

            failed = still_failed

        # 更新失敗列表
        report.failed_items = failed

    def download_symbols(
        self,
        symbols: List[str],
        timeframes: Optional[List[str]] = None,
    ) -> DownloadReport:
        """下載指定幣種"""
        return self.download_all(
            symbols=symbols,
            timeframes=timeframes,
            resume=True,
        )

    def get_status(self) -> dict:
        """獲取下載狀態"""
        progress = self.downloader.get_progress()
        return {
            "completed": self.downloader.get_completed_count(),
            "current_progress": {
                "total": progress.total_tasks,
                "completed": progress.completed_tasks,
                "failed": progress.failed_tasks,
                "percent": f"{progress.percent:.1f}%",
            },
            "rate_limiter": self.rate_limiter.get_stats(),
        }

    def clear_checkpoint(self):
        """清除檢查點"""
        self.downloader.clear_checkpoint()

    def clear_data(self, confirm: bool = False):
        """清除所有下載的數據"""
        if not confirm:
            logger.warning("需要 confirm=True 才能清除數據")
            return

        import shutil

        output_path = Path(self.config.output_dir)
        if output_path.exists():
            shutil.rmtree(output_path)
            output_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"已清除: {output_path}")

        self.clear_checkpoint()


# ===== 便捷函數 =====


def download_all(
    config_path: Optional[str] = None,
    symbols: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
) -> DownloadReport:
    """下載所有數據（便捷函數）"""
    downloader = RobustDownloader(config_path=config_path)
    return downloader.download_all(symbols=symbols, timeframes=timeframes)


def download_top_n(
    n: int = 100,
    timeframes: Optional[List[str]] = None,
) -> DownloadReport:
    """下載 Top N 幣種（便捷函數）"""
    config = DownloadConfig(
        symbols_source="binance_top",
        symbols_count=n,
        timeframes=timeframes or ["1h", "4h", "1d"],
    )
    downloader = RobustDownloader(config=config)
    return downloader.download_all()
