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
===== 00_PHILOSOPHY.md 開始 =====

SuperDog 核心哲學（v0.1）

本文件說明 SuperDog 系統的「交易哲學與開發哲學」。

⸻

	1.	交易哲學（Trading Philosophy）

⸻

1.1 趨勢優先
	•	系統第一階段專注順勢策略，因為最通用、最易回測且風控清晰。

1.2 固定風險
	•	倉位大小 = (固定風險金額) / (停損距離)
	•	不加碼、不重壓、不猜底。

1.3 接受虧損
	•	虧損是成本，不是錯誤。
	•	追求穩定期望值，不追求連勝。

1.4 重視期望值 > 重視勝率
	•	（勝率 × 平均獲利）－（虧損率 × 平均虧損）才是最重要的。

⸻

	2.	開發哲學（Development Principles）

⸻

2.1 先能跑，再寫漂亮
	•	MVP 原則：可運行 > 完美。

2.2 規章來自痛點，不是想像
	•	遇到同類問題 3 次以上 → 才寫成文件。

2.3 模組化但不過度工程化
	•	只拆有必要的，不提前預支未來 5 年的需求。

2.4 小步快跑
	•	commit 應該小而頻繁。

⸻

	3.	三 AI 分工

⸻

3.1 ChatGPT（架構師 / 交易邏輯）
	•	設計系統架構
	•	設計策略與風控邏輯
	•	審核 Claude 的 code
	•	釐清需求與 spec

3.2 Claude（工程實作）
	•	撰寫 Python 程式
	•	重構與模組化
	•	撰寫 docstring
	•	按 spec 完成功能

3.3 NotebookLM（知識庫）
	•	收集回測結果
	•	彙整技術文章
	•	查詢專案歷史
	•	不記錄 meta 對話

⸻

	4.	人類角色（你）

⸻

	•	你是最終決策者
	•	你決定方向與優先順序
	•	AI 是加速器，但不替你承擔風險

===== 00_PHILOSOPHY.md 結束 =====
===== 00_WORKFLOW.md 開始 =====

SuperDog 系統開發流程（v0.1）

⸻

	1.	新模組開發流程

⸻

Step 1：需求釐清（你 ↔ GPT）
Step 2：撰寫 spec（放進 spec/*.md）
Step 3：Claude 實作
Step 4：你本地測試
Step 5：通過後 commit

⸻

	2.	Git Flow（簡化）

⸻

分支：
	•	main：穩定可跑
	•	dev：開發主線
	•	feature/*：功能分支

流程：
	1.	git checkout -b feature/data-v0.1
	2.	完成功能後：
	•	git checkout dev
	•	git merge feature/data-v0.1
	3.	測試無誤：
	•	git checkout main
	•	git merge dev
	4.	git tag v0.1-data

⸻

	3.	Debug 流程

⸻

問題類型：
	1.	Bug（Claude 修）
	2.	規格問題（GPT 重寫 spec）
	3.	設計問題（記錄到 TODO / DECISIONS）

⸻

	4.	文件更新時機

⸻

	•	完成模組 → 記錄到 TODO / CHANGELOG
	•	大改動 → 更新 spec
	•	設計決策 → DECISIONS.md
	•	技術與知識 → NotebookLM

===== 00_WORKFLOW.md 結束 =====
