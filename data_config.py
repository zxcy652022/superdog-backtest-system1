"""
Data Path Configuration for SuperDog Backtest

管理數據存儲路徑，支援主專案與SSD分離
"""

import os
import platform
from pathlib import Path
from typing import Dict

import pandas as pd


class DataConfig:
    """數據路徑配置管理器"""

    def __init__(self, ssd_name: str = "權志龍的寶藏"):
        self.ssd_name = ssd_name
        self._base_paths = self._detect_paths()

    def _detect_paths(self) -> Dict[str, Path]:
        """自動偵測系統路徑"""
        system = platform.system()

        if system == "Darwin":  # macOS
            ssd_path = Path(f"/Volumes/{self.ssd_name}/SuperDogData")
        elif system == "Windows":
            # 掃描可能的磁碟代號
            for drive in "DEFGHIJK":
                potential_path = Path(f"{drive}:/SuperDogData")
                if potential_path.parent.exists():
                    ssd_path = potential_path
                    break
            else:
                ssd_path = Path("D:/SuperDogData")  # 預設D槽
        else:  # Linux
            ssd_path = Path(f"/media/{os.getuser()}/{self.ssd_name}/SuperDogData")

        # 檢查SSD是否可用
        ssd_volume = Path(f"/Volumes/{self.ssd_name}")
        if not ssd_volume.exists():
            ssd_path = Path.cwd() / "local_data"
            print(f"⚠️  SSD「{self.ssd_name}」未偵測到，使用本地路徑: {ssd_path}")
        elif not ssd_path.exists():
            # SSD存在但SuperDogData資料夾不存在，將會在setup時創建
            pass

        return {"project": Path.cwd(), "ssd": ssd_path, "data": ssd_path}

    @property
    def project_root(self) -> Path:
        """專案根目錄"""
        return self._base_paths["project"]

    @property
    def data_root(self) -> Path:
        """數據根目錄（SSD）"""
        return self._base_paths["data"]

    @property
    def historical_data(self) -> Path:
        """歷史數據目錄"""
        return self.data_root / "historical"

    @property
    def backtest_results(self) -> Path:
        """回測結果目錄"""
        return self.data_root / "backtest_results"

    @property
    def cache_dir(self) -> Path:
        """緩存目錄"""
        return self.data_root / "cache"

    @property
    def models_dir(self) -> Path:
        """模型目錄"""
        return self.data_root / "models"

    @property
    def exports_dir(self) -> Path:
        """導出目錄"""
        return self.data_root / "exports"

    def setup_directories(self):
        """創建必要的目錄結構"""
        dirs_to_create = [
            self.data_root,
            self.historical_data,
            self.backtest_results,
            self.cache_dir,
            self.models_dir,
            self.exports_dir,
            self.historical_data / "binance",
            self.historical_data / "bybit",
            self.historical_data / "coinbase",
            self.backtest_results / "single_runs",
            self.backtest_results / "portfolio_runs",
        ]

        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)

        print(f"✅ 數據目錄結構已創建: {self.data_root}")

    def get_data_file_path(self, symbol: str, timeframe: str, exchange: str = "binance") -> Path:
        """獲取數據文件路徑"""
        return self.historical_data / exchange / f"{symbol}_{timeframe}.csv"

    def get_backtest_result_path(self, strategy: str, symbol: str, timeframe: str) -> Path:
        """獲取回測結果路徑"""
        filename = (
            f"{strategy}_{symbol}_{timeframe}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        )
        return self.backtest_results / "single_runs" / filename

    def get_portfolio_result_path(self, portfolio_name: str) -> Path:
        """獲取批量回測結果路徑"""
        filename = f"portfolio_{portfolio_name}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        return self.backtest_results / "portfolio_runs" / filename

    def is_ssd_available(self) -> bool:
        """檢查SSD是否可用"""
        return self._base_paths["ssd"].parent.exists()

    def get_status(self) -> Dict[str, any]:
        """獲取配置狀態"""
        return {
            "ssd_available": self.is_ssd_available(),
            "ssd_name": self.ssd_name,
            "project_root": str(self.project_root),
            "data_root": str(self.data_root),
            "ssd_free_space": self._get_free_space(self.data_root)
            if self.is_ssd_available()
            else None,
        }

    def _get_free_space(self, path: Path) -> str:
        """獲取磁碟可用空間"""
        try:
            import shutil

            total, used, free = shutil.disk_usage(path)
            return f"{free // (2**30)} GB"
        except Exception:
            return "Unknown"


# 全局配置實例
config = DataConfig()


# 便捷函數
def setup_data_environment():
    """初始化數據環境"""
    config.setup_directories()
    status = config.get_status()

    print("🚀 SuperDog 數據環境配置")
    print("=" * 40)
    print(f"SSD 狀態: {'✅ 可用' if status['ssd_available'] else '❌ 不可用'}")
    print(f"SSD 名稱: {status['ssd_name']}")
    print(f"專案目錄: {status['project_root']}")
    print(f"數據目錄: {status['data_root']}")
    if status["ssd_free_space"]:
        print(f"可用空間: {status['ssd_free_space']}")
    print("=" * 40)

    return config


if __name__ == "__main__":
    # 測試配置
    setup_data_environment()
