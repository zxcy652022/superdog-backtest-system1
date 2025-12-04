SuperDog Backtest TODO List

⸻

High Priority（下一版）

Backtest Engine v0.2
	•	建立 spec/backtest_engine_v0.2.md
	•	資金管理模式
	•	all-in
	•	fixed cash
	•	percent of equity
	•	實作停損停利
	•	擴充 BacktestResult
	•	trade log
	•	增加測試案例
	•	擴充 metrics

⸻

Medium Priority
	•	新策略實作
	•	breakout strategy
	•	mean reversion
	•	文件補齊 docs/
	•	回測流程說明

⸻

Low Priority / Future
	•	多商品
	•	多時間週期
	•	做空與槓桿
	•	CLI 整合
	•	報表匯出
	•	圖形視覺化

⸻

幣圈警犬宗旨：

不要亂補程式
不要硬幹架構
不要為寫而寫

要寫：
可擴充的
可維護的
可演進的

系統。

High Priority（v0.2）

✓ Position Sizer 系統  
✓ 停損 / 停利  
✓ Trade Log  
✓ Metrics 擴充  
✓ 測試案例新增  
✓ 建立 spec/backtest_engine_v0.2.md  

Medium Priority（下一版 v0.3）
- 多商品 backtest
- 多策略執行 / 策略池
- 做空 / 槓桿
- 報表模組（利用 trade log）
- CLI 整合

Low Priority / Future
- 可視化工具
- 進階 SL/TP（分批、移動停損）
- 多週期
High Priority（v0.2 – 已完成）
✓ Position Sizer 系統  
✓ 停損 / 停利（SL/TP）  
✓ Trade Log（含 entry_reason / holding_bars / mae / mfe）  
✓ Metrics 2.0  
✓ 新增 v0.2 測試案例  
✓ 更新 spec / CHANGELOG / DECISIONS / README  

---

Medium Priority（v0.3）
- 多商品 backtest
- 多策略 / 策略池
- 做空 / 槓桿
- 報表模組（基於 trade_log）
- CLI 整合

---

Low Priority / Future
- 可視化（損益曲線 / MFE/MAE 圖）
- 多週期回測
- 進階 SL/TP（移動停損、分批）

High Priority（v0.3）
- 新增 Portfolio Runner（批量回測）
- 新增 Strategy Registry（策略 plug-in 系統）
- 簡化版做空 / 槓桿支援
- 新增 Text Reporter（標準文字報表）
- 建立 CLI v0.3（backtest 指令）
- 新增 v0.3 專屬測試案例

Medium Priority
- 進階報表模組（HTML / 圖像化）
- Config 設計（YAML）與 Profile 管理
- 進階策略參數化（param sweeps）

Low Priority / Future
- Multi-Timeframe 支援
- Portfolio 資金池、再平衡
- 進階 risk model（R 倉位 / 波動調整）
