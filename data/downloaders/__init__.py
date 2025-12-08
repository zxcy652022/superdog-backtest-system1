"""
SuperDog v0.7 智能數據抓取系統

核心模組:
- SymbolMapper: 符號映射器
- RateLimiter: 速率限制器
- TopSymbolsFetcher: Top 100 抓取器
- MultiTimeframeDownloader: 多時間週期下載器
- RobustDownloader: 健壯下載器（主入口）

Version: v0.7
"""

from data.downloaders.multi_tf_downloader import MultiTimeframeDownloader
from data.downloaders.rate_limiter import RateLimiter
from data.downloaders.robust_downloader import (
    DownloadConfig,
    DownloadReport,
    RobustDownloader,
    download_all,
)
from data.downloaders.symbol_mapper import SymbolMapper, normalize_symbol
from data.downloaders.top_symbols_fetcher import (TopSymbolsFetcher,
                                                  get_top_symbols)

__all__ = [
    "SymbolMapper",
    "normalize_symbol",
    "RateLimiter",
    "TopSymbolsFetcher",
    "get_top_symbols",
    "MultiTimeframeDownloader",
    "RobustDownloader",
    "DownloadConfig",
    "DownloadReport",
    "download_all",
]

__version__ = "0.7.0"
