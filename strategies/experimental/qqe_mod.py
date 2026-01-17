"""
QQE Mod 策略

基於 TradingView 的 QQE Mod 指標
適合短線交易 (15m/1h)

QQE = Quantitative Qualitative Estimation
結合 RSI + ATR 的動態平滑指標
"""

import numpy as np
import pandas as pd


def calculate_qqe_mod(
    df: pd.DataFrame,
    rsi_period: int = 6,
    rsi_smoothing: int = 5,
    qqe_factor: float = 3.0,
    threshold: float = 3.0,
    bb_length: int = 50,
    bb_mult: float = 0.35,
    qqe2_factor: float = 1.61,
) -> pd.DataFrame:
    """
    計算 QQE Mod 指標

    Args:
        df: OHLCV DataFrame
        rsi_period: RSI 週期 (預設 6)
        rsi_smoothing: RSI 平滑週期 (預設 5)
        qqe_factor: QQE 因子 (預設 3.0)
        threshold: 閾值 (預設 3.0)
        bb_length: 布林帶長度 (預設 50)
        bb_mult: 布林帶倍數 (預設 0.35)
        qqe2_factor: 第二 QQE 因子 (預設 1.61)

    Returns:
        添加 QQE 指標的 DataFrame
    """
    df = df.copy()
    close = df["close"]

    # === QQE 1 ===
    wilders_period = rsi_period * 2 - 1

    # RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # RSI MA (EMA smoothing)
    rsi_ma = rsi.ewm(span=rsi_smoothing, adjust=False).mean()

    # ATR of RSI
    atr_rsi = abs(rsi_ma - rsi_ma.shift(1))
    ma_atr_rsi = atr_rsi.ewm(span=wilders_period, adjust=False).mean()
    dar = ma_atr_rsi.ewm(span=wilders_period, adjust=False).mean() * qqe_factor

    # Dynamic bands
    rs_index = rsi_ma
    longband = pd.Series(index=df.index, dtype=float)
    shortband = pd.Series(index=df.index, dtype=float)
    trend = pd.Series(index=df.index, dtype=int)

    longband.iloc[0] = 0
    shortband.iloc[0] = 100
    trend.iloc[0] = 1

    for i in range(1, len(df)):
        new_longband = rs_index.iloc[i] - dar.iloc[i]
        new_shortband = rs_index.iloc[i] + dar.iloc[i]

        # Longband logic
        if rs_index.iloc[i - 1] > longband.iloc[i - 1] and rs_index.iloc[i] > longband.iloc[i - 1]:
            longband.iloc[i] = max(longband.iloc[i - 1], new_longband)
        else:
            longband.iloc[i] = new_longband

        # Shortband logic
        if (
            rs_index.iloc[i - 1] < shortband.iloc[i - 1]
            and rs_index.iloc[i] < shortband.iloc[i - 1]
        ):
            shortband.iloc[i] = min(shortband.iloc[i - 1], new_shortband)
        else:
            shortband.iloc[i] = new_shortband

        # Trend logic
        if rs_index.iloc[i] > shortband.iloc[i - 1]:
            trend.iloc[i] = 1
        elif rs_index.iloc[i] < longband.iloc[i - 1]:
            trend.iloc[i] = -1
        else:
            trend.iloc[i] = trend.iloc[i - 1]

    fast_atr_rsi_tl = pd.Series(index=df.index, dtype=float)
    for i in range(len(df)):
        if trend.iloc[i] == 1:
            fast_atr_rsi_tl.iloc[i] = longband.iloc[i]
        else:
            fast_atr_rsi_tl.iloc[i] = shortband.iloc[i]

    # Bollinger Bands on QQE
    basis = (fast_atr_rsi_tl - 50).rolling(bb_length).mean()
    dev = bb_mult * (fast_atr_rsi_tl - 50).rolling(bb_length).std()
    upper_bb = basis + dev
    lower_bb = basis - dev

    # === QQE 2 (用於 qqeline) ===
    wilders_period2 = rsi_period * 2 - 1

    rsi_ma2 = rsi.ewm(span=rsi_smoothing, adjust=False).mean()
    atr_rsi2 = abs(rsi_ma2 - rsi_ma2.shift(1))
    ma_atr_rsi2 = atr_rsi2.ewm(span=wilders_period2, adjust=False).mean()
    dar2 = ma_atr_rsi2.ewm(span=wilders_period2, adjust=False).mean() * qqe2_factor

    rs_index2 = rsi_ma2
    longband2 = pd.Series(index=df.index, dtype=float)
    shortband2 = pd.Series(index=df.index, dtype=float)
    trend2 = pd.Series(index=df.index, dtype=int)

    longband2.iloc[0] = 0
    shortband2.iloc[0] = 100
    trend2.iloc[0] = 1

    for i in range(1, len(df)):
        new_longband2 = rs_index2.iloc[i] - dar2.iloc[i]
        new_shortband2 = rs_index2.iloc[i] + dar2.iloc[i]

        if (
            rs_index2.iloc[i - 1] > longband2.iloc[i - 1]
            and rs_index2.iloc[i] > longband2.iloc[i - 1]
        ):
            longband2.iloc[i] = max(longband2.iloc[i - 1], new_longband2)
        else:
            longband2.iloc[i] = new_longband2

        if (
            rs_index2.iloc[i - 1] < shortband2.iloc[i - 1]
            and rs_index2.iloc[i] < shortband2.iloc[i - 1]
        ):
            shortband2.iloc[i] = min(shortband2.iloc[i - 1], new_shortband2)
        else:
            shortband2.iloc[i] = new_shortband2

        if rs_index2.iloc[i] > shortband2.iloc[i - 1]:
            trend2.iloc[i] = 1
        elif rs_index2.iloc[i] < longband2.iloc[i - 1]:
            trend2.iloc[i] = -1
        else:
            trend2.iloc[i] = trend2.iloc[i - 1]

    fast_atr_rsi2_tl = pd.Series(index=df.index, dtype=float)
    for i in range(len(df)):
        if trend2.iloc[i] == 1:
            fast_atr_rsi2_tl.iloc[i] = longband2.iloc[i]
        else:
            fast_atr_rsi2_tl.iloc[i] = shortband2.iloc[i]

    # QQE Line
    qqe_line = fast_atr_rsi2_tl - 50

    # Bar colors
    greenbar1 = (rsi_ma2 - 50) > threshold
    greenbar2 = (rsi_ma - 50) > upper_bb
    redbar1 = (rsi_ma2 - 50) < -threshold
    redbar2 = (rsi_ma - 50) < lower_bb

    # 儲存到 DataFrame
    df["qqe_rsi_ma"] = rsi_ma
    df["qqe_rsi_ma2"] = rsi_ma2
    df["qqe_line"] = qqe_line
    df["qqe_upper_bb"] = upper_bb
    df["qqe_lower_bb"] = lower_bb
    df["qqe_greenbar1"] = greenbar1
    df["qqe_greenbar2"] = greenbar2
    df["qqe_redbar1"] = redbar1
    df["qqe_redbar2"] = redbar2
    df["qqe_trend"] = trend
    df["qqe_trend2"] = trend2

    return df


def generate_signals(
    df: pd.DataFrame,
    signal_type: str = "line",  # "line", "bar", "line_and_bar"
) -> pd.DataFrame:
    """
    生成 QQE Mod 交易信號

    Args:
        df: 包含 QQE 指標的 DataFrame
        signal_type: 信號類型
            - "line": QQE line > 0 做多, < 0 做空
            - "bar": Greenbar 做多, Redbar 做空
            - "line_and_bar": 兩者都需要確認

    Returns:
        添加信號的 DataFrame
    """
    df = df.copy()

    if signal_type == "line":
        df["signal_long"] = df["qqe_line"] > 0
        df["signal_short"] = df["qqe_line"] < 0

    elif signal_type == "bar":
        df["signal_long"] = df["qqe_greenbar1"] & df["qqe_greenbar2"]
        df["signal_short"] = df["qqe_redbar1"] & df["qqe_redbar2"]

    elif signal_type == "line_and_bar":
        df["signal_long"] = (
            (df["qqe_line"] > 0)
            & df["qqe_greenbar1"]
            & df["qqe_greenbar2"]
            & ((df["qqe_rsi_ma2"] - 50) > 0)
        )
        df["signal_short"] = (
            (df["qqe_line"] < 0)
            & df["qqe_redbar1"]
            & df["qqe_redbar2"]
            & ((df["qqe_rsi_ma2"] - 50) < 0)
        )

    # 生成進場信號（狀態變化時）
    df["entry_long"] = df["signal_long"] & ~df["signal_long"].shift(1).fillna(False)
    df["entry_short"] = df["signal_short"] & ~df["signal_short"].shift(1).fillna(False)

    # 生成出場信號
    df["exit_long"] = df["signal_short"]  # 空頭信號出現時平多
    df["exit_short"] = df["signal_long"]  # 多頭信號出現時平空

    return df


class QQEModStrategy:
    """QQE Mod 策略類"""

    def __init__(
        self,
        rsi_period: int = 6,
        rsi_smoothing: int = 5,
        qqe_factor: float = 3.0,
        threshold: float = 3.0,
        bb_length: int = 50,
        bb_mult: float = 0.35,
        qqe2_factor: float = 1.61,
        signal_type: str = "line",
        stop_loss_pct: float = 0.02,  # 2% 止損
        take_profit_pct: float = 0.04,  # 4% 止盈
    ):
        self.rsi_period = rsi_period
        self.rsi_smoothing = rsi_smoothing
        self.qqe_factor = qqe_factor
        self.threshold = threshold
        self.bb_length = bb_length
        self.bb_mult = bb_mult
        self.qqe2_factor = qqe2_factor
        self.signal_type = signal_type
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """準備數據並計算指標"""
        df = calculate_qqe_mod(
            df,
            rsi_period=self.rsi_period,
            rsi_smoothing=self.rsi_smoothing,
            qqe_factor=self.qqe_factor,
            threshold=self.threshold,
            bb_length=self.bb_length,
            bb_mult=self.bb_mult,
            qqe2_factor=self.qqe2_factor,
        )
        df = generate_signals(df, self.signal_type)
        return df

    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 1000,
        leverage: float = 10,
        fee_rate: float = 0.0004,
        position_size_pct: float = 0.5,
    ) -> dict:
        """
        回測策略

        Args:
            df: OHLCV DataFrame
            initial_capital: 初始資金
            leverage: 槓桿倍數
            fee_rate: 手續費率
            position_size_pct: 倉位大小（資金百分比）

        Returns:
            回測結果字典
        """
        df = self.prepare_data(df)

        capital = initial_capital
        position = None  # None, 'long', 'short'
        entry_price = 0
        entry_time = None
        trades = []
        equity_curve = [initial_capital]

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            current_price = row["close"]
            current_time = row.name if hasattr(row, "name") else i

            # 無持倉，檢查進場
            if position is None:
                if row["entry_long"]:
                    position = "long"
                    entry_price = current_price
                    entry_time = current_time
                    # 扣除手續費
                    position_value = capital * position_size_pct * leverage
                    fee = position_value * fee_rate
                    capital -= fee

                elif row["entry_short"]:
                    position = "short"
                    entry_price = current_price
                    entry_time = current_time
                    position_value = capital * position_size_pct * leverage
                    fee = position_value * fee_rate
                    capital -= fee

            # 有持倉，檢查出場
            elif position == "long":
                pnl_pct = (current_price - entry_price) / entry_price

                # 止損/止盈/信號出場
                should_exit = (
                    pnl_pct <= -self.stop_loss_pct
                    or pnl_pct >= self.take_profit_pct
                    or row["exit_long"]
                )

                if should_exit:
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
                            "exit_price": current_price,
                            "pnl_pct": pnl_pct * 100,
                            "pnl": pnl - fee,
                            "exit_reason": "stop_loss"
                            if pnl_pct <= -self.stop_loss_pct
                            else "take_profit"
                            if pnl_pct >= self.take_profit_pct
                            else "signal",
                        }
                    )
                    position = None

            elif position == "short":
                pnl_pct = (entry_price - current_price) / entry_price

                should_exit = (
                    pnl_pct <= -self.stop_loss_pct
                    or pnl_pct >= self.take_profit_pct
                    or row["exit_short"]
                )

                if should_exit:
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
                            "exit_price": current_price,
                            "pnl_pct": pnl_pct * 100,
                            "pnl": pnl - fee,
                            "exit_reason": "stop_loss"
                            if pnl_pct <= -self.stop_loss_pct
                            else "take_profit"
                            if pnl_pct >= self.take_profit_pct
                            else "signal",
                        }
                    )
                    position = None

            equity_curve.append(capital)

        # 計算統計
        if len(trades) > 0:
            trades_df = pd.DataFrame(trades)
            wins = len(trades_df[trades_df["pnl"] > 0])
            losses = len(trades_df[trades_df["pnl"] <= 0])
            win_rate = wins / len(trades) * 100
            total_pnl = trades_df["pnl"].sum()
            avg_pnl = trades_df["pnl"].mean()
            max_drawdown = self._calculate_max_drawdown(equity_curve)

            # 計算盈虧比
            avg_win = trades_df[trades_df["pnl"] > 0]["pnl"].mean() if wins > 0 else 0
            avg_loss = abs(trades_df[trades_df["pnl"] <= 0]["pnl"].mean()) if losses > 0 else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

        else:
            win_rate = 0
            total_pnl = 0
            avg_pnl = 0
            max_drawdown = 0
            profit_factor = 0
            wins = 0
            losses = 0
            trades_df = pd.DataFrame()

        return {
            "initial_capital": initial_capital,
            "final_capital": capital,
            "total_return_pct": (capital - initial_capital) / initial_capital * 100,
            "total_trades": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "max_drawdown_pct": max_drawdown,
            "profit_factor": profit_factor,
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


if __name__ == "__main__":
    # 測試
    print("QQE Mod Strategy loaded successfully")
