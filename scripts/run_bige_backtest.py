#!/usr/bin/env python3
"""
幣哥雙均線策略回測腳本

測試不同參數組合：
- 槓桿：5x, 10x, 20x, 50x
- 加倉模式：fixed_30, fixed_50, floating_pnl
- 止盈模式：fixed_r, fibonacci, ma20_break

使用方式:
  # 快速測試（Top 20）
  python scripts/run_bige_backtest.py --top 20

  # 完整測試
  python scripts/run_bige_backtest.py --top 100

  # 指定槓桿
  python scripts/run_bige_backtest.py --leverage 20

Version: v1.0
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.paths import get_raw_data_dir  # noqa: E402
from execution.runner import RunConfig, run_portfolio  # noqa: E402


def get_available_symbols(timeframe: str = "1h") -> list:
    """獲取已下載的幣種列表"""
    data_dir = get_raw_data_dir("binance") / timeframe
    if not data_dir.exists():
        return []

    symbols = []
    for f in data_dir.glob("*_*.csv"):
        symbol = f.stem.split("_")[0]
        symbols.append(symbol)

    return sorted(set(symbols))


def main():
    parser = argparse.ArgumentParser(description="幣哥雙均線策略回測")
    parser.add_argument("--strategy", default="bigedualma", help="策略名稱")
    parser.add_argument("--timeframes", default="1h,4h", help="時間週期")
    parser.add_argument("--top", type=int, default=50, help="Top N 幣種")
    parser.add_argument("--start", default="2024-06-01", help="開始日期")
    parser.add_argument("--end", default="2025-12-01", help="結束日期")
    parser.add_argument("--initial-cash", type=float, default=500, help="初始資金")
    parser.add_argument("--fee-rate", type=float, default=0.0005, help="手續費率")
    parser.add_argument("--leverage", type=int, default=10, help="槓桿倍數")
    parser.add_argument(
        "--add-mode",
        default="fixed_50",
        choices=["fixed_30", "fixed_50", "floating_pnl"],
        help="加倉模式",
    )
    parser.add_argument(
        "--tp-mode", default="fixed_r", choices=["fixed_r", "fibonacci", "ma20_break"], help="止盈模式"
    )
    parser.add_argument("--verbose", action="store_true", help="詳細輸出")
    args = parser.parse_args()

    timeframes = [t.strip() for t in args.timeframes.split(",")]

    # 獲取可用幣種
    all_symbols = None
    for tf in timeframes:
        symbols = set(get_available_symbols(tf))
        if all_symbols is None:
            all_symbols = symbols
        else:
            all_symbols = all_symbols & symbols

    all_symbols = sorted(all_symbols) if all_symbols else []

    if args.top:
        all_symbols = all_symbols[: args.top]

    print("=" * 60)
    print("🐕 SuperDog Quant - 幣哥雙均線策略回測")
    print("=" * 60)
    print(f"策略: {args.strategy}")
    print(f"幣種數量: {len(all_symbols)}")
    print(f"時間週期: {', '.join(timeframes)}")
    print(f"日期範圍: {args.start} ~ {args.end}")
    print(f"初始資金: {args.initial_cash} USDT")
    print(f"槓桿倍數: {args.leverage}x")
    print(f"加倉模式: {args.add_mode}")
    print(f"止盈模式: {args.tp_mode}")
    print(f"總回測數: {len(all_symbols) * len(timeframes)}")
    print("=" * 60)

    if not all_symbols:
        print("❌ 沒有找到可用的數據")
        return 1

    # 策略參數
    strategy_params = {
        "leverage": args.leverage,
        "add_position_mode": args.add_mode,
        "take_profit_mode": args.tp_mode,
        "position_size_pct": 0.10,  # 每筆 10%
    }

    # 建立配置
    configs = []
    for symbol in all_symbols:
        for tf in timeframes:
            config = RunConfig(
                strategy=args.strategy,
                symbol=symbol,
                timeframe=tf,
                start=args.start,
                end=args.end,
                initial_cash=args.initial_cash,
                fee_rate=args.fee_rate,
                strategy_params=strategy_params,
            )
            configs.append(config)

    print(f"\n🚀 開始回測 {len(configs)} 個任務...\n")
    result = run_portfolio(configs, verbose=args.verbose)

    # 顯示結果
    print("\n" + "=" * 60)
    print("📊 回測完成!")
    print("=" * 60)
    print(result.summary())

    # Top 10 最佳
    print("\n🏆 Top 10 最佳收益:")
    print("-" * 50)
    best = result.get_best_by("total_return", top_n=10)
    for i, r in enumerate(best, 1):
        ret = r.get_metric("total_return", 0)
        print(f"  {i:2d}. {r.symbol:12s} {r.timeframe:4s}  {ret:+.2%}")

    # Top 5 最差
    print("\n💀 Top 5 最差收益:")
    print("-" * 50)
    worst = result.get_worst_by("total_return", bottom_n=5)
    for i, r in enumerate(worst, 1):
        ret = r.get_metric("total_return", 0)
        print(f"  {i:2d}. {r.symbol:12s} {r.timeframe:4s}  {ret:+.2%}")

    # 統計
    df = result.to_dataframe()
    if not df.empty and "total_return" in df.columns:
        print("\n📈 統計:")
        print("-" * 50)
        print(f"  平均收益: {df['total_return'].mean():.2%}")
        print(f"  中位數: {df['total_return'].median():.2%}")
        print(f"  最大: {df['total_return'].max():.2%}")
        print(f"  最小: {df['total_return'].min():.2%}")
        print(f"  正收益: {(df['total_return'] > 0).sum()}/{len(df)}")
        print(f"  勝率: {(df['total_return'] > 0).sum()/len(df):.1%}")

        # 按槓桿和時間週期分組
        if "timeframe" in df.columns:
            print("\n📊 按時間週期:")
            for tf in df["timeframe"].unique():
                tf_df = df[df["timeframe"] == tf]
                avg_ret = tf_df["total_return"].mean()
                win_rate = (tf_df["total_return"] > 0).sum() / len(tf_df)
                print(f"  {tf}: 平均 {avg_ret:+.2%}, 勝率 {win_rate:.1%}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
