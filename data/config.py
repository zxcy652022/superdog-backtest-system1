"""
Data Config - 數據路徑配置

兼容層：將舊的 data_config 整合到 data.paths

Version: v0.7
"""

from pathlib import Path

from .paths import get_data_root, get_ohlcv_path, get_raw_data_dir, is_ssd_available


class DataConfig:
    """數據路徑配置管理器（兼容舊 API）"""

    def __init__(self, ssd_name: str = "權志龍的寶藏"):
        self.ssd_name = ssd_name

    @property
    def base_path(self) -> Path:
        """獲取數據基礎路徑"""
        return get_data_root()

    @property
    def ssd_path(self) -> Path:
        """獲取 SSD 路徑"""
        return get_data_root()

    @property
    def data_path(self) -> Path:
        """獲取數據路徑"""
        return get_data_root()

    @property
    def data_root(self) -> Path:
        """獲取數據根目錄（兼容 OHLCVStorage）"""
        return get_data_root()

    @property
    def raw_data_dir(self) -> Path:
        """獲取原始數據目錄"""
        return get_raw_data_dir()

    def is_ssd_available(self) -> bool:
        """檢查 SSD 是否可用"""
        return is_ssd_available()


# 全局配置實例（兼容舊代碼）
config = DataConfig()
