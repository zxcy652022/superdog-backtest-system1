"""
BiGe 7x 實盤運行器 v1.1

實盤策略運行腳本 - 連接幣安永續合約

功能:
- 定時獲取 K 線數據
- 執行策略信號
- 自動下單
- 狀態監控與日誌
- Telegram 通知（警犬風格）

使用方式:
    python -m live.runner

Version: v1.1 - 新增 Telegram 通知
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

from dotenv import load_dotenv  # noqa: E402

from config.production_phase1 import PHASE1_CONFIG, STOP_CONDITIONS  # noqa: E402
from live.binance_broker import BinanceFuturesBroker  # noqa: E402
from live.notifier import SuperDogNotifier  # noqa: E402

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

        # 初始化通知器
        self.notifier = SuperDogNotifier()

        # 策略狀態
        self.position_direction: Optional[str] = None  # "long", "short", None
        self.entry_price: Optional[float] = None
        self.entry_time: Optional[datetime] = None
        self.stop_loss: Optional[float] = None
        self.add_count: int = 0
        self.below_stop_count: int = 0  # 止損確認計數
        self.current_bar: int = 0  # 當前 K 線編號（用於加倉間隔計算）
        self.entry_bar: int = 0  # 開倉時的 K 線編號
        self.last_add_bar: int = 0  # 最後一次加倉的 K 線編號

        # 監控狀態
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.total_pnl: float = 0.0
        self.start_time: Optional[datetime] = None
        self.start_equity: Optional[float] = None

        # 數據緩存
        self.data_cache: Optional[pd.DataFrame] = None
        self.last_bar_time: Optional[int] = None

        # 日報追蹤
        self.daily_start_equity: Optional[float] = None
        self.daily_trades: int = 0
        self.daily_wins: int = 0
        self.last_daily_report_date: Optional[datetime] = None

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

        # 檢查是否有現有持倉並恢復狀態
        position = self.broker.get_position(self.symbol)
        if position:
            logger.info(f"檢測到現有持倉: {position.side} {position.qty} @ {position.entry_price}")
            self.position_direction = position.side.lower()
            self.entry_price = position.entry_price
            self.entry_time = datetime.now()  # 近似值

            # 恢復止損位：需要先獲取 K 線數據計算 MA20
            try:
                df = self.fetch_klines()
                if df is not None and len(df) >= 60:
                    row = df.iloc[-1]
                    avg20 = row["avg20"]
                    if not pd.isna(avg20):
                        if self.position_direction == "long":
                            self.stop_loss = avg20 * (1 - self.config["ma20_buffer"])
                        else:
                            self.stop_loss = avg20 * (1 + self.config["ma20_buffer"])
                        logger.info(f"恢復止損位: {self.stop_loss:.2f}")
                    else:
                        logger.warning("無法計算 MA20，止損位未設置")
                else:
                    logger.warning("數據不足，止損位未設置")
            except Exception as e:
                logger.error(f"恢復止損位失敗: {e}")

            # 加倉次數無法精確恢復，設為保守值
            self.add_count = self.config["max_add_count"]  # 假設已用完，避免過度加倉
            logger.info(f"加倉次數設為最大值（保守處理）: {self.add_count}")

            # 發送恢復通知
            self.notifier.send_alert(
                "POSITION_RECOVERED",
                f"檢測到現有 {position.side} 持倉\n"
                f"├ 數量：{position.qty}\n"
                f"├ 進場價：${position.entry_price:,.2f}\n"
                f"├ 止損位：${self.stop_loss:,.2f}"
                if self.stop_loss
                else "├ 止損位：未設置（請注意！）",
            )

        logger.info("初始化完成！")
        logger.info(f"交易對: {self.symbol}")
        logger.info(f"週期: {self.timeframe}")
        logger.info(f"槓桿: {leverage}x")
        logger.info(f"倉位大小: {self.config['position_size_pct'] * 100:.0f}%")
        logger.info(f"最大加倉次數: {self.config['max_add_count']}")
        logger.info("=" * 60)

        # 記錄日報起始權益
        self.daily_start_equity = balance["total"]

        # 發送啟動通知
        config_summary = (
            f"├ 倉位大小：{self.config['position_size_pct'] * 100:.0f}%\n"
            f"├ 最大加倉：{self.config['max_add_count']} 次\n"
            f"└ 止損模式：MA20 追蹤"
        )
        self.notifier.send_startup(
            equity=balance["total"],
            leverage=leverage,
            symbol=self.symbol,
            config_summary=config_summary,
        )

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

    def check_emergency_stop(self, row: pd.Series) -> bool:
        """
        檢查緊急止損（黑天鵝保護）

        當單根 K 線跌破/突破 MA20 超過 N 倍 ATR 時，立即止損
        不等待確認根數，防止極端行情造成巨大損失

        Args:
            row: 最新 K 線

        Returns:
            是否觸發緊急止損
        """
        if self.position_direction is None:
            return False

        p = self.config
        emergency_atr = p.get("emergency_stop_atr", 3.5)  # 預設 3.5 倍 ATR

        if emergency_atr <= 0:
            return False

        atr = row.get("atr")
        avg20 = row.get("avg20")

        if pd.isna(atr) or pd.isna(avg20) or atr <= 0:
            return False

        if self.position_direction == "long":
            # 多單：檢查最低價跌破 MA20 的幅度
            low = row["low"]
            breach = avg20 - low  # 跌破幅度（正值表示跌破）
            if breach > 0 and breach > emergency_atr * atr:
                logger.warning(f"觸發緊急止損！跌破 MA20 達 {breach/atr:.1f} 倍 ATR")
                return True

        elif self.position_direction == "short":
            # 空單：檢查最高價突破 MA20 的幅度
            high = row["high"]
            breach = high - avg20  # 突破幅度（正值表示突破）
            if breach > 0 and breach > emergency_atr * atr:
                logger.warning(f"觸發緊急止損！突破 MA20 達 {breach/atr:.1f} 倍 ATR")
                return True

        return False

    def check_exit_signal(self, row: pd.Series) -> bool:
        """
        檢查出場信號（止損）

        Args:
            row: 最新 K 線

        Returns:
            是否應該出場
        """
        # 優先檢查緊急止損（黑天鵝保護）
        if self.check_emergency_stop(row):
            return True

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

        # 檢查加倉間隔（與回測一致）
        min_interval = p.get("add_position_min_interval", 3)
        bars_since_last = self.current_bar - max(self.entry_bar, self.last_add_bar)
        if bars_since_last < min_interval:
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
            self.entry_bar = self.current_bar
            self.last_add_bar = self.current_bar

            logger.info(f"進場成功: {direction.upper()} {qty} @ {result.avg_price}")
            logger.info(f"止損位: {self.stop_loss:.2f}")

            # 發送開倉通知
            balance = self.broker.get_account_balance()
            self.notifier.send_entry(
                direction=direction.upper(),
                symbol=self.symbol,
                qty=qty,
                price=result.avg_price,
                leverage=self.config["leverage"],
                stop_loss=self.stop_loss,
                equity=balance["total"],
            )
            return True
        else:
            logger.error("進場失敗！")
            self.notifier.send_alert("TRADE_ERROR", "開倉失敗！請檢查帳戶狀態。")
            return False

    def execute_exit(self, reason: str = "止損") -> bool:
        """
        執行出場（平倉）

        Args:
            reason: 平倉原因

        Returns:
            是否成功
        """
        # 記錄平倉前的資訊
        exit_direction = self.position_direction
        exit_entry_price = self.entry_price
        position = self.broker.get_position(self.symbol)
        exit_qty = position.qty if position else 0

        result = self.broker.close_position(self.symbol)

        if result:
            logger.info(f"平倉成功: {result.avg_price}")

            # 計算盈虧
            pnl_pct = 0
            pnl_amount = 0
            if exit_entry_price:
                if exit_direction == "long":
                    pnl_pct = (result.avg_price - exit_entry_price) / exit_entry_price
                else:
                    pnl_pct = (exit_entry_price - result.avg_price) / exit_entry_price

                # 計算實際盈虧金額
                pnl_amount = exit_qty * exit_entry_price * pnl_pct

                logger.info(f"本單盈虧: {pnl_pct * 100:.2f}%")

                self.total_trades += 1
                self.daily_trades += 1
                if pnl_pct > 0:
                    self.winning_trades += 1
                    self.daily_wins += 1
                self.total_pnl += pnl_pct

            # 發送平倉通知
            self.notifier.send_exit(
                direction=exit_direction.upper() if exit_direction else "UNKNOWN",
                symbol=self.symbol,
                qty=exit_qty,
                entry_price=exit_entry_price or 0,
                exit_price=result.avg_price,
                pnl=pnl_amount,
                pnl_pct=pnl_pct * 100,
                reason=reason,
            )

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
            self.notifier.send_alert("TRADE_ERROR", "平倉失敗！請立即檢查！")
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
            self.last_add_bar = self.current_bar
            logger.info(f"加倉成功: 第 {self.add_count} 次加倉")

            # 取得更新後的持倉資訊
            updated_position = self.broker.get_position(self.symbol)
            total_qty = updated_position.qty if updated_position else add_qty
            avg_price = updated_position.entry_price if updated_position else price

            # 發送加倉通知
            self.notifier.send_add_position(
                direction=self.position_direction.upper() if self.position_direction else "UNKNOWN",
                symbol=self.symbol,
                add_qty=add_qty,
                price=price,
                add_count=self.add_count,
                max_add=self.config["max_add_count"],
                total_qty=total_qty,
                avg_price=avg_price,
            )
            return True
        else:
            logger.error("加倉失敗！")
            self.notifier.send_alert("TRADE_ERROR", f"加倉失敗！第 {self.add_count + 1} 次加倉未能執行。")
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
        self.current_bar += 1  # 遞增 K 線計數器
        logger.info(f"處理 K 線: {bar_time} (bar #{self.current_bar})")
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

    def check_and_send_daily_report(self):
        """檢查並發送日報（每天早上 8 點）"""
        now = datetime.now()

        # 檢查是否已經發過今天的日報
        if self.last_daily_report_date and self.last_daily_report_date.date() == now.date():
            return

        # 只在早上 8 點到 9 點之間發送
        if now.hour != 8:
            return

        # 取得帳戶資訊
        balance = self.broker.get_account_balance()
        equity = balance["total"]

        # 計算權益變化
        equity_change = 0
        equity_change_pct = 0
        if self.daily_start_equity and self.daily_start_equity > 0:
            equity_change = equity - self.daily_start_equity
            equity_change_pct = (equity_change / self.daily_start_equity) * 100

        # 取得持倉資訊
        position = self.broker.get_position(self.symbol)
        position_info = None
        if position:
            position_info = f"{position.side} {position.qty} @ ${position.entry_price:,.2f}"

        # 計算運行時長
        uptime_hours = 0
        if self.start_time:
            uptime_hours = (now - self.start_time).total_seconds() / 3600

        # 發送日報
        self.notifier.send_daily_report(
            equity=equity,
            equity_change=equity_change,
            equity_change_pct=equity_change_pct,
            trades_today=self.daily_trades,
            wins_today=self.daily_wins,
            position_info=position_info,
            uptime_hours=uptime_hours,
        )

        # 更新狀態
        self.last_daily_report_date = now
        self.daily_start_equity = equity  # 重置日報起始權益
        self.daily_trades = 0
        self.daily_wins = 0

    def send_heartbeat_if_needed(self):
        """發送心跳通知（每小時一次）"""
        balance = self.broker.get_account_balance()
        price = self.broker.get_current_price(self.symbol)
        position = self.broker.get_position(self.symbol)

        position_info = None
        positions_pnl = None
        total_unrealized_pnl = None

        if position:
            position_info = f"{position.side} {position.qty} BTC @ ${position.entry_price:,.2f}"

            # 計算盈虧百分比
            if position.entry_price > 0 and price > 0:
                if position.side.lower() == "long":
                    pnl_pct = (price - position.entry_price) / position.entry_price * 100
                else:
                    pnl_pct = (position.entry_price - price) / position.entry_price * 100

                positions_pnl = [
                    {
                        "symbol": self.symbol,
                        "direction": position.side.upper()[:1],  # L 或 S
                        "pnl_pct": pnl_pct,
                    }
                ]
                total_unrealized_pnl = balance.get("unrealized_pnl", 0)

        uptime_hours = None
        if self.start_time:
            uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600

        self.notifier.send_heartbeat(
            equity=balance["total"],
            price=price,
            position_info=position_info,
            uptime_hours=uptime_hours,
            positions_pnl=positions_pnl,
            total_unrealized_pnl=total_unrealized_pnl,
        )

    def run(self, interval_seconds: int = 60):
        """
        運行主循環

        Args:
            interval_seconds: 檢查間隔（秒）
        """
        if not self.initialize():
            logger.error("初始化失敗，退出")
            self.notifier.send_alert("SYSTEM_ERROR", "系統初始化失敗！無法啟動交易。")
            return

        logger.info(f"開始運行，每 {interval_seconds} 秒檢查一次...")

        last_status_time = time.time()
        status_interval = 3600  # 每小時打印一次狀態
        consecutive_errors = 0
        max_consecutive_errors = 5

        try:
            while True:
                try:
                    # 處理 K 線
                    self.process_bar()

                    # 定期打印狀態 + 發送心跳
                    current_time = time.time()
                    if current_time - last_status_time >= status_interval:
                        self.print_status()
                        self.send_heartbeat_if_needed()
                        last_status_time = current_time

                    # 檢查日報
                    self.check_and_send_daily_report()

                    # 重置錯誤計數
                    consecutive_errors = 0

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"處理錯誤: {e}", exc_info=True)

                    # 連續錯誤過多，發送警報
                    if consecutive_errors >= max_consecutive_errors:
                        self.notifier.send_alert(
                            "SYSTEM_ERROR",
                            f"連續發生 {consecutive_errors} 次錯誤！\n系統可能不穩定，請檢查。",
                            str(e),
                        )
                        consecutive_errors = 0  # 重置，避免重複發送

                # 等待下一次檢查
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("收到停止信號，退出...")
            self.print_status()

            # 發送關閉通知
            balance = self.broker.get_account_balance()
            self.notifier.send_shutdown(
                reason="手動停止 (Ctrl+C)",
                equity=balance["total"],
                total_trades=self.total_trades,
                total_pnl=self.total_pnl * 100,  # 轉為百分比
            )


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
