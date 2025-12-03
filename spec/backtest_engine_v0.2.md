# Backtest Engine v0.2 Specification
版本：v0.2  
狀態：最終版  
目標：在 v0.1「能跑」的基礎上，建立真正可研究的回測核心能力，包括倉位管理、停損/停利、完整交易紀錄與進階績效指標。

---

# 1. 版本目標（Objectives）

v0.2 的重點是讓系統進入「研究級別」。包含：

1. Position Sizer 系統（倉位管理）
2. 停損 / 停利（SL/TP）
3. 完整 Trade Log（交易紀錄 DataFrame）
4. Metrics 2.0（強化績效指標）
5. v0.2 專屬測試案例

不新增策略、不做多品種、不做做空、也不做可視化。  
這些留給 v0.3 之後。

---

# 2. Position Sizer 系統

新增模組：`backtest/position_sizer.py`

## 2.1 抽象類別

```python
class BasePositionSizer:
    def get_size(self, equity: float, price: float) -> float:
        raise NotImplementedError
```

此方法輸出「要下多少數量」。

## 2.2 三種內建 Sizer

### (A) AllInSizer
重現 v0.1 的行為，但抽離成獨立類別：

```python
size = equity / price
```

### (B) FixedCashSizer

```python
size = fixed_cash / price
```

### (C) PercentOfEquitySizer

```python
position_value = equity * pct
size = position_value / price
```

## 2.3 邊界規則（v0.2 標準）

- size 允許小數（符合加密貨幣）
- 若 `size <= 0` → 忽略該次進場（不報錯）
- 不處理交易所最小下單單位（已知限制）

## 2.4 Engine 整合

`run_backtest()` 新增參數：

```python
position_sizer: BasePositionSizer
```

在 BUY 訊號：

```python
size = position_sizer.get_size(equity, price)
broker.buy(size)
```

---

# 3. 停損 / 停利（SL/TP）

v0.2 支援「固定百分比」停損與停利。

## 3.1 參數

```
stop_loss_pct: Optional[float] = None
take_profit_pct: Optional[float] = None
```

## 3.2 盤中觸發規則（整合改良後）

**檢查順序：**

```python
if bar['low'] <= sl_price:
    exit_price = sl_price
    exit_reason = "stop_loss"
elif bar['high'] >= tp_price:
    exit_price = tp_price
    exit_reason = "take_profit"
```

- 使用 high/low，不使用 close 觸發
- 強制成交價 = 觸發價（不模擬滑價）

## 3.3 同一根 K 同時 hit SL 和 TP？

規則：

- **停損優先**（先確保不爆倉）
- 這是 v0.2 的簡化模型，滑價與撮合留給 v0.3

---

# 4. Trade Log（交易紀錄）

新增：

```
result.trade_log: pd.DataFrame
```

## 4.1 欄位定義（整合後完整版）

| 欄位 | 描述 |
|------|------|
| entry_time | 進場時間 |
| exit_time | 出場時間 |
| entry_price | 進場價 |
| exit_price | 出場價 |
| size | 下單數量 |
| fee | 手續費 |
| pnl | 損益 |
| pnl_pct | 報酬率 |
| entry_reason | 進場的原因（由策略提供） |
| exit_reason | sl / tp / strategy_exit |
| holding_bars | 持倉 K 數 |
| mae | 最大不利變化（%） |
| mfe | 最大有利變化（%） |
| equity_after | 出場後權益 |

## 4.2 MAE / MFE 計算方法（v0.2 版）

- mae = (min(low during holding) - entry_price) / entry_price  
- mfe = (max(high during holding) - entry_price) / entry_price  

先以百分比型式實作，後續版本可延伸。

---

# 5. Metrics 擴充（Metrics 2.0）

新增以下指標：

- profit_factor  
- avg_win  
- avg_loss  
- win_loss_ratio  
- expectancy  
- max_consecutive_win（選用）  
- max_consecutive_loss（選用）

## 5.1 邊界情況處理

- `total_loss == 0` → profit_factor = +inf  
- `num_trades == 0` → 所有指標回傳 NaN  
- 單筆交易 → expectancy 正常計算，但不計算標準差類指標

所有邊界都需要單元測試覆蓋。

---

# 6. 測試（tests/test_backtest_v02.py）

## 6.1 Position Sizer 測試

- fixed cash → size 正確  
- percent → size 隨 equity 變動  
- all-in → 與 v0.1 行為一致  
- size <= 0 → 不進場

## 6.2 SL/TP 測試

- SL 由 low 觸發  
- TP 由 high 觸發  
- SL 與 TP 同時命中 → SL 優先  
- exit_reason 正確

## 6.3 Trade Log 測試

- 欄位齊全  
- pnl / pnl_pct / mae / mfe 計算正確  
- holding_bars 累計正確  
- 每次平倉都寫一列

## 6.4 Metrics 測試

- profit_factor 邊界  
- avg_win / avg_loss  
- win_loss_ratio  
- expectancy  
- 全部 win / 全部 loss / 只有一筆交易

---

# 7. 已知限制（Known Limitations）

- 同一根 K 只會觸發一次 SL/TP  
- 不模擬滑價與跳空  
- 不強制交易所最小名目/單位  
- 只做多、不做空  
- 單商品、單策略、單週期  

---

# 8. Definition of Done（交付標準）

- 五大功能完全實作  
- 所有測試通過  
- 更新：CHANGELOG / README / DECISIONS / TODO  
- trade_log 與 metrics 與 engine 稳定運作  

v0.2 完成後，系統即可開始「策略研究」與「交易行為分析」。
