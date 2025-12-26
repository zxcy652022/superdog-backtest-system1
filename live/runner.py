"""
BiGe 7x 實盤運行器 v1.0

實盤策略運行腳本 - 連接幣安永續合約

功能:
- 定時獲取 K 線數據
- 執行策略信號
- 自動下單
- 狀態監控與日誌

使用方式:
    python -m live.runner

Version: v1.0
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from config.production_phase1 import PHASE1_CONFIG, STOP_CONDITIONS
from live.binance_broker import BinanceFuturesBroker

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("live_trading.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class LiveStrategyRunner:
    """實盤策略運行器"""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        config: Optional[dict] = None,
    ):
        """
        初始化運行器

        Args:
            symbol: 交易對
            timeframe: K 線週期
            config: 策略配置（默認使用 PHASE1_CONFIG）
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.config = config or PHASE1_CONFIG

        # 初始化 Broker
        self.broker = BinanceFuturesBroker()

        # 策略狀態
        self.position_direction: Optional[str] = None  # "long", "short", None
        self.entry_price: Optional[float] = None
        self.entry_time: Optional[datetime] = None
        self.stop_loss: Optional[float] = None
        self.add_count: int = 0
        self.below_stop_count: int = 0  # 止損確認計數

        # 監控狀態
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.total_pnl: float = 0.0
        self.start_time: Optional[datetime] = None
        self.start_equity: Optional[float] = None

        # 數據緩存
        self.data_cache: Optional[pd.DataFrame] = None
        self.last_bar_time: Optional[int] = None

    def initialize(self) -> bool:
        """
        初始化：測試連線、設定槓桿和保證金模式

        Returns:
            是否成功初始化
        """
        logger.info("=" * 60)
        logger.info("BiGe 7x 實盤交易系統 v1.0")
        logger.info("=" * 60)

        # 測試 API 連線
        logger.info("測試 API 連線...")
        if not self.broker.test_connection():
            logger.error("API 連線失敗！")
            return False
        logger.info("API 連線成功")

        # 設定槓桿
        leverage = self.config["leverage"]
        logger.info(f"設定 {self.symbol} 槓桿為 {leverage}x...")
        if not self.broker.set_leverage(self.symbol, leverage):
            logger.error("設定槓桿失敗！")
            return False

        # 設定保證金模式（逐倉）
        logger.info(f"設定 {self.symbol} 為逐倉模式...")
        if not self.broker.set_margin_type(self.symbol, "ISOLATED"):
            logger.warning("設定保證金模式失敗，可能已經是逐倉模式")

        # 取得帳戶餘額
        balance = self.broker.get_account_balance()
        logger.info(f"帳戶餘額: {balance['total']:.2f} USDT (可用: {balance['available']:.2f})")

        # 記錄啟動狀態
        self.start_time = datetime.now()
        self.start_equity = balance["total"]

        # 檢查是否有現有持倉
        position = self.broker.get_position(self.symbol)
        if position:
            logger.info(f"檢測到現有持倉: {position.side} {position.qty} @ {position.entry_price}")
            self.position_direction = position.side.lower()
            self.entry_price = position.entry_price
            # TODO: 恢復其他狀態

        logger.info("初始化完成！")
        logger.info(f"交易對: {self.symbol}")
        logger.info(f"週期: {self.timeframe}")
        logger.info(f"槓桿: {leverage}x")
        logger.info(f"倉位大小: {self.config['position_size_pct'] * 100:.0f}%")
        logger.info(f"最大加倉次數: {self.config['max_add_count']}")
        logger.info("=" * 60)

        return True

    def fetch_klines(self, limit: int = 200) -> pd.DataFrame:
        """
        獲取最新 K 線數據

        Args:
            limit: 獲取數量

        Returns:
            K 線 DataFrame
        """
        klines = self.broker.get_klines(self.symbol, self.timeframe, limit)

        df = pd.DataFrame(klines)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # 計算指標
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma60"] = df["close"].rolling(60).mean()
        df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema60"] = df["close"].ewm(span=60, adjust=False).mean()
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2

        # ATR
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.rolling(14).mean()

        self.data_cache = df
        return df

    def check_entry_signal(self, row: pd.Series) -> Optional[str]:
        """
        檢查進場信號

        Args:
            row: 最新 K 線

        Returns:
            "long", "short", 或 None
        """
        p = self.config
        close = row["close"]
        low = row["low"]
        high = row["high"]
        avg20 = row["avg20"]
        avg60 = row["avg60"]

        if pd.isna(avg20) or pd.isna(avg60):
            return None

        # 趨勢判斷（loose 模式）
        is_uptrend = avg20 > avg60
        is_downtrend = avg20 < avg60

        # 多單進場：回踩 MA20
        if is_uptrend:
            near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            not_break = low > avg20 * (1 - p["ma20_buffer"])
            bullish_close = close > avg20

            if near_ma20 and not_break and bullish_close:
                return "long"

        # 空單進場：反彈 MA20
        if is_downtrend:
            near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            not_break = high < avg20 * (1 + p["ma20_buffer"])
            bearish_close = close < avg20

            if near_ma20 and not_break and bearish_close:
                return "short"

        return None

    def check_exit_signal(self, row: pd.Series) -> bool:
        """
        檢查出場信號（止損）

        Args:
            row: 最新 K 線

        Returns:
            是否應該出場
        """
        if self.stop_loss is None:
            return False

        p = self.config
        confirm_bars = p.get("stop_loss_confirm_bars", 10)

        if self.position_direction == "long":
            if row["low"] <= self.stop_loss:
                self.below_stop_count += 1
                if self.below_stop_count >= confirm_bars:
                    return True
            else:
                self.below_stop_count = 0

        elif self.position_direction == "short":
            if row["high"] >= self.stop_loss:
                self.below_stop_count += 1
                if self.below_stop_count >= confirm_bars:
                    return True
            else:
                self.below_stop_count = 0

        return False

    def check_add_position_signal(self, row: pd.Series) -> bool:
        """
        檢查加倉信號

        Args:
            row: 最新 K 線

        Returns:
            是否應該加倉
        """
        p = self.config

        if self.position_direction is None:
            return False

        if self.add_count >= p["max_add_count"]:
            return False

        close = row["close"]
        low = row["low"]
        high = row["high"]
        avg20 = row["avg20"]

        if self.position_direction == "long":
            near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            above_stop = self.stop_loss is not None and low > self.stop_loss
            bullish_close = close > avg20
            return near_ma20 and above_stop and bullish_close

        elif self.position_direction == "short":
            near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            below_stop = self.stop_loss is not None and high < self.stop_loss
            bearish_close = close < avg20
            return near_ma20 and below_stop and bearish_close

        return False

    def calculate_position_qty(self, price: float) -> float:
        """
        計算倉位數量

        Args:
            price: 入場價格

        Returns:
            倉位數量
        """
        p = self.config
        balance = self.broker.get_account_balance()
        equity = balance["available"]

        # 保證金 = 權益 * 倉位比例
        margin = equity * p["position_size_pct"]

        # 倉位價值 = 保證金 * 槓桿
        position_value = margin * p["leverage"]

        # 數量 = 倉位價值 / 價格
        qty = position_value / price

        # 取得精度
        precision = self.broker.get_symbol_precision(self.symbol)
        qty = round(qty, precision["qty"])

        return qty

    def execute_entry(self, direction: str, row: pd.Series) -> bool:
        """
        執行進場

        Args:
            direction: "long" 或 "short"
            row: 最新 K 線

        Returns:
            是否成功
        """
        p = self.config
        price = row["close"]
        avg20 = row["avg20"]

        qty = self.calculate_position_qty(price)

        if qty <= 0:
            logger.warning(f"計算倉位數量為 0，跳過進場")
            return False

        logger.info(f"嘗試 {direction.upper()} 進場: {qty} @ {price}")

        if direction == "long":
            result = self.broker.market_buy(self.symbol, qty)
            if result:
                self.stop_loss = avg20 * (1 - p["ma20_buffer"])
        else:
            result = self.broker.market_sell(self.symbol, qty)
            if result:
                self.stop_loss = avg20 * (1 + p["ma20_buffer"])

        if result:
            self.position_direction = direction
            self.entry_price = result.avg_price
            self.entry_time = datetime.now()
            self.add_count = 0
            self.below_stop_count = 0

            logger.info(f"進場成功: {direction.upper()} {qty} @ {result.avg_price}")
            logger.info(f"止損位: {self.stop_loss:.2f}")
            return True
        else:
            logger.error("進場失敗！")
            return False

    def execute_exit(self) -> bool:
        """
        執行出場（平倉）

        Returns:
            是否成功
        """
        result = self.broker.close_position(self.symbol)

        if result:
            logger.info(f"平倉成功: {result.avg_price}")

            # 計算盈虧
            if self.entry_price:
                if self.position_direction == "long":
                    pnl_pct = (result.avg_price - self.entry_price) / self.entry_price
                else:
                    pnl_pct = (self.entry_price - result.avg_price) / self.entry_price

                logger.info(f"本單盈虧: {pnl_pct * 100:.2f}%")

                self.total_trades += 1
                if pnl_pct > 0:
                    self.winning_trades += 1
                self.total_pnl += pnl_pct

            # 重置狀態
            self.position_direction = None
            self.entry_price = None
            self.entry_time = None
            self.stop_loss = None
            self.add_count = 0
            self.below_stop_count = 0

            return True
        else:
            logger.error("平倉失敗！")
            return False

    def execute_add_position(self, row: pd.Series) -> bool:
        """
        執行加倉

        Args:
            row: 最新 K 線

        Returns:
            是否成功
        """
        p = self.config
        price = row["close"]

        # 加倉數量 = 初始倉位 * 50%
        position = self.broker.get_position(self.symbol)
        if not position:
            return False

        add_qty = position.qty * 0.5  # fixed_50 模式

        # 取得精度
        precision = self.broker.get_symbol_precision(self.symbol)
        add_qty = round(add_qty, precision["qty"])

        if add_qty <= 0:
            return False

        logger.info(f"嘗試加倉: {add_qty} @ {price}")

        if self.position_direction == "long":
            result = self.broker.market_buy(self.symbol, add_qty)
        else:
            result = self.broker.market_sell(self.symbol, add_qty)

        if result:
            self.add_count += 1
            logger.info(f"加倉成功: 第 {self.add_count} 次加倉")
            return True
        else:
            logger.error("加倉失敗！")
            return False

    def update_trailing_stop(self, row: pd.Series):
        """更新追蹤止損"""
        if self.stop_loss is None or self.position_direction is None:
            return

        p = self.config
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return

        if self.position_direction == "long":
            new_stop = avg20 * (1 - p["ma20_buffer"])
            if new_stop > self.stop_loss:
                self.stop_loss = new_stop
                logger.info(f"止損上移至: {self.stop_loss:.2f}")

        elif self.position_direction == "short":
            new_stop = avg20 * (1 + p["ma20_buffer"])
            if new_stop < self.stop_loss:
                self.stop_loss = new_stop
                logger.info(f"止損下移至: {self.stop_loss:.2f}")

    def process_bar(self):
        """
        處理最新 K 線
        """
        # 獲取數據
        df = self.fetch_klines()
        if df is None or len(df) < 60:
            logger.warning("數據不足，跳過")
            return

        row = df.iloc[-2]  # 使用倒數第二根（已完成的 K 線）
        bar_time = row.name

        # 檢查是否是新 K 線
        if self.last_bar_time is not None and bar_time <= self.last_bar_time:
            return

        self.last_bar_time = bar_time
        logger.info(f"處理 K 線: {bar_time}")
        logger.info(
            f"  價格: O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f}"
        )
        logger.info(f"  MA20={row['avg20']:.2f} MA60={row['avg60']:.2f}")

        # 有持倉
        if self.position_direction is not None:
            # 更新追蹤止損
            self.update_trailing_stop(row)

            # 檢查出場
            if self.check_exit_signal(row):
                logger.info("觸發止損信號！")
                self.execute_exit()
                return

            # 檢查加倉
            if self.check_add_position_signal(row):
                logger.info("觸發加倉信號！")
                self.execute_add_position(row)

        # 無持倉
        else:
            # 檢查進場
            signal = self.check_entry_signal(row)
            if signal:
                logger.info(f"觸發 {signal.upper()} 進場信號！")
                self.execute_entry(signal, row)

    def print_status(self):
        """打印狀態摘要"""
        balance = self.broker.get_account_balance()
        position = self.broker.get_position(self.symbol)
        price = self.broker.get_current_price(self.symbol)

        logger.info("=" * 40)
        logger.info("狀態摘要")
        logger.info("=" * 40)
        logger.info(f"當前價格: ${price:,.2f}")
        logger.info(f"帳戶餘額: {balance['total']:.2f} USDT")
        logger.info(f"未實現盈虧: {balance['unrealized_pnl']:.2f} USDT")

        if position:
            logger.info(f"持倉: {position.side} {position.qty} @ {position.entry_price}")
            logger.info(f"浮動盈虧: {position.unrealized_pnl:.2f} USDT")
            if self.stop_loss:
                logger.info(f"止損位: {self.stop_loss:.2f}")
            logger.info(f"加倉次數: {self.add_count}/{self.config['max_add_count']}")
        else:
            logger.info("持倉: 無")

        if self.total_trades > 0:
            win_rate = self.winning_trades / self.total_trades * 100
            logger.info(f"交易統計: {self.total_trades} 筆, 勝率 {win_rate:.1f}%")

        logger.info("=" * 40)

    def run(self, interval_seconds: int = 60):
        """
        運行主循環

        Args:
            interval_seconds: 檢查間隔（秒）
        """
        if not self.initialize():
            logger.error("初始化失敗，退出")
            return

        logger.info(f"開始運行，每 {interval_seconds} 秒檢查一次...")

        last_status_time = time.time()
        status_interval = 3600  # 每小時打印一次狀態

        try:
            while True:
                try:
                    # 處理 K 線
                    self.process_bar()

                    # 定期打印狀態
                    current_time = time.time()
                    if current_time - last_status_time >= status_interval:
                        self.print_status()
                        last_status_time = current_time

                except Exception as e:
                    logger.error(f"處理錯誤: {e}", exc_info=True)

                # 等待下一次檢查
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("收到停止信號，退出...")
            self.print_status()


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="BiGe 7x 實盤交易系統")
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="交易對（如 BTCUSDT, ETHUSDT）",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="4h",
        help="K 線週期（如 4h, 1h）",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="檢查間隔（秒）",
    )

    args = parser.parse_args()

    # 創建運行器
    runner = LiveStrategyRunner(
        symbol=args.symbol,
        timeframe=args.timeframe,
        config=PHASE1_CONFIG,
    )

    # 運行
    runner.run(interval_seconds=args.interval)


# === Top 主流幣列表（未來動態獲取）===
TOP_SYMBOLS = [
    "BTCUSDT",  # BTC - 必選
    "ETHUSDT",  # ETH - 必選
    # Phase 2 加入
    # "BNBUSDT",
    # "SOLUSDT",
    # "XRPUSDT",
    # "ADAUSDT",
    # "DOGEUSDT",
    # "AVAXUSDT",
    # "DOTUSDT",
    # "LINKUSDT",
]


if __name__ == "__main__":
    main()
