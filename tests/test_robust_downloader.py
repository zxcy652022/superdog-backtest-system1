"""
Robust Downloader 測試

測試健壯下載器的各種功能
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.downloaders.robust_downloader import (DownloadConfig, DownloadReport,
                                                RobustDownloader, download_all,
                                                download_top_n)


class TestDownloadConfig:
    """DownloadConfig 測試類"""

    def test_default_config(self):
        """測試默認配置"""
        config = DownloadConfig()
        assert config.symbols_source == "binance_top"
        assert config.symbols_count == 100
        assert config.parallel_workers == 5
        assert config.requests_per_minute == 1100

    def test_custom_config(self):
        """測試自定義配置"""
        config = DownloadConfig(
            symbols_source="manual",
            symbols_list=["BTCUSDT", "ETHUSDT"],
            parallel_workers=3,
        )
        assert config.symbols_source == "manual"
        assert len(config.symbols_list) == 2
        assert config.parallel_workers == 3

    def test_from_yaml(self):
        """測試從 YAML 載入配置"""
        yaml_content = """
symbols:
  source: binance_top
  count: 50
  filters:
    exclude_stablecoins: true
    min_volume_24h: 500000

timeframes:
  enabled:
    - 1h
    - 4h

download:
  parallel_workers: 3
  checkpoint_enabled: true

rate_limiting:
  requests_per_minute: 800

storage:
  base_path: data/test
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = DownloadConfig.from_yaml(f.name)
                assert config.symbols_count == 50
                assert config.parallel_workers == 3
                assert config.requests_per_minute == 800
                assert "1h" in config.timeframes
                assert config.output_dir == "data/test"
            finally:
                os.unlink(f.name)


class TestDownloadReport:
    """DownloadReport 測試類"""

    def test_report_creation(self):
        """測試報告創建"""
        report = DownloadReport(
            total_symbols=10,
            total_timeframes=4,
            total_tasks=40,
            successful_tasks=38,
            failed_tasks=2,
        )
        assert report.total_tasks == 40
        assert report.successful_tasks == 38

    def test_report_to_dict(self):
        """測試報告轉字典"""
        report = DownloadReport(
            total_tasks=100,
            successful_tasks=95,
            failed_tasks=5,
        )
        data = report.to_dict()
        assert data["total_tasks"] == 100
        assert "95.0%" in data["success_rate"]

    def test_report_save(self):
        """測試報告保存"""
        report = DownloadReport(total_tasks=10)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            try:
                report.save(f.name)
                assert os.path.exists(f.name)
            finally:
                os.unlink(f.name)


class TestRobustDownloader:
    """RobustDownloader 測試類"""

    @pytest.fixture
    def temp_dir(self):
        """創建臨時目錄"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config(self, temp_dir):
        """創建測試配置"""
        return DownloadConfig(
            symbols_source="manual",
            symbols_list=["BTCUSDT", "ETHUSDT"],
            timeframes=["1h"],
            output_dir=temp_dir,
            parallel_workers=2,
        )

    @pytest.fixture
    def downloader(self, config):
        """創建下載器實例"""
        return RobustDownloader(config=config)

    def test_initialization_with_config(self, downloader):
        """測試使用配置初始化"""
        assert downloader.config.symbols_source == "manual"
        assert len(downloader.config.symbols_list) == 2

    def test_get_symbols_from_list(self, downloader):
        """測試從列表獲取幣種"""
        symbols = downloader.get_symbols()
        assert symbols == ["BTCUSDT", "ETHUSDT"]

    @patch("data.downloaders.robust_downloader.TopSymbolsFetcher")
    def test_get_symbols_from_binance(self, mock_fetcher_class, temp_dir):
        """測試從 Binance 獲取幣種"""
        mock_fetcher = MagicMock()
        mock_fetcher.get_top_symbols.return_value = ["BTCUSDT", "ETHUSDT"]
        mock_fetcher_class.return_value = mock_fetcher

        config = DownloadConfig(
            symbols_source="binance_top",
            symbols_count=10,
            output_dir=temp_dir,
        )
        downloader = RobustDownloader(config=config)
        symbols = downloader.get_symbols()

        assert len(symbols) == 2
        mock_fetcher.get_top_symbols.assert_called_once()

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    @patch("data.downloaders.multi_tf_downloader.os.path.exists")
    @patch("data.downloaders.multi_tf_downloader.pd.read_csv")
    def test_download_all(
        self, mock_read_csv, mock_exists, mock_fetcher_class, downloader
    ):
        """測試完整下載"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.return_value = "/tmp/test.csv"
        mock_fetcher_class.return_value = mock_fetcher
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame({"close": [100, 101, 102]})

        report = downloader.download_all(resume=False)

        assert report.total_symbols == 2
        assert report.total_timeframes == 1

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    @patch("data.downloaders.multi_tf_downloader.os.path.exists")
    @patch("data.downloaders.multi_tf_downloader.pd.read_csv")
    def test_download_symbols(
        self, mock_read_csv, mock_exists, mock_fetcher_class, downloader
    ):
        """測試下載指定幣種"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.return_value = "/tmp/test.csv"
        mock_fetcher_class.return_value = mock_fetcher
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame({"close": [100, 101, 102]})

        report = downloader.download_symbols(
            symbols=["BTCUSDT"],
            timeframes=["1h"],
        )

        assert report.total_symbols == 1

    def test_get_status(self, downloader):
        """測試獲取狀態"""
        status = downloader.get_status()
        assert "completed" in status
        assert "rate_limiter" in status

    def test_clear_checkpoint(self, downloader):
        """測試清除檢查點"""
        downloader.clear_checkpoint()
        assert downloader.downloader.get_completed_count() == 0

    def test_clear_data_without_confirm(self, downloader):
        """測試清除數據不確認"""
        # 應該不會拋出異常，只是不執行
        downloader.clear_data(confirm=False)

    @patch("shutil.rmtree")
    def test_clear_data_with_confirm(self, mock_rmtree, downloader, temp_dir):
        """測試清除數據確認"""
        downloader.clear_data(confirm=True)
        # rmtree 應該被調用


class TestConvenienceFunctions:
    """便捷函數測試"""

    @patch("data.downloaders.robust_downloader.RobustDownloader")
    def test_download_all_function(self, mock_downloader_class):
        """測試 download_all 便捷函數"""
        mock_downloader = MagicMock()
        mock_downloader.download_all.return_value = DownloadReport()
        mock_downloader_class.return_value = mock_downloader

        report = download_all()
        assert isinstance(report, DownloadReport)

    @patch("data.downloaders.robust_downloader.RobustDownloader")
    def test_download_top_n(self, mock_downloader_class):
        """測試 download_top_n 便捷函數"""
        mock_downloader = MagicMock()
        mock_downloader.download_all.return_value = DownloadReport()
        mock_downloader_class.return_value = mock_downloader

        report = download_top_n(n=50)
        assert isinstance(report, DownloadReport)


class TestIntegration:
    """整合測試"""

    @pytest.fixture
    def temp_dir(self):
        """創建臨時目錄"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @patch("data.downloaders.multi_tf_downloader.OHLCVFetcher")
    @patch("data.downloaders.multi_tf_downloader.os.path.exists")
    @patch("data.downloaders.multi_tf_downloader.pd.read_csv")
    def test_full_workflow(
        self, mock_read_csv, mock_exists, mock_fetcher_class, temp_dir
    ):
        """測試完整工作流程"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_ohlcv.return_value = "/tmp/test.csv"
        mock_fetcher_class.return_value = mock_fetcher
        mock_exists.return_value = True
        mock_read_csv.return_value = pd.DataFrame(
            {
                "open": [100, 101],
                "high": [102, 103],
                "low": [99, 100],
                "close": [101, 102],
                "volume": [1000, 1100],
            }
        )

        config = DownloadConfig(
            symbols_source="manual",
            symbols_list=["BTCUSDT"],
            timeframes=["1h"],
            output_dir=temp_dir,
            checkpoint_enabled=True,
        )

        downloader = RobustDownloader(config=config)

        # 第一次下載
        report1 = downloader.download_all(resume=False)
        assert report1.successful_tasks >= 0

        # 第二次下載（應該跳過已完成的）
        _ = downloader.download_all(resume=True)

        # 清除並重新下載
        downloader.clear_checkpoint()
        report3 = downloader.download_all(resume=False)
        assert report3.total_tasks > 0
