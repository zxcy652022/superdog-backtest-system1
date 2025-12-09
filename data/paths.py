"""
SuperDog 數據路徑配置

統一管理所有數據存儲路徑，支援 SSD 外接硬碟

環境變數:
- DATA_ROOT: 數據根目錄 (默認: /Volumes/權志龍的寶藏/SuperDogData)

Version: v0.7
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# 核心路徑配置
# ============================================================

# SSD 路徑 (從環境變數讀取，支援 .env 文件)
DEFAULT_SSD_PATH = "/Volumes/權志龍的寶藏/SuperDogData"
DATA_ROOT = os.getenv("DATA_ROOT", DEFAULT_SSD_PATH)

# 本地 fallback 路徑 (當 SSD 未連接時)
LOCAL_FALLBACK = "data/raw"


def get_data_root() -> Path:
    """
    獲取數據根目錄

    優先順序:
    1. 環境變數 DATA_ROOT
    2. SSD 路徑 (如果存在)
    3. 本地 fallback

    Returns:
        Path: 數據根目錄路徑
    """
    # 優先使用環境變數
    env_path = os.getenv("DATA_ROOT")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        else:
            logger.warning(f"DATA_ROOT 路徑不存在: {env_path}")

    # 檢查默認 SSD 路徑
    ssd_path = Path(DEFAULT_SSD_PATH)
    if ssd_path.exists():
        return ssd_path

    # Fallback 到本地
    logger.warning(f"SSD 未連接，使用本地路徑: {LOCAL_FALLBACK}")
    local_path = Path(LOCAL_FALLBACK)
    local_path.mkdir(parents=True, exist_ok=True)
    return local_path


def get_raw_data_dir(exchange: str = "binance") -> Path:
    """
    獲取原始數據目錄

    Args:
        exchange: 交易所名稱

    Returns:
        Path: 原始數據目錄 (e.g., /Volumes/.../raw/binance)
    """
    path = get_data_root() / "raw" / exchange
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_historical_dir(exchange: str = "binance") -> Path:
    """
    獲取歷史數據目錄

    Args:
        exchange: 交易所名稱

    Returns:
        Path: 歷史數據目錄
    """
    path = get_data_root() / "historical" / exchange
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_experiments_dir() -> Path:
    """
    獲取實驗結果目錄

    Returns:
        Path: 實驗目錄
    """
    path = get_data_root() / "experiments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_universe_dir() -> Path:
    """
    獲取幣種宇宙數據目錄

    Returns:
        Path: 幣種宇宙目錄
    """
    path = get_data_root() / "universe"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_ohlcv_path(
    symbol: str, timeframe: str, exchange: str = "binance", create_dir: bool = True
) -> Path:
    """
    獲取 OHLCV 數據文件路徑

    Args:
        symbol: 交易對 (e.g., BTCUSDT)
        timeframe: 時間週期 (e.g., 1h)
        exchange: 交易所名稱
        create_dir: 是否自動創建目錄

    Returns:
        Path: CSV 文件路徑 (e.g., /Volumes/.../raw/binance/1h/BTCUSDT_1h.csv)
    """
    base_dir = get_raw_data_dir(exchange) / timeframe
    if create_dir:
        base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{symbol}_{timeframe}.csv"


def is_ssd_available() -> bool:
    """
    檢查 SSD 是否可用

    Returns:
        bool: SSD 是否已連接並可用
    """
    ssd_path = Path(DEFAULT_SSD_PATH)
    return ssd_path.exists() and ssd_path.is_dir()


def get_storage_info() -> dict:
    """
    獲取存儲信息

    Returns:
        dict: 存儲配置信息
    """
    data_root = get_data_root()
    return {
        "data_root": str(data_root),
        "ssd_available": is_ssd_available(),
        "ssd_path": DEFAULT_SSD_PATH,
        "env_data_root": os.getenv("DATA_ROOT"),
        "using_ssd": str(data_root).startswith("/Volumes/"),
        "raw_dir": str(get_raw_data_dir()),
        "experiments_dir": str(get_experiments_dir()),
    }


# ============================================================
# 初始化檢查
# ============================================================


def _init_check():
    """啟動時檢查存儲配置"""
    info = get_storage_info()
    if info["using_ssd"]:
        logger.info(f"✅ 使用 SSD 存儲: {info['data_root']}")
    else:
        logger.warning(f"⚠️ 使用本地存儲: {info['data_root']} (SSD 未連接)")


# 模組載入時執行檢查
_init_check()
