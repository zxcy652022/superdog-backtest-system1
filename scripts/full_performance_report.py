#!/usr/bin/env python3
"""
完整績效報告 - BiGe 雙均線策略

配置：
- 槓桿：5x（現實配置，避免爆倉）
- 爆倉檢測：啟用
- 滑點：0.05%
- 加倉：無限制

報告內容：
1. 多幣種回測（Top 20）
2. 逐年績效
3. 分季度績效
4. 隨機抽樣測試
5. Buy & Hold 比較
6. 風險指標
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

os.environ["DATA_ROOT"] = "/Volumes/權志龍的寶藏/Data"

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy

# === 配置 ===
INITIAL_CASH = 500
LEVERAGE = 5  # 5x 槓桿（現實配置）
SLIPPAGE = 0.0005  # 0.05%

TOP_20_COINS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "SHIBUSDT",
    "DOTUSDT",
    "LINKUSDT",
    "TRXUSDT",
    "MATICUSDT",
    "UNIUSDT",
    "NEARUSDT",
    "LTCUSDT",
    "APTUSDT",
    "FILUSDT",
    "ARBUSDT",
    "OPUSDT",
]


def load_data(symbol: str, timeframe: str = "4h") -> pd.DataFrame:
    """載入歷史數據"""
    data_path = f"/Volumes/權志龍的寶藏/SuperDogData/raw/binance/{timeframe}/{symbol}_{timeframe}.csv"
    if not os.path.exists(data_path):
        return None
    df = pd.read_csv(data_path)
    df.columns = [c.lower() for c in df.columns]
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
    return df


def run_backtest(df: pd.DataFrame) -> Dict:
    """執行回測"""
    if df is None or len(df) < 200:
        return None

    broker = SimulatedBroker(
        initial_cash=INITIAL_CASH,
        slippage_rate=SLIPPAGE,
    )

    strategy = BiGeDualMAStrategy(
        broker,
        df.copy(),
        leverage=LEVERAGE,
        dynamic_leverage=False,
        enable_add_position=True,
        max_add_count=100,
        max_drawdown_pct=1.0,
    )

    peak = INITIAL_CASH
    max_dd = 0
    equity_curve = []

    for i, (idx, row) in enumerate(strategy.data.iterrows()):
        strategy.on_bar(i, row)
        eq = broker.get_current_equity(row["close"])
        equity_curve.append((idx, eq))
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
    lose_trades = [t for t in trades if t.pnl < 0]

    # Buy & Hold 計算
    bh_return = (df.iloc[-1]["close"] / df.iloc[0]["close"] - 1) * 100

    return {
        "final": broker.cash,
        "return_pct": (broker.cash / INITIAL_CASH - 1) * 100,
        "trades": len(trades),
        "win_trades": len(win_trades),
        "lose_trades": len(lose_trades),
        "win_rate": len(win_trades) / len(trades) * 100 if trades else 0,
        "max_dd": max_dd * 100,
        "profit_factor": sum(t.pnl for t in win_trades) / abs(sum(t.pnl for t in lose_trades))
        if lose_trades
        else float("inf"),
        "avg_win": np.mean([t.pnl for t in win_trades]) if win_trades else 0,
        "avg_lose": np.mean([t.pnl for t in lose_trades]) if lose_trades else 0,
        "bh_return": bh_return,
        "liquidations": broker.liquidation_count,
        "equity_curve": equity_curve,
    }


def print_header(title: str):
    """打印標題"""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def section_config():
    """打印配置"""
    print_header("BiGe 雙均線策略 - 完整績效報告")
    print(
        f"""
┌────────────────────────────────────────────────────────────────┐
│  策略配置                                                      │
├────────────────────────────────────────────────────────────────┤
│  初始資金：${INITIAL_CASH:<10}                                    │
│  槓桿倍數：{LEVERAGE}x                                             │
│  滑點率：  {SLIPPAGE*100:.2f}%                                          │
│  爆倉檢測：啟用                                                │
│  加倉限制：無限制                                              │
│  時間框架：4H                                                  │
└────────────────────────────────────────────────────────────────┘
"""
    )


def section_multi_coin():
    """多幣種回測"""
    print_header("1. 多幣種回測 (Top 20)")

    results = []

    for symbol in TOP_20_COINS:
        df = load_data(symbol)
        if df is None:
            continue

        # 全期回測
        r = run_backtest(df)
        if r:
            results.append(
                {
                    "symbol": symbol.replace("USDT", ""),
                    "return_pct": r["return_pct"],
                    "win_rate": r["win_rate"],
                    "max_dd": r["max_dd"],
                    "trades": r["trades"],
                    "bh_return": r["bh_return"],
                    "profit_factor": r["profit_factor"],
                    "liquidations": r["liquidations"],
                }
            )

    # 按收益排序
    results.sort(key=lambda x: x["return_pct"], reverse=True)

    print(
        f"\n{'幣種':<8} {'策略收益':>14} {'BH收益':>12} {'超額α':>10} {'勝率':>8} {'回撤':>8} {'盈虧比':>8} {'交易':>6} {'爆倉':>6}"
    )
    print("-" * 95)

    for r in results:
        alpha = r["return_pct"] - r["bh_return"]
        pf = f"{r['profit_factor']:.1f}" if r["profit_factor"] != float("inf") else "∞"

        # 格式化收益
        if r["return_pct"] > 10000:
            ret_str = f"{r['return_pct']/100:>+12.0f}x"
        else:
            ret_str = f"{r['return_pct']:>+12.0f}%"

        if r["bh_return"] > 10000:
            bh_str = f"{r['bh_return']/100:>+10.0f}x"
        else:
            bh_str = f"{r['bh_return']:>+10.0f}%"

        if abs(alpha) > 10000:
            alpha_str = f"{alpha/100:>+8.0f}x"
        else:
            alpha_str = f"{alpha:>+8.0f}%"

        print(
            f"{r['symbol']:<8} {ret_str} {bh_str} {alpha_str} {r['win_rate']:>7.0f}% {r['max_dd']:>7.1f}% {pf:>8} {r['trades']:>6} {r['liquidations']:>6}"
        )

    # 統計
    print("-" * 95)
    returns = [r["return_pct"] for r in results]
    bh_returns = [r["bh_return"] for r in results]
    profitable = len([r for r in returns if r > 0])
    beat_bh = len([r for r in results if r["return_pct"] > r["bh_return"]])

    print(f"\n統計摘要：")
    print(f"  測試幣種：{len(results)}")
    print(f"  盈利幣種：{profitable} ({profitable/len(results)*100:.0f}%)")
    print(f"  打敗 BH：{beat_bh} ({beat_bh/len(results)*100:.0f}%)")
    print(f"  平均收益：{np.mean(returns):+,.0f}%")
    print(f"  中位數收益：{np.median(returns):+,.0f}%")
    print(f"  平均 BH：{np.mean(bh_returns):+,.0f}%")

    return results


def section_yearly(symbol: str = "BTCUSDT"):
    """逐年績效"""
    print_header(f"2. 逐年績效 ({symbol.replace('USDT', '')})")

    df = load_data(symbol)
    years = sorted(df.index.year.unique())

    results = []

    print(
        f"\n{'年份':<8} {'策略收益':>14} {'BH收益':>12} {'超額α':>10} {'勝率':>8} {'回撤':>8} {'交易':>6} {'爆倉':>6}"
    )
    print("-" * 80)

    for year in years:
        df_year = df[df.index.year == year]
        if len(df_year) < 200:
            continue

        r = run_backtest(df_year)
        if r:
            alpha = r["return_pct"] - r["bh_return"]

            # 格式化
            if r["return_pct"] > 1000:
                ret_str = f"{r['return_pct']/100:>+12.0f}x"
            else:
                ret_str = f"{r['return_pct']:>+12.0f}%"

            if r["bh_return"] > 1000:
                bh_str = f"{r['bh_return']/100:>+10.0f}x"
            else:
                bh_str = f"{r['bh_return']:>+10.0f}%"

            print(
                f"{year:<8} {ret_str} {bh_str} {alpha:>+10.0f}% {r['win_rate']:>7.0f}% {r['max_dd']:>7.1f}% {r['trades']:>6} {r['liquidations']:>6}"
            )

            results.append(
                {
                    "year": year,
                    "return_pct": r["return_pct"],
                    "bh_return": r["bh_return"],
                    "win_rate": r["win_rate"],
                    "max_dd": r["max_dd"],
                }
            )

    # 複利計算
    cumulative = 1.0
    bh_cumulative = 1.0
    for r in results:
        cumulative *= 1 + r["return_pct"] / 100
        bh_cumulative *= 1 + r["bh_return"] / 100

    print("-" * 80)
    print(f"{'累計':<8} {(cumulative-1)*100:>+12.0f}%{'':>2} {(bh_cumulative-1)*100:>+10.0f}%")

    # 統計
    returns = [r["return_pct"] for r in results]
    profitable_years = len([r for r in returns if r > 0])

    print(f"\n統計：")
    print(f"  測試年數：{len(results)}")
    print(f"  盈利年數：{profitable_years} ({profitable_years/len(results)*100:.0f}%)")
    print(f"  平均年收益：{np.mean(returns):+,.0f}%")
    print(f"  複利累計：{cumulative:.0f}x")

    return results


def section_quarterly(symbol: str = "BTCUSDT"):
    """分季度績效"""
    print_header(f"3. 分季度績效 ({symbol.replace('USDT', '')} 2020-2024)")

    df = load_data(symbol)

    results = []

    print(f"\n{'季度':<10} {'行情':<6} {'BTC漲跌':>10} {'策略收益':>12} {'勝率':>8} {'回撤':>8} {'交易':>6}")
    print("-" * 70)

    for year in range(2020, 2025):
        for q in range(1, 5):
            start_month = (q - 1) * 3 + 1
            end_month = q * 3

            df_q = df[
                (df.index.year == year)
                & (df.index.month >= start_month)
                & (df.index.month <= end_month)
            ]

            if len(df_q) < 50:
                continue

            r = run_backtest(df_q)
            if r:
                btc_return = r["bh_return"]
                market = "牛" if btc_return > 15 else ("熊" if btc_return < -15 else "震盪")

                quarter_str = f"{year}Q{q}"
                print(
                    f"{quarter_str:<10} {market:<6} {btc_return:>+10.1f}% {r['return_pct']:>+10.1f}% {r['win_rate']:>7.0f}% {r['max_dd']:>7.1f}% {r['trades']:>6}"
                )

                results.append(
                    {
                        "quarter": quarter_str,
                        "market": market,
                        "btc_return": btc_return,
                        "return_pct": r["return_pct"],
                    }
                )

    # 按行情分類統計
    print("-" * 70)

    bull = [r for r in results if r["market"] == "牛"]
    bear = [r for r in results if r["market"] == "熊"]
    sideways = [r for r in results if r["market"] == "震盪"]

    print(f"\n按行情類型統計：")
    if bull:
        bull_returns = [r["return_pct"] for r in bull]
        bull_win = len([r for r in bull_returns if r > 0])
        print(
            f"  牛市 ({len(bull)}季)：平均 {np.mean(bull_returns):+.0f}%，勝率 {bull_win/len(bull)*100:.0f}%"
        )
    if bear:
        bear_returns = [r["return_pct"] for r in bear]
        bear_win = len([r for r in bear_returns if r > 0])
        print(
            f"  熊市 ({len(bear)}季)：平均 {np.mean(bear_returns):+.0f}%，勝率 {bear_win/len(bear)*100:.0f}%"
        )
    if sideways:
        sideways_returns = [r["return_pct"] for r in sideways]
        sideways_win = len([r for r in sideways_returns if r > 0])
        print(
            f"  震盪 ({len(sideways)}季)：平均 {np.mean(sideways_returns):+.0f}%，勝率 {sideways_win/len(sideways)*100:.0f}%"
        )

    # 總勝率
    all_returns = [r["return_pct"] for r in results]
    total_win = len([r for r in all_returns if r > 0])
    print(f"\n  總季度勝率：{total_win}/{len(results)} ({total_win/len(results)*100:.0f}%)")

    return results


def section_random_sampling(symbol: str = "BTCUSDT", num_tests: int = 20):
    """隨機抽樣測試"""
    print_header(f"4. 隨機抽樣測試 ({symbol.replace('USDT', '')})")

    df = load_data(symbol)

    random.seed(42)
    results = []

    print(f"\n{'測試':<6} {'期間':<24} {'策略收益':>12} {'BH收益':>10} {'勝率':>8} {'回撤':>8}")
    print("-" * 75)

    for i in range(num_tests):
        # 隨機選擇 6-18 個月的區間
        months = random.randint(6, 18)
        max_start = len(df) - months * 30 * 6  # 4H K線
        if max_start < 0:
            continue

        start_idx = random.randint(0, max_start)
        end_idx = start_idx + months * 30 * 6

        df_sample = df.iloc[start_idx:end_idx]
        if len(df_sample) < 200:
            continue

        r = run_backtest(df_sample)
        if r:
            start_date = df_sample.index[0].strftime("%Y-%m-%d")
            end_date = df_sample.index[-1].strftime("%Y-%m-%d")
            period = f"{start_date} ~ {end_date}"

            print(
                f"{i+1:<6} {period:<24} {r['return_pct']:>+10.0f}% {r['bh_return']:>+8.0f}% {r['win_rate']:>7.0f}% {r['max_dd']:>7.1f}%"
            )

            results.append(
                {
                    "return_pct": r["return_pct"],
                    "bh_return": r["bh_return"],
                    "win_rate": r["win_rate"],
                }
            )

    # 統計
    print("-" * 75)
    returns = [r["return_pct"] for r in results]
    profitable = len([r for r in returns if r > 0])
    beat_bh = len([r for r in results if r["return_pct"] > r["bh_return"]])

    print(f"\n統計：")
    print(f"  測試次數：{len(results)}")
    print(f"  盈利次數：{profitable} ({profitable/len(results)*100:.0f}%)")
    print(f"  打敗 BH：{beat_bh} ({beat_bh/len(results)*100:.0f}%)")
    print(f"  平均收益：{np.mean(returns):+,.0f}%")
    print(f"  收益標準差：{np.std(returns):,.0f}%")

    return results


def section_risk_metrics(symbol: str = "BTCUSDT"):
    """風險指標"""
    print_header(f"5. 風險指標 ({symbol.replace('USDT', '')} 全期)")

    df = load_data(symbol)
    r = run_backtest(df)

    if not r:
        print("無法計算")
        return

    # 計算更多指標
    equity_curve = r["equity_curve"]
    equities = [e[1] for e in equity_curve]

    # 計算日收益率（以 6 根 4H K線 = 1天）
    daily_equities = equities[::6]
    daily_returns = []
    for i in range(1, len(daily_equities)):
        ret = (daily_equities[i] - daily_equities[i - 1]) / daily_equities[i - 1]
        daily_returns.append(ret)

    # 夏普比率（假設無風險利率 = 0）
    if daily_returns:
        avg_daily_return = np.mean(daily_returns)
        std_daily_return = np.std(daily_returns)
        sharpe = (
            (avg_daily_return * 365) / (std_daily_return * np.sqrt(365))
            if std_daily_return > 0
            else 0
        )
    else:
        sharpe = 0

    # 卡瑪比率
    calmar = r["return_pct"] / abs(r["max_dd"]) if r["max_dd"] != 0 else 0

    # 盈虧比
    rr_ratio = abs(r["avg_win"] / r["avg_lose"]) if r["avg_lose"] != 0 else float("inf")

    print(
        f"""
┌────────────────────────────────────────────────────────────────┐
│  績效指標                                                      │
├────────────────────────────────────────────────────────────────┤
│  總收益率：{r['return_pct']:>+,.0f}%{'':<40}│
│  Buy & Hold：{r['bh_return']:>+,.0f}%{'':<38}│
│  超額收益 α：{r['return_pct'] - r['bh_return']:>+,.0f}%{'':<38}│
├────────────────────────────────────────────────────────────────┤
│  交易統計                                                      │
├────────────────────────────────────────────────────────────────┤
│  總交易數：{r['trades']:<50}│
│  獲勝交易：{r['win_trades']:<50}│
│  虧損交易：{r['lose_trades']:<50}│
│  勝率：{r['win_rate']:.1f}%{'':<52}│
│  平均獲利：${r['avg_win']:,.2f}{'':<44}│
│  平均虧損：${r['avg_lose']:,.2f}{'':<44}│
│  盈虧比：{rr_ratio:.2f}{'':<51}│
├────────────────────────────────────────────────────────────────┤
│  風險指標                                                      │
├────────────────────────────────────────────────────────────────┤
│  最大回撤：{r['max_dd']:.1f}%{'':<49}│
│  爆倉次數：{r['liquidations']:<50}│
│  夏普比率：{sharpe:.2f}{'':<50}│
│  卡瑪比率：{calmar:.2f}{'':<50}│
│  盈虧比因子：{r['profit_factor']:.2f}{'':<47}│
└────────────────────────────────────────────────────────────────┘
"""
    )

    return r


def section_summary(
    coin_results: List, yearly_results: List, quarterly_results: List, random_results: List
):
    """總結"""
    print_header("6. 總結")

    # 計算各項統計
    coin_returns = [r["return_pct"] for r in coin_results]
    coin_profitable = len([r for r in coin_returns if r > 0])

    yearly_returns = [r["return_pct"] for r in yearly_results]
    yearly_profitable = len([r for r in yearly_returns if r > 0])

    quarterly_returns = [r["return_pct"] for r in quarterly_results]
    quarterly_profitable = len([r for r in quarterly_returns if r > 0])

    random_returns = [r["return_pct"] for r in random_results]
    random_profitable = len([r for r in random_returns if r > 0])

    print(
        f"""
┌────────────────────────────────────────────────────────────────────────────┐
│  策略穩健性評估                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  測試維度              測試數量        盈利數量        勝率                │
├────────────────────────────────────────────────────────────────────────────┤
│  多幣種適應性          {len(coin_results):<15} {coin_profitable:<15} {coin_profitable/len(coin_results)*100:>5.0f}%              │
│  年度穩定性            {len(yearly_results):<15} {yearly_profitable:<15} {yearly_profitable/len(yearly_results)*100:>5.0f}%              │
│  季度一致性            {len(quarterly_results):<15} {quarterly_profitable:<15} {quarterly_profitable/len(quarterly_results)*100:>5.0f}%              │
│  隨機抽樣              {len(random_results):<15} {random_profitable:<15} {random_profitable/len(random_results)*100:>5.0f}%              │
├────────────────────────────────────────────────────────────────────────────┤
│  綜合評估                                                                  │
├────────────────────────────────────────────────────────────────────────────┤
"""
    )

    # 綜合評分
    scores = [
        coin_profitable / len(coin_results),
        yearly_profitable / len(yearly_results),
        quarterly_profitable / len(quarterly_results),
        random_profitable / len(random_results),
    ]
    avg_score = np.mean(scores) * 100

    if avg_score >= 80:
        rating = "優秀 ★★★★★"
        comment = "策略具有極高穩健性，適合實盤使用"
    elif avg_score >= 65:
        rating = "良好 ★★★★☆"
        comment = "策略穩健性良好，建議小倉位實盤測試"
    elif avg_score >= 50:
        rating = "一般 ★★★☆☆"
        comment = "策略有一定適應性，需謹慎使用"
    else:
        rating = "較差 ★★☆☆☆"
        comment = "策略穩健性不足，不建議實盤"

    print(f"│  綜合勝率：{avg_score:.0f}%{'':<62}│")
    print(f"│  評級：{rating:<67}│")
    print(f"│  建議：{comment:<58}│")
    print("└────────────────────────────────────────────────────────────────────────────┘")

    print(
        f"""
風險提示：
- 回測結果不代表未來表現
- 最大回撤可達 50-70%，需有心理準備
- 建議使用可承受損失的資金
- 實盤前建議先進行模擬交易
"""
    )


def main():
    """主函數"""
    section_config()

    # 1. 多幣種回測
    coin_results = section_multi_coin()

    # 2. 逐年績效
    yearly_results = section_yearly("BTCUSDT")

    # 3. 分季度績效
    quarterly_results = section_quarterly("BTCUSDT")

    # 4. 隨機抽樣
    random_results = section_random_sampling("BTCUSDT", num_tests=20)

    # 5. 風險指標
    section_risk_metrics("BTCUSDT")

    # 6. 總結
    section_summary(coin_results, yearly_results, quarterly_results, random_results)


if __name__ == "__main__":
    main()
