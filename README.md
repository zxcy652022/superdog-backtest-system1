========================
README.md

SuperDog Backtest System

This repository is the backtest engine and research system for the SuperDog（幣圈警犬俠）交易計劃。

本專案不是一般回測框架，而是為了未來整合：
	•	CLI 工具
	•	TradingView 策略
	•	加密貨幣研究流程
	•	AI 協作開發流程

所打造的一個「可長期演化的量化研究專案」。

⸻

專案目前狀態（Project Status）

Data Module v0.1：已完成
	•	CSV 載入功能
	•	資料驗證與格式整理
	•	範例資料：BTCUSDT_1h_test.csv

Backtest Engine v0.1：已完成
	•	backtest/broker.py 模擬交易所
	•	模擬買入與賣出
	•	全倉進出（buy_all / sell_all）
	•	手續費與資金追蹤
	•	backtest/engine.py 回測引擎核心
	•	BaseStrategy 抽象類別
	•	主回測流程 run_backtest
	•	backtest/metrics.py 指標模組
	•	基本績效計算
	•	strategies/simple_sma.py 策略模組
	•	SMA 均線交叉測試策略
	•	tests/test_backtest.py 測試模組
	•	所有測試通過

Backtest Engine v0.2：規劃中
	•	持倉比例與資金管理
	•	停損／停利
	•	擴充績效指標
	•	更完整的交易紀錄（Trade log）

⸻

資料夾結構簡述

backtest/        回測引擎與模擬交易所
data/            資料載入與整理模組
spec/            各版本設計文件
strategies/      策略實作
tests/           單元測試
docs/            文件（預留）
utils/           工具模組（預留）

⸻

基本使用範例

from data.storage import load_ohlcv
from backtest.engine import run_backtest
from strategies.simple_sma import SimpleSMAStrategy

data = load_ohlcv(“data/raw/BTCUSDT_1h_test.csv”)

result = run_backtest(
data=data,
strategy_cls=SimpleSMAStrategy,
initial_cash=10000,
fee_rate=0.0005
)

print(result.metrics)

⸻

版本規則

專案版本以模組里程碑為主：

v0.1 = 能正常跑回測
v0.2 = 加入資金控管與風險
v0.3 = 多策略 / 多商品
後續版本逐步導入 CLI 與自動化決策

詳見 CHANGELOG.md

⸻

如果你剛 clone 此專案

請先執行：

pytest

檢查所有測試有無通過。

⸻

本計畫目標

打造一套：
可理解、可維護、可延伸、可自動化、可升級
的完整交易研究與回測系統。

這裡不是單純寫程式，而是打造一個可以進化的「幣圈警犬實驗室」。
