"""
BiGe 7x 多幣種實盤運行器 v1.0

同時監控 Top 10 幣種，獨立判斷進出場

功能:
- 同時監控多個交易對
- 每個幣種獨立策略狀態
- 資金平均分配
- Telegram 通知（警犬風格）

使用方式:
    python -m live.multi_runner

Version: v1.0
"""

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

from config.production_phase1 import PHASE1_CONFIG  # noqa: E402
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
        logging.FileHandler("live_multi_trading.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# Top 5 幣種（$300 分 5 個，每幣 $60，效率較好）
TOP_5_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
]

# Top 10 幣種（備用，等本金滾大再用）
TOP_10_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "LINKUSDT",
]


@dataclass
class SymbolState:
    """單一幣種的策略狀態"""

    symbol: str
    position_direction: Optional[str] = None  # "long", "short", None
    entry_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    stop_loss: Optional[float] = None
    add_count: int = 0
    below_stop_count: int = 0
    last_bar_time: Optional[pd.Timestamp] = None
    data_cache: Optional[pd.DataFrame] = None
    current_bar: int = 0  # 當前 K 線編號（用於加倉間隔計算）
    entry_bar: int = 0  # 開倉時的 K 線編號
    last_add_bar: int = 0  # 最後一次加倉的 K 線編號


class MultiSymbolRunner:
    """多幣種實盤運行器"""

    def __init__(
        self,
        symbols: List[str] = None,
        timeframe: str = "4h",
        config: Optional[dict] = None,
    ):
        """
        初始化運行器

        Args:
            symbols: 交易對列表（默認 Top 10）
            timeframe: K 線週期
            config: 策略配置
        """
        self.symbols = symbols or TOP_5_SYMBOLS
        self.timeframe = timeframe
        self.config = config or PHASE1_CONFIG

        # 初始化 Broker 和通知器
        self.broker = BinanceFuturesBroker()
        self.notifier = SuperDogNotifier()

        # 每個幣種的狀態
        self.states: Dict[str, SymbolState] = {
            symbol: SymbolState(symbol=symbol) for symbol in self.symbols
        }

        # 全局統計
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.total_pnl: float = 0.0
        self.start_time: Optional[datetime] = None
        self.start_equity: Optional[float] = None

        # 日報追蹤
        self.daily_start_equity: Optional[float] = None
        self.daily_trades: int = 0
        self.daily_wins: int = 0
        self.last_daily_report_date: Optional[datetime] = None

    def initialize(self) -> bool:
        """初始化：測試連線、設定槓桿"""
        logger.info("=" * 60)
        logger.info("BiGe 7x 多幣種實盤交易系統 v1.0")
        logger.info(f"監控幣種: {len(self.symbols)} 個")
        logger.info("=" * 60)

        # 測試 API 連線
        logger.info("測試 API 連線...")
        if not self.broker.test_connection():
            logger.error("API 連線失敗！")
            self.notifier.send_alert("SYSTEM_ERROR", "API 連線失敗！無法啟動。")
            return False
        logger.info("API 連線成功")

        # 設定每個幣種的槓桿
        leverage = self.config["leverage"]
        for symbol in self.symbols:
            logger.info(f"設定 {symbol} 槓桿為 {leverage}x...")
            self.broker.set_leverage(symbol, leverage)
            self.broker.set_margin_type(symbol, "ISOLATED")

        # 取得帳戶餘額
        balance = self.broker.get_account_balance()
        logger.info(f"帳戶餘額: {balance['total']:.2f} USDT")

        # 計算每個幣種的資金分配
        per_symbol_equity = balance["total"] / len(self.symbols)
        logger.info(f"每幣分配: {per_symbol_equity:.2f} USDT")

        # 記錄啟動狀態
        self.start_time = datetime.now()
        self.start_equity = balance["total"]
        self.daily_start_equity = balance["total"]

        # 檢查現有持倉並恢復狀態
        recovered_positions = []
        for symbol in self.symbols:
            position = self.broker.get_position(symbol)
            if position:
                logger.info(f"  {symbol}: {position.side} {position.qty} @ {position.entry_price}")
                state = self.states[symbol]
                state.position_direction = position.side.lower()
                state.entry_price = position.entry_price
                state.entry_time = datetime.now()

                # 恢復止損位
                try:
                    df = self.fetch_klines(symbol)
                    if df is not None and len(df) >= 60:
                        row = df.iloc[-1]
                        avg20 = row["avg20"]
                        if not pd.isna(avg20):
                            if state.position_direction == "long":
                                state.stop_loss = avg20 * (1 - self.config["ma20_buffer"])
                            else:
                                state.stop_loss = avg20 * (1 + self.config["ma20_buffer"])
                            logger.info(f"    止損位恢復: {state.stop_loss:.2f}")
                except Exception as e:
                    logger.error(f"    止損位恢復失敗: {e}")

                # 加倉次數設為最大值（保守處理）
                state.add_count = self.config["max_add_count"]
                recovered_positions.append(f"{symbol}: {position.side}")

        # 發送恢復通知
        if recovered_positions:
            self.notifier.send_alert(
                "POSITIONS_RECOVERED",
                f"檢測到 {len(recovered_positions)} 個現有持倉\n"
                + "\n".join([f"├ {p}" for p in recovered_positions]),
            )

        logger.info("=" * 60)
        logger.info("初始化完成！")

        # 發送啟動通知
        symbols_text = ", ".join([s.replace("USDT", "") for s in self.symbols])
        config_summary = (
            f"├ 幣種：{symbols_text}\n"
            f"├ 每幣資金：${per_symbol_equity:.2f}\n"
            f"├ 槓桿：{leverage}x\n"
            f"├ 最大加倉：{self.config['max_add_count']} 次\n"
            f"└ 止損模式：MA20 追蹤"
        )
        self.notifier.send_startup(
            equity=balance["total"],
            leverage=leverage,
            symbol=f"{len(self.symbols)} 幣種",
            config_summary=config_summary,
        )

        return True

    def fetch_klines(self, symbol: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """獲取指定幣種的 K 線數據"""
        try:
            klines = self.broker.get_klines(symbol, self.timeframe, limit)
            if not klines:
                return None

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

            return df
        except Exception as e:
            logger.error(f"獲取 {symbol} K 線失敗: {e}")
            return None

    def check_entry_signal(self, row: pd.Series) -> Optional[str]:
        """檢查進場信號"""
        p = self.config
        close = row["close"]
        low = row["low"]
        high = row["high"]
        avg20 = row["avg20"]
        avg60 = row["avg60"]

        if pd.isna(avg20) or pd.isna(avg60):
            return None

        is_uptrend = avg20 > avg60
        is_downtrend = avg20 < avg60

        # 多單進場
        if is_uptrend:
            near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            not_break = low > avg20 * (1 - p["ma20_buffer"])
            bullish_close = close > avg20
            if near_ma20 and not_break and bullish_close:
                return "long"

        # 空單進場
        if is_downtrend:
            near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            not_break = high < avg20 * (1 + p["ma20_buffer"])
            bearish_close = close < avg20
            if near_ma20 and not_break and bearish_close:
                return "short"

        return None

    def check_emergency_stop(self, state: SymbolState, row: pd.Series) -> bool:
        """
        檢查緊急止損（黑天鵝保護）

        當單根 K 線跌破/突破 MA20 超過 N 倍 ATR 時，立即止損
        """
        if state.position_direction is None:
            return False

        p = self.config
        emergency_atr = p.get("emergency_stop_atr", 3.5)

        if emergency_atr <= 0:
            return False

        atr = row.get("atr")
        avg20 = row.get("avg20")

        if pd.isna(atr) or pd.isna(avg20) or atr <= 0:
            return False

        if state.position_direction == "long":
            low = row["low"]
            breach = avg20 - low
            if breach > 0 and breach > emergency_atr * atr:
                logger.warning(f"[{state.symbol}] 觸發緊急止損！跌破 MA20 達 {breach/atr:.1f} 倍 ATR")
                return True

        elif state.position_direction == "short":
            high = row["high"]
            breach = high - avg20
            if breach > 0 and breach > emergency_atr * atr:
                logger.warning(f"[{state.symbol}] 觸發緊急止損！突破 MA20 達 {breach/atr:.1f} 倍 ATR")
                return True

        return False

    def check_exit_signal(self, state: SymbolState, row: pd.Series) -> bool:
        """檢查出場信號"""
        # 優先檢查緊急止損
        if self.check_emergency_stop(state, row):
            return True

        if state.stop_loss is None:
            return False

        p = self.config
        confirm_bars = p.get("stop_loss_confirm_bars", 10)

        if state.position_direction == "long":
            if row["low"] <= state.stop_loss:
                state.below_stop_count += 1
                if state.below_stop_count >= confirm_bars:
                    return True
            else:
                state.below_stop_count = 0

        elif state.position_direction == "short":
            if row["high"] >= state.stop_loss:
                state.below_stop_count += 1
                if state.below_stop_count >= confirm_bars:
                    return True
            else:
                state.below_stop_count = 0

        return False

    def check_add_position_signal(self, state: SymbolState, row: pd.Series) -> bool:
        """檢查加倉信號"""
        p = self.config

        if state.position_direction is None:
            return False

        if state.add_count >= p["max_add_count"]:
            return False

        # 檢查加倉間隔（與回測一致）
        min_interval = p.get("add_position_min_interval", 3)
        bars_since_last = state.current_bar - max(state.entry_bar, state.last_add_bar)
        if bars_since_last < min_interval:
            return False

        close = row["close"]
        low = row["low"]
        high = row["high"]
        avg20 = row["avg20"]

        if state.position_direction == "long":
            near_ma20 = abs(low - avg20) / avg20 < p["pullback_tolerance"]
            above_stop = state.stop_loss is not None and low > state.stop_loss
            bullish_close = close > avg20
            return near_ma20 and above_stop and bullish_close

        elif state.position_direction == "short":
            near_ma20 = abs(high - avg20) / avg20 < p["pullback_tolerance"]
            below_stop = state.stop_loss is not None and high < state.stop_loss
            bearish_close = close < avg20
            return near_ma20 and below_stop and bearish_close

        return False

    def calculate_position_qty(self, symbol: str, price: float) -> float:
        """計算倉位數量（按幣種平均分配）"""
        p = self.config
        balance = self.broker.get_account_balance()

        # 每個幣種分配的權益
        per_symbol_equity = balance["available"] / len(self.symbols)

        # 保證金 = 分配權益 * 倉位比例
        margin = per_symbol_equity * p["position_size_pct"]

        # 倉位價值 = 保證金 * 槓桿
        position_value = margin * p["leverage"]

        # 數量 = 倉位價值 / 價格
        qty = position_value / price

        # 取得精度
        precision = self.broker.get_symbol_precision(symbol)
        qty = round(qty, precision["qty"])

        return qty

    def execute_entry(self, symbol: str, direction: str, row: pd.Series) -> bool:
        """執行進場"""
        state = self.states[symbol]
        p = self.config
        price = row["close"]
        avg20 = row["avg20"]

        qty = self.calculate_position_qty(symbol, price)

        if qty <= 0:
            logger.warning(f"[{symbol}] 計算倉位數量為 0，跳過")
            return False

        logger.info(f"[{symbol}] 嘗試 {direction.upper()} 進場: {qty} @ {price}")

        if direction == "long":
            result = self.broker.market_buy(symbol, qty)
            if result:
                state.stop_loss = avg20 * (1 - p["ma20_buffer"])
        else:
            result = self.broker.market_sell(symbol, qty)
            if result:
                state.stop_loss = avg20 * (1 + p["ma20_buffer"])

        if result:
            state.position_direction = direction
            state.entry_price = result.avg_price
            state.entry_time = datetime.now()
            state.add_count = 0
            state.below_stop_count = 0
            state.entry_bar = state.current_bar
            state.last_add_bar = state.current_bar

            logger.info(f"[{symbol}] 進場成功: {direction.upper()} {qty} @ {result.avg_price}")

            # 發送通知
            balance = self.broker.get_account_balance()
            self.notifier.send_entry(
                direction=direction.upper(),
                symbol=symbol,
                qty=qty,
                price=result.avg_price,
                leverage=p["leverage"],
                stop_loss=state.stop_loss,
                equity=balance["total"],
            )
            return True
        else:
            logger.error(f"[{symbol}] 進場失敗！")
            return False

    def execute_exit(self, symbol: str, reason: str = "止損") -> bool:
        """執行出場"""
        state = self.states[symbol]

        exit_direction = state.position_direction
        exit_entry_price = state.entry_price
        position = self.broker.get_position(symbol)
        exit_qty = position.qty if position else 0

        result = self.broker.close_position(symbol)

        if result:
            logger.info(f"[{symbol}] 平倉成功: {result.avg_price}")

            pnl_pct = 0
            pnl_amount = 0
            if exit_entry_price:
                if exit_direction == "long":
                    pnl_pct = (result.avg_price - exit_entry_price) / exit_entry_price
                else:
                    pnl_pct = (exit_entry_price - result.avg_price) / exit_entry_price

                pnl_amount = exit_qty * exit_entry_price * pnl_pct

                self.total_trades += 1
                self.daily_trades += 1
                if pnl_pct > 0:
                    self.winning_trades += 1
                    self.daily_wins += 1
                self.total_pnl += pnl_pct

            # 發送通知
            self.notifier.send_exit(
                direction=exit_direction.upper() if exit_direction else "UNKNOWN",
                symbol=symbol,
                qty=exit_qty,
                entry_price=exit_entry_price or 0,
                exit_price=result.avg_price,
                pnl=pnl_amount,
                pnl_pct=pnl_pct * 100,
                reason=reason,
            )

            # 重置狀態
            state.position_direction = None
            state.entry_price = None
            state.entry_time = None
            state.stop_loss = None
            state.add_count = 0
            state.below_stop_count = 0

            return True
        else:
            logger.error(f"[{symbol}] 平倉失敗！")
            self.notifier.send_alert("TRADE_ERROR", f"{symbol} 平倉失敗！請檢查！")
            return False

    def execute_add_position(self, symbol: str, row: pd.Series) -> bool:
        """執行加倉"""
        state = self.states[symbol]
        p = self.config
        price = row["close"]

        position = self.broker.get_position(symbol)
        if not position:
            return False

        add_qty = position.qty * 0.5
        precision = self.broker.get_symbol_precision(symbol)
        add_qty = round(add_qty, precision["qty"])

        if add_qty <= 0:
            return False

        logger.info(f"[{symbol}] 嘗試加倉: {add_qty} @ {price}")

        if state.position_direction == "long":
            result = self.broker.market_buy(symbol, add_qty)
        else:
            result = self.broker.market_sell(symbol, add_qty)

        if result:
            state.add_count += 1
            state.last_add_bar = state.current_bar
            logger.info(f"[{symbol}] 加倉成功: 第 {state.add_count} 次")

            updated_position = self.broker.get_position(symbol)
            total_qty = updated_position.qty if updated_position else add_qty
            avg_price = updated_position.entry_price if updated_position else price

            self.notifier.send_add_position(
                direction=state.position_direction.upper()
                if state.position_direction
                else "UNKNOWN",
                symbol=symbol,
                add_qty=add_qty,
                price=price,
                add_count=state.add_count,
                max_add=p["max_add_count"],
                total_qty=total_qty,
                avg_price=avg_price,
            )
            return True
        else:
            logger.error(f"[{symbol}] 加倉失敗！")
            return False

    def update_trailing_stop(self, state: SymbolState, row: pd.Series):
        """更新追蹤止損"""
        if state.stop_loss is None or state.position_direction is None:
            return

        p = self.config
        avg20 = row["avg20"]

        if pd.isna(avg20):
            return

        if state.position_direction == "long":
            new_stop = avg20 * (1 - p["ma20_buffer"])
            if new_stop > state.stop_loss:
                state.stop_loss = new_stop

        elif state.position_direction == "short":
            new_stop = avg20 * (1 + p["ma20_buffer"])
            if new_stop < state.stop_loss:
                state.stop_loss = new_stop

    def process_symbol(self, symbol: str):
        """處理單一幣種"""
        state = self.states[symbol]

        # 獲取數據
        df = self.fetch_klines(symbol)
        if df is None or len(df) < 60:
            return

        row = df.iloc[-2]  # 使用已完成的 K 線
        bar_time = row.name

        # 檢查是否是新 K 線
        if state.last_bar_time is not None and bar_time <= state.last_bar_time:
            return

        state.last_bar_time = bar_time
        state.current_bar += 1  # 遞增 K 線計數器
        state.data_cache = df

        # 有持倉
        if state.position_direction is not None:
            self.update_trailing_stop(state, row)

            if self.check_exit_signal(state, row):
                logger.info(f"[{symbol}] 觸發止損！")
                self.execute_exit(symbol, "止損")
                return

            if self.check_add_position_signal(state, row):
                logger.info(f"[{symbol}] 觸發加倉！")
                self.execute_add_position(symbol, row)

        # 無持倉
        else:
            signal = self.check_entry_signal(row)
            if signal:
                logger.info(f"[{symbol}] 觸發 {signal.upper()} 進場！")
                self.execute_entry(symbol, signal, row)

    def print_status(self):
        """打印狀態摘要"""
        balance = self.broker.get_account_balance()

        logger.info("=" * 50)
        logger.info("多幣種狀態摘要")
        logger.info("=" * 50)
        logger.info(f"帳戶權益: {balance['total']:.2f} USDT")
        logger.info(f"未實現盈虧: {balance['unrealized_pnl']:.2f} USDT")

        # 顯示各幣種持倉
        positions_count = 0
        for symbol in self.symbols:
            position = self.broker.get_position(symbol)
            if position:
                positions_count += 1
                state = self.states[symbol]
                logger.info(
                    f"  {symbol}: {position.side} {position.qty} @ {position.entry_price:.2f} "
                    f"(加倉 {state.add_count}/{self.config['max_add_count']})"
                )

        if positions_count == 0:
            logger.info("  無持倉")

        if self.total_trades > 0:
            win_rate = self.winning_trades / self.total_trades * 100
            logger.info(f"交易統計: {self.total_trades} 筆, 勝率 {win_rate:.1f}%")

        logger.info("=" * 50)

    def check_and_send_daily_report(self):
        """發送日報"""
        now = datetime.now()

        if self.last_daily_report_date and self.last_daily_report_date.date() == now.date():
            return

        if now.hour != 8:
            return

        balance = self.broker.get_account_balance()
        equity = balance["total"]

        equity_change = 0
        equity_change_pct = 0
        if self.daily_start_equity and self.daily_start_equity > 0:
            equity_change = equity - self.daily_start_equity
            equity_change_pct = (equity_change / self.daily_start_equity) * 100

        # 統計持倉
        positions = []
        for symbol in self.symbols:
            position = self.broker.get_position(symbol)
            if position:
                positions.append(f"{symbol.replace('USDT', '')}: {position.side}")

        position_info = ", ".join(positions) if positions else "空倉"

        uptime_hours = 0
        if self.start_time:
            uptime_hours = (now - self.start_time).total_seconds() / 3600

        self.notifier.send_daily_report(
            equity=equity,
            equity_change=equity_change,
            equity_change_pct=equity_change_pct,
            trades_today=self.daily_trades,
            wins_today=self.daily_wins,
            position_info=position_info,
            uptime_hours=uptime_hours,
        )

        self.last_daily_report_date = now
        self.daily_start_equity = equity
        self.daily_trades = 0
        self.daily_wins = 0

    def send_heartbeat_if_needed(self):
        """發送心跳"""
        balance = self.broker.get_account_balance()
        btc_price = self.broker.get_current_price("BTCUSDT")

        # 統計持倉和盈虧
        position_symbols = []
        positions_pnl = []
        total_unrealized_pnl = 0.0

        for symbol in self.symbols:
            position = self.broker.get_position(symbol)
            if position:
                position_symbols.append(f"{symbol.replace('USDT', '')}")

                # 計算盈虧百分比
                current_price = self.broker.get_current_price(symbol)
                if position.entry_price > 0 and current_price > 0:
                    if position.side.lower() == "long":
                        pnl_pct = (
                            (current_price - position.entry_price) / position.entry_price * 100
                        )
                    else:
                        pnl_pct = (
                            (position.entry_price - current_price) / position.entry_price * 100
                        )

                    # 計算未實現盈虧金額
                    unrealized_pnl = (
                        position.unrealized_pnl if hasattr(position, "unrealized_pnl") else 0
                    )

                    positions_pnl.append(
                        {
                            "symbol": symbol,
                            "direction": position.side.upper()[:1],  # L 或 S
                            "pnl_pct": pnl_pct,
                        }
                    )
                    total_unrealized_pnl += unrealized_pnl

        position_info = f"持倉: {', '.join(position_symbols)}" if position_symbols else "空倉待命中"

        uptime_hours = None
        if self.start_time:
            uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600

        self.notifier.send_heartbeat(
            equity=balance["total"],
            price=btc_price,
            position_info=position_info,
            uptime_hours=uptime_hours,
            positions_pnl=positions_pnl if positions_pnl else None,
            total_unrealized_pnl=balance.get("unrealized_pnl", 0) if positions_pnl else None,
        )

    def run(self, interval_seconds: int = 60):
        """運行主循環"""
        if not self.initialize():
            logger.error("初始化失敗，退出")
            return

        logger.info(f"開始運行，每 {interval_seconds} 秒檢查一次...")
        logger.info(f"監控幣種: {', '.join(self.symbols)}")

        last_status_time = time.time()
        status_interval = 3600
        consecutive_errors = 0
        max_consecutive_errors = 5

        try:
            while True:
                try:
                    # 處理每個幣種
                    for symbol in self.symbols:
                        try:
                            self.process_symbol(symbol)
                        except Exception as e:
                            logger.error(f"[{symbol}] 處理錯誤: {e}")

                    # 定期打印狀態 + 發送心跳
                    current_time = time.time()
                    if current_time - last_status_time >= status_interval:
                        self.print_status()
                        self.send_heartbeat_if_needed()
                        last_status_time = current_time

                    # 檢查日報
                    self.check_and_send_daily_report()

                    consecutive_errors = 0

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"處理錯誤: {e}", exc_info=True)

                    if consecutive_errors >= max_consecutive_errors:
                        self.notifier.send_alert(
                            "SYSTEM_ERROR",
                            f"連續發生 {consecutive_errors} 次錯誤！",
                            str(e),
                        )
                        consecutive_errors = 0

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("收到停止信號，退出...")
            self.print_status()

            balance = self.broker.get_account_balance()
            self.notifier.send_shutdown(
                reason="手動停止 (Ctrl+C)",
                equity=balance["total"],
                total_trades=self.total_trades,
                total_pnl=self.total_pnl * 100,
            )


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="BiGe 7x 多幣種實盤交易系統")
    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        default=TOP_5_SYMBOLS,
        help="交易對列表",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="4h",
        help="K 線週期",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="檢查間隔（秒）",
    )

    args = parser.parse_args()

    runner = MultiSymbolRunner(
        symbols=args.symbols,
        timeframe=args.timeframe,
        config=PHASE1_CONFIG,
    )

    runner.run(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
