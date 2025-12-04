# SuperDog Backtest System

研究級加密貨幣回測引擎，專為量化交易策略研究設計。

## 🚀 快速開始

### 安裝

```bash
git clone https://github.com/zxcy652022/superdog-backtest-system1.git
cd superdog-backtest-system1
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 基本使用

```python
from data.storage import load_ohlcv
from backtest.engine import run_backtest
from backtest.position_sizer import PercentOfEquitySizer
from strategies.simple_sma import SimpleSMAStrategy

# 載入資料
data = load_ohlcv("data/raw/BTCUSDT_1h_test.csv")

# 執行回測
result = run_backtest(
    data=data,
    strategy_cls=SimpleSMAStrategy,
    initial_cash=10000,
    fee_rate=0.0005,
    position_sizer=PercentOfEquitySizer(percent=0.95)
)

# 查看結果
print(result.metrics)
print(result.trade_log)
```

### 執行測試

```bash
pytest
```

## 📊 目前功能

### ✅ v0.2 (已完成)
- **Position Sizer 系統**：AllIn / FixedCash / PercentOfEquity
- **停損停利**：盤中觸發（使用 high/low）
- **完整 Trade Log**：含 MAE/MFE、holding_bars、entry/exit_reason
- **進階 Metrics**：profit_factor、expectancy、win_loss_ratio、consecutive wins/losses

### 📋 v0.3 (規劃中)
- Portfolio Runner（批量回測）
- Strategy Registry（策略插件系統）
- 做空與槓桿支援（簡化模型）
- CLI 工具

## 📖 文件

- [架構說明](docs/architecture/overview.md)
- [開發哲學](docs/architecture/philosophy.md)
- [開發流程](docs/architecture/workflow.md)
- [技術規格](docs/specs/)
- [設計決策](docs/decisions/)
- [開發規範](docs/CONTRIBUTING.md)

## 🧪 測試涵蓋

- 回測引擎核心邏輯
- Position Sizer 各種模式
- SL/TP 觸發機制
- Trade Log 計算正確性
- Metrics 邊界條件

## 📝 版本歷史

詳見 [CHANGELOG.md](CHANGELOG.md)

## 🎯 專案目標

打造一套**可理解、可維護、可擴充**的量化研究系統，整合 AI 協作開發流程。

## 📄 授權

MIT License
