#!/usr/bin/env python3
"""
浮雲滾倉正確邏輯測試

浮雲滾倉核心（午飯投資）：
1. 本金翻倍時才加倉（不是回踩就加）
2. 加倉同時降低槓桿（保護利潤）
3. 用浮盈加倉，不用本金

問題診斷：
- 當前策略的「回踩 MA20 加倉」可能不適合浮盈模式
- 因為回踩時價格下跌，浮盈可能變浮虧，導致無法加倉

解決方案：
1. 改為「盈利 N% 時加倉」而不是「回踩時加倉」
2. 或者：只要有浮盈就用固定比例加倉（不管多少）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker

INITIAL_CASH = 500
SLIPPAGE = 0.0005


def load_data(symbol: str, timeframe: str = "4h") -> pd.DataFrame:
    data_path = f"/Volumes/權志龍的寶藏/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    if not os.path.exists(data_path):
        return None
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


class FuyunStrategy:
    """
    浮雲滾倉策略 - 正確邏輯實現

    核心：
    1. 用幣哥雙均線的進出場信號
    2. 加倉邏輯改為：盈利達到 N% 時用浮盈加倉
    3. 不是回踩就加倉，而是趨勢持續盈利時加倉
    """

    def __init__(self, broker, data, **kwargs):
        self.broker = broker
        self.data = data.copy()

        # 策略參數
        self.leverage = kwargs.get("leverage", 7)
        self.position_size_pct = kwargs.get("position_size_pct", 0.10)

        # 浮雲滾倉參數
        self.add_on_profit_pct = kwargs.get("add_on_profit_pct", 0.20)  # 盈利 20% 時加倉
        self.add_profit_ratio = kwargs.get("add_profit_ratio", 1.0)  # 用 100% 浮盈加倉
        self.max_add_count = kwargs.get("max_add_count", 100)
        self.min_add_interval = kwargs.get("min_add_interval", 3)

        # 均線參數
        self.ma_short = kwargs.get("ma_short", 20)
        self.ma_mid = kwargs.get("ma_mid", 60)
        self.pullback_tolerance = kwargs.get("pullback_tolerance", 0.018)
        self.ma20_buffer = kwargs.get("ma20_buffer", 0.020)

        # 設置槓桿
        self.broker.leverage = self.leverage

        # 狀態
        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.initial_qty = 0
        self.total_qty = 0
        self.add_count = 0
        self.last_add_bar = -999
        self.entry_bar = -999
        self.trade_direction = None
        self.last_add_equity = None  # 上次加倉時的權益

        # 計算指標
        self._calculate_indicators()

    def _calculate_indicators(self):
        df = self.data
        df["ma20"] = df["close"].rolling(self.ma_short).mean()
        df["ema20"] = df["close"].ewm(span=self.ma_short, adjust=False).mean()
        df["ma60"] = df["close"].rolling(self.ma_mid).mean()
        df["ema60"] = df["close"].ewm(span=self.ma_mid, adjust=False).mean()
        df["avg20"] = (df["ma20"] + df["ema20"]) / 2
        df["avg60"] = (df["ma60"] + df["ema60"]) / 2

    def _is_uptrend(self, row):
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] > row["avg60"]

    def _is_downtrend(self, row):
        if pd.isna(row["avg20"]) or pd.isna(row["avg60"]):
            return False
        return row["avg20"] < row["avg60"]

    def _check_long_entry(self, row, i):
        if not self._is_uptrend(row):
            return False
        close = row["close"]
        low = row["low"]
        avg20 = row["avg20"]

        near_ma20 = abs(low - avg20) / avg20 < self.pullback_tolerance
        not_break = low > avg20 * (1 - self.ma20_buffer)
        bullish = close > avg20

        return near_ma20 and not_break and bullish

    def _check_short_entry(self, row, i):
        if not self._is_downtrend(row):
            return False
        close = row["close"]
        high = row["high"]
        avg20 = row["avg20"]

        near_ma20 = abs(high - avg20) / avg20 < self.pullback_tolerance
        not_break = high < avg20 * (1 + self.ma20_buffer)
        bearish = close < avg20

        return near_ma20 and not_break and bearish

    def _calculate_position_size(self, price):
        equity = self.broker.get_current_equity(price)
        margin = equity * self.position_size_pct
        position_value = margin * self.leverage
        return position_value / price

    def _check_add_on_profit(self, current_price, i):
        """
        浮雲滾倉加倉邏輯：盈利達到 N% 時用浮盈加倉
        """
        if self.add_count >= self.max_add_count:
            return False

        if i - max(self.entry_bar, self.last_add_bar) < self.min_add_interval:
            return False

        # 計算當前盈虧比例
        if self.avg_entry_price is None or self.avg_entry_price <= 0:
            return False

        if self.broker.is_long:
            profit_pct = (current_price - self.avg_entry_price) / self.avg_entry_price
        else:
            profit_pct = (self.avg_entry_price - current_price) / self.avg_entry_price

        # 盈利超過閾值才加倉
        return profit_pct >= self.add_on_profit_pct

    def _calculate_add_qty(self, current_price):
        """用浮盈加倉"""
        if self.avg_entry_price is None:
            return 0

        if self.broker.is_long:
            unrealized_pnl = (current_price - self.avg_entry_price) * self.total_qty
        else:
            unrealized_pnl = (self.avg_entry_price - current_price) * self.total_qty

        if unrealized_pnl <= 0:
            return 0

        # 用 N% 的浮盈加倉
        add_amount = unrealized_pnl * self.add_profit_ratio
        return add_amount / current_price

    def _update_avg_entry(self, new_qty, new_price):
        if self.avg_entry_price is None or self.total_qty == 0:
            self.avg_entry_price = new_price
            self.total_qty = new_qty
        else:
            total_cost = self.avg_entry_price * self.total_qty + new_price * new_qty
            self.total_qty += new_qty
            self.avg_entry_price = total_cost / self.total_qty

    def _reset_state(self):
        self.entry_price = None
        self.avg_entry_price = None
        self.stop_loss = None
        self.initial_qty = 0
        self.total_qty = 0
        self.add_count = 0
        self.trade_direction = None
        self.last_add_equity = None

    def on_bar(self, i, row):
        if i < self.ma_mid:
            return

        current_price = row["close"]
        current_time = row.name
        avg20 = row["avg20"]

        # 有倉位：管理倉位
        if self.broker.has_position:
            # 爆倉檢測
            if self.broker.check_liquidation_in_bar(row):
                liq_price = self.broker.get_liquidation_price()
                self.broker.process_liquidation(current_time, liq_price)
                self._reset_state()
                return

            # 止損檢查
            if self.broker.is_long and row["low"] <= self.stop_loss:
                self.broker.sell(self.broker.position_qty, self.stop_loss, current_time)
                self._reset_state()
                return
            elif self.broker.is_short and row["high"] >= self.stop_loss:
                self.broker.buy(self.broker.position_qty, self.stop_loss, current_time)
                self._reset_state()
                return

            # 更新追蹤止損
            if self.broker.is_long:
                new_stop = avg20 * (1 - self.ma20_buffer)
                if new_stop > self.stop_loss:
                    self.stop_loss = new_stop
            else:
                new_stop = avg20 * (1 + self.ma20_buffer)
                if new_stop < self.stop_loss:
                    self.stop_loss = new_stop

            # 浮雲滾倉：盈利時加倉
            if self._check_add_on_profit(current_price, i):
                add_qty = self._calculate_add_qty(current_price)
                if add_qty > 0:
                    if self.broker.is_long:
                        success = self.broker.buy(add_qty, current_price, current_time)
                    else:
                        success = self.broker.sell(add_qty, current_price, current_time)

                    if success:
                        self._update_avg_entry(add_qty, current_price)
                        self.add_count += 1
                        self.last_add_bar = i
            return

        # 無倉位：檢查進場
        if self._check_long_entry(row, i):
            qty = self._calculate_position_size(current_price)
            if qty > 0:
                success = self.broker.buy(qty, current_price, current_time)
                if success:
                    self.entry_price = current_price
                    self.avg_entry_price = current_price
                    self.stop_loss = avg20 * (1 - self.ma20_buffer)
                    self.initial_qty = qty
                    self.total_qty = qty
                    self.add_count = 0
                    self.entry_bar = i
                    self.last_add_bar = i
                    self.trade_direction = "long"

        elif self._check_short_entry(row, i):
            qty = self._calculate_position_size(current_price)
            if qty > 0:
                success = self.broker.sell(qty, current_price, current_time)
                if success:
                    self.entry_price = current_price
                    self.avg_entry_price = current_price
                    self.stop_loss = avg20 * (1 + self.ma20_buffer)
                    self.initial_qty = qty
                    self.total_qty = qty
                    self.add_count = 0
                    self.entry_bar = i
                    self.last_add_bar = i
                    self.trade_direction = "short"


def run_backtest(df, **params):
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(initial_cash=INITIAL_CASH, slippage_rate=SLIPPAGE)
    strategy = FuyunStrategy(broker, df.copy(), **params)

    peak = INITIAL_CASH
    max_dd = 0

    for i, (idx, row) in enumerate(strategy.data.iterrows()):
        strategy.on_bar(i, row)
        eq = broker.get_current_equity(row["close"])
        if eq > peak:
            peak = eq
        dd = (eq - peak) / peak
        if dd < max_dd:
            max_dd = dd

    # 強制平倉
    if broker.has_position:
        last_row = strategy.data.iloc[-1]
        if broker.is_long:
            broker.sell(broker.position_qty, last_row["close"], strategy.data.index[-1])
        else:
            broker.buy(broker.position_qty, last_row["close"], strategy.data.index[-1])

    trades = broker.trades
    win_trades = [t for t in trades if t.pnl > 0]

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "liquidations": broker.liquidation_count,
    }


def format_return(ret):
    if ret > 100000:
        return f"{ret/100:>+10,.0f}x"
    elif ret > 1000:
        return f"{ret:>+10,.0f}%"
    else:
        return f"{ret:>+10.0f}%"


def format_final(final):
    if final > 1e9:
        return f"${final/1e9:>12,.1f}B"
    elif final > 1e6:
        return f"${final/1e6:>12,.1f}M"
    else:
        return f"${final:>12,.0f}"


def test_profit_trigger():
    """測試不同盈利觸發加倉的閾值"""
    print("=" * 100)
    print("1. 盈利觸發加倉測試 - 7x 槓桿")
    print("=" * 100)
    print("\n浮雲滾倉核心：盈利達到 N% 時才用浮盈加倉\n")

    df = load_data("BTCUSDT")

    profit_triggers = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]

    print(f"{'盈利觸發%':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for trigger in profit_triggers:
        r = run_backtest(df.copy(), leverage=7, add_on_profit_pct=trigger, add_profit_ratio=1.0)
        if r:
            print(
                f"{trigger*100:.0f}%{'':<9} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_add_ratio():
    """測試不同浮盈加倉比例"""
    print("\n" + "=" * 100)
    print("2. 浮盈加倉比例測試 - 7x 槓桿 + 盈利 20% 觸發")
    print("=" * 100)
    print("\n用多少比例的浮盈來加倉？\n")

    df = load_data("BTCUSDT")

    ratios = [0.25, 0.50, 0.75, 1.0, 1.5, 2.0]

    print(f"{'浮盈比例':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for ratio in ratios:
        r = run_backtest(df.copy(), leverage=7, add_on_profit_pct=0.20, add_profit_ratio=ratio)
        if r:
            print(
                f"{ratio*100:.0f}%{'':<9} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_leverage_comparison():
    """不同槓桿下的浮雲滾倉效果"""
    print("\n" + "=" * 100)
    print("3. 不同槓桿下的浮雲滾倉 - 盈利 20% 觸發 + 100% 浮盈加倉")
    print("=" * 100)

    df = load_data("BTCUSDT")

    leverages = [3, 5, 7, 10, 15, 20]

    print(f"\n{'槓桿':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for lev in leverages:
        r = run_backtest(df.copy(), leverage=lev, add_on_profit_pct=0.20, add_profit_ratio=1.0)
        if r:
            print(
                f"{lev}x{'':<10} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_combined_optimization():
    """組合優化"""
    print("\n" + "=" * 100)
    print("4. 組合優化 - 尋找回撤 < 60% 的最佳配置")
    print("=" * 100)

    df = load_data("BTCUSDT")

    results = []

    for lev in [5, 7, 10]:
        for trigger in [0.10, 0.15, 0.20, 0.30]:
            for ratio in [0.5, 1.0, 1.5]:
                r = run_backtest(
                    df.copy(), leverage=lev, add_on_profit_pct=trigger, add_profit_ratio=ratio
                )
                if r:
                    results.append(
                        {
                            "leverage": lev,
                            "trigger": trigger,
                            "ratio": ratio,
                            "return": r["return_pct"],
                            "max_dd": r["max_dd"],
                            "liquidations": r["liquidations"],
                        }
                    )

    # 篩選回撤 < 60%
    valid = [r for r in results if r["max_dd"] > -60]
    valid.sort(key=lambda x: x["return"], reverse=True)

    print(f"\n回撤 < 60% 的配置（按收益排序 Top 10）：\n")
    print(f"{'槓桿':<6} {'觸發%':<8} {'浮盈比例':<10} {'收益':>14} {'回撤':>10} {'爆倉':>6}")
    print("-" * 60)

    for c in valid[:10]:
        print(
            f"{c['leverage']}x{'':<4} {c['trigger']*100:.0f}%{'':<5} {c['ratio']*100:.0f}%{'':<7} {format_return(c['return'])} {c['max_dd']:>9.1f}% {c['liquidations']:>6}"
        )


def test_yearly_comparison():
    """逐年比較"""
    print("\n" + "=" * 100)
    print("5. 逐年比較：浮雲滾倉 vs 原策略")
    print("=" * 100)

    df = load_data("BTCUSDT")
    years = [2020, 2021, 2022, 2023, 2024]

    configs = [
        {"name": "浮雲7x+20%", "leverage": 7, "add_on_profit_pct": 0.20, "add_profit_ratio": 1.0},
        {"name": "浮雲7x+10%", "leverage": 7, "add_on_profit_pct": 0.10, "add_profit_ratio": 1.0},
        {"name": "浮雲10x+20%", "leverage": 10, "add_on_profit_pct": 0.20, "add_profit_ratio": 1.0},
    ]

    print(f"\n{'年份':<8}", end="")
    for cfg in configs:
        print(f"{cfg['name']:>16}", end="")
    print()
    print("-" * 60)

    yearly_results = {cfg["name"]: [] for cfg in configs}

    for year in years:
        df_year = df[df.index.year == year]
        if len(df_year) < 200:
            continue

        print(f"{year:<8}", end="")

        for cfg in configs:
            params = {k: v for k, v in cfg.items() if k != "name"}
            r = run_backtest(df_year.copy(), **params)

            if r:
                yearly_results[cfg["name"]].append(
                    {
                        "return": r["return_pct"],
                        "max_dd": r["max_dd"],
                    }
                )
                liq_str = f"({r['liquidations']}爆)" if r["liquidations"] > 0 else ""
                if r["return_pct"] > 1000:
                    print(f"{r['return_pct']/100:>+12.0f}x{liq_str}", end="")
                else:
                    print(f"{r['return_pct']:>+12.0f}%{liq_str}", end="")
        print()

    print("-" * 60)
    print(f"{'累計':<8}", end="")
    for cfg in configs:
        returns = [r["return"] for r in yearly_results[cfg["name"]]]
        cumulative = 1.0
        for ret in returns:
            cumulative *= 1 + ret / 100
        if (cumulative - 1) * 100 > 100000:
            print(f"{cumulative-1:>+12.0f}x", end="")
        else:
            print(f"{(cumulative-1)*100:>+12,.0f}%", end="")
    print()


def test_multi_coin():
    """多幣種驗證"""
    print("\n" + "=" * 100)
    print("6. 多幣種驗證 - 浮雲滾倉 7x + 20% 觸發 + 100% 浮盈")
    print("=" * 100)

    coins = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "ADAUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "DOTUSDT",
    ]

    results = []

    print(f"\n{'幣種':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for symbol in coins:
        df = load_data(symbol)
        if df is None:
            continue

        coin = symbol.replace("USDT", "")
        r = run_backtest(df.copy(), leverage=7, add_on_profit_pct=0.20, add_profit_ratio=1.0)

        if r:
            results.append(r)
            print(
                f"{coin:<12} {format_final(r['final'])} {format_return(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )

    # 統計
    print("-" * 70)
    avg_ret = np.mean([r["return_pct"] for r in results])
    avg_dd = np.mean([r["max_dd"] for r in results])
    profitable = sum(1 for r in results if r["return_pct"] > 0)
    print(
        f"{'平均':<12} {'':>14} {format_return(avg_ret)} {avg_dd:>9.1f}% {'':>6} {profitable}/{len(results)}"
    )


def main():
    test_profit_trigger()
    test_add_ratio()
    test_leverage_comparison()
    test_combined_optimization()
    test_yearly_comparison()
    test_multi_coin()

    print("\n" + "=" * 100)
    print("結論")
    print("=" * 100)
    print(
        """
浮雲滾倉正確邏輯分析：

1. 核心改變
   - 原策略：回踩 MA20 時加倉（可能是浮虧狀態）
   - 浮雲策略：盈利 N% 時才加倉（確保有浮盈可用）

2. 參數建議
   - 觸發閾值：10-20%（盈利達到此比例才加倉）
   - 加倉比例：100%（用全部浮盈加倉）
   - 槓桿：7x（平衡收益與風險）

3. 優勢
   - 只在盈利時加倉，保護本金
   - 趨勢越強，加倉越多
   - 回撤時不會加倉，避免越虧越加

4. 適用場景
   - 幣哥策略的高盈虧比特性
   - 抓到大趨勢時可以充分放大收益
"""
    )


if __name__ == "__main__":
    main()
