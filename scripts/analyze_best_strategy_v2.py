#!/usr/bin/env python3
"""
最佳策略深入分析 v2 - 使用標準績效統計格式
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.broker import SimulatedBroker
from strategies.bige_dual_ma import BiGeDualMAStrategy


def load_data(filepath: str) -> pd.DataFrame:
    """載入數據"""
    df = pd.read_csv(filepath)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    return df


def run_backtest(data: pd.DataFrame, initial_cash: float = 500, **kwargs) -> dict:
    """執行回測"""
    broker = SimulatedBroker(
        initial_cash=initial_cash,
        fee_rate=0.0004,
        leverage=kwargs.get("leverage", 10),
        maintenance_margin_rate=0.005,
    )

    strategy = BiGeDualMAStrategy(broker=broker, data=data, **kwargs)

    equity_curve = []
    peak_equity = initial_cash
    max_drawdown = 0.0

    for i, (timestamp, row) in enumerate(data.iterrows()):
        strategy.on_bar(i, row)
        current_equity = broker.get_current_equity(row["close"])
        equity_curve.append(current_equity)

        if current_equity > peak_equity:
            peak_equity = current_equity
        dd = (peak_equity - current_equity) / peak_equity
        if dd > max_drawdown:
            max_drawdown = dd

    final_equity = broker.get_current_equity(data.iloc[-1]["close"])
    trades = broker.trades
    winning = sum(1 for t in trades if t.pnl > 0)
    total_trades = len(trades)
    win_rate = winning / total_trades if total_trades > 0 else 0
    liquidation_count = sum(1 for t in trades if hasattr(t, "is_liquidation") and t.is_liquidation)

    return {
        "final_equity": final_equity,
        "total_return": (final_equity / initial_cash - 1) * 100,
        "max_drawdown": max_drawdown * 100,
        "total_trades": total_trades,
        "win_rate": win_rate * 100,
        "liquidation_count": liquidation_count,
        "equity_curve": equity_curve,
    }


def print_performance_table(title: str, results: list, key_field: str):
    """使用標準格式輸出績效表"""
    print(f"\n{'=' * 90}")
    print(f"{title}")
    print(f"{'=' * 90}")
    print(f"{'配置':<25} {'收益率':>15} {'最大回撤':>12} {'勝率':>10} {'交易數':>8} {'爆倉':>6}")
    print("-" * 90)

    for r in results:
        config_name = str(r[key_field])
        print(
            f"{config_name:<25} {r['return']:>14,.0f}% {r['max_dd']:>11.1f}% "
            f"{r['win_rate']:>9.1f}% {r['trades']:>8} {r['liquidations']:>6}"
        )

    print("-" * 90)

    # 找最佳
    best = max(results, key=lambda x: x["return"])
    best_risk_adj = max(results, key=lambda x: x["return"] / max(x["max_dd"], 1))

    print(f"✓ 最高收益: {best[key_field]} ({best['return']:,.0f}%)")
    print(
        f"✓ 最佳風險調整: {best_risk_adj[key_field]} (收益/回撤 = {best_risk_adj['return']/max(best_risk_adj['max_dd'],1):.1f})"
    )


def main():
    print("=" * 90)
    print("BiGe 雙均線策略 - 深度參數分析")
    print("=" * 90)

    # 載入數據
    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    print(f"\n載入數據: {data_path}")
    data = load_data(data_path)
    print(f"數據範圍: {data.index[0]} ~ {data.index[-1]}")
    print(f"共 {len(data)} 根 K 線")

    # ============================================================
    # 1. 槓桿對比
    # ============================================================
    leverage_results = []
    for leverage in [3, 5, 7, 10, 15, 20]:
        result = run_backtest(
            data.copy(),
            leverage=leverage,
            add_position_mode="fixed_50",
            trend_mode="loose",
        )
        leverage_results.append(
            {
                "leverage": f"{leverage}x",
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "trades": result["total_trades"],
                "liquidations": result["liquidation_count"],
            }
        )

    print_performance_table("1. 槓桿對比分析", leverage_results, "leverage")

    # ============================================================
    # 2. 止損確認根數對比
    # ============================================================
    stop_confirm_results = []
    for confirm_bars in [1, 3, 5, 7, 10, 15, 20]:
        result = run_backtest(
            data.copy(),
            leverage=10,
            add_position_mode="fixed_50",
            stop_loss_confirm_bars=confirm_bars,
            trend_mode="loose",
        )
        stop_confirm_results.append(
            {
                "confirm": f"{confirm_bars} 根",
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "trades": result["total_trades"],
                "liquidations": result["liquidation_count"],
            }
        )

    print_performance_table("2. 止損確認根數對比（10x 槓桿）", stop_confirm_results, "confirm")

    # ============================================================
    # 3. 最大加倉次數對比
    # ============================================================
    max_add_results = []
    for max_add in [1, 2, 3, 5, 7, 10, 15, 20]:
        result = run_backtest(
            data.copy(),
            leverage=10,
            add_position_mode="fixed_50",
            max_add_count=max_add,
            trend_mode="loose",
        )
        max_add_results.append(
            {
                "max_add": f"{max_add} 次",
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "trades": result["total_trades"],
                "liquidations": result["liquidation_count"],
            }
        )

    print_performance_table("3. 最大加倉次數對比（10x 槓桿）", max_add_results, "max_add")

    # ============================================================
    # 4. 回踩容許範圍對比
    # ============================================================
    pullback_results = []
    for tolerance in [0.010, 0.015, 0.018, 0.020, 0.025, 0.030]:
        result = run_backtest(
            data.copy(),
            leverage=10,
            add_position_mode="fixed_50",
            pullback_tolerance=tolerance,
            trend_mode="loose",
        )
        pullback_results.append(
            {
                "tolerance": f"{tolerance*100:.1f}%",
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "trades": result["total_trades"],
                "liquidations": result["liquidation_count"],
            }
        )

    print_performance_table("4. 回踩容許範圍對比（10x 槓桿）", pullback_results, "tolerance")

    # ============================================================
    # 5. MA20 緩衝對比
    # ============================================================
    buffer_results = []
    for buffer in [0.010, 0.015, 0.020, 0.025, 0.030]:
        result = run_backtest(
            data.copy(),
            leverage=10,
            add_position_mode="fixed_50",
            ma20_buffer=buffer,
            trend_mode="loose",
        )
        buffer_results.append(
            {
                "buffer": f"{buffer*100:.1f}%",
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "trades": result["total_trades"],
                "liquidations": result["liquidation_count"],
            }
        )

    print_performance_table("5. MA20 緩衝對比（10x 槓桿）", buffer_results, "buffer")

    # ============================================================
    # 6. 年度表現分析
    # ============================================================
    print(f"\n{'=' * 90}")
    print("6. 年度表現分析（10x 槓桿，最佳配置）")
    print(f"{'=' * 90}")
    print(f"{'年份':<10} {'收益率':>15} {'最大回撤':>12} {'勝率':>10} {'交易數':>8}")
    print("-" * 90)

    years = data.index.year.unique()
    yearly_returns = []

    for year in sorted(years):
        year_data = data[data.index.year == year]
        if len(year_data) < 100:
            continue

        result = run_backtest(
            year_data.copy(),
            leverage=10,
            add_position_mode="fixed_50",
            trend_mode="loose",
        )

        yearly_returns.append(result["total_return"])

        print(
            f"{year:<10} {result['total_return']:>+14,.0f}% {result['max_drawdown']:>11.1f}% "
            f"{result['win_rate']:>9.1f}% {result['total_trades']:>8}"
        )

    print("-" * 90)
    if yearly_returns:
        print(f"平均年收益: {sum(yearly_returns)/len(yearly_returns):,.0f}%")
        print(f"年度勝率: {sum(1 for r in yearly_returns if r > 0)}/{len(yearly_returns)}")

    # ============================================================
    # 7. 最終推薦配置
    # ============================================================
    print(f"\n{'=' * 90}")
    print("7. 推薦配置總結")
    print(f"{'=' * 90}")

    # 保守配置
    conservative = run_backtest(
        data.copy(),
        leverage=7,
        add_position_mode="fixed_50",
        max_add_count=3,
        trend_mode="loose",
    )

    # 平衡配置
    balanced = run_backtest(
        data.copy(),
        leverage=10,
        add_position_mode="fixed_50",
        max_add_count=5,
        trend_mode="loose",
    )

    # 積極配置
    aggressive = run_backtest(
        data.copy(),
        leverage=10,
        add_position_mode="fixed_50",
        max_add_count=10,
        trend_mode="loose",
    )

    configs = [
        {"name": "保守型 (7x, 3次加倉)", **conservative},
        {"name": "平衡型 (10x, 5次加倉)", **balanced},
        {"name": "積極型 (10x, 10次加倉)", **aggressive},
    ]

    print(f"\n{'配置':<30} {'收益率':>15} {'最大回撤':>12} {'勝率':>10} {'爆倉':>8}")
    print("-" * 90)

    for c in configs:
        print(
            f"{c['name']:<30} {c['total_return']:>14,.0f}% {c['max_drawdown']:>11.1f}% "
            f"{c['win_rate']:>9.1f}% {c['liquidation_count']:>8}"
        )

    print("-" * 90)

    print(
        """
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              推薦配置詳細                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  【保守型】適合新手                                                              │
│   • 槓桿: 7x                                                                    │
│   • 最大加倉: 3 次                                                              │
│   • 止損確認: 10 根 K 線                                                        │
│   • 趨勢模式: loose (MA20 > MA60)                                               │
│   • 預期年化: 100-200%                                                          │
│   • 最大回撤: ~45%                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  【平衡型】推薦配置                                                              │
│   • 槓桿: 10x                                                                   │
│   • 最大加倉: 5 次                                                              │
│   • 止損確認: 10 根 K 線                                                        │
│   • 趨勢模式: loose (MA20 > MA60)                                               │
│   • 預期年化: 200-400%                                                          │
│   • 最大回撤: ~75%                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  【積極型】高風險高收益                                                          │
│   • 槓桿: 10x                                                                   │
│   • 最大加倉: 10 次                                                             │
│   • 止損確認: 10 根 K 線                                                        │
│   • 趨勢模式: loose (MA20 > MA60)                                               │
│   • 預期年化: 500%+                                                             │
│   • 最大回撤: ~87%                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
"""
    )

    # ============================================================
    # 8. 核心參數建議
    # ============================================================
    print(f"{'=' * 90}")
    print("8. 核心參數建議")
    print(f"{'=' * 90}")
    print(
        """
  ┌────────────────────┬────────────────────────────────────────────────────────┐
  │ 參數               │ 建議值                                                  │
  ├────────────────────┼────────────────────────────────────────────────────────┤
  │ 槓桿               │ 7x（風險調整最佳） / 10x（絕對收益最佳）                  │
  │ 止損確認根數       │ 10 根（關鍵參數！太少會被假跌破掃損）                     │
  │ 加倉模式           │ fixed_50（固定 50%）                                    │
  │ 最大加倉次數       │ 3-5 次（保守） / 10 次（積極）                           │
  │ 趨勢模式           │ loose（MA20 > MA60）                                    │
  │ 回踩容許範圍       │ 1.8%                                                    │
  │ MA20 緩衝          │ 2.0%                                                    │
  │ 每筆倉位           │ 10%                                                     │
  └────────────────────┴────────────────────────────────────────────────────────┘
"""
    )


if __name__ == "__main__":
    main()
