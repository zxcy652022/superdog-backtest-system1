"""
交易日誌記錄器

記錄每筆開倉、平倉的詳細分析，用於 Phase 1 結束後回顧優化
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


class TradeLogger:
    """交易日誌記錄器"""

    def __init__(self, log_dir: str = "docs/trade_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 當月日誌檔案
        self.current_month = datetime.now().strftime("%Y-%m")
        self.log_file = self.log_dir / f"trades_{self.current_month}.json"

        # 載入現有日誌
        self.trades = self._load_trades()

    def _load_trades(self) -> list:
        """載入現有交易記錄"""
        if self.log_file.exists():
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_trades(self):
        """儲存交易記錄"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.trades, f, ensure_ascii=False, indent=2)

    def _calculate_ma_analysis(self, df: pd.DataFrame) -> dict:
        """計算均線分析"""
        if df is None or len(df) < 60:
            return {}

        row = df.iloc[-1]

        # 確保有必要的欄位
        required = ["close", "avg20", "avg60", "atr"]
        for col in required:
            if col not in df.columns:
                return {}

        avg20 = row.get("avg20")
        avg60 = row.get("avg60")
        atr = row.get("atr")
        close = row.get("close")

        if pd.isna(avg20) or pd.isna(avg60) or pd.isna(atr) or atr <= 0:
            return {}

        ma_gap = abs(avg20 - avg60)
        ma_gap_pct = ma_gap / close * 100 if close > 0 else 0
        ma_gap_atr = ma_gap / atr if atr > 0 else 0

        return {
            "avg20": float(avg20),
            "avg60": float(avg60),
            "atr": float(atr),
            "ma_gap": float(ma_gap),
            "ma_gap_pct": round(ma_gap_pct, 3),
            "ma_gap_atr": round(ma_gap_atr, 2),
            "trend": "LONG" if avg20 > avg60 else "SHORT",
        }

    def log_entry(
        self,
        symbol: str,
        direction: str,
        qty: float,
        price: float,
        stop_loss: float,
        df: Optional[pd.DataFrame] = None,
        reason: str = "趨勢進場",
    ):
        """記錄開倉"""
        ma_analysis = self._calculate_ma_analysis(df) if df is not None else {}

        trade = {
            "id": f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "type": "ENTRY",
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "direction": direction.upper(),
            "qty": qty,
            "price": price,
            "stop_loss": stop_loss,
            "reason": reason,
            "analysis": {
                "ma": ma_analysis,
                "quality_score": self._calculate_entry_quality(ma_analysis),
            },
        }

        self.trades.append(trade)
        self._save_trades()

        # 同時寫入可讀的 markdown
        self._write_entry_markdown(trade)

        return trade["id"]

    def log_exit(
        self,
        symbol: str,
        direction: str,
        qty: float,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        pnl_amount: float,
        reason: str,
        df: Optional[pd.DataFrame] = None,
        entry_id: Optional[str] = None,
    ):
        """記錄平倉"""
        ma_analysis = self._calculate_ma_analysis(df) if df is not None else {}

        # 計算持倉時間
        holding_bars = None
        if entry_id:
            for t in self.trades:
                if t.get("id") == entry_id:
                    entry_time = datetime.fromisoformat(t["timestamp"])
                    holding_hours = (datetime.now() - entry_time).total_seconds() / 3600
                    holding_bars = int(holding_hours / 4)  # 4H K 線
                    break

        # 判斷平倉類型
        exit_type = self._categorize_exit(reason, pnl_pct)

        trade = {
            "id": f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_exit",
            "type": "EXIT",
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "direction": direction.upper(),
            "qty": qty,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_pct": round(pnl_pct, 2),
            "pnl_amount": round(pnl_amount, 2),
            "reason": reason,
            "exit_type": exit_type,
            "holding_bars": holding_bars,
            "entry_id": entry_id,
            "analysis": {
                "ma": ma_analysis,
            },
        }

        self.trades.append(trade)
        self._save_trades()

        # 同時寫入可讀的 markdown
        self._write_exit_markdown(trade)

        return trade["id"]

    def _calculate_entry_quality(self, ma_analysis: dict) -> str:
        """評估開倉品質"""
        if not ma_analysis:
            return "UNKNOWN"

        gap_pct = ma_analysis.get("ma_gap_pct", 0)
        gap_atr = ma_analysis.get("ma_gap_atr", 0)

        # 評分標準
        if gap_pct >= 1.0 and gap_atr >= 1.5:
            return "A - 優質趨勢"
        elif gap_pct >= 0.5 and gap_atr >= 1.0:
            return "B - 正常趨勢"
        elif gap_pct >= 0.3 and gap_atr >= 0.5:
            return "C - 弱趨勢"
        else:
            return "D - 盤整/高風險"

    def _categorize_exit(self, reason: str, pnl_pct: float) -> str:
        """分類平倉類型"""
        if "緊急" in reason:
            return "EMERGENCY_STOP"
        elif "止損" in reason:
            return "STOP_LOSS"
        elif "止盈" in reason or pnl_pct > 5:
            return "TAKE_PROFIT"
        elif "趨勢" in reason:
            return "TREND_CHANGE"
        else:
            return "OTHER"

    def _write_entry_markdown(self, trade: dict):
        """寫入開倉 markdown"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        md_file = self.log_dir / f"daily_{date_str}.md"

        ma = trade["analysis"].get("ma", {})
        quality = trade["analysis"].get("quality_score", "UNKNOWN")

        content = f"""
## {trade['timestamp'][:19]} - {trade['symbol']} 開倉

| 項目 | 值 |
|------|-----|
| 方向 | {trade['direction']} |
| 價格 | {trade['price']} |
| 數量 | {trade['qty']} |
| 止損 | {trade['stop_loss']} |
| 原因 | {trade['reason']} |

### 均線分析
| 指標 | 值 | 評估 |
|------|-----|------|
| AVG20 | {ma.get('avg20', 'N/A')} | |
| AVG60 | {ma.get('avg60', 'N/A')} | |
| 間距% | {ma.get('ma_gap_pct', 'N/A')}% | {'正常' if ma.get('ma_gap_pct', 0) > 0.5 else '偏小'} |
| 間距ATR | {ma.get('ma_gap_atr', 'N/A')}x | {'正常' if ma.get('ma_gap_atr', 0) > 1.0 else '偏小'} |

**開倉品質: {quality}**

---
"""

        with open(md_file, "a", encoding="utf-8") as f:
            f.write(content)

    def _write_exit_markdown(self, trade: dict):
        """寫入平倉 markdown"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        md_file = self.log_dir / f"daily_{date_str}.md"

        pnl_emoji = "+" if trade["pnl_pct"] > 0 else ""
        result_emoji = "W" if trade["pnl_pct"] > 0 else "L"

        content = f"""
## {trade['timestamp'][:19]} - {trade['symbol']} 平倉 [{result_emoji}]

| 項目 | 值 |
|------|-----|
| 方向 | {trade['direction']} |
| 進場價 | {trade['entry_price']} |
| 出場價 | {trade['exit_price']} |
| 盈虧 | {pnl_emoji}{trade['pnl_pct']}% (${trade['pnl_amount']}) |
| 原因 | {trade['reason']} |
| 類型 | {trade['exit_type']} |
| 持倉 | {trade.get('holding_bars', 'N/A')} 根 K 線 |

---
"""

        with open(md_file, "a", encoding="utf-8") as f:
            f.write(content)

    def get_summary(self) -> dict:
        """取得交易統計摘要"""
        entries = [t for t in self.trades if t["type"] == "ENTRY"]
        exits = [t for t in self.trades if t["type"] == "EXIT"]

        wins = [t for t in exits if t.get("pnl_pct", 0) > 0]
        losses = [t for t in exits if t.get("pnl_pct", 0) <= 0]

        # 按品質分類
        quality_counts = {}
        for e in entries:
            q = e.get("analysis", {}).get("quality_score", "UNKNOWN")
            quality_counts[q] = quality_counts.get(q, 0) + 1

        # 按平倉類型分類
        exit_type_counts = {}
        for e in exits:
            t = e.get("exit_type", "OTHER")
            exit_type_counts[t] = exit_type_counts.get(t, 0) + 1

        return {
            "total_entries": len(entries),
            "total_exits": len(exits),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(exits) * 100 if exits else 0,
            "total_pnl_pct": sum(t.get("pnl_pct", 0) for t in exits),
            "entry_quality": quality_counts,
            "exit_types": exit_type_counts,
        }


# 全域實例
_trade_logger: Optional[TradeLogger] = None


def get_trade_logger() -> TradeLogger:
    """取得全域交易日誌實例"""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger
