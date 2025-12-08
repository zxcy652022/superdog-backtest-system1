"""
Multi-Timeframe Downloader 測試

測試多時間週期並行下載器的各種功能
"""

import tempfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.downloaders.multi_tf_downloader import (DownloadProgress,
                                                  DownloadResult, DownloadTask,
                                                  MultiTimeframeDownloader,
                                                  download_symbols_multi_tf)


class TestDownloadTask:
    """DownloadTask 測試類"""

    def test_task_creation(self):
        """測試任務創建"""
        task = DownloadTask(
            symbol="BTCUSDT",
            timeframe="1h",
            start_date="2024-01-01",
            priority=1,
        )
        assert task.symbol == "BTCUSDT"
        assert task.timeframe == "1h"
        assert task.priority == 1

    def test_task_default_priority(self):
        """測試默認優先級"""
        task = DownloadTask(symbol="BTCUSDT", timeframe="1h")
        assert task.priority == 0


class TestDownloadResult:
    """DownloadResult 測試類"""

    def test_result_success(self):
        """測試成功結果"""
        result = DownloadResult(
            symbol="BTCUSDT",
            timeframe="1h",
            success=True,
            rows=1000,
            file_path="/path/to/file.csv",
        )
        assert result.success is True
        assert result.rows == 1000

    def test_result_failure(self):
        """測試失敗結果"""
        result = DownloadResult(
            symbol="BTCUSDT",
            timeframe="1h",
            success=False,
            error="Connection timeout",
        )
        assert result.success is False
        assert result.error == "Connection timeout"


class TestDownloadProgress:
    """DownloadProgress 測試類"""

    def test_progress_percent(self):
        """測試完成百分比"""
        progress = DownloadProgress(total_tasks=100, completed_tasks=50)
        assert progress.percent == 50.0

    def test_progress_percent_empty(self):
        """測試空任務的百分比"""
        progress = DownloadProgress(total_tasks=0)
        assert progress.percent == 0.0

    def test_progress_eta(self):
        """測試預估剩餘時間"""
        progress = DownloadProgress(total_tasks=100, completed_tasks=50)
        # ETA 需要 elapsed_time，這裡只測試有 completed_tasks 時返回非 None
        assert progress.eta is not None or progress.completed_tasks == 0


class TestMultiTimeframeDownloader:
    """MultiTimeframeDownloader 測試類"""

    @pytest.fixture
    def temp_dir(self):
        """創建臨時目錄"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def downloader(self, temp_dir):
        """創建下載器實例"""
        return MultiTimeframeDownloader(
            output_dir=temp_dir,
            max_workers=2,
        )

    def test_initialization(self, downloader, temp_dir):
        """測試初始化"""
        assert downloader.max_workers == 2
        assert str(downloader.output_dir) == temp_dir

    def test_timeframe_priority(self, downloader):
        """測試時間週期優先級"""
        assert downloader.TIMEFRAME_PRIORITY["1h"] == 1
        assert downloader.TIMEFRAME_PRIORITY["1d"] == 1
        assert downloader.TIMEFRAME_PRIORITY["4h"] == 2
        assert downloader.TIMEFRAME_PRIORITY["15m"] == 3

    def test_create_tasks(self, downloader):
        """測試創建任務"""
        tasks = downloader._create_tasks(
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframes=["1h", "4h"],
            start_date=None,
            end_date=None,
        )
        assert len(tasks) == 4  # 2 symbols x 2 timeframes

    def test_filter_completed_tasks(self, downloader):
        """測試過濾已完成任務"""
        downloader.completed_tasks = {"BTCUSDT_1h"}
        tasks = [
            DownloadTask(symbol="BTCUSDT", timeframe="1h"),
            DownloadTask(symbol="BTCUSDT", timeframe="4h"),
        ]
        filtered = downloader._filter_completed_tasks(tasks)
        assert len(filtered) == 1
        assert filtered[0].timeframe == "4h"

    def test_mark_completed(self, downloader):
        """測試標記完成"""
        task = DownloadTask(symbol="BTCUSDT", timeframe="1h")
        downloader._mark_completed(task)
        assert "BTCUSDT_1h" in downloader.completed_tasks

    def test_checkpoint_save_and_load(self, downloader, temp_dir):
        """測試檢查點保存和載入"""
        downloader.completed_tasks = {"BTCUSDT_1h", "ETHUSDT_1h"}
        downloader._save_checkpoint()

        # 創建新實例載入檢查點
        new_downloader = MultiTimeframeDownloader(output_dir=temp_dir)
        assert "BTCUSDT_1h" in new_downloader.completed_tasks
        assert "ETHUSDT_1h" in new_downloader.completed_tasks

    def test_clear_checkpoint(self, downloader):
        """測試清除檢查點"""
        downloader.completed_tasks = {"BTCUSDT_1h"}
        downloader._save_checkpoint()
        downloader.clear_checkpoint()
        assert len(downloader.completed_tasks) == 0

    def test_set_progress_callback(self, downloader):
        """測試設置進度回調"""
        callback = MagicMock()
        downloader.set_progress_callback(callback)
        assert downloader._progress_callback == callback

    def test_get_progress(self, downloader):
        """測試獲取進度"""
        progress = downloader.get_progress()
        assert isinstance(progress, DownloadProgress)

    def test_get_completed_count(self, downloader):
        """測試獲取完成數量"""
        downloader.completed_tasks = {"a", "b", "c"}
        assert downloader.get_completed_count() == 3

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    @patch("data.downloaders.multi_tf_downloader.os.path.exists")
    @patch("data.downloaders.multi_tf_downloader.pd.read_csv")
    def test_download_single_success(
        self, mock_read_csv, mock_exists, mock_fetcher_class, downloader
    ):
        """測試單個下載成功"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.return_value = "/tmp/test.csv"
        mock_fetcher_class.return_value = mock_fetcher
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame({"close": [100, 101, 102]})

        task = DownloadTask(symbol="BTCUSDT", timeframe="1h")
        result = downloader._download_single(task)

        assert result.success is True
        assert result.rows == 3

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    @patch("data.downloaders.multi_tf_downloader.os.path.exists")
    def test_download_single_empty_data(
        self, mock_exists, mock_fetcher_class, downloader
    ):
        """測試單個下載返回空數據"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.return_value = "/tmp/test.csv"
        mock_fetcher_class.return_value = mock_fetcher
        mock_exists.return_value = False

        task = DownloadTask(symbol="BTCUSDT", timeframe="1h")
        result = downloader._download_single(task)

        assert result.success is False
        assert "No data" in result.error

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    def test_download_single_exception(self, mock_fetcher_class, downloader):
        """測試單個下載異常"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.side_effect = Exception("Network error")
        mock_fetcher_class.return_value = mock_fetcher

        task = DownloadTask(symbol="BTCUSDT", timeframe="1h")
        result = downloader._download_single(task)

        assert result.success is False
        assert "Network error" in result.error

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    @patch("data.downloaders.multi_tf_downloader.os.path.exists")
    @patch("data.downloaders.multi_tf_downloader.pd.read_csv")
    def test_download_multi_timeframe(
        self, mock_read_csv, mock_exists, mock_fetcher_class, downloader
    ):
        """測試多時間週期下載"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.return_value = "/tmp/test.csv"
        mock_fetcher_class.return_value = mock_fetcher
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame({"close": [100, 101, 102]})

        results = downloader.download_multi_timeframe(
            symbols=["BTCUSDT"],
            timeframes=["1h"],
            resume=False,
        )

        assert len(results) == 1
        assert results[0].success is True

    def test_download_no_tasks(self, downloader):
        """測試無任務下載"""
        downloader.completed_tasks = {"BTCUSDT_1h"}
        results = downloader.download_multi_timeframe(
            symbols=["BTCUSDT"],
            timeframes=["1h"],
            resume=True,
        )
        assert len(results) == 0


class TestConvenienceFunctions:
    """便捷函數測試"""

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    @patch("data.downloaders.multi_tf_downloader.os.path.exists")
    @patch("data.downloaders.multi_tf_downloader.pd.read_csv")
    def test_download_symbols_multi_tf(
        self, mock_read_csv, mock_exists, mock_fetcher_class
    ):
        """測試便捷函數"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.return_value = "/tmp/test.csv"
        mock_fetcher_class.return_value = mock_fetcher
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame({"close": [100, 101, 102]})

        with tempfile.TemporaryDirectory() as tmpdir:
            results = download_symbols_multi_tf(
                symbols=["BTCUSDT"],
                timeframes=["1h"],
                output_dir=tmpdir,
            )
            assert isinstance(results, list)
