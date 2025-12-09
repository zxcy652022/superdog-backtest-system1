"""
Universe Calculator v0.6

幣種屬性計算器 - 計算幣種的各種量化指標

核心功能:
- 成交額計算（30日、7日平均）
- 上市天數計算
- 持倉量指標（平均值、趨勢）
- 資產類型檢測（穩定幣、永續合約、DeFi等）
- 市值排名獲取

Version: v0.6 Phase 1
Design Reference: docs/specs/v0.6/superdog_v06_universe_manager_spec.md
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class VolumeMetrics:
    """成交額指標"""

    volume_30d_avg: float  # 30日平均成交額 (USD)
    volume_7d_avg: float  # 7日平均成交額 (USD)
    volume_30d_total: float  # 30日總成交額 (USD)
    volume_trend: float  # 成交量趨勢 (-1到1)
    volume_volatility: float  # 成交量波動率


@dataclass
class OIMetrics:
    """持倉量指標"""

    oi_avg_usd: float  # 平均持倉量 (USD)
    oi_trend: float  # 持倉量趨勢 (-1到1)
    oi_volatility: float  # 持倉量波動率
    oi_growth_rate: float  # 年化增長率


@dataclass
class AssetTypeInfo:
    """資產類型信息"""

    is_stablecoin: bool  # 是否穩定幣
    has_perpetual: bool  # 是否有永續合約
    is_defi: bool  # 是否DeFi代幣
    is_layer1: bool  # 是否Layer1公鏈
    is_meme: bool  # 是否Meme幣


class UniverseCalculator:
    """幣種屬性計算器

    負責計算幣種的各種量化指標，用於宇宙分類

    Example:
        >>> calc = UniverseCalculator()
        >>> vol_metrics = calc.calculate_volume_metrics('BTCUSDT', days=30)
        >>> print(f"30日平均成交額: ${vol_metrics.volume_30d_avg:,.0f}")
    """

    # 穩定幣列表
    STABLECOINS = ["USDT", "USDC", "BUSD", "DAI", "TUSD", "USDP", "USDD", "FRAX"]

    # DeFi代幣列表
    DEFI_TOKENS = [
        "UNI",
        "SUSHI",
        "AAVE",
        "COMP",
        "CRV",
        "YFI",
        "MKR",
        "1INCH",
        "SNX",
        "BAL",
        "ALPHA",
        "RUNE",
        "LUNA",
        "CAKE",
    ]

    # Layer1公鏈列表
    LAYER1_CHAINS = [
        "BTC",
        "ETH",
        "BNB",
        "SOL",
        "ADA",
        "AVAX",
        "DOT",
        "MATIC",
        "ATOM",
        "NEAR",
        "FTM",
        "ALGO",
        "ONE",
        "EGLD",
        "HBAR",
    ]

    # Meme幣列表
    MEME_COINS = ["DOGE", "SHIB", "PEPE", "FLOKI", "ELON", "BONK", "BABYDOGE"]

    def __init__(self, data_dir: Optional[str] = None):
        """初始化計算器

        Args:
            data_dir: 數據目錄路徑，默認為 'data/raw'
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "raw"
        self.data_dir = Path(data_dir)

    def calculate_volume_metrics(
        self, symbol: str, days: int = 30, ohlcv_data: Optional[pd.DataFrame] = None
    ) -> VolumeMetrics:
        """計算成交額相關指標

        Args:
            symbol: 交易對符號，例如 'BTCUSDT'
            days: 計算天數，默認30天
            ohlcv_data: 可選的OHLCV數據，如果為None則自動加載

        Returns:
            VolumeMetrics: 成交額指標對象

        Raises:
            FileNotFoundError: 當找不到數據文件時
            ValueError: 當數據不足時

        Example:
            >>> metrics = calc.calculate_volume_metrics('BTCUSDT', days=30)
            >>> print(f"30日平均: ${metrics.volume_30d_avg:,.0f}")
        """
        # 加載OHLCV數據
        if ohlcv_data is None:
            ohlcv_data = self._load_ohlcv(symbol, days)

        # 驗證數據長度
        if len(ohlcv_data) < 7:
            raise ValueError(f"數據不足: 只有 {len(ohlcv_data)} 天，至少需要 7 天")

        # 計算成交額 (成交量 * 收盤價 = USD成交額)
        volume_usd = ohlcv_data["volume"] * ohlcv_data["close"]

        # 計算各項指標
        volume_30d_avg = volume_usd.tail(min(30, len(volume_usd))).mean()
        volume_7d_avg = volume_usd.tail(min(7, len(volume_usd))).mean()
        volume_30d_total = volume_usd.tail(min(30, len(volume_usd))).sum()
        volume_trend = self._calculate_volume_trend(volume_usd)
        volume_volatility = (
            volume_usd.tail(min(30, len(volume_usd))).std()
            / volume_usd.tail(min(30, len(volume_usd))).mean()
            if volume_usd.tail(min(30, len(volume_usd))).mean() > 0
            else 0
        )

        return VolumeMetrics(
            volume_30d_avg=volume_30d_avg,
            volume_7d_avg=volume_7d_avg,
            volume_30d_total=volume_30d_total,
            volume_trend=volume_trend,
            volume_volatility=volume_volatility,
        )

    def calculate_history_days(self, symbol: str, ohlcv_data: Optional[pd.DataFrame] = None) -> int:
        """計算上市天數

        Args:
            symbol: 交易對符號
            ohlcv_data: 可選的OHLCV數據

        Returns:
            int: 上市天數

        Example:
            >>> days = calc.calculate_history_days('BTCUSDT')
            >>> print(f"上市天數: {days}")
        """
        # 加載數據
        if ohlcv_data is None:
            try:
                # 嘗試加載所有可用數據
                ohlcv_data = self._load_ohlcv(symbol, days=3650)  # 最多10年
            except Exception as e:
                logger.warning(f"加載 {symbol} 完整歷史數據失敗: {e}")
                return 0

        if len(ohlcv_data) == 0:
            return 0

        # 計算第一個數據點到現在的天數
        first_date = pd.to_datetime(ohlcv_data.index[0])
        current_date = pd.Timestamp.now(tz=first_date.tz)

        return (current_date - first_date).days

    def calculate_oi_metrics(self, symbol: str, days: int = 30) -> OIMetrics:
        """計算持倉量相關指標

        Args:
            symbol: 交易對符號
            days: 計算天數，默認30天

        Returns:
            OIMetrics: 持倉量指標對象

        Note:
            如果沒有永續合約數據，返回零值指標

        Example:
            >>> metrics = calc.calculate_oi_metrics('BTCUSDT', days=30)
            >>> print(f"平均持倉量: ${metrics.oi_avg_usd:,.0f}")
        """
        # 檢查是否有永續合約
        if not self._has_perpetual_data(symbol):
            return OIMetrics(oi_avg_usd=0, oi_trend=0, oi_volatility=0, oi_growth_rate=0)

        try:
            # 加載持倉量數據
            oi_data = self._load_open_interest(symbol, days)
            ohlcv_data = self._load_ohlcv(symbol, days)

            # 對齊數據
            aligned_data = self._align_data(oi_data, ohlcv_data)

            # 計算USD價值 (OI * 價格)
            oi_usd = aligned_data["open_interest"] * aligned_data["close"]

            # 計算各項指標
            oi_avg_usd = oi_usd.mean()
            oi_trend = self._calculate_oi_trend(oi_usd)
            oi_volatility = oi_usd.std() / oi_usd.mean() if oi_usd.mean() > 0 else 0

            # 計算年化增長率
            if len(oi_usd) >= 2:
                oi_growth_rate = (
                    (oi_usd.iloc[-1] / oi_usd.iloc[0] - 1) * 365 / days if oi_usd.iloc[0] > 0 else 0
                )
            else:
                oi_growth_rate = 0

            return OIMetrics(
                oi_avg_usd=oi_avg_usd,
                oi_trend=oi_trend,
                oi_volatility=oi_volatility,
                oi_growth_rate=oi_growth_rate,
            )

        except Exception as e:
            logger.warning(f"計算 {symbol} 持倉量指標失敗: {e}")
            return OIMetrics(0, 0, 0, 0)

    def detect_asset_type(self, symbol: str) -> AssetTypeInfo:
        """檢測資產類型

        Args:
            symbol: 交易對符號

        Returns:
            AssetTypeInfo: 資產類型信息

        Example:
            >>> info = calc.detect_asset_type('BTCUSDT')
            >>> if info.is_layer1:
            ...     print("這是Layer1公鏈")
        """
        # 從結尾移除報價幣種後綴（按長度排序以避免部分匹配問題）
        base_asset = symbol
        for quote in ["USDT", "USDC", "BUSD", "USD"]:
            if symbol.endswith(quote):
                base_asset = symbol[: -len(quote)]
                break

        # 檢測各種類型
        # 檢查 base_asset 是否是穩定幣，而不是檢查整個 symbol（避免把 BTCUSDT 誤判為穩定幣）
        is_stablecoin = base_asset in self.STABLECOINS
        is_defi = base_asset in self.DEFI_TOKENS
        is_layer1 = base_asset in self.LAYER1_CHAINS
        is_meme = base_asset in self.MEME_COINS
        has_perpetual = self._has_perpetual_data(symbol)

        return AssetTypeInfo(
            is_stablecoin=is_stablecoin,
            has_perpetual=has_perpetual,
            is_defi=is_defi,
            is_layer1=is_layer1,
            is_meme=is_meme,
        )

    def get_market_cap_rank(self, symbol: str) -> Optional[int]:
        """獲取市值排名

        Args:
            symbol: 交易對符號

        Returns:
            Optional[int]: 市值排名，如果無法獲取則返回None

        Note:
            目前使用預定義的排名，未來可以整合CoinGecko或CoinMarketCap API
        """
        # 預定義的市值排名（前50）
        market_cap_ranks = {
            "BTC": 1,
            "ETH": 2,
            "BNB": 3,
            "SOL": 4,
            "XRP": 5,
            "ADA": 6,
            "DOGE": 7,
            "AVAX": 8,
            "TRX": 9,
            "DOT": 10,
            "MATIC": 11,
            "LTC": 12,
            "LINK": 13,
            "UNI": 14,
            "ATOM": 15,
            "XLM": 16,
            "XMR": 17,
            "ALGO": 18,
            "VET": 19,
            "FIL": 20,
            "NEAR": 21,
            "HBAR": 22,
            "APT": 23,
            "ICP": 24,
            "AAVE": 25,
            "MKR": 26,
            "SNX": 27,
            "RUNE": 28,
            "EGLD": 29,
            "SAND": 30,
            "MANA": 31,
            "AXS": 32,
            "FTM": 33,
            "ONE": 34,
            "ROSE": 35,
            "GALA": 36,
            "ENJ": 37,
            "CHZ": 38,
            "THETA": 39,
            "ZIL": 40,
            "BAT": 41,
            "COMP": 42,
            "YFI": 43,
            "CRV": 44,
            "1INCH": 45,
            "SUSHI": 46,
            "CAKE": 47,
            "ALPHA": 48,
            "BAL": 49,
            "LUNA": 50,
        }

        base_asset = symbol.replace("USDT", "").replace("USD", "").replace("BUSD", "")
        return market_cap_ranks.get(base_asset)

    # ===== 私有輔助方法 =====

    def _load_ohlcv(self, symbol: str, days: int) -> pd.DataFrame:
        """加載OHLCV數據

        Args:
            symbol: 交易對符號
            days: 天數

        Returns:
            pd.DataFrame: OHLCV數據

        Raises:
            FileNotFoundError: 找不到數據文件
        """
        # 構建文件路徑 (假設1d時間週期)
        file_path = self.data_dir / f"{symbol}_1d.csv"

        if not file_path.exists():
            raise FileNotFoundError(f"找不到數據文件: {file_path}")

        # 加載數據
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)

        # 取最近N天
        return df.tail(days)

    def _load_open_interest(self, symbol: str, days: int) -> pd.DataFrame:
        """加載持倉量數據

        Args:
            symbol: 交易對符號
            days: 天數

        Returns:
            pd.DataFrame: 持倉量數據
        """
        # 嘗試從永續數據目錄加載
        try:
            from data.perpetual import fetch_open_interest

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            oi_data = fetch_open_interest(symbol, start_time, end_time, interval="1d")
            return oi_data

        except Exception as e:
            logger.debug(f"加載 {symbol} 持倉量數據失敗: {e}")
            raise

    def _has_perpetual_data(self, symbol: str) -> bool:
        """檢查是否有永續合約數據

        Args:
            symbol: 交易對符號

        Returns:
            bool: 是否有永續合約
        """
        try:
            # 嘗試加載少量資金費率數據作為檢測
            from data.perpetual import get_latest_funding_rate

            result = get_latest_funding_rate(symbol)
            return result is not None

        except Exception:
            return False

    def _align_data(self, oi_data: pd.DataFrame, ohlcv_data: pd.DataFrame) -> pd.DataFrame:
        """對齊持倉量和OHLCV數據

        Args:
            oi_data: 持倉量數據
            ohlcv_data: OHLCV數據

        Returns:
            pd.DataFrame: 對齊後的數據
        """
        # 將兩個數據集按時間對齊
        merged = pd.merge(
            oi_data[["open_interest"]],
            ohlcv_data[["close"]],
            left_index=True,
            right_index=True,
            how="inner",
        )

        return merged

    def _calculate_volume_trend(self, volume_series: pd.Series) -> float:
        """計算成交量趨勢

        Args:
            volume_series: 成交量序列

        Returns:
            float: 趨勢值 (-1到1)
        """
        if len(volume_series) < 7:
            return 0.0

        recent_avg = volume_series.tail(7).mean()
        historical_avg = volume_series.tail(min(30, len(volume_series))).mean()

        if historical_avg == 0:
            return 0.0

        trend = (recent_avg - historical_avg) / historical_avg
        return float(np.clip(trend, -1, 1))

    def _calculate_oi_trend(self, oi_series: pd.Series) -> float:
        """計算持倉量趨勢 (使用線性回歸)

        Args:
            oi_series: 持倉量序列

        Returns:
            float: 趨勢值 (-1到1)
        """
        if len(oi_series) < 2:
            return 0.0

        # 使用線性回歸計算斜率
        x = np.arange(len(oi_series))
        slope, _ = np.polyfit(x, oi_series.values, 1)

        # 標準化到-1到1範圍
        mean_oi = oi_series.mean()
        if mean_oi == 0:
            return 0.0

        normalized_slope = np.tanh(slope / mean_oi * 100)
        return float(normalized_slope)


# ===== 便捷函數 =====


def calculate_all_metrics(
    symbol: str, days: int = 30, calculator: Optional[UniverseCalculator] = None
) -> Dict:
    """計算幣種所有指標

    便捷函數，一次性計算所有指標

    Args:
        symbol: 交易對符號
        days: 計算天數
        calculator: 可選的計算器實例

    Returns:
        Dict: 包含所有指標的字典

    Example:
        >>> metrics = calculate_all_metrics('BTCUSDT', days=30)
        >>> print(metrics['volume_30d_avg'])
        >>> print(metrics['history_days'])
    """
    if calculator is None:
        calculator = UniverseCalculator()

    try:
        vol_metrics = calculator.calculate_volume_metrics(symbol, days)
        history_days = calculator.calculate_history_days(symbol)
        oi_metrics = calculator.calculate_oi_metrics(symbol, days)
        asset_type = calculator.detect_asset_type(symbol)
        market_cap_rank = calculator.get_market_cap_rank(symbol)

        return {
            "symbol": symbol,
            "volume_30d_avg": vol_metrics.volume_30d_avg,
            "volume_7d_avg": vol_metrics.volume_7d_avg,
            "volume_30d_total": vol_metrics.volume_30d_total,
            "volume_trend": vol_metrics.volume_trend,
            "volume_volatility": vol_metrics.volume_volatility,
            "history_days": history_days,
            "oi_avg_usd": oi_metrics.oi_avg_usd,
            "oi_trend": oi_metrics.oi_trend,
            "oi_volatility": oi_metrics.oi_volatility,
            "oi_growth_rate": oi_metrics.oi_growth_rate,
            "is_stablecoin": asset_type.is_stablecoin,
            "has_perpetual": asset_type.has_perpetual,
            "is_defi": asset_type.is_defi,
            "is_layer1": asset_type.is_layer1,
            "is_meme": asset_type.is_meme,
            "market_cap_rank": market_cap_rank,
            "last_updated": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"計算 {symbol} 指標失敗: {e}")
        return {"symbol": symbol, "error": str(e), "last_updated": datetime.now().isoformat()}
