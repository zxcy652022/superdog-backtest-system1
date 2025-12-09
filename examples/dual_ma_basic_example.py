"""
測試 DualMA 策略
"""

from pathlib import Path

import pandas as pd

from backtest.engine import run_backtest
from data.paths import get_ohlcv_path
from data.storage import OHLCVStorage
from strategies.dual_ma_v1 import DualMAStrategyV1


def main():
    """執行 DualMA 策略回測"""
    print("=" * 60)
    print("DualMA 策略 v1.0 回測測試")
    print("=" * 60)

    # 1. 載入數據
    storage = OHLCVStorage()

    # 嘗試多個可能的數據路徑
    data_paths = [
        get_ohlcv_path("BTCUSDT", "1h"),
        Path("data/raw/BTCUSDT_1h.csv"),
        Path("data/raw/binance/1h/BTCUSDT_1h.csv"),
    ]

    df = None
    used_path = None
    for path in data_paths:
        if path.exists():
            print(f"\n載入數據: {path}")
            df = storage.load_ohlcv(str(path))
            used_path = path
            break

    if df is None:
        print("\n❌ 找不到 BTCUSDT 1h 數據文件")
        print("請先下載數據：")
        print("  from data.downloaders.robust_downloader import download_top_n")
        print("  download_top_n(n=10, timeframes=['1h'])")
        return

    print(f"數據範圍: {df.index[0]} ~ {df.index[-1]}")
    print(f"數據筆數: {len(df)}")

    # 2. 執行回測
    print("\n執行回測...")
    result = run_backtest(
        data=df,
        strategy_cls=DualMAStrategyV1,
        initial_cash=10000,
        fee_rate=0.001,
    )

    # 3. 顯示結果
    print("\n" + "=" * 60)
    print("DualMA 策略回測結果")
    print("=" * 60)

    metrics = result.metrics
    print(f"\n📊 績效指標:")
    print(f"  總收益率: {metrics['total_return']:.2%}")
    print(f"  最大回撤: {metrics['max_drawdown']:.2%}")
    print(f"  交易次數: {metrics['num_trades']}")
    print(f"  勝率: {metrics['win_rate']:.2%}")
    print(f"  平均交易收益: {metrics['avg_trade_return']:.2%}")
    print(f"  總損益: {metrics['total_pnl']:.2f}")
    print(f"  平均損益: {metrics['avg_pnl']:.2f}")

    if "profit_factor" in metrics and not pd.isna(metrics["profit_factor"]):
        print(f"  盈利因子: {metrics['profit_factor']:.2f}")
    if "win_loss_ratio" in metrics and not pd.isna(metrics["win_loss_ratio"]):
        print(f"  盈虧比: {metrics['win_loss_ratio']:.2f}")
    if "max_consecutive_loss" in metrics:
        print(f"  最大連續虧損: {metrics['max_consecutive_loss']} 次")
    if "max_consecutive_win" in metrics:
        print(f"  最大連續盈利: {metrics['max_consecutive_win']} 次")

    # 4. 顯示交易記錄
    if len(result.trades) > 0:
        print(f"\n📝 交易記錄 (共 {len(result.trades)} 筆):")
        print("-" * 80)

        # 使用 trade_log 如果有的話
        if result.trade_log is not None and not result.trade_log.empty:
            display_cols = [
                "entry_time",
                "exit_time",
                "entry_price",
                "exit_price",
                "pnl",
                "pnl_pct",
            ]
            available_cols = [c for c in display_cols if c in result.trade_log.columns]
            trade_df = result.trade_log[available_cols].head(10)
            print("\n前 10 筆交易:")
            print(trade_df.to_string(index=False))
        else:
            # 從 trades 列表構建
            print("\n前 10 筆交易:")
            for i, trade in enumerate(result.trades[:10], 1):
                print(
                    f"  {i}. {trade.entry_time.strftime('%Y-%m-%d %H:%M')} -> "
                    f"{trade.exit_time.strftime('%Y-%m-%d %H:%M')}"
                )
                print(f"     進場: {trade.entry_price:.2f} -> 出場: {trade.exit_price:.2f}")
                print(f"     損益: {trade.pnl:.2f} ({trade.return_pct:.2%})")
                print(f"     方向: {trade.direction}")
                print()

    # 5. 權益曲線統計
    if len(result.equity_curve) > 0:
        print(f"\n📈 權益曲線:")
        print(f"  初始資金: {result.equity_curve.iloc[0]:.2f}")
        print(f"  最終資金: {result.equity_curve.iloc[-1]:.2f}")
        print(f"  最高權益: {result.equity_curve.max():.2f}")
        print(f"  最低權益: {result.equity_curve.min():.2f}")

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)

    return result


if __name__ == "__main__":
    result = main()
