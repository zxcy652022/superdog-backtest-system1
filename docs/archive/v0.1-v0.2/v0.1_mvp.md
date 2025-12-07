Backtest Engine v0.1 規格文件

本版本目標：建立最小可用 (MVP) 的回測核心，只支援：
	•	單商品（先用 BTCUSDT）
	•	單時間週期（1h）
	•	只做多，不做空，不槓桿
	•	以收盤價做進出場
	•	固定手續費率

未包含：
	•	多商品支援
	•	多 timeframe 支援
	•	進階倉位管理
	•	追蹤止損、風控等（後續版本加入）
	•	畫圖功能

⸻

	1.	範圍 (Scope)

⸻

Backtest Engine 的負責範圍：

必須包含：
	•	接收已清洗完畢的 OHLCV DataFrame（由 data module 產生）
	•	依照策略輸出交易行為
	•	模擬買入與賣出（全部資金進出）
	•	計算權益曲線（equity curve）
	•	計算基本績效指標（由 metrics 模組負責）
	•	回傳 BacktestResult 結構

不包含：
	•	讀取 CSV（由 storage 模組負責）
	•	清洗資料（由 validator 模組負責）
	•	多策略、多商品、複雜倉位管理

⸻

	2.	依賴 (Dependencies)

⸻

必須使用：
	•	pandas
	•	numpy
	•	Python 3.11+ 標準函式庫

禁止：
	•	ccxt（回測只吃 DataFrame，不吃即時資料）
	•	在模組內使用 sys.path.append（測試檔可以）

⸻

	3.	Input（資料輸入格式）

⸻

run_backtest() 的 data 輸入為 pandas.DataFrame：

index：DatetimeIndex（UTC 時間）
必備欄位：
	•	open
	•	high
	•	low
	•	close
	•	volume

前置假設：
	•	DataFrame 為乾淨、連續、無缺漏（由 data module 負責）
	•	時間排序為升序

⸻

	4.	核心架構 (Modules & Classes)

⸻

4.1 backtest/engine.py

需要定義：

Trade dataclass：
	•	entry_time
	•	exit_time
	•	entry_price
	•	exit_price
	•	qty
	•	pnl
	•	return_pct

BacktestResult dataclass：
	•	equity_curve (pd.Series)
	•	trades (List[Trade])
	•	metrics (Dict[str, float])

BaseStrategy：
	•	init(broker, data)
	•	on_bar(i, row)：每根 K 線會被呼叫

run_backtest(data, strategy_cls, initial_cash=10000, fee_rate=0.0005)：
主要流程：
	1.	建立 SimulatedBroker
	2.	建立策略實例
	3.	逐根 K 線呼叫策略 on_bar()
	4.	策略可透過 broker.buy_all() / sell_all() 操作
	5.	每根 K 線更新權益
	6.	回收交易紀錄與績效指標
	7.	回傳 BacktestResult

4.2 backtest/broker.py

SimulatedBroker 需包含：
	•	initial_cash
	•	cash
	•	position_qty
	•	position_entry_price
	•	fee_rate
	•	equity_history（列表紀錄每根 bar 權益）
	•	trades（Trade 物件列表）

方法：
buy_all(price, time)
	•	若無持倉，用全部現金買入
	•	記錄手續費：price * qty * fee_rate

sell_all(price, time)
	•	若有持倉，全部賣出
	•	計算 pnl、return_pct
	•	產生 Trade 寫入 trades

update_equity(price, time)
	•	若持倉：equity = cash + qty * price
	•	無持倉：equity = cash
	•	加入 equity_history

4.3 backtest/metrics.py

compute_basic_metrics(equity_curve, trades) 必須回傳 dict，含至少：
	•	total_return：最後權益 / 初始權益 - 1
	•	max_drawdown：最大回撤（負值）
	•	num_trades：交易數量
	•	win_rate：勝率（贏的交易 / 全部交易）
	•	avg_trade_return：平均每筆報酬率

不需要過度嚴格，只要邏輯正確即可。

⸻

	5.	策略介面（BaseStrategy）

⸻

策略寫法：
策略繼承 BaseStrategy，並覆寫 on_bar(i, row)

策略可使用：
	•	self.broker.buy_all(price, time)
	•	self.broker.sell_all(price, time)
	•	row[‘close’], row[‘open’], row[‘high’], row[‘low’]
	•	pandas 計算移動平均等工具

v0.1 示範策略（SimpleSMAStrategy）：
	•	close > SMA20 且無持倉 → 買入
	•	close < SMA20 且有持倉 → 賣出

⸻

	6.	測試（tests/test_backtest.py）

⸻

測試檔需求：
	•	最上面加三行 bootstrap（依照 IMPORT_POLICY）：
import sys, os
sys.path.append(os.path.abspath(”.”))

測試內容：
	•	從 data/raw/ 載入 BTCUSDT_1h_test.csv
	•	建立一個簡單 SMA20 策略
	•	呼叫 run_backtest()
	•	Assertions：
	•	回傳型別為 BacktestResult
	•	equity_curve 長度 > 0
	•	metrics[“num_trades”] > 0

v0.1 測試不要求非常嚴格，只要 pipeline 能順利跑完。

⸻

	7.	Definition of Done（完成標準）

⸻

	•	run_backtest 能在資料上跑完整個回測
	•	不拋出例外
	•	回傳 BacktestResult，包含：
	•	有效的 equity_curve
	•	trades 列表
	•	metrics 字典（且至少有五個指標）
	•	模組內沒有 sys.path.append
	•	測試檔在 Python 3.11+ 下可直接跑 pass
	•	符合 ENCODING / IMPORT_POLICY
