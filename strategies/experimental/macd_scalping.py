"""
MACD 短線策略

適合 15 分鐘時間框架的高頻交易策略
基於 MACD 黃金/死亡交叉信號，配合固定止損止盈

特點:
- 快速進出，每天多筆交易
- 固定 TP/SL (不依賴信號出場，避免震盪)
- 高槓桿低本金操作
- 最佳參數: SL 0.8%, TP 2.4% (1:3 風報比)
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd


def calculate_macd(
    df: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    """
    計算 MACD 指標

    Args:
        df: OHLCV DataFrame
        fast_period: 快線週期 (預設 12)
        slow_period: 慢線週期 (預設 26)
        signal_period: 信號線週期 (預設 9)

    Returns:
        添加 MACD 指標的 DataFrame
    """
    df = df.copy()
    close = df["close"]

    # EMA 計算
    ema_fast = close.ewm(span=fast_period, adjust=False).mean()
    ema_slow = close.ewm(span=slow_period, adjust=False).mean()

    # MACD 線 = 快 EMA - 慢 EMA
    macd_line = ema_fast - ema_slow

    # 信號線 = MACD 的 EMA
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

    # MACD 柱狀圖
    histogram = macd_line - signal_line

    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_hist"] = histogram

    return df


def generate_macd_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    生成 MACD 交易信號

    進場條件:
    - 做多: MACD 線上穿信號線 (黃金交叉)
    - 做空: MACD 線下穿信號線 (死亡交叉)

    Returns:
        添加信號的 DataFrame
    """
    df = df.copy()

    macd = df["macd"]
    signal = df["macd_signal"]

    # 當前和前一根 K 線的相對位置
    above_signal = macd > signal
    below_signal = macd < signal

    # 黃金交叉: 前一根在下，當前在上
    prev_below = below_signal.shift(1)
    prev_below = prev_below.where(prev_below.notna(), False)
    df["entry_long"] = above_signal & prev_below

    # 死亡交叉: 前一根在上，當前在下
    prev_above = above_signal.shift(1)
    prev_above = prev_above.where(prev_above.notna(), False)
    df["entry_short"] = below_signal & prev_above

    return df


class MACDScalpingStrategy:
    """MACD 短線策略類"""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        stop_loss_pct: float = 0.008,  # 0.8% 止損
        take_profit_pct: float = 0.024,  # 2.4% 止盈 (1:3 風報比)
    ):
        """
        初始化策略

        Args:
            fast_period: MACD 快線週期
            slow_period: MACD 慢線週期
            signal_period: 信號線週期
            stop_loss_pct: 止損百分比 (0.008 = 0.8%)
            take_profit_pct: 止盈百分比 (0.024 = 2.4%)
        """
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """準備數據並計算指標"""
        df = calculate_macd(
            df,
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            signal_period=self.signal_period,
        )
        df = generate_macd_signals(df)
        return df

    def get_signal(self, df: pd.DataFrame) -> Tuple[str, dict]:
        """
        取得當前 K 線的交易信號

        Returns:
            (signal, analysis)
            signal: "LONG", "SHORT", "NONE"
            analysis: 分析數據字典
        """
        df = self.prepare_data(df)
        row = df.iloc[-1]

        analysis = {
            "macd": float(row["macd"]),
            "macd_signal": float(row["macd_signal"]),
            "macd_hist": float(row["macd_hist"]),
            "price": float(row["close"]),
        }

        if row.get("entry_long", False):
            return "LONG", analysis
        elif row.get("entry_short", False):
            return "SHORT", analysis
        else:
            return "NONE", analysis

    def calculate_exit_prices(self, entry_price: float, direction: str) -> Tuple[float, float]:
        """
        計算止損止盈價格

        Args:
            entry_price: 進場價格
            direction: "LONG" 或 "SHORT"

        Returns:
            (stop_loss_price, take_profit_price)
        """
        if direction == "LONG":
            stop_loss = entry_price * (1 - self.stop_loss_pct)
            take_profit = entry_price * (1 + self.take_profit_pct)
        else:  # SHORT
            stop_loss = entry_price * (1 + self.stop_loss_pct)
            take_profit = entry_price * (1 - self.take_profit_pct)

        return stop_loss, take_profit

    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 500,
        leverage: float = 20,
        fee_rate: float = 0.0004,
        position_size_pct: float = 0.5,
    ) -> dict:
        """
        回測策略

        Args:
            df: OHLCV DataFrame
            initial_capital: 初始資金
            leverage: 槓桿倍數
            fee_rate: 手續費率 (0.0004 = 0.04%)
            position_size_pct: 倉位大小 (資金百分比)

        Returns:
            回測結果字典
        """
        df = self.prepare_data(df)

        capital = initial_capital
        position = None  # None, 'long', 'short'
        entry_price = 0
        stop_loss = 0
        take_profit = 0
        entry_time = None
        trades = []
        equity_curve = [initial_capital]

        for i in range(1, len(df)):
            row = df.iloc[i]
            high = row["high"]
            low = row["low"]
            close = row["close"]
            current_time = row.name if hasattr(row, "name") else i

            # 無持倉，檢查進場信號
            if position is None:
                if row.get("entry_long", False):
                    position = "long"
                    entry_price = close
                    stop_loss, take_profit = self.calculate_exit_prices(entry_price, "LONG")
                    entry_time = current_time
                    # 扣除進場手續費
                    position_value = capital * position_size_pct * leverage
                    fee = position_value * fee_rate
                    capital -= fee

                elif row.get("entry_short", False):
                    position = "short"
                    entry_price = close
                    stop_loss, take_profit = self.calculate_exit_prices(entry_price, "SHORT")
                    entry_time = current_time
                    position_value = capital * position_size_pct * leverage
                    fee = position_value * fee_rate
                    capital -= fee

            # 有持倉，檢查止損止盈
            elif position == "long":
                exit_price = None
                exit_reason = None

                # 檢查止損 (用 low 判斷)
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                # 檢查止盈 (用 high 判斷)
                elif high >= take_profit:
                    exit_price = take_profit
                    exit_reason = "take_profit"

                if exit_price:
                    pnl_pct = (exit_price - entry_price) / entry_price
                    position_value = capital * position_size_pct * leverage
                    pnl = position_value * pnl_pct
                    fee = position_value * fee_rate
                    capital += pnl - fee

                    trades.append(
                        {
                            "entry_time": entry_time,
                            "exit_time": current_time,
                            "direction": "long",
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "pnl_pct": pnl_pct * 100,
                            "pnl": pnl - fee,
                            "exit_reason": exit_reason,
                        }
                    )
                    position = None

            elif position == "short":
                exit_price = None
                exit_reason = None

                # 檢查止損 (用 high 判斷)
                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "stop_loss"
                # 檢查止盈 (用 low 判斷)
                elif low <= take_profit:
                    exit_price = take_profit
                    exit_reason = "take_profit"

                if exit_price:
                    pnl_pct = (entry_price - exit_price) / entry_price
                    position_value = capital * position_size_pct * leverage
                    pnl = position_value * pnl_pct
                    fee = position_value * fee_rate
                    capital += pnl - fee

                    trades.append(
                        {
                            "entry_time": entry_time,
                            "exit_time": current_time,
                            "direction": "short",
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "pnl_pct": pnl_pct * 100,
                            "pnl": pnl - fee,
                            "exit_reason": exit_reason,
                        }
                    )
                    position = None

            equity_curve.append(capital)

        # 計算統計
        return self._calculate_statistics(trades, equity_curve, initial_capital, capital)

    def _calculate_statistics(
        self,
        trades: list,
        equity_curve: list,
        initial_capital: float,
        final_capital: float,
    ) -> dict:
        """計算回測統計"""
        if len(trades) > 0:
            trades_df = pd.DataFrame(trades)
            wins = len(trades_df[trades_df["pnl"] > 0])
            losses = len(trades_df[trades_df["pnl"] <= 0])
            win_rate = wins / len(trades) * 100
            total_pnl = trades_df["pnl"].sum()
            avg_pnl = trades_df["pnl"].mean()
            max_drawdown = self._calculate_max_drawdown(equity_curve)

            # 盈虧比
            avg_win = trades_df[trades_df["pnl"] > 0]["pnl"].mean() if wins > 0 else 0
            avg_loss = abs(trades_df[trades_df["pnl"] <= 0]["pnl"].mean()) if losses > 0 else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

            # 按出場原因統計
            exit_reasons = trades_df["exit_reason"].value_counts().to_dict()

        else:
            win_rate = 0
            total_pnl = 0
            avg_pnl = 0
            max_drawdown = 0
            profit_factor = 0
            wins = 0
            losses = 0
            trades_df = pd.DataFrame()
            exit_reasons = {}

        return {
            "initial_capital": initial_capital,
            "final_capital": final_capital,
            "total_return_pct": (final_capital - initial_capital) / initial_capital * 100,
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "max_drawdown_pct": max_drawdown,
            "profit_factor": profit_factor,
            "exit_reasons": exit_reasons,
            "trades": trades_df,
            "equity_curve": equity_curve,
        }

    def _calculate_max_drawdown(self, equity_curve: list) -> float:
        """計算最大回撤"""
        peak = equity_curve[0]
        max_dd = 0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return max_dd


# 推薦配置常數
RECOMMENDED_CONFIG = {
    "timeframe": "15m",
    "fast_period": 12,
    "slow_period": 26,
    "signal_period": 9,
    "stop_loss_pct": 0.008,  # 0.8%
    "take_profit_pct": 0.024,  # 2.4%
    "leverage": 20,
    "position_size_pct": 0.5,
}

# 適合的幣種 (回測表現好的)
RECOMMENDED_SYMBOLS = [
    "BTCUSDT",  # +56%
    "ETHUSDT",  # +53%
    "DOGEUSDT",  # +437%
    "AVAXUSDT",  # +129%
    "LTCUSDT",  # +99%
    "OPUSDT",  # +87%
    "SOLUSDT",  # +6%
    "XRPUSDT",  # +5%
]


if __name__ == "__main__":
    print("MACD Scalping Strategy loaded successfully")
    print(f"Recommended config: {RECOMMENDED_CONFIG}")
    print(f"Recommended symbols: {RECOMMENDED_SYMBOLS}")
