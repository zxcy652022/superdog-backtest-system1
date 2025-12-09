"""
DualMA v2.0 多幣種多週期回測腳本

功能：
- 支援多幣種回測（Top 10 主流幣）
- 支援多時間週期（1個月、3個月、6個月、1年）
- 生成完整回測報表
- 參數可調整

Author: DDragon
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from backtest.engine import run_backtest
from data.storage import OHLCVStorage
from strategies.dual_ma_v2 import DualMAStrategyV2

# === 配置 ===

# Top 10 主流幣種
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "SOLUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "LINKUSDT",
]

# 回測週期配置
PERIODS = {
    "1M": 30,  # 1 個月
    "3M": 90,  # 3 個月
    "6M": 180,  # 6 個月
    "1Y": 365,  # 1 年
}

# 數據路徑
DATA_PATHS = [
    Path("/Volumes/權志龍的寶藏/SuperDogData/raw/binance/1h"),
    Path("data/raw/binance/1h"),
    Path("data/raw/1h"),
    Path("data/raw"),
]


def find_data_file(symbol: str) -> Optional[Path]:
    """尋找幣種數據文件"""
    for base_path in DATA_PATHS:
        file_path = base_path / f"{symbol}_1h.csv"
        if file_path.exists():
            return file_path
    return None


def load_data(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """
    載入數據並截取指定天數

    Args:
        symbol: 幣種
        days: 回測天數

    Returns:
        DataFrame 或 None
    """
    file_path = find_data_file(symbol)
    if file_path is None:
        print(f"  ⚠️  找不到 {symbol} 數據")
        return None

    storage = OHLCVStorage()
    df = storage.load_ohlcv(str(file_path))

    if df is None or len(df) == 0:
        return None

    # 截取最近 N 天
    end_time = df.index[-1]
    start_time = end_time - timedelta(days=days)
    df = df[df.index >= start_time]

    return df


def run_single_backtest(
    symbol: str,
    df: pd.DataFrame,
    params: Dict,
    initial_cash: float = 10000,
) -> Dict:
    """
    執行單個回測

    Returns:
        回測結果字典
    """
    try:
        # 分離 engine 參數和策略參數
        leverage = params.get("leverage", 10)

        # 創建自定義策略類（帶參數）
        class ConfiguredStrategy(DualMAStrategyV2):
            def __init__(self, broker, data):
                super().__init__(broker, data, **params)

        result = run_backtest(
            data=df,
            strategy_cls=ConfiguredStrategy,
            initial_cash=initial_cash,
            fee_rate=0.001,
            leverage=leverage,
        )

        metrics = result.metrics
        return {
            "symbol": symbol,
            "total_return": metrics.get("total_return", 0),
            "max_drawdown": metrics.get("max_drawdown", 0),
            "num_trades": metrics.get("num_trades", 0),
            "win_rate": metrics.get("win_rate", 0),
            "profit_factor": metrics.get("profit_factor", 0),
            "total_pnl": metrics.get("total_pnl", 0),
            "avg_trade_return": metrics.get("avg_trade_return", 0),
            "initial_equity": initial_cash,
            "final_equity": result.equity_curve.iloc[-1]
            if len(result.equity_curve) > 0
            else initial_cash,
            "data_points": len(df),
            "status": "success",
        }

    except Exception as e:
        return {
            "symbol": symbol,
            "status": "error",
            "error": str(e),
        }


def run_multi_backtest(
    symbols: List[str],
    period_name: str,
    period_days: int,
    params: Dict,
) -> List[Dict]:
    """
    執行多幣種回測

    Returns:
        所有回測結果列表
    """
    results = []

    print(f"\n{'='*60}")
    print(f"回測週期: {period_name} ({period_days} 天)")
    print(f"{'='*60}")

    for symbol in symbols:
        print(f"\n處理 {symbol}...")
        df = load_data(symbol, period_days)

        if df is None:
            results.append(
                {
                    "symbol": symbol,
                    "period": period_name,
                    "status": "no_data",
                }
            )
            continue

        print(f"  數據範圍: {df.index[0]} ~ {df.index[-1]}")
        print(f"  數據筆數: {len(df)}")

        result = run_single_backtest(symbol, df, params)
        result["period"] = period_name
        result["period_days"] = period_days
        results.append(result)

        if result.get("status") == "success":
            print(f"  ✅ 收益率: {result['total_return']:.2%}")
            print(f"     最大回撤: {result['max_drawdown']:.2%}")
            print(f"     交易次數: {result['num_trades']}")
            print(f"     勝率: {result['win_rate']:.2%}")

    return results


def generate_report(all_results: List[Dict], params: Dict) -> str:
    """生成回測報表"""

    report = []
    report.append("=" * 80)
    report.append("DualMA v2.0 多幣種多週期回測報告")
    report.append(f"生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)

    # 參數摘要
    report.append("\n📊 策略參數:")
    report.append("-" * 40)
    for key, value in params.items():
        report.append(f"  {key}: {value}")

    # 按週期分組
    for period_name in PERIODS.keys():
        period_results = [
            r
            for r in all_results
            if r.get("period") == period_name and r.get("status") == "success"
        ]

        if not period_results:
            continue

        report.append(f"\n\n{'='*60}")
        report.append(f"📈 {period_name} 回測結果")
        report.append("=" * 60)

        # 表頭
        report.append(f"\n{'幣種':<12} {'收益率':>10} {'最大回撤':>10} {'交易數':>8} {'勝率':>8} {'盈虧比':>8}")
        report.append("-" * 60)

        total_return_sum = 0
        for r in period_results:
            pf = r.get("profit_factor", 0)
            pf_str = f"{pf:.2f}" if pf and pf < 1000 else "∞" if pf else "N/A"

            report.append(
                f"{r['symbol']:<12} "
                f"{r['total_return']:>9.2%} "
                f"{r['max_drawdown']:>9.2%} "
                f"{r['num_trades']:>8} "
                f"{r['win_rate']:>7.2%} "
                f"{pf_str:>8}"
            )
            total_return_sum += r.get("total_return", 0)

        # 平均績效
        avg_return = total_return_sum / len(period_results) if period_results else 0
        avg_dd = (
            sum(r.get("max_drawdown", 0) for r in period_results) / len(period_results)
            if period_results
            else 0
        )
        avg_wr = (
            sum(r.get("win_rate", 0) for r in period_results) / len(period_results)
            if period_results
            else 0
        )

        report.append("-" * 60)
        report.append(f"{'平均':<12} {avg_return:>9.2%} {avg_dd:>9.2%} {'-':>8} {avg_wr:>7.2%}")

    # 總結
    success_results = [r for r in all_results if r.get("status") == "success"]
    report.append(f"\n\n{'='*60}")
    report.append("📊 總結")
    report.append("=" * 60)
    report.append(f"  總回測數: {len(all_results)}")
    report.append(f"  成功: {len(success_results)}")
    report.append(f"  失敗/無數據: {len(all_results) - len(success_results)}")

    if success_results:
        overall_avg = sum(r.get("total_return", 0) for r in success_results) / len(success_results)
        best = max(success_results, key=lambda x: x.get("total_return", 0))
        worst = min(success_results, key=lambda x: x.get("total_return", 0))

        report.append(f"\n  整體平均收益率: {overall_avg:.2%}")
        report.append(f"  最佳: {best['symbol']} ({best['period']}) - {best['total_return']:.2%}")
        report.append(f"  最差: {worst['symbol']} ({worst['period']}) - {worst['total_return']:.2%}")

    return "\n".join(report)


def main():
    """主函數"""
    print("=" * 60)
    print("DualMA v2.0 多幣種多週期回測")
    print("=" * 60)

    # 策略參數（可調整）
    params = {
        # 槓桿
        "leverage": 10,
        # 風險管理
        "risk_per_trade_pct": 0.01,  # 每筆風險 1%
        # 止盈 R 值
        "tp1_rr": 2.0,
        "tp2_rr": 4.0,
        "tp3_rr": 8.0,
        # 分批止盈
        "tp1_pct": 0.3,
        "tp2_pct": 0.3,
        # 加倉設定
        "enable_add_position": True,
        "add_position_mode": "floating_pnl",  # "fixed" 或 "floating_pnl"
        "add_position_pnl_pct": 1.0,  # 浮盈 100% 加倉
        "add_position_min_interval": 3,
        # 均線參數
        "ma_len_short": 20,
        "ma_len_mid": 60,
        "ma_len_long": 120,
        "cluster_threshold": 0.01,
    }

    print("\n📋 策略參數:")
    for k, v in params.items():
        print(f"  {k}: {v}")

    # 執行回測
    all_results = []

    for period_name, period_days in PERIODS.items():
        results = run_multi_backtest(SYMBOLS, period_name, period_days, params)
        all_results.extend(results)

    # 生成報表
    report = generate_report(all_results, params)
    print("\n" + report)

    # 保存結果
    output_dir = Path("data/experiments")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存 JSON
    json_path = output_dir / "dual_ma_v2_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str, ensure_ascii=False)
    print(f"\n💾 結果已保存至: {json_path}")

    # 保存報表
    report_path = output_dir / "dual_ma_v2_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"📄 報表已保存至: {report_path}")

    return all_results


if __name__ == "__main__":
    results = main()
