"""
BiGe 幣哥雙均線策略 - 影子交易模式 (Shadow Trading)

策略版本: v2 (均線糾纏突破策略)
程式版本: 1.0.2

功能：
- 與 multi_runner.py 共享完全相同的交易架構
- 只有策略邏輯（進場/出場判斷）不同
- 不實際下單，只記錄訊號
- 用於驗證新策略 vs 舊策略的差異
- 完整模擬權益追蹤（等同實盤交易）

架構設計：
- 整個交易架構是一部車子，只是換一個駕駛員（策略）
- 共用：Broker、K線獲取、指標計算、錯誤處理、通知系統
- 不同：check_entry_signal(), check_exit_signal()

使用方式：
    python -m live.shadow_runner

輸出：
    - data/shadow_signals.json: 所有訊號記錄
    - data/shadow_equity.json: 模擬權益記錄
    - shadow_trading.log: 運行日誌

更新日誌:
- v1.0.0: 初始版本（從 multi_runner 架構衍生）
- v1.0.1: 新增 add_position_min_profit 檢查、狀態完整重置
- v1.0.2: 新增完整模擬權益追蹤（USDT 金額、持倉市值、權益曲線）
"""

import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from live.binance_broker import BinanceFuturesBroker
from live.notifier import SuperDogNotifier

load_dotenv()

# 設定日誌（與 multi_runner 相同格式）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("shadow_trading.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# 訊號記錄檔
SIGNALS_FILE = Path("data/shadow_signals.json")
EQUITY_FILE = Path("data/shadow_equity.json")


# =============================================================================
# 新策略配置（幣哥雙均線 v2 - 均線糾纏突破）
# =============================================================================

SHADOW_CONFIG = {
    # === 交易對（與 multi_runner 相同）===
    "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
    "timeframe": "4h",
    # === 槓桿設定（動態槓桿）===
    "leverage": 7,  # 基礎槓桿（用於初始化）
    "initial_leverage": 7,
    "leverage_ladder": "aggressive",  # 25x→20x→15x→10x→5x→3x→2x
    # === 倉位管理 ===
    "position_size_pct": 0.25,  # 25%
    # === 趨勢判斷（與 v1 相同的基礎結構）===
    "trend_mode": "strict",
    "trend_strength": 0.03,  # 3%
    "ma_fast": 20,
    "ma_slow": 60,
    "min_entry_interval": 6,
    # === 進場條件 - 均線糾纏突破（v2 特有）===
    "cluster_threshold": 0.05,  # 5% 糾纏閾值
    "min_cluster_bars": 8,  # 最少糾纏 8 根 K 線
    "min_vol_ratio": 2.0,  # 成交量放大 2 倍
    "breakout_body_pct": 1.5,  # 突破 K 線實體 > 1.5%
    "min_bars_above": 2,  # 站穩 2 根 K 線
    # === 做空條件（v2 特有）===
    "short_rsi_max": 40,  # RSI < 40
    "short_require_full_downtrend": True,  # 需要完整下跌趨勢
    # === 止損設定（與 v1 結構相同）===
    "stop_loss_confirm_bars": 10,
    "ma20_buffer": 0.02,
    "emergency_stop_atr": 3.5,
    "stop_loss_buffer": 0.7,  # 動態止損：爆倉距離的 70%
    # === 回踩加倉設定（與 v1 相同）===
    "pullback_tolerance": 0.018,
    "add_position_min_interval": 6,
    "add_position_min_profit": 0.03,
    # === 加倉（與 v1 結構相同）===
    "max_add_count": 3,
    "add_position_mode": "fixed_50",
    "min_bars_between_add": 4,
    "confirm_threshold": 0.002,
    # === 交易成本（與 v1 相同）===
    "fee_rate": 0.0004,
    "maintenance_margin_rate": 0.005,
    # === 風控參數（與 v1 相同）===
    "max_position_value_pct": 0.50,
    "daily_loss_limit_pct": 0.10,
}


# =============================================================================
# 資料結構
# =============================================================================


@dataclass
class Signal:
    """訊號記錄"""

    timestamp: str
    symbol: str
    direction: str  # "long", "short", "exit", "add"
    price: float
    reason: str
    indicators: Dict = field(default_factory=dict)


@dataclass
class ShadowEquitySnapshot:
    """權益快照（用於追蹤模擬權益曲線）"""

    timestamp: str
    equity: float  # 當前模擬權益（USDT）
    position_value: float  # 當前持倉市值
    unrealized_pnl: float  # 未實現盈虧
    realized_pnl: float  # 已實現盈虧（累計）
    trade_count: int  # 交易次數
    win_count: int  # 獲勝次數


@dataclass
class ShadowSymbolState:
    """
    單一幣種的影子策略狀態
    與 multi_runner.SymbolState 結構對齊，但增加 v2 策略特有的欄位
    """

    symbol: str
    position_direction: Optional[str] = None  # "long", "short", None
    entry_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    stop_loss: Optional[float] = None
    add_count: int = 0
    below_stop_count: int = 0
    last_bar_time: Optional[pd.Timestamp] = None
    data_cache: Optional[pd.DataFrame] = None
    current_bar: int = 0
    entry_bar: int = 0
    last_add_bar: int = 0

    # v2 策略特有欄位
    cluster_bars: int = 0  # 均線糾纏持續根數
    in_cluster: bool = False  # 是否在糾纏區間
    bars_above_ma20: int = 0  # 站穩 MA20 上方根數
    bars_below_ma20: int = 0  # 跌破 MA20 根數
    bars_below_ma: int = 0  # 持續跌破/突破 MA20 根數（用於出場）
    had_breakout_up: bool = False  # 曾經向上突破
    had_breakout_down: bool = False  # 曾經向下突破

    # 模擬持倉資訊（用於權益計算）
    simulated_qty: float = 0.0  # 模擬持倉數量
    simulated_notional: float = 0.0  # 模擬持倉名義價值（USDT）


# =============================================================================
# 影子交易運行器
# =============================================================================


class ShadowRunner:
    """
    影子交易運行器

    與 MultiSymbolRunner 共享：
    - Broker 連線
    - K 線獲取方式
    - 基礎指標計算（MA, EMA, ATR）
    - 錯誤處理層級
    - 通知系統（可選）
    - 主循環結構

    不同：
    - check_entry_signal() - 使用 v2 均線糾纏突破策略
    - check_exit_signal() - 使用 v2 出場邏輯
    - 不實際下單，只記錄訊號
    """

    def __init__(
        self,
        symbols: List[str] = None,
        timeframe: str = "4h",
        config: Optional[dict] = None,
        enable_notifications: bool = False,  # 預設關閉通知
    ):
        """
        初始化運行器

        Args:
            symbols: 交易對列表
            timeframe: K 線週期
            config: 策略配置
            enable_notifications: 是否啟用 Telegram 通知
        """
        self.config = config or SHADOW_CONFIG
        self.symbols = symbols or self.config["symbols"]
        self.timeframe = timeframe

        # === 與 multi_runner 相同的初始化 ===
        self.broker = BinanceFuturesBroker()
        self.notifier = SuperDogNotifier() if enable_notifications else None

        # 每個幣種的狀態（使用 v2 狀態結構）
        self.states: Dict[str, ShadowSymbolState] = {
            symbol: ShadowSymbolState(symbol=symbol) for symbol in self.symbols
        }

        # 全局統計
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.total_pnl: float = 0.0
        self.start_time: Optional[datetime] = None
        self.start_equity: Optional[float] = None

        # 日報追蹤（與 multi_runner 相同）
        self.daily_start_equity: Optional[float] = None
        self.daily_trades: int = 0
        self.daily_wins: int = 0
        self.last_daily_report_date: Optional[datetime] = None

        # === v2 特有：訊號記錄 ===
        self.signals: List[Signal] = []
        self.equity_multiple = 1.0  # 模擬權益倍數（用於動態槓桿）

        # === 模擬權益追蹤（等同實盤交易）===
        self.simulated_equity: float = 0.0  # 模擬權益（USDT）
        self.simulated_initial_equity: float = 0.0  # 初始模擬權益
        self.simulated_realized_pnl: float = 0.0  # 已實現盈虧累計
        self.equity_history: List[ShadowEquitySnapshot] = []  # 權益曲線

        self._load_signals()
        self._load_equity()

    # =========================================================================
    # 訊號記錄（v2 特有）
    # =========================================================================

    def _load_signals(self):
        """載入之前的訊號記錄"""
        if SIGNALS_FILE.exists():
            try:
                with open(SIGNALS_FILE, "r") as f:
                    data = json.load(f)
                    self.signals = [Signal(**s) for s in data]
                logger.info(f"載入 {len(self.signals)} 個歷史訊號")
            except Exception as e:
                logger.error(f"載入訊號失敗: {e}")

    def _save_signals(self):
        """儲存訊號記錄"""
        SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SIGNALS_FILE, "w") as f:
            json.dump([asdict(s) for s in self.signals], f, indent=2, default=str)

    def _load_equity(self):
        """載入之前的權益記錄"""
        if EQUITY_FILE.exists():
            try:
                with open(EQUITY_FILE, "r") as f:
                    data = json.load(f)
                    self.simulated_equity = data.get("simulated_equity", 0.0)
                    self.simulated_initial_equity = data.get("simulated_initial_equity", 0.0)
                    self.simulated_realized_pnl = data.get("simulated_realized_pnl", 0.0)
                    self.equity_multiple = data.get("equity_multiple", 1.0)
                    self.total_trades = data.get("total_trades", 0)
                    self.winning_trades = data.get("winning_trades", 0)
                    self.total_pnl = data.get("total_pnl", 0.0)
                    # 載入權益曲線
                    history_data = data.get("equity_history", [])
                    self.equity_history = [ShadowEquitySnapshot(**h) for h in history_data]
                logger.info(f"載入權益記錄: ${self.simulated_equity:,.2f} USDT")
            except Exception as e:
                logger.error(f"載入權益記錄失敗: {e}")

    def _save_equity(self):
        """儲存權益記錄"""
        EQUITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "simulated_equity": self.simulated_equity,
            "simulated_initial_equity": self.simulated_initial_equity,
            "simulated_realized_pnl": self.simulated_realized_pnl,
            "equity_multiple": self.equity_multiple,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "total_pnl": self.total_pnl,
            "equity_history": [asdict(h) for h in self.equity_history[-1000:]],  # 最多保留 1000 筆
            "last_updated": datetime.now().isoformat(),
        }
        with open(EQUITY_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _record_equity_snapshot(self):
        """記錄權益快照"""
        # 計算當前持倉市值和未實現盈虧
        total_position_value = 0.0
        total_unrealized_pnl = 0.0

        for symbol, state in self.states.items():
            if state.position_direction and state.entry_price and state.data_cache is not None:
                current_price = state.data_cache.iloc[-1]["close"]
                if state.position_direction == "long":
                    unrealized = (current_price - state.entry_price) / state.entry_price
                else:
                    unrealized = (state.entry_price - current_price) / state.entry_price

                # 計算持倉市值
                position_value = state.simulated_notional
                total_position_value += position_value
                total_unrealized_pnl += position_value * unrealized

        snapshot = ShadowEquitySnapshot(
            timestamp=datetime.now().isoformat(),
            equity=self.simulated_equity + total_unrealized_pnl,
            position_value=total_position_value,
            unrealized_pnl=total_unrealized_pnl,
            realized_pnl=self.simulated_realized_pnl,
            trade_count=self.total_trades,
            win_count=self.winning_trades,
        )
        self.equity_history.append(snapshot)
        self._save_equity()

    def _record_signal(
        self, symbol: str, direction: str, price: float, reason: str, indicators: dict = None
    ):
        """記錄訊號（不實際下單）"""
        signal = Signal(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            direction=direction,
            price=price,
            reason=reason,
            indicators=indicators or {},
        )
        self.signals.append(signal)
        self._save_signals()

        logger.info(f"[SHADOW] {symbol} {direction.upper()} @ {price:.2f} - {reason}")

        # 發送影子通知（如果啟用）
        if self.notifier:
            self._send_shadow_notification(symbol, direction, price, reason, indicators)

    def _send_shadow_notification(
        self, symbol: str, direction: str, price: float, reason: str, indicators: dict = None
    ):
        """發送影子交易專屬通知"""
        from datetime import timedelta, timezone

        now = datetime.now(timezone(timedelta(hours=8)))  # 台灣時間

        indicators = indicators or {}

        if direction == "long":
            emoji = "👻🟢"
            action = "做多訊號"
        elif direction == "short":
            emoji = "👻🔴"
            action = "做空訊號"
        elif direction == "exit":
            emoji = "👻⚪"
            action = "平倉訊號"
            pnl_pct = indicators.get("pnl_pct", 0)
            pnl_usdt = indicators.get("pnl_usdt", 0)
            notional = indicators.get("notional", 0)
            fees = indicators.get("fees", 0)
            pnl_emoji = "💰" if pnl_pct > 0 else "💸"

            # 計算累計收益率
            total_return = 0
            if self.simulated_initial_equity > 0:
                total_return = (self.simulated_equity / self.simulated_initial_equity - 1) * 100

            message = f"""
<b>{emoji} 影子交易 - {action}</b>

🔮 <b>這不是實際交易！</b>

📊 <b>訊號詳情</b>
├ 幣種：{symbol.replace("USDT", "")}
├ 平倉價：<code>${price:,.2f}</code>
├ 進場價：<code>${indicators.get("entry_price", 0):,.2f}</code>
├ 持倉：{indicators.get("hold_bars", 0)} 根 K 線
├ 名義價值：<code>${notional:,.2f}</code>
├ 手續費：<code>${fees:,.2f}</code>
└ 原因：{reason}

💰 <b>本次盈虧</b>
├ 百分比：{pnl_emoji} <code>{pnl_pct:+.1f}%</code>
└ 金額：{pnl_emoji} <code>${pnl_usdt:+,.2f}</code> USDT

📈 <b>模擬帳戶狀態</b>
├ 模擬權益：<code>${self.simulated_equity:,.2f}</code> USDT
├ 累計收益：<code>{total_return:+.2f}%</code>
├ 已實現盈虧：<code>${self.simulated_realized_pnl:+,.2f}</code>
├ 交易次數：{self.total_trades} 筆
└ 勝率：{(self.winning_trades/self.total_trades*100) if self.total_trades > 0 else 0:.1f}%

<i>👻 影子策略 v2 - 僅供觀察</i>
"""
            self.notifier._send_message(message.strip())
            return

        elif direction == "add":
            emoji = "👻➕"
            action = "加倉訊號"

            message = f"""
<b>{emoji} 影子交易 - {action}</b>

🔮 <b>這不是實際交易！</b>

📊 <b>訊號詳情</b>
├ 幣種：{symbol.replace("USDT", "")}
├ 價格：<code>${price:,.2f}</code>
└ 加倉：第 {indicators.get("add_count", 0)}/{indicators.get("max_add", 3)} 次

<i>👻 影子策略 v2 - 僅供觀察</i>
"""
            self.notifier._send_message(message.strip())
            return

        else:
            return  # 未知類型不發送

        # 進場訊號（long/short）
        leverage = indicators.get("leverage", 7)
        position_size_pct = self.config.get("position_size_pct", 0.25)
        simulated_notional = self.simulated_equity * position_size_pct * leverage

        # 計算累計收益率
        total_return = 0
        if self.simulated_initial_equity > 0:
            total_return = (self.simulated_equity / self.simulated_initial_equity - 1) * 100

        message = f"""
<b>{emoji} 影子交易 - {action}</b>

🔮 <b>這不是實際交易！</b>

📊 <b>訊號詳情</b>
├ 幣種：{symbol.replace("USDT", "")}
├ 方向：<b>{direction.upper()}</b>
├ 價格：<code>${price:,.2f}</code>
└ 原因：{reason}

📈 <b>指標數據</b>
├ 均線離散：{indicators.get("ma_spread", 0)*100:.2f}%
├ 成交量比：{indicators.get("vol_ratio", 0):.1f}x
├ RSI：{indicators.get("rsi", 0):.0f}
├ K線實體：{indicators.get("body_pct", 0):.2f}%
└ 槓桿：{leverage}x

💼 <b>模擬倉位</b>
├ 倉位比例：{position_size_pct*100:.0f}%
├ 名義價值：<code>${simulated_notional:,.2f}</code>
└ 保證金：<code>${simulated_notional/leverage:,.2f}</code>

📊 <b>模擬帳戶</b>
├ 模擬權益：<code>${self.simulated_equity:,.2f}</code> USDT
├ 累計收益：<code>{total_return:+.2f}%</code>
└ 總訊號數：{len(self.signals)}

<i>👻 影子策略 v2 - 均線糾纏突破</i>
"""
        self.notifier._send_message(message.strip())

    # =========================================================================
    # 初始化（與 multi_runner 相同，但不實際下單）
    # =========================================================================

    def initialize(self) -> bool:
        """初始化：測試連線（與 multi_runner 相同）"""
        logger.info("=" * 60)
        logger.info("BiGe 雙均線 v2 - 影子交易系統")
        logger.info("注意：此模式不會實際下單，只記錄訊號")
        logger.info(f"監控幣種: {len(self.symbols)} 個")
        logger.info("=" * 60)

        # 測試 API 連線（與 multi_runner 相同）
        logger.info("測試 API 連線...")
        if not self.broker.test_connection():
            logger.error("API 連線失敗！")
            if self.notifier:
                self.notifier.send_alert("SYSTEM_ERROR", "[SHADOW] API 連線失敗！")
            return False
        logger.info("API 連線成功")

        # 取得帳戶餘額（用於計算模擬倉位）
        balance = self.broker.get_account_balance()
        logger.info(f"帳戶餘額: {balance['total']:.2f} USDT")

        # 記錄啟動狀態
        self.start_time = datetime.now()
        self.start_equity = balance["total"]
        self.daily_start_equity = balance["total"]

        # === 初始化模擬權益（如果是首次運行）===
        if self.simulated_equity == 0.0:
            self.simulated_equity = balance["total"]
            self.simulated_initial_equity = balance["total"]
            logger.info(f"初始化模擬權益: ${self.simulated_equity:,.2f} USDT")
            self._save_equity()
        else:
            logger.info(
                f"恢復模擬權益: ${self.simulated_equity:,.2f} USDT "
                f"(初始: ${self.simulated_initial_equity:,.2f})"
            )
            # 計算累計收益
            if self.simulated_initial_equity > 0:
                total_return = (self.simulated_equity / self.simulated_initial_equity - 1) * 100
                logger.info(f"模擬累計收益: {total_return:+.2f}%")

        logger.info("=" * 60)
        logger.info("初始化完成！")

        # 發送影子專屬啟動通知（如果啟用）
        if self.notifier:
            symbols_text = ", ".join([s.replace("USDT", "") for s in self.symbols])
            message = f"""
<b>👻 影子交易系統啟動</b>

🔮 <b>這不是實盤！僅記錄訊號</b>

📊 <b>系統配置</b>
├ 策略：均線糾纏突破 v2
├ 幣種：{symbols_text}
├ 動態槓桿：{self.config['initial_leverage']}x 起始
├ 糾纏閾值：{self.config['cluster_threshold']*100:.0f}%
└ 帳戶參考：<code>${balance['total']:,.2f}</code> USDT

📈 <b>v2 策略特點</b>
├ 進場：6均線糾纏 + 放量突破
├ 做空：需完整下跌趨勢
└ 槓桿：獲利後自動遞減

<i>👻 影子觀察開始...</i>
"""
            self.notifier._send_message(message.strip())

        return True

    # =========================================================================
    # K 線獲取（與 multi_runner 相同 + v2 額外指標）
    # =========================================================================

    def fetch_klines(self, symbol: str, limit: int = 200) -> Optional[pd.DataFrame]:
        """
        獲取指定幣種的 K 線數據

        與 multi_runner 相同的基礎指標 + v2 額外指標
        """
        try:
            klines = self.broker.get_klines(symbol, self.timeframe, limit)
            if not klines:
                return None

            df = pd.DataFrame(klines)
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            # === 基礎指標（與 multi_runner 完全相同）===
            df["ma20"] = df["close"].rolling(20).mean()
            df["ma60"] = df["close"].rolling(60).mean()
            df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
            df["ema60"] = df["close"].ewm(span=60, adjust=False).mean()
            df["avg20"] = (df["ma20"] + df["ema20"]) / 2
            df["avg60"] = (df["ma60"] + df["ema60"]) / 2

            # ATR（與 multi_runner 相同）
            high = df["high"]
            low = df["low"]
            close = df["close"]
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df["atr"] = tr.rolling(14).mean()

            # === v2 額外指標 ===
            # MA120（用於完整下跌趨勢判斷）
            df["ma120"] = df["close"].rolling(120).mean()
            df["ema120"] = df["close"].ewm(span=120, adjust=False).mean()
            df["avg120"] = (df["ma120"] + df["ema120"]) / 2

            # 均線離散度（用於糾纏判斷）
            ma_cols = ["ma20", "ma60", "ma120", "ema20", "ema60", "ema120"]

            def calc_spread(row):
                values = [row[col] for col in ma_cols if pd.notna(row[col])]
                if len(values) < 6:
                    return np.nan
                return (max(values) - min(values)) / min(values)

            df["ma_spread"] = df.apply(calc_spread, axis=1)

            # 成交量比
            if "volume" in df.columns:
                df["vol_ma20"] = df["volume"].rolling(20).mean()
                df["vol_ratio"] = df["volume"] / df["vol_ma20"]
            else:
                df["vol_ratio"] = 1.0

            # RSI
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df["rsi"] = 100 - (100 / (1 + rs))

            # K 線實體
            df["body_pct"] = (df["close"] - df["open"]) / df["open"] * 100

            # MACD
            ema12 = df["close"].ewm(span=12, adjust=False).mean()
            ema26 = df["close"].ewm(span=26, adjust=False).mean()
            df["macd"] = ema12 - ema26
            df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
            df["macd_hist"] = df["macd"] - df["macd_signal"]
            df["macd_hist_prev"] = df["macd_hist"].shift(1)
            df["macd_momentum"] = df["macd_hist"] - df["macd_hist_prev"]

            return df
        except Exception as e:
            logger.error(f"獲取 {symbol} K 線失敗: {e}")
            return None

    # =========================================================================
    # 動態槓桿（v2 特有）
    # =========================================================================

    def get_dynamic_leverage(self) -> int:
        """動態槓桿計算"""
        profit_pct = self.equity_multiple - 1

        if profit_pct < 0.04:
            return min(self.config["initial_leverage"], 25)
        elif profit_pct < 0.09:
            return 20
        elif profit_pct < 0.16:
            return 15
        elif profit_pct < 0.31:
            return 10
        elif profit_pct < 0.64:
            return 5
        elif profit_pct < 1.0:
            return 3
        else:
            return 2

    # =========================================================================
    # 策略邏輯（v2 特有 - 均線糾纏突破）
    # =========================================================================

    def check_entry_signal(self, state: ShadowSymbolState, row: pd.Series) -> Optional[str]:
        """
        檢查進場訊號（v2 均線糾纏突破策略）

        與 multi_runner.check_entry_signal() 結構相同，但邏輯不同
        """
        p = self.config

        close = row["close"]
        high = row["high"]
        low = row["low"]
        ma20 = row.get("ma20")
        ma60 = row.get("ma60")
        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        avg120 = row.get("avg120")
        spread = row.get("ma_spread")
        vol_ratio = row.get("vol_ratio", 0)
        rsi = row.get("rsi", 50)
        body_pct = row.get("body_pct", 0)
        macd_hist = row.get("macd_hist", 0)
        macd_momentum = row.get("macd_momentum", 0)

        if pd.isna(avg20) or pd.isna(avg60):
            return None

        # 檢查均線糾纏
        is_cluster = pd.notna(spread) and spread < p["cluster_threshold"]

        if is_cluster:
            if not state.in_cluster:
                state.in_cluster = True
                state.cluster_bars = 1
            else:
                state.cluster_bars += 1
        else:
            state.in_cluster = False
            state.cluster_bars = 0

        # 價格位置
        price_above_ma20 = close > ma20 if pd.notna(ma20) else False
        price_below_ma20 = close < ma20 if pd.notna(ma20) else False

        if price_above_ma20:
            state.bars_above_ma20 += 1
            state.bars_below_ma20 = 0
        elif price_below_ma20:
            state.bars_below_ma20 += 1
            state.bars_above_ma20 = 0
        else:
            state.bars_above_ma20 = 0
            state.bars_below_ma20 = 0

        # MA 趨勢
        ma20_above_ma60 = ma20 > ma60 if pd.notna(ma20) and pd.notna(ma60) else False
        ma20_below_ma60 = ma20 < ma60 if pd.notna(ma20) and pd.notna(ma60) else False

        # 完整下跌趨勢
        full_downtrend = (
            pd.notna(avg20) and pd.notna(avg60) and pd.notna(avg120) and avg20 < avg60 < avg120
        )

        # 做多條件：均線糾纏突破
        breakout_long_ok = (
            is_cluster
            and state.cluster_bars >= p["min_cluster_bars"]
            and vol_ratio >= p["min_vol_ratio"]
            and price_above_ma20
            and ma20_above_ma60
            and rsi <= 85
            and body_pct >= p["breakout_body_pct"]
            and state.bars_above_ma20 >= p["min_bars_above"]
            and (macd_hist > 0 or macd_momentum > 0)
        )

        if breakout_long_ok:
            return "long"

        # 做空條件：需要完整下跌趨勢
        breakout_short_ok = (
            is_cluster
            and state.cluster_bars >= p["min_cluster_bars"]
            and vol_ratio >= p["min_vol_ratio"]
            and price_below_ma20
            and ma20_below_ma60
            and body_pct <= -p["breakout_body_pct"]
            and state.bars_below_ma20 >= p["min_bars_above"]
            and (macd_hist < 0 or macd_momentum < 0)
            and rsi <= p["short_rsi_max"]
            and (full_downtrend if p["short_require_full_downtrend"] else True)
        )

        if breakout_short_ok:
            return "short"

        return None

    def check_emergency_stop(self, state: ShadowSymbolState, row: pd.Series) -> bool:
        """
        檢查緊急止損（黑天鵝保護）

        與 multi_runner.check_emergency_stop() 完全相同
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
                return True

        elif state.position_direction == "short":
            high = row["high"]
            breach = high - avg20
            if breach > 0 and breach > emergency_atr * atr:
                return True

        return False

    def check_exit_signal(self, state: ShadowSymbolState, row: pd.Series) -> bool:
        """
        檢查出場訊號（v2 策略）

        與 multi_runner.check_exit_signal() 結構相同
        """
        # 優先檢查緊急止損
        if self.check_emergency_stop(state, row):
            return True

        if state.position_direction is None:
            return False

        p = self.config
        close = row["close"]
        high = row["high"]
        low = row["low"]
        ma20 = row.get("ma20")

        # 動態止損檢查（v2 特有）
        leverage = self.get_dynamic_leverage()
        stop_pct = (1 / leverage) * p.get("stop_loss_buffer", 0.7)

        if state.position_direction == "long":
            if state.entry_price:
                stop_price = state.entry_price * (1 - stop_pct)
                if low <= stop_price:
                    return True

            # 跌破 MA20 計數
            if pd.notna(ma20) and close < ma20:
                state.bars_below_ma += 1
            else:
                state.bars_below_ma = 0

        elif state.position_direction == "short":
            if state.entry_price:
                stop_price = state.entry_price * (1 + stop_pct)
                if high >= stop_price:
                    return True

            # 突破 MA20 計數
            if pd.notna(ma20) and close > ma20:
                state.bars_below_ma += 1
            else:
                state.bars_below_ma = 0

        # 跌破/突破 MA20 持續 N 根出場
        confirm_bars = p.get("stop_loss_confirm_bars", 10)
        if state.bars_below_ma >= confirm_bars:
            return True

        return False

    def check_add_position_signal(self, state: ShadowSymbolState, row: pd.Series) -> bool:
        """
        檢查加倉信號

        與 multi_runner.check_add_position_signal() 結構相同
        """
        p = self.config

        if state.position_direction is None:
            return False

        if state.add_count >= p["max_add_count"]:
            return False

        # 檢查加倉間隔
        min_interval = p.get("add_position_min_interval", 3)
        bars_since_last = state.current_bar - max(state.entry_bar, state.last_add_bar)
        if bars_since_last < min_interval:
            return False

        close = row["close"]
        low = row["low"]
        high = row["high"]
        avg20 = row["avg20"]

        # 防止除以零（與 multi_runner 對齊）
        if pd.isna(avg20) or avg20 == 0:
            return False

        # 🔴 關鍵修復：必須盈利才能加倉（與 multi_runner 對齊）
        min_profit = p.get("add_position_min_profit", 0.03)  # 預設 3%
        if state.entry_price and state.entry_price > 0:
            if state.position_direction == "long":
                current_pnl_pct = (close - state.entry_price) / state.entry_price
            else:
                current_pnl_pct = (state.entry_price - close) / state.entry_price

            if current_pnl_pct < min_profit:
                return False

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

    # =========================================================================
    # 處理邏輯（與 multi_runner 結構相同，但不實際下單）
    # =========================================================================

    def process_symbol(self, symbol: str):
        """
        處理單一幣種

        與 multi_runner.process_symbol() 結構相同
        """
        state = self.states[symbol]

        # 獲取數據（需要 120 根 K 線用於 MA120）
        df = self.fetch_klines(symbol)
        if df is None or len(df) < 120:
            return

        row = df.iloc[-2]  # 使用已完成的 K 線
        bar_time = row.name

        # 檢查是否是新 K 線
        if state.last_bar_time is not None and bar_time <= state.last_bar_time:
            return

        state.last_bar_time = bar_time
        state.current_bar += 1
        state.data_cache = df

        # 有影子持倉
        if state.position_direction is not None:
            # 更新追蹤止損（與 multi_runner 相同邏輯）
            self._update_trailing_stop(state, row)

            # 檢查出場
            if self.check_exit_signal(state, row):
                is_emergency = self.check_emergency_stop(state, row)
                reason = "緊急止損" if is_emergency else "止損/趨勢反轉"

                # 計算模擬盈虧
                if state.position_direction == "long":
                    pnl_pct = (row["close"] - state.entry_price) / state.entry_price
                else:
                    pnl_pct = (state.entry_price - row["close"]) / state.entry_price

                # === 計算實際 USDT 盈虧（等同實盤）===
                leverage = self.get_dynamic_leverage()
                # 計算手續費（開倉 + 平倉）
                fee_rate = self.config.get("fee_rate", 0.0004)
                total_fees = state.simulated_notional * fee_rate * 2  # 開 + 平
                # 計算淨盈虧（USDT）
                gross_pnl = state.simulated_notional * pnl_pct
                net_pnl = gross_pnl - total_fees

                self._record_signal(
                    symbol=symbol,
                    direction="exit",
                    price=row["close"],
                    reason=f"{reason} (PnL: {pnl_pct*100:.1f}%)",
                    indicators={
                        "entry_price": state.entry_price,
                        "pnl_pct": pnl_pct * 100,
                        "pnl_usdt": net_pnl,
                        "hold_bars": state.current_bar - state.entry_bar,
                        "leverage": leverage,
                        "notional": state.simulated_notional,
                        "fees": total_fees,
                    },
                )

                # 更新統計
                self.total_trades += 1
                self.daily_trades += 1
                if pnl_pct > 0:
                    self.winning_trades += 1
                    self.daily_wins += 1
                self.total_pnl += pnl_pct

                # === 更新模擬權益（等同實盤）===
                self.simulated_equity += net_pnl
                self.simulated_realized_pnl += net_pnl
                self.equity_multiple = self.simulated_equity / self.simulated_initial_equity

                logger.info(
                    f"[SHADOW] {symbol} 模擬平倉: "
                    f"PnL ${net_pnl:+,.2f} USDT ({pnl_pct*100:+.1f}%), "
                    f"權益 ${self.simulated_equity:,.2f}"
                )

                # 記錄權益快照
                self._record_equity_snapshot()

                # 重置狀態（完整重置所有欄位）
                state.position_direction = None
                state.entry_price = None
                state.entry_time = None
                state.stop_loss = None
                state.add_count = 0
                state.below_stop_count = 0
                state.bars_below_ma = 0
                # v2 策略特有欄位也需重置
                state.bars_above_ma20 = 0
                state.bars_below_ma20 = 0
                state.cluster_bars = 0
                state.in_cluster = False
                state.had_breakout_up = False
                state.had_breakout_down = False
                # 模擬持倉欄位
                state.simulated_qty = 0.0
                state.simulated_notional = 0.0
                return

            # 檢查加倉
            if self.check_add_position_signal(state, row):
                state.add_count += 1
                state.last_add_bar = state.current_bar

                self._record_signal(
                    symbol=symbol,
                    direction="add",
                    price=row["close"],
                    reason=f"加倉 #{state.add_count}",
                    indicators={
                        "add_count": state.add_count,
                        "max_add": self.config["max_add_count"],
                    },
                )

        # 無影子持倉
        else:
            signal = self.check_entry_signal(state, row)
            if signal:
                self._record_signal(
                    symbol=symbol,
                    direction=signal,
                    price=row["close"],
                    reason=f"均線糾纏突破 (cluster_bars={state.cluster_bars})",
                    indicators={
                        "ma_spread": row.get("ma_spread"),
                        "vol_ratio": row.get("vol_ratio"),
                        "rsi": row.get("rsi"),
                        "body_pct": row.get("body_pct"),
                        "leverage": self.get_dynamic_leverage(),
                    },
                )

                # 建立影子持倉
                state.position_direction = signal
                state.entry_price = row["close"]
                state.entry_time = datetime.now()
                state.entry_bar = state.current_bar
                state.last_add_bar = state.current_bar
                state.add_count = 0
                state.below_stop_count = 0
                state.bars_below_ma = 0

                # === 計算模擬持倉（等同實盤）===
                leverage = self.get_dynamic_leverage()
                position_size_pct = self.config["position_size_pct"]
                # 以模擬權益計算倉位
                notional_value = self.simulated_equity * position_size_pct * leverage
                state.simulated_notional = notional_value
                state.simulated_qty = notional_value / row["close"]
                logger.info(f"[SHADOW] {symbol} 模擬開倉: " f"${notional_value:,.2f} ({leverage}x)")

                # 設定止損
                avg20 = row["avg20"]
                p = self.config
                if signal == "long":
                    state.stop_loss = avg20 * (1 - p["ma20_buffer"])
                else:
                    state.stop_loss = avg20 * (1 + p["ma20_buffer"])

    def _update_trailing_stop(self, state: ShadowSymbolState, row: pd.Series):
        """
        更新追蹤止損

        與 multi_runner.update_trailing_stop() 完全相同
        """
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

    # =========================================================================
    # 狀態顯示（與 multi_runner 結構相同）
    # =========================================================================

    def print_status(self):
        """打印狀態摘要"""
        balance = self.broker.get_account_balance()

        logger.info("=" * 60)
        logger.info("👻 影子交易狀態摘要")
        logger.info("=" * 60)

        # 實盤帳戶（參考用）
        logger.info(f"實盤帳戶: ${balance['total']:,.2f} USDT")

        # 模擬帳戶狀態
        logger.info("-" * 40)
        logger.info("📊 模擬帳戶狀態")
        logger.info(f"  模擬權益: ${self.simulated_equity:,.2f} USDT")
        logger.info(f"  初始權益: ${self.simulated_initial_equity:,.2f} USDT")

        if self.simulated_initial_equity > 0:
            total_return = (self.simulated_equity / self.simulated_initial_equity - 1) * 100
            logger.info(f"  累計收益: {total_return:+.2f}%")

        logger.info(f"  已實現盈虧: ${self.simulated_realized_pnl:+,.2f} USDT")
        logger.info(f"  權益倍數: {self.equity_multiple:.2f}x")
        logger.info(f"  動態槓桿: {self.get_dynamic_leverage()}x")

        # 計算未實現盈虧
        total_unrealized = 0.0
        for symbol, state in self.states.items():
            if state.position_direction and state.entry_price and state.data_cache is not None:
                current_price = state.data_cache.iloc[-1]["close"]
                if state.position_direction == "long":
                    unrealized_pct = (current_price - state.entry_price) / state.entry_price
                else:
                    unrealized_pct = (state.entry_price - current_price) / state.entry_price
                unrealized_usdt = state.simulated_notional * unrealized_pct
                total_unrealized += unrealized_usdt

        if total_unrealized != 0:
            logger.info(f"  未實現盈虧: ${total_unrealized:+,.2f} USDT")

        # 交易統計
        logger.info("-" * 40)
        logger.info("📈 交易統計")
        logger.info(f"  總訊號數: {len(self.signals)}")

        if self.total_trades > 0:
            win_rate = self.winning_trades / self.total_trades * 100
            logger.info(f"  完成交易: {self.total_trades} 筆")
            logger.info(f"  勝率: {win_rate:.1f}%")
            logger.info(f"  勝/負: {self.winning_trades}/{self.total_trades - self.winning_trades}")

        # 訊號分類
        long_signals = len([s for s in self.signals if s.direction == "long"])
        short_signals = len([s for s in self.signals if s.direction == "short"])
        exit_signals = len([s for s in self.signals if s.direction == "exit"])
        add_signals = len([s for s in self.signals if s.direction == "add"])

        logger.info(
            f"  訊號分佈: 做多 {long_signals}, 做空 {short_signals}, "
            f"加倉 {add_signals}, 出場 {exit_signals}"
        )

        # 當前影子持倉
        logger.info("-" * 40)
        logger.info("💼 當前影子持倉")
        has_position = False
        for symbol in self.symbols:
            state = self.states[symbol]
            if state.position_direction:
                has_position = True
                # 計算未實現盈虧
                if state.data_cache is not None:
                    current_price = state.data_cache.iloc[-1]["close"]
                    if state.position_direction == "long":
                        pnl_pct = (current_price - state.entry_price) / state.entry_price * 100
                    else:
                        pnl_pct = (state.entry_price - current_price) / state.entry_price * 100
                    pnl_usdt = state.simulated_notional * pnl_pct / 100
                    logger.info(
                        f"  {symbol}: {state.position_direction.upper()} "
                        f"@ ${state.entry_price:,.2f} "
                        f"(PnL: {pnl_pct:+.1f}%, ${pnl_usdt:+,.2f})"
                    )
                else:
                    logger.info(
                        f"  {symbol}: {state.position_direction.upper()} "
                        f"@ ${state.entry_price:,.2f}"
                    )

        if not has_position:
            logger.info("  無持倉")

        logger.info("=" * 60)

    # =========================================================================
    # 主循環（與 multi_runner 結構相同）
    # =========================================================================

    def run(self, interval_seconds: int = 60):
        """
        運行主循環

        與 multi_runner.run() 結構相同
        """
        if not self.initialize():
            logger.error("初始化失敗，退出")
            return

        logger.info(f"開始運行，每 {interval_seconds} 秒檢查一次...")
        logger.info(f"監控幣種: {', '.join(self.symbols)}")

        last_status_time = time.time()
        status_interval = 3600  # 每小時打印一次
        consecutive_errors = 0
        max_consecutive_errors = 5

        try:
            while True:
                try:
                    # 處理每個幣種（與 multi_runner 相同）
                    for symbol in self.symbols:
                        try:
                            self.process_symbol(symbol)
                        except Exception as e:
                            logger.error(f"[{symbol}] 處理錯誤: {e}")

                    # 定期打印狀態
                    current_time = time.time()
                    if current_time - last_status_time >= status_interval:
                        self.print_status()
                        last_status_time = current_time

                    consecutive_errors = 0

                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"處理錯誤: {e}", exc_info=True)

                    if consecutive_errors >= max_consecutive_errors:
                        if self.notifier:
                            self.notifier.send_alert(
                                "SYSTEM_ERROR",
                                f"[SHADOW] 連續發生 {consecutive_errors} 次錯誤！",
                                str(e),
                            )
                        consecutive_errors = 0

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("收到停止信號，退出...")
            self.print_status()

            # 輸出最終統計
            logger.info("\n最後 10 個訊號:")
            for s in self.signals[-10:]:
                logger.info(f"  {s.timestamp} {s.symbol} {s.direction} @ {s.price:.2f}")


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description="BiGe 雙均線 v2 - 影子交易系統")
    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        default=SHADOW_CONFIG["symbols"],
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
    parser.add_argument(
        "--notify",
        action="store_true",
        help="啟用 Telegram 通知",
    )

    args = parser.parse_args()

    runner = ShadowRunner(
        symbols=args.symbols,
        timeframe=args.timeframe,
        config=SHADOW_CONFIG,
        enable_notifications=args.notify,
    )

    runner.run(interval_seconds=args.interval)


if __name__ == "__main__":
    main()
