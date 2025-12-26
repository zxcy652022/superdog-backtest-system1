#!/usr/bin/env python3
"""
最佳策略深入分析

分析 BiGe 回踩 + 固定50%加倉 策略的各個面向：
1. 不同槓桿對比
2. 不同加倉比例對比
3. 不同止損方式對比
4. 年度表現分析
5. 牛熊市表現分析
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


def run_yearly_analysis(data: pd.DataFrame, params: dict) -> dict:
    """年度表現分析"""
    years = data.index.year.unique()
    results = {}

    for year in sorted(years):
        year_data = data[data.index.year == year]
        if len(year_data) < 100:  # 至少 100 根 K 線
            continue

        result = run_backtest(year_data.copy(), **params)
        results[year] = result

    return results


def main():
    print("=" * 80)
    print("BiGe 最佳策略深入分析")
    print("=" * 80)

    # 載入數據
    data_path = "/Volumes/權志龍的寶藏/SuperDogData/raw/binance/4h/BTCUSDT_4h.csv"
    print(f"\n載入數據: {data_path}")
    data = load_data(data_path)
    print(f"數據範圍: {data.index[0]} ~ {data.index[-1]}")
    print(f"共 {len(data)} 根 K 線")

    # ============================================================
    # 1. 槓桿對比
    # ============================================================
    print("\n" + "=" * 80)
    print("1. 槓桿對比分析")
    print("=" * 80)

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
        print(
            f"  {leverage}x: {result['total_return']:,.0f}% 收益, "
            f"{result['max_drawdown']:.1f}% 回撤, "
            f"{result['liquidation_count']} 爆倉"
        )

    # 找最佳槓桿
    best_leverage = max(leverage_results, key=lambda x: x["return"])
    print(f"\n  ✓ 最佳槓桿: {best_leverage['leverage']} " f"({best_leverage['return']:,.0f}% 收益)")

    # ============================================================
    # 2. 加倉比例對比
    # ============================================================
    print("\n" + "=" * 80)
    print("2. 加倉比例對比分析")
    print("=" * 80)

    add_pct_results = []
    for add_pct in [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 1.0]:
        result = run_backtest(
            data.copy(),
            leverage=10,
            add_position_mode="fixed_50",
            add_position_fixed_pct=add_pct,
            trend_mode="loose",
        )
        add_pct_results.append(
            {
                "add_pct": f"{int(add_pct*100)}%",
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "liquidations": result["liquidation_count"],
            }
        )
        print(
            f"  {int(add_pct*100)}%: {result['total_return']:,.0f}% 收益, "
            f"{result['max_drawdown']:.1f}% 回撤"
        )

    best_add = max(add_pct_results, key=lambda x: x["return"])
    print(f"\n  ✓ 最佳加倉比例: {best_add['add_pct']} " f"({best_add['return']:,.0f}% 收益)")

    # ============================================================
    # 3. 止損確認根數對比
    # ============================================================
    print("\n" + "=" * 80)
    print("3. 止損確認根數對比分析")
    print("=" * 80)

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
                "confirm_bars": confirm_bars,
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
                "trades": result["total_trades"],
            }
        )
        print(
            f"  {confirm_bars} 根: {result['total_return']:,.0f}% 收益, "
            f"{result['max_drawdown']:.1f}% 回撤, "
            f"{result['total_trades']} 交易"
        )

    best_confirm = max(stop_confirm_results, key=lambda x: x["return"])
    print(f"\n  ✓ 最佳確認根數: {best_confirm['confirm_bars']} " f"({best_confirm['return']:,.0f}% 收益)")

    # ============================================================
    # 4. 最大加倉次數對比
    # ============================================================
    print("\n" + "=" * 80)
    print("4. 最大加倉次數對比分析")
    print("=" * 80)

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
                "max_add": max_add,
                "return": result["total_return"],
                "max_dd": result["max_drawdown"],
                "win_rate": result["win_rate"],
            }
        )
        print(
            f"  最多 {max_add} 次: {result['total_return']:,.0f}% 收益, "
            f"{result['max_drawdown']:.1f}% 回撤"
        )

    best_max_add = max(max_add_results, key=lambda x: x["return"])
    print(f"\n  ✓ 最佳加倉次數: {best_max_add['max_add']} " f"({best_max_add['return']:,.0f}% 收益)")

    # ============================================================
    # 5. 年度表現分析
    # ============================================================
    print("\n" + "=" * 80)
    print("5. 年度表現分析（使用最佳配置）")
    print("=" * 80)

    best_params = {
        "leverage": 10,
        "add_position_mode": "fixed_50",
        "trend_mode": "loose",
    }

    yearly_results = run_yearly_analysis(data, best_params)

    for year, result in yearly_results.items():
        print(
            f"  {year}: {result['total_return']:+,.0f}% 收益, "
            f"{result['max_drawdown']:.1f}% 回撤, "
            f"{result['total_trades']} 交易, "
            f"{result['win_rate']:.1f}% 勝率"
        )

    # 計算年化收益
    total_years = len(yearly_results)
    if total_years > 0:
        avg_return = sum(r["total_return"] for r in yearly_results.values()) / total_years
        print(f"\n  平均年收益: {avg_return:,.0f}%")

    # ============================================================
    # 6. 最佳配置總結
    # ============================================================
    print("\n" + "=" * 80)
    print("6. 最佳配置總結")
    print("=" * 80)

    # 使用最佳參數組合運行
    final_result = run_backtest(
        data.copy(),
        leverage=10,
        add_position_mode="fixed_50",
        add_position_fixed_pct=0.50,
        max_add_count=best_max_add["max_add"],
        stop_loss_confirm_bars=best_confirm["confirm_bars"],
        trend_mode="loose",
    )

    print(
        f"""
  推薦配置:
  ─────────────────────────────────
  槓桿倍數:       10x
  加倉模式:       固定 50%
  加倉比例:       {best_add['add_pct']}
  最大加倉次數:   {best_max_add['max_add']}
  止損確認根數:   {best_confirm['confirm_bars']}
  趨勢模式:       loose (MA20 > MA60)
  ─────────────────────────────────
  預期績效:
  總收益率:       {final_result['total_return']:,.0f}%
  最大回撤:       {final_result['max_drawdown']:.1f}%
  勝率:           {final_result['win_rate']:.1f}%
  總交易數:       {final_result['total_trades']}
  爆倉次數:       {final_result['liquidation_count']}
  ─────────────────────────────────
"""
    )

    # ============================================================
    # 7. 風險調整收益分析
    # ============================================================
    print("=" * 80)
    print("7. 風險調整收益分析")
    print("=" * 80)

    # 計算不同槓桿的風險調整收益
    print("\n  槓桿     收益率      回撤     收益/回撤")
    print("  " + "-" * 45)
    for r in leverage_results:
        risk_adj = r["return"] / max(r["max_dd"], 1)
        print(
            f"  {r['leverage']:>5s}  {r['return']:>10,.0f}%  {r['max_dd']:>6.1f}%  {risk_adj:>10.1f}"
        )

    best_risk_adj = max(leverage_results, key=lambda x: x["return"] / max(x["max_dd"], 1))
    print(f"\n  ✓ 風險調整收益最佳: {best_risk_adj['leverage']}")


if __name__ == "__main__":
    main()
