"""
SuperDog Telegram 通知模組 v1.0

警犬風格通知系統 - 忠心耿耿守護你的倉位

通知分級：
1. 心跳通知 (HEARTBEAT) - 每小時一次，確認系統存活
2. 事件通知 (TRADE) - 開倉/加倉/平倉時發送
3. 警報通知 (ALERT) - 系統異常時發送
4. 日報通知 (DAILY) - 每天固定時間發送

Version: v1.0
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 台灣時區 (UTC+8)
TW_TIMEZONE = timezone(timedelta(hours=8))


def get_tw_time() -> datetime:
    """取得台灣時間"""
    return datetime.now(TW_TIMEZONE)


class SuperDogNotifier:
    """
    警犬通知器 - 忠誠守護你的每一筆交易
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        初始化通知器

        Args:
            bot_token: Telegram Bot Token（或從環境變數 TELEGRAM_BOT_TOKEN 讀取）
            chat_id: Telegram Chat ID（或從環境變數 TELEGRAM_CHAT_ID 讀取）
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)

        # 頻率限制
        self.last_heartbeat_time: Optional[datetime] = None
        self.last_daily_report_time: Optional[datetime] = None
        self.last_alert_time: dict = {}  # alert_type -> last_time
        self.alert_cooldown_minutes = 10  # 同類警報冷卻時間

        # 統計
        self.messages_sent = 0
        self.errors_count = 0

        if not self.enabled:
            logger.warning("Telegram 通知未設定，請設定 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")

    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        發送 Telegram 訊息

        Args:
            text: 訊息內容
            parse_mode: 解析模式（HTML 或 Markdown）

        Returns:
            是否成功發送
        """
        if not self.enabled:
            logger.debug(f"[Telegram 未啟用] {text[:50]}...")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                self.messages_sent += 1
                logger.debug(f"Telegram 訊息已發送: {text[:50]}...")
                return True
            else:
                self.errors_count += 1
                logger.error(f"Telegram 發送失敗: {response.status_code} {response.text}")
                return False
        except Exception as e:
            self.errors_count += 1
            logger.error(f"Telegram 發送錯誤: {e}")
            return False

    # ========== 心跳通知 ==========

    def send_heartbeat(
        self,
        equity: float,
        price: float,
        position_info: Optional[str] = None,
        uptime_hours: Optional[float] = None,
        positions_pnl: Optional[list] = None,
        total_unrealized_pnl: Optional[float] = None,
    ) -> bool:
        """
        發送心跳通知（每小時一次）

        Args:
            equity: 帳戶權益
            price: 當前 BTC 價格
            position_info: 持倉資訊（如 "LONG 0.003 BTC"）
            uptime_hours: 運行時長（小時）
            positions_pnl: 各持倉盈虧列表 [{"symbol": "BTC", "pnl_pct": 5.2}, ...]
            total_unrealized_pnl: 總未實現盈虧（USDT）
        """
        # 頻率限制：每小時一次
        now = get_tw_time()
        if self.last_heartbeat_time:
            elapsed = (now - self.last_heartbeat_time).total_seconds()
            if elapsed < 3600:  # 60 分鐘
                return False

        self.last_heartbeat_time = now

        # 組裝訊息
        position_text = position_info if position_info else "空倉待命中"
        uptime_text = f"{uptime_hours:.1f}h" if uptime_hours else "剛啟動"

        # 持倉盈虧摘要
        pnl_section = ""
        if positions_pnl and len(positions_pnl) > 0:
            pnl_lines = []
            for pos in positions_pnl:
                symbol = pos.get("symbol", "???").replace("USDT", "")
                pnl_pct = pos.get("pnl_pct", 0)
                direction = pos.get("direction", "")
                emoji = "📈" if pnl_pct >= 0 else "📉"
                sign = "+" if pnl_pct >= 0 else ""
                pnl_lines.append(f"├ {symbol} ({direction}): {emoji} {sign}{pnl_pct:.2f}%")

            if total_unrealized_pnl is not None:
                total_emoji = "💚" if total_unrealized_pnl >= 0 else "❤️"
                total_sign = "+" if total_unrealized_pnl >= 0 else ""
                pnl_lines.append(f"└ 總計：{total_emoji} {total_sign}${total_unrealized_pnl:.2f}")

            pnl_section = "\n\n📊 <b>持倉盈虧</b>\n" + "\n".join(pnl_lines)

        message = f"""
<b>🐕 汪！主人，我還在崗位上！</b>

📊 <b>系統狀態</b>
├ 時間：{now.strftime("%Y-%m-%d %H:%M")} (台灣)
├ 運行：{uptime_text}
└ 狀態：正常運作中

💰 <b>帳戶資訊</b>
├ 權益：<code>${equity:,.2f}</code> USDT
├ BTC：<code>${price:,.2f}</code>
└ 持倉：{position_text}{pnl_section}

<i>🦴 警犬持續巡邏中...</i>
"""
        return self._send_message(message.strip())

    # ========== 事件通知 ==========

    def send_entry(
        self,
        direction: str,
        symbol: str,
        qty: float,
        price: float,
        leverage: int,
        stop_loss: float,
        equity: float,
    ) -> bool:
        """
        發送開倉通知

        Args:
            direction: "LONG" 或 "SHORT"
            symbol: 交易對
            qty: 數量
            price: 入場價格
            leverage: 槓桿
            stop_loss: 止損價
            equity: 帳戶權益
        """
        now = get_tw_time()

        if direction.upper() == "LONG":
            emoji = "🟢"
            action = "做多"
            dog_mood = "尾巴搖起來！發現獵物了！"
        else:
            emoji = "🔴"
            action = "做空"
            dog_mood = "耳朵豎起來！準備狩獵！"

        # 計算倉位價值
        position_value = qty * price
        margin_used = position_value / leverage

        message = f"""
<b>{emoji} 汪汪！開倉啦！{dog_mood}</b>

🎯 <b>交易詳情</b>
├ 方向：<b>{action}</b> {symbol}
├ 數量：<code>{qty}</code>
├ 價格：<code>${price:,.2f}</code>
├ 槓桿：{leverage}x
├ 倉位價值：<code>${position_value:,.2f}</code>
└ 保證金：<code>${margin_used:,.2f}</code>

🛡️ <b>風控設定</b>
└ 止損位：<code>${stop_loss:,.2f}</code>

💰 帳戶權益：<code>${equity:,.2f}</code> USDT

<i>🐕 警犬已就位，緊盯獵物中...</i>
"""
        return self._send_message(message.strip())

    def send_add_position(
        self,
        direction: str,
        symbol: str,
        add_qty: float,
        price: float,
        add_count: int,
        max_add: int,
        total_qty: float,
        avg_price: float,
    ) -> bool:
        """
        發送加倉通知

        Args:
            direction: "LONG" 或 "SHORT"
            symbol: 交易對
            add_qty: 加倉數量
            price: 加倉價格
            add_count: 第幾次加倉
            max_add: 最大加倉次數
            total_qty: 總持倉數量
            avg_price: 平均持倉價格
        """
        now = get_tw_time()
        emoji = "🟢" if direction.upper() == "LONG" else "🔴"

        # 加倉次數提示
        if add_count == max_add:
            add_hint = "（已達上限，不能再加了汪！）"
        elif add_count >= max_add - 1:
            add_hint = "（快到上限了，謹慎汪！）"
        else:
            add_hint = ""

        message = f"""
<b>{emoji} 汪！加碼出擊！</b>

📈 <b>加倉詳情</b>
├ 方向：{direction.upper()} {symbol}
├ 加倉數量：<code>{add_qty}</code>
├ 加倉價格：<code>${price:,.2f}</code>
└ 次數：第 {add_count}/{max_add} 次 {add_hint}

📊 <b>持倉更新</b>
├ 總數量：<code>{total_qty}</code>
└ 均價：<code>${avg_price:,.2f}</code>

<i>🦴 加倉完成，繼續盯盤...</i>
"""
        return self._send_message(message.strip())

    def send_exit(
        self,
        direction: str,
        symbol: str,
        qty: float,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = "止損",
    ) -> bool:
        """
        發送平倉通知

        Args:
            direction: "LONG" 或 "SHORT"
            symbol: 交易對
            qty: 平倉數量
            entry_price: 入場價格
            exit_price: 出場價格
            pnl: 盈虧金額
            pnl_pct: 盈虧百分比
            reason: 平倉原因（止損/止盈/手動）
        """
        now = get_tw_time()

        if pnl >= 0:
            emoji = "🎉"
            result = "獲利"
            dog_mood = "汪汪！賺到骨頭了！搖尾巴～"
            pnl_color = "+"
        else:
            emoji = "😢"
            result = "虧損"
            dog_mood = "嗚...這次沒抓到獵物..."
            pnl_color = ""

        message = f"""
<b>{emoji} 平倉完成！{dog_mood}</b>

📋 <b>交易結算</b>
├ 方向：{direction.upper()} {symbol}
├ 數量：<code>{qty}</code>
├ 入場：<code>${entry_price:,.2f}</code>
├ 出場：<code>${exit_price:,.2f}</code>
└ 原因：{reason}

💵 <b>損益結果</b>
├ {result}：<code>{pnl_color}${abs(pnl):,.2f}</code> USDT
└ 報酬率：<code>{pnl_color}{pnl_pct:.2f}%</code>

<i>🐕 休息一下，準備下一次狩獵...</i>
"""
        return self._send_message(message.strip())

    # ========== 警報通知 ==========

    def send_alert(self, alert_type: str, message: str, details: Optional[str] = None) -> bool:
        """
        發送警報通知（有冷卻時間）

        Args:
            alert_type: 警報類型（如 "API_ERROR", "CONNECTION_LOST", "LIQUIDATION_RISK"）
            message: 警報訊息
            details: 詳細資訊
        """
        # 冷卻檢查
        now = get_tw_time()
        if alert_type in self.last_alert_time:
            elapsed = (now - self.last_alert_time[alert_type]).total_seconds()
            if elapsed < self.alert_cooldown_minutes * 60:
                logger.debug(f"警報 {alert_type} 冷卻中，跳過")
                return False

        self.last_alert_time[alert_type] = now

        # 根據類型選擇表情
        alert_emojis = {
            "API_ERROR": "🚨",
            "CONNECTION_LOST": "📡",
            "LIQUIDATION_RISK": "💀",
            "SYSTEM_ERROR": "🔥",
            "STOP_LOSS_TRIGGERED": "🛑",
            "LOW_BALANCE": "💸",
        }
        emoji = alert_emojis.get(alert_type, "⚠️")

        details_text = f"\n\n📝 <b>詳情</b>\n<code>{details}</code>" if details else ""

        alert_msg = f"""
<b>{emoji} 汪汪汪！警報！警報！</b>

🚨 <b>類型：{alert_type}</b>

{message}{details_text}

⏰ 時間：{now.strftime("%Y-%m-%d %H:%M:%S")}

<i>🐕 警犬正在處理中，請關注後續...</i>
"""
        return self._send_message(alert_msg.strip())

    def send_api_error(self, error_msg: str, retry_count: int = 0) -> bool:
        """發送 API 錯誤警報"""
        return self.send_alert(
            "API_ERROR",
            f"API 連線出現問題！\n已重試 {retry_count} 次",
            error_msg,
        )

    def send_liquidation_warning(
        self, current_price: float, liq_price: float, distance_pct: float
    ) -> bool:
        """發送爆倉風險警報"""
        return self.send_alert(
            "LIQUIDATION_RISK",
            f"⚠️ 接近爆倉價位！\n\n"
            f"當前價格：${current_price:,.2f}\n"
            f"爆倉價格：${liq_price:,.2f}\n"
            f"距離：{distance_pct:.2f}%\n\n"
            f"<b>請立即關注！</b>",
        )

    # ========== 日報通知 ==========

    def send_daily_report(
        self,
        equity: float,
        equity_change: float,
        equity_change_pct: float,
        trades_today: int,
        wins_today: int,
        position_info: Optional[str] = None,
        uptime_hours: float = 0,
    ) -> bool:
        """
        發送每日報告

        Args:
            equity: 當前權益
            equity_change: 權益變化金額
            equity_change_pct: 權益變化百分比
            trades_today: 今日交易次數
            wins_today: 今日獲勝次數
            position_info: 持倉資訊
            uptime_hours: 運行時長
        """
        now = get_tw_time()

        # 檢查是否已經發過日報（每天只發一次）
        if self.last_daily_report_time:
            if self.last_daily_report_time.date() == now.date():
                return False

        self.last_daily_report_time = now

        # 計算勝率
        win_rate = (wins_today / trades_today * 100) if trades_today > 0 else 0

        # 判斷今日表現
        if equity_change_pct > 5:
            emoji = "🚀"
            comment = "今天超棒！獎勵一根大骨頭！"
        elif equity_change_pct > 0:
            emoji = "😊"
            comment = "穩穩的，繼續保持汪！"
        elif equity_change_pct > -5:
            emoji = "😐"
            comment = "小虧而已，明天再戰！"
        else:
            emoji = "😢"
            comment = "今天不太順...但警犬不會放棄！"

        position_text = position_info if position_info else "空倉休息中"
        change_sign = "+" if equity_change >= 0 else ""

        message = f"""
<b>{emoji} 警犬日報 - {now.strftime("%Y-%m-%d")}</b>

{comment}

💰 <b>帳戶狀態</b>
├ 當前權益：<code>${equity:,.2f}</code> USDT
├ 今日損益：<code>{change_sign}${equity_change:,.2f}</code> ({change_sign}{equity_change_pct:.2f}%)
└ 持倉：{position_text}

📊 <b>交易統計</b>
├ 今日交易：{trades_today} 筆
├ 獲勝：{wins_today} 筆
└ 勝率：{win_rate:.1f}%

⏱️ 系統運行：{uptime_hours:.1f} 小時

<i>🐕 明天繼續守護你的資產汪！</i>
"""
        return self._send_message(message.strip())

    # ========== 系統通知 ==========

    def send_startup(
        self, equity: float, leverage: int, symbol: str, config_summary: str = ""
    ) -> bool:
        """
        發送系統啟動通知

        Args:
            equity: 帳戶權益
            leverage: 槓桿設定
            symbol: 交易對
            config_summary: 配置摘要
        """
        now = get_tw_time()
        config_text = config_summary if config_summary else "├ 倉位大小：10%\n├ 最大加倉：3 次\n└ 止損模式：MA20 追蹤"

        message = f"""
<b>🐕 汪！警犬上線啦！</b>

系統啟動時間：{now.strftime("%Y-%m-%d %H:%M:%S")}

⚙️ <b>配置資訊</b>
├ 交易對：{symbol}
├ 槓桿：{leverage}x
├ 帳戶權益：<code>${equity:,.2f}</code> USDT
└ 模式：BiGe 7x 策略

📋 <b>策略設定</b>
{config_text}

<i>🦴 開始巡邏！有任何風吹草動都會通知你！</i>
"""
        return self._send_message(message.strip())

    def send_shutdown(
        self, reason: str, equity: float, total_trades: int, total_pnl: float
    ) -> bool:
        """
        發送系統關閉通知

        Args:
            reason: 關閉原因
            equity: 最終權益
            total_trades: 總交易次數
            total_pnl: 總損益
        """
        now = get_tw_time()
        pnl_sign = "+" if total_pnl >= 0 else ""

        message = f"""
<b>🐕 汪...警犬下班了</b>

關閉時間：{now.strftime("%Y-%m-%d %H:%M:%S")}
原因：{reason}

📊 <b>本次運行統計</b>
├ 最終權益：<code>${equity:,.2f}</code> USDT
├ 總交易：{total_trades} 筆
└ 總損益：<code>{pnl_sign}${total_pnl:,.2f}</code>

<i>🦴 警犬休息去了，下次見！</i>
"""
        return self._send_message(message.strip())


# 測試用
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    notifier = SuperDogNotifier()

    if notifier.enabled:
        print("Telegram 通知已啟用，發送測試訊息...")
        notifier.send_startup(
            equity=311.53,
            leverage=7,
            symbol="BTCUSDT",
        )
    else:
        print("Telegram 通知未設定")
        print("請在 .env 中設定：")
        print("  TELEGRAM_BOT_TOKEN=your_bot_token")
        print("  TELEGRAM_CHAT_ID=your_chat_id")
