#!/usr/bin/env python3
"""
盈利驅動加倉策略測試

核心改變：
- 原策略：回踩 MA20 時加倉（可能已經漲了 30%+，成本高）
- 新策略：盈利達到 N% 時就加倉（趨勢初期就開始滾倉）

浮雲滾倉正確邏輯：
1. 進場後，盈利達到 10-20% 就用浮盈加倉
2. 不需要等回踩，趨勢持續就持續加
3. 加倉同時可以降低槓桿（保護利潤）
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


class ProfitBasedAddStrategy:
    """
    盈利驅動加倉策略

    核心改變：
    - 不在回踩時加倉
    - 盈利達到閾值時用浮盈加倉
    - 趨勢持續時持續滾倉
    """

    def __init__(self, broker, data, **kwargs):
        self.broker = broker
        self.data = data.copy()

        # 基礎參數
        self.leverage = kwargs.get("leverage", 7)
        self.position_size_pct = kwargs.get("position_size_pct", 0.10)

        # 盈利加倉參數
        self.profit_add_threshold = kwargs.get("profit_add_threshold", 0.15)  # 盈利 15% 時加倉
        self.profit_add_ratio = kwargs.get("profit_add_ratio", 1.0)  # 用 100% 浮盈加倉
        self.max_add_count = kwargs.get("max_add_count", 10)
        self.min_add_interval = kwargs.get("min_add_interval", 3)  # 最少間隔 3 根 K 線

        # 均線參數
        self.ma_short = kwargs.get("ma_short", 20)
        self.ma_mid = kwargs.get("ma_mid", 60)
        self.pullback_tolerance = kwargs.get("pullback_tolerance", 0.018)
        self.ma20_buffer = kwargs.get("ma20_buffer", 0.020)

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
        self.last_profit_pct = 0  # 上次加倉時的盈利比例

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
        """多單進場：回踩 MA20 + 趨勢確認"""
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
        """空單進場：反彈 MA20 + 趨勢確認"""
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

    def _get_current_profit_pct(self, current_price):
        """計算當前盈利比例"""
        if self.avg_entry_price is None or self.avg_entry_price <= 0:
            return 0

        if self.broker.is_long:
            return (current_price - self.avg_entry_price) / self.avg_entry_price
        else:
            return (self.avg_entry_price - current_price) / self.avg_entry_price

    def _check_profit_add(self, current_price, i):
        """
        盈利驅動加倉邏輯

        條件：
        1. 當前盈利 > 上次加倉盈利 + 閾值
        2. 間隔足夠
        3. 未達最大次數
        """
        if self.add_count >= self.max_add_count:
            return False

        if i - max(self.entry_bar, self.last_add_bar) < self.min_add_interval:
            return False

        current_profit = self._get_current_profit_pct(current_price)

        # 盈利必須超過閾值
        if current_profit < self.profit_add_threshold:
            return False

        # 盈利必須比上次加倉時增加了閾值
        if current_profit < self.last_profit_pct + self.profit_add_threshold:
            return False

        return True

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

        add_amount = unrealized_pnl * self.profit_add_ratio
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
        self.last_profit_pct = 0

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

            # 盈利驅動加倉（核心改變）
            if self._check_profit_add(current_price, i):
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
                        self.last_profit_pct = self._get_current_profit_pct(current_price)
            return

        # 無倉位：檢查進場（仍用回踩邏輯）
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
                    self.last_profit_pct = 0

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
                    self.last_profit_pct = 0


def run_backtest(df, **params):
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(initial_cash=INITIAL_CASH, slippage_rate=SLIPPAGE)
    strategy = ProfitBasedAddStrategy(broker, df.copy(), **params)

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


def fmt_ret(ret):
    if ret > 100000:
        return f"{ret/100:>+10,.0f}x"
    elif ret > 1000:
        return f"{ret:>+10,.0f}%"
    else:
        return f"{ret:>+10.0f}%"


def fmt_final(f):
    if f > 1e9:
        return f"${f/1e9:>12,.1f}B"
    elif f > 1e6:
        return f"${f/1e6:>12,.1f}M"
    else:
        return f"${f:>12,.0f}"


def test_profit_threshold():
    """測試不同盈利閾值"""
    print("=" * 100)
    print("1. 盈利閾值測試 - 7x 槓桿")
    print("=" * 100)
    print("\n盈利達到多少時加倉？\n")

    df = load_data("BTCUSDT")

    thresholds = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50]

    print(f"{'盈利閾值':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for th in thresholds:
        r = run_backtest(df.copy(), leverage=7, profit_add_threshold=th, max_add_count=100)
        if r:
            print(
                f"{th*100:.0f}%{'':<9} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_add_ratio():
    """測試不同浮盈加倉比例"""
    print("\n" + "=" * 100)
    print("2. 浮盈加倉比例 - 7x + 15% 盈利閾值")
    print("=" * 100)
    print("\n每次用多少比例的浮盈加倉？\n")

    df = load_data("BTCUSDT")

    ratios = [0.25, 0.50, 0.75, 1.0, 1.5, 2.0]

    print(f"{'浮盈比例':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for ratio in ratios:
        r = run_backtest(
            df.copy(),
            leverage=7,
            profit_add_threshold=0.15,
            profit_add_ratio=ratio,
            max_add_count=100,
        )
        if r:
            print(
                f"{ratio*100:.0f}%{'':<9} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_max_add_count():
    """測試最大加倉次數"""
    print("\n" + "=" * 100)
    print("3. 加倉次數限制 - 7x + 15% 閾值 + 100% 浮盈")
    print("=" * 100)

    df = load_data("BTCUSDT")

    counts = [3, 5, 10, 20, 50, 100]

    print(f"\n{'最大次數':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for cnt in counts:
        r = run_backtest(
            df.copy(),
            leverage=7,
            profit_add_threshold=0.15,
            profit_add_ratio=1.0,
            max_add_count=cnt,
        )
        if r:
            print(
                f"{cnt:<12} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_leverage():
    """測試不同槓桿"""
    print("\n" + "=" * 100)
    print("4. 槓桿測試 - 15% 閾值 + 100% 浮盈 + 無限加倉")
    print("=" * 100)

    df = load_data("BTCUSDT")

    leverages = [3, 5, 7, 10, 15, 20]

    print(f"\n{'槓桿':<12} {'最終資金':>14} {'收益':>12} {'回撤':>10} {'爆倉':>6} {'勝率':>8}")
    print("-" * 70)

    for lev in leverages:
        r = run_backtest(
            df.copy(),
            leverage=lev,
            profit_add_threshold=0.15,
            profit_add_ratio=1.0,
            max_add_count=100,
        )
        if r:
            print(
                f"{lev}x{'':<10} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )


def test_combined():
    """組合優化"""
    print("\n" + "=" * 100)
    print("5. 組合優化 - 尋找回撤 < 60% 的最佳配置")
    print("=" * 100)

    df = load_data("BTCUSDT")

    results = []

    for lev in [5, 7, 10]:
        for threshold in [0.10, 0.15, 0.20]:
            for ratio in [0.5, 1.0, 1.5]:
                for max_add in [5, 10, 20, 100]:
                    r = run_backtest(
                        df.copy(),
                        leverage=lev,
                        profit_add_threshold=threshold,
                        profit_add_ratio=ratio,
                        max_add_count=max_add,
                    )
                    if r:
                        results.append(
                            {
                                "leverage": lev,
                                "threshold": threshold,
                                "ratio": ratio,
                                "max_add": max_add,
                                "return": r["return_pct"],
                                "max_dd": r["max_dd"],
                                "liquidations": r["liquidations"],
                            }
                        )

    # 篩選回撤 < 60% 且無爆倉
    valid = [r for r in results if r["max_dd"] > -60 and r["liquidations"] == 0]
    valid.sort(key=lambda x: x["return"], reverse=True)

    print(f"\n回撤 < 60% 且無爆倉（按收益排序 Top 15）：\n")
    print(f"{'槓桿':<6} {'閾值':<8} {'浮盈比例':<10} {'加倉上限':<10} {'收益':>12} {'回撤':>10}")
    print("-" * 65)

    for c in valid[:15]:
        add_str = f"{c['max_add']}" if c["max_add"] < 100 else "無限"
        print(
            f"{c['leverage']}x{'':<4} {c['threshold']*100:.0f}%{'':<5} {c['ratio']*100:.0f}%{'':<7} {add_str:<10} {fmt_ret(c['return'])} {c['max_dd']:>9.1f}%"
        )

    if not valid:
        print("（沒有符合條件的配置，放寬條件...）")
        # 放寬到 < 70%
        valid = [r for r in results if r["max_dd"] > -70]
        valid.sort(key=lambda x: x["return"], reverse=True)
        print(f"\n回撤 < 70%（按收益排序 Top 15）：\n")
        for c in valid[:15]:
            add_str = f"{c['max_add']}" if c["max_add"] < 100 else "無限"
            liq_str = f"({c['liquidations']}爆)" if c["liquidations"] > 0 else ""
            print(
                f"{c['leverage']}x{'':<4} {c['threshold']*100:.0f}%{'':<5} {c['ratio']*100:.0f}%{'':<7} {add_str:<10} {fmt_ret(c['return'])} {c['max_dd']:>9.1f}% {liq_str}"
            )


def test_yearly():
    """逐年測試"""
    print("\n" + "=" * 100)
    print("6. 逐年比較")
    print("=" * 100)

    df = load_data("BTCUSDT")
    years = [2020, 2021, 2022, 2023, 2024]

    configs = [
        {
            "name": "盈利15%+7x",
            "leverage": 7,
            "profit_add_threshold": 0.15,
            "profit_add_ratio": 1.0,
            "max_add_count": 100,
        },
        {
            "name": "盈利10%+7x",
            "leverage": 7,
            "profit_add_threshold": 0.10,
            "profit_add_ratio": 1.0,
            "max_add_count": 100,
        },
        {
            "name": "盈利20%+10x",
            "leverage": 10,
            "profit_add_threshold": 0.20,
            "profit_add_ratio": 1.0,
            "max_add_count": 100,
        },
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
                        "liquidations": r["liquidations"],
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
    print("7. 多幣種驗證 - 盈利 15% 閾值 + 7x + 100% 浮盈")
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
        r = run_backtest(
            df.copy(),
            leverage=7,
            profit_add_threshold=0.15,
            profit_add_ratio=1.0,
            max_add_count=100,
        )

        if r:
            results.append(r)
            print(
                f"{coin:<12} {fmt_final(r['final'])} {fmt_ret(r['return_pct'])} {r['max_dd']:>9.1f}% {r['liquidations']:>6} {r['win_rate']:>7.0f}%"
            )

    print("-" * 70)
    avg_ret = np.mean([r["return_pct"] for r in results])
    avg_dd = np.mean([r["max_dd"] for r in results])
    profitable = sum(1 for r in results if r["return_pct"] > 0)
    print(
        f"{'平均':<12} {'':>14} {fmt_ret(avg_ret)} {avg_dd:>9.1f}% {'':>6} {profitable}/{len(results)}"
    )


def main():
    test_profit_threshold()
    test_add_ratio()
    test_max_add_count()
    test_leverage()
    test_combined()
    test_yearly()
    test_multi_coin()

    print("\n" + "=" * 100)
    print("結論")
    print("=" * 100)
    print(
        """
盈利驅動加倉策略分析：

核心改變：
- 不再等「回踩 MA20」才加倉
- 盈利達到閾值（如 15%）時就用浮盈加倉
- 趨勢持續時持續滾倉

與原策略對比：
- 原策略（回踩加倉）：回踩時可能已漲 30%+，成本高
- 新策略（盈利加倉）：趨勢初期就開始加倉，成本低

適用場景：
- 需要大趨勢行情
- 幣哥策略的高盈虧比特性正好適合
"""
    )


if __name__ == "__main__":
    main()
