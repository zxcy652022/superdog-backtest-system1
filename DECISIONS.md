# v0.2 Design Decisions – 2025-12-03

---

## 1. SL/TP 觸發規則
- 採用 high/low 盤中判斷，不看 close。  
- 觸發價 = 成交價（不模擬滑價、跳空）。  
- 同根K同時 hit SL & TP → 停損優先。  
- 理由：v0.2 追求簡單實作且不扭曲回測結果；詳細撮合行為留至 v0.3。

---

## 2. Position Sizer 邊界行為
- size 允許小數（加密貨幣特性）。  
- 若 size <= 0 → 不觸發交易。  
- 不考慮 minimum notional 或交易所最小下單單位。  
- 手續費於 broker 層計算（依照 size * price * fee_rate）。  

---

## 3. Trade Log 設計
- 必須包含 entry_reason / exit_reason。  
- holding_bars 為策略分析重要資訊，於 v0.2 加入。  
- mae / mfe 為風險分析核心指標，以「百分比版本」實作。  
- 未做：分批出場、部分加碼，留待 v0.3+。

---

## 4. Metrics 边界规则
- profit_factor：若 total_loss == 0 → +inf  
- 無交易 → 所有指標回傳 NaN  
- expectancy 不依賴樣本數，可在單筆交易下運作  
- max_consecutive_win/loss 為可選指標  

---

## 5. 範圍取捨（Scope Control）
延後至 v0.3 或更後版本：

- 做空 / 槓桿  
- 多商品  
- 多週期  
- 進階 SL/TP  
- 報表模組  
- 可視化模組  

理由：避免 v0.2 過於複雜，確保核心基礎穩定。

---
