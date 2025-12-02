===== spec/data_module_v0.1.md 開始 =====

Data Module v0.1 規格文件

本版目標：建立最小可行（MVP）的歷史 K 線下載模組。

⸻

	1.	範圍（Scope）

⸻

v0.1 包含：
	•	交易所：Binance
	•	商品：BTCUSDT
	•	Timeframe：1h
	•	期間：2020-01-01 ～ 2024-01-01
	•	輸出：CSV

不包含：
	•	多幣種
	•	其他交易所
	•	Parquet 格式
	•	DB
	•	自動更新

⸻

	2.	功能（Features）

⸻

2.1 下載 OHLCV
	•	使用 ccxt
	•	可指定 symbol, timeframe, start, end
	•	回傳 CSV 路徑

2.2 CSV 儲存
欄位格式：
timestamp, open, high, low, close, volume

2.3 數據驗證
validate_ohlcv_csv(file_path) 檢查：
	•	欄位是否正確
	•	缺漏估計
	•	回傳 dict，例如：
{
“ok”: true,
“missing_bars”: 5,
“total_rows”: 35040
}

2.4 資料讀取（DataFrame）
load_ohlcv(file_path) → pandas DataFrame（datetime index / UTC）

⸻

	3.	Input / Output

⸻

Input:
	•	symbol：「BTCUSDT」
	•	timeframe：「1h」
	•	start：「2020-01-01」
	•	end：「2024-01-01」
	•	save_path：string

Output:
	•	CSV 檔案
	•	DataFrame

⸻

	4.	錯誤處理

⸻

	•	API 錯誤：重試 3 次後拋例外
	•	缺漏：只回報，不補洞
	•	CSV 格式錯：拋例外

⸻

	5.	完成標準（Definition of Done）

⸻

	•	成功抓下 BTCUSDT 1h（2020~2024）
	•	validator 能輸出檢查報告
	•	storage 能讀成 DataFrame
	•	可在 notebook 畫出 K 線
	•	commit + 更新 TODO / CHANGELOG

===== spec/data_module_v0.1.md 結束 =====
