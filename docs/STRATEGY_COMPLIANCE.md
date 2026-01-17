# 策略架構合規性報告

> 根據 RULES.md v1.0 進行審核
> 審核日期: 2026-01-16

---

## 核心規範摘要

根據 RULES.md §2.1-2.2：

1. **策略只產生進場信號**
2. **止損/止盈/加倉由引擎處理**
3. **通過 ExecutionConfig 提供執行配置**

---

## 策略合規性總覽

| 策略 | 符合規範 | ExecutionConfig | 備註 |
|-----|---------|----------------|------|
| bige_correct.py | ✅ | ✅ | v2.0 重構完成 |
| bige_simple_hold.py | ✅ | ✅ | v2.0 重構完成 |
| bige_trend_follow.py | ✅ | ✅ | v2.0 重構完成 |
| bige_signal_based.py | ✅ | ✅ | v2.0 重構完成 |
| simple_sma.py | ✅ | ✅ | v0.2 重構完成 |
| macd_scalping_v2.py | ✅ | ✅ | 新建兼容版 |
| qqe_mod_v2.py | ✅ | ✅ | 新建兼容版 |
| bige_dual_ma_v2.py | ⚠️ | ✅ | 部分執行邏輯在策略中 |
| bige_signal.py | ⚠️ | ✅ | 需要檢查 |
| dual_ma.py | ❌ | ❌ | 嚴重違規：內含止損止盈加倉 |
| bige_v3.py | ❌ | ❌ | 嚴重違規：內含止損止盈加倉 |
| bige_dual_ma.py | ❌ | ❌ | 舊版本，需要重構 |
| macd_scalping.py | ⚠️ | ❌ | 獨立回測邏輯，不繼承 BaseStrategy |
| qqe_mod.py | ⚠️ | ❌ | 獨立回測邏輯，不繼承 BaseStrategy |

---

## 詳細說明

### ✅ 完全合規的策略

這些策略已經完全符合 RULES.md 規範：

1. **bige_correct.py** - 幣哥策略正確版
2. **bige_simple_hold.py** - 簡單持有版
3. **bige_trend_follow.py** - 趨勢跟隨版
4. **bige_signal_based.py** - 信號驅動版
5. **simple_sma.py** - 簡單 SMA 策略
6. **macd_scalping_v2.py** - MACD 短線策略 v2
7. **qqe_mod_v2.py** - QQE Mod 策略 v2

**特徵**：
- `on_bar()` 只產生進場信號
- 有持倉時直接 `return`，讓引擎處理
- 通過 `get_execution_config()` 提供配置

### ❌ 需要重構的策略

這些策略違反了 §2.2 禁止事項：

1. **dual_ma.py**
   - 第 503-591 行：`_manage_position()` 處理止損止盈加倉
   - 重構工作量：高

2. **bige_v3.py**
   - 第 488+ 行：`_handle_position()` 處理止損止盈
   - 重構工作量：高

3. **bige_dual_ma.py**
   - 舊版本，與 bige_dual_ma_v2.py 功能重複
   - 建議：刪除或歸檔

### ⚠️ 需要遷移的策略

這些策略使用獨立回測邏輯，不兼容統一引擎：

1. **macd_scalping.py** - 有獨立 `backtest()` 方法
2. **qqe_mod.py** - 有獨立 `backtest()` 方法

**已創建兼容版本**：
- `macd_scalping_v2.py`
- `qqe_mod_v2.py`

---

## 重構優先級

### 高優先級（立即）
1. ~~bige_correct.py~~ ✅ 完成
2. ~~bige_simple_hold.py~~ ✅ 完成
3. ~~bige_trend_follow.py~~ ✅ 完成
4. ~~bige_signal_based.py~~ ✅ 完成

### 中優先級（建議）
1. dual_ma.py → 需要完整重構
2. bige_v3.py → 需要完整重構

### 低優先級（可選）
1. bige_dual_ma.py → 考慮刪除
2. macd_scalping.py → 保留舊版，使用 v2
3. qqe_mod.py → 保留舊版，使用 v2

---

## 正確的策略模板

```python
from backtest.engine import BaseStrategy
from backtest.strategy_config import (
    ExecutionConfig,
    StopConfig,
    AddPositionConfig,
    PositionSizingConfig,
)

class MyStrategy(BaseStrategy):
    """符合 RULES.md 的策略"""

    @classmethod
    def get_default_parameters(cls):
        """策略參數 - 只影響信號計算"""
        return {
            "param1": 20,
            "param2": 0.05,
        }

    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        """執行配置 - 告訴引擎如何處理"""
        return ExecutionConfig(
            stop_config=StopConfig(
                type="simple",
                fixed_stop_pct=0.03,
            ),
            add_position_config=AddPositionConfig(enabled=False),
            position_sizing_config=PositionSizingConfig(type="all_in"),
            take_profit_pct=0.09,
            leverage=7.0,
        )

    def __init__(self, broker, data, **kwargs):
        super().__init__(broker, data)
        self.params = self.get_default_parameters()
        # ... 初始化指標

    def on_bar(self, i: int, row: pd.Series):
        """只產生進場信號"""
        # 有持倉時不做任何事
        if self.broker.has_position:
            return

        # 檢查進場條件
        if self._entry_condition(row):
            self.broker.buy_all(row["close"], row.name)
```

---

## 總結

- **符合規範**: 7 個策略 (50%)
- **需要重構**: 3 個策略 (21%)
- **需要遷移**: 2 個策略 (14%)
- **待確認**: 2 個策略 (14%)

**下一步行動**：
1. 繼續使用已重構的策略進行開發
2. 逐步重構 dual_ma.py 和 bige_v3.py
3. 考慮刪除舊版本策略

---

**維護者**: DDragon
**更新日期**: 2026-01-16
