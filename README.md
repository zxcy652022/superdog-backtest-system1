# SuperDog Backtest v0.3

研究級加密貨幣回測引擎，專為量化交易策略研究設計。v0.3 聚焦於多策略批量回測、方向感知風控、純文本報表與 CLI 入口。

## 新功能 (v0.3)

### 核心功能
- ✅ 做空交易支援 (Short Selling)
- ✅ 槓桿交易 (Leverage 1-100x)
- ✅ 方向感知的 SL/TP (Long/Short)
- ✅ 批量回測 (Portfolio Runner)
- ✅ 文本報表生成器
- ✅ 命令行介面 (CLI)

## 快速開始

### 安裝

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install click  # CLI 依賴
```

### 單策略回測

```bash
superdog run -s simple_sma -m BTCUSDT -t 1h --sl 0.02 --tp 0.05
```

### 批量回測

```bash
superdog portfolio -c configs/multi_strategy.yml -o report.txt
```

### Python API

```python
from execution_engine.portfolio_runner import RunConfig, run_portfolio

config = RunConfig(
    strategy="simple_sma",
    symbol="BTCUSDT",
    timeframe="1h",
    leverage=2.0,
    stop_loss_pct=0.02
)

result = run_portfolio([config], verbose=True)
print(result.summary())
```

## API 文檔

- **Broker v0.3**  
  `buy(size, price, time, leverage)` 開多/平空；`sell(...)` 開空/平多；`position_direction`；`is_long`/`is_short`
- **Engine v0.3**  
  `run_backtest(..., leverage=1.0)`；方向感知 `_check_sl_tp()`
- **Portfolio Runner v0.3**  
  `run_portfolio(configs)`；`RunConfig`；`PortfolioResult`；`load_configs_from_yaml(path)`
- **Text Reporter v0.3**  
  `render_single(result)`；`render_portfolio(result)`

## 測試

```bash
# 運行所有 v0.3 測試
python tests/test_broker_v03.py
python tests/test_engine_v03.py
python tests/test_portfolio_runner_v03.py
python tests/test_text_reporter_v03.py
python tests/test_cli_v03.py
python tests/test_integration_v03.py

# v0.2 向後兼容測試
python tests/test_backtest_v02.py
```

## 文件

- [架構說明](docs/architecture/overview.md)
- [開發哲學](docs/architecture/philosophy.md)
- [開發流程](docs/architecture/workflow.md)
- [技術規格](docs/specs/)
- [設計決策](docs/decisions/)
- [開發規範](docs/CONTRIBUTING.md)

## 版本歷史

詳見 [CHANGELOG.md](CHANGELOG.md)

## 授權

MIT License
