===== 00_ARCHITECTURE.md 開始 =====

SuperDog 量化交易系統 - 架構總覽（v0.1）

本文件說明 SuperDog 系統的整體模組架構、職責、依賴關係與 3 個月開發規劃。

⸻

	1.	整體架構（Overview）

⸻

superdog-quant/
│
├── spec/                 # 規格文件
├── data/                 # 數據層
├── backtest/             # 回測層
├── strategies/           # 策略層
├── risk/                 # 風控層
├── live/                 # 實盤層
├── utils/                # 工具層
├── tests/                # 測試層
└── notebooks/            # 研究層

依賴關係（由底層向上）：
utils → data → backtest → strategies → risk → live

tests / notebooks 可測試或使用任一層的輸出。

⸻

	2.	模組職責（Module Responsibilities）

⸻

spec/
	•	模組說明、功能邊界、介面定義。
	•	v0.1 只寫 data module。

data/
	•	fetcher.py：下載 OHLCV（BTCUSDT, 1h）
	•	validator.py：缺漏、欄位檢查
	•	storage.py：存取 CSV（預留 Parquet 介面）
	•	raw/：原始數據

backtest/
	•	engine.py：主回測邏輯（使用 backtesting.py）
	•	broker.py：手續費、滑價
	•	metrics.py：績效指標
	•	reports/：回測輸出

strategies/
	•	base.py：策略 interface
	•	indicators.py：pandas-ta 的封裝
	•	trend_follow.py：第一個策略

risk/
	•	position_sizer.py：固定風險倉位
	•	stop_loss.py / take_profit.py：止損止盈邏輯
	•	portfolio.py：未來多策略管理

live/
	•	monitor.py：即時行情（未來 Phase）
	•	signal_generator.py：訊號
	•	executor.py：下單（測試網）
	•	telegram_bot.py：推播

utils/
	•	config.py：設定
	•	logger.py：log
	•	helpers.py：小工具
	•	database.py：未來 DB 使用

tests/
	•	各模組單元測試

notebooks/
	•	回測分析、資料探索

⸻

	3.	關鍵架構決策（Architecture Decisions）

⸻

3.1 數據存儲格式（決定）
	•	Phase 1：CSV
	•	Phase 2：Parquet（主力格式）
	•	Phase 3：可選 SQLite / Postgres
策略層永遠只吃 DataFrame。

3.2 回測框架（決定）
	•	Phase 1–2：backtesting.py
	•	Phase 3：必要時才寫自有引擎

3.3 指標庫（決定）
	•	Phase 1–2：pandas-ta
	•	封裝於 indicators.py

3.4 即時數據（決定）
	•	Phase 1–3 不做
	•	Phase 4：WebSocket（ccxt）

3.5 多幣種（決定）
	•	Phase 1–2：BTC
	•	Phase 3：3–5 幣種

⸻

	4.	三個月計畫（Roadmap）

⸻

Month 1：Data + Backtest
	•	完成 data module v0.1
	•	抓 BTCUSDT 1h 歷史資料（2020–2024）
	•	回測引擎雛形跑通假策略

Month 2：策略 + 風控
	•	完成 indicators.py
	•	完成 trend_follow v0.1
	•	完成風控模組（position_sizer + stop_loss）

Month 3：實盤 + 強化
	•	Telegram 推播
	•	多幣種
	•	Parquet 支援
	•	增加 tests、log、例外處理

===== 00_ARCHITECTURE.md 結束 =====
