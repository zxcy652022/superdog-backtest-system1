CHANGELOG.md

Changelog

專案版本紀錄檔（SuperDog Backtest System）

⸻

[v0.1] Backtest Engine MVP （已完成）

完成項目：

資料模組 Data Module v0.1
	•	CSV 載入
	•	基本格式驗證
	•	範例資料 BTCUSDT 1h

Broker 模組（backtest/broker.py）
	•	模擬交易所
	•	全倉買賣
	•	手續費處理
	•	權益更新

Engine 模組（backtest/engine.py）
	•	BaseStrategy 抽象類別
	•	run_backtest 主流程
	•	單商品
	•	單時間週期
	•	只做多

Metrics 模組（backtest/metrics.py）
計算以下指標：
	•	total_return
	•	max_drawdown
	•	num_trades
	•	win_rate
	•	avg_trade_return
	•	total_pnl
	•	avg_pnl

Strategy 模組（strategies/simple_sma.py）
	•	簡單均線交叉策略
	•	收盤價進出

測試（tests/test_backtest.py）
	•	全部通過
	•	已驗證整體流程可以正常運作

測試成果摘要：
	•	約 700+ 根 1h K 線
	•	約 47 筆交易
	•	勝率約 27%
	•	報酬約 20%
	•	最大回撤約 -8%

⸻

Unreleased（規劃中）

v0.2
	•	資金管理
	•	全倉（保留）
	•	固定金額
	•	固定比例
	•	停損 / 停利
	•	Trade log DataFrame
	•	指標擴充
	•	profit factor
	•	avg win / avg loss
	•	win loss ratio

[v0.2] Backtest Engine – Risk & Position Upgrade（已完成）

本版本將系統從「能跑」推進到「能研究」，重點建置核心風控能力。

[v0.2] Backtest Engine – Risk & Position Upgrade（已完成）

本版本重點：在 v0.1 的回測骨架之上，建立研究級別的倉位模型、風險管理、交易紀錄與強化績效指標。

---

## 完成項目

### 1. Position Sizer 系統
- 新增 BasePositionSizer 抽象類別
- 新增 AllInSizer / FixedCashSizer / PercentOfEquitySizer
- 若 size <= 0 → 忽略該筆進場
- 下單邏輯改採 position_sizer 管控

### 2. 停損 / 停利（SL/TP）
- 支援固定百分比 SL/TP
- 使用 high/low 進行盤中觸發
- 成交價 = 觸發價（不模擬滑價）
- SL 與 TP 同時觸發 → SL 優先

### 3. Trade Log（完整交易紀錄）
新增 result.trade_log（pandas DataFrame），欄位包含：

entry_time, exit_time, entry_price, exit_price, size, fee, pnl, pnl_pct,  
entry_reason, exit_reason, holding_bars, mae, mfe, equity_after

### 4. Metrics 2.0
新增：
- profit_factor
- avg_win / avg_loss
- win_loss_ratio
- expectancy
- max_consecutive_win / loss（可選）

並加入除零與邊界保護。

### 5. 測試模組更新
新增 v0.2 測試：
- Position Sizer 測試
- SL / TP 盤中觸發測試
- 同 bar SL/TP 競合測試
- trade log 欄位與計算測試
- 新 metrics 的邊界測試

---

## 版本狀態
v0.2 已具備研究級回測能力。  
下一版本（v0.3）將聚焦：多商品、多策略、做空與報表模組。

[v0.3] Multi-Strategy & Multi-Asset Upgrade（規劃中）

本版本將回測系統從「單策略研究」推向「多策略、多商品」的批次研究架構。  
v0.3 將新增：

1. Portfolio Runner：批量回測層，可同時執行多策略、多幣種
2. Strategy Registry：策略模組 plug-in 化
3. 做空＋槓桿支援（簡化模型）
4. Text Reporter：標準文字報表（單策略＋排行）
5. CLI v0.3：提供初步回測指令（superdog bt run）
6. 新增 v0.3 單元測試（runner、registry、short、reports）

本版本將讓 SuperDog Backtest 系統開始具備「自動化策略研究」的能力。
