# SuperDog Strategy API v1.0

本文件定義了 SuperDog 回測系統的策略開發標準。按照此格式建立策略，即可無縫接入回測系統。

---

## 快速開始

### 最簡策略模板

```python
"""
策略名稱：[你的策略名稱]
策略說明：[策略簡述]
"""
from engine.base_strategy import BaseStrategy
from strategies.base import OptimizableStrategyMixin, ParamCategory
from strategies.base import int_param, float_param, choice_param, bool_param


class MyStrategy(BaseStrategy, OptimizableStrategyMixin):
    """策略類別"""

    # ===== 必填：可優化參數定義 =====
    OPTIMIZABLE_PARAMS = {
        "ma_period": int_param(
            default=20,
            description="均線週期",
            range_min=5,
            range_max=100,
            step=5,
            category=ParamCategory.SIGNAL,
        ),
        "stop_loss_pct": float_param(
            default=0.05,
            description="停損百分比",
            range_min=0.01,
            range_max=0.20,
            step=0.01,
            category=ParamCategory.EXECUTION,
        ),
    }

    def __init__(self, broker, data, params=None):
        super().__init__(broker, data)
        # 合併默認參數與用戶參數
        defaults = self.get_default_params()
        self.params = {**defaults, **(params or {})}

        # 初始化策略狀態
        self._position_open = False

    def on_bar(self, bar):
        """每根K線觸發的交易邏輯"""
        close = bar["close"]

        # 你的交易邏輯
        # ...

        # 開倉示例
        if should_buy and not self._position_open:
            self.broker.buy(size=..., price=close)
            self._position_open = True

        # 平倉示例
        if should_sell and self._position_open:
            self.broker.close_position()
            self._position_open = False
```

---

## 參數定義系統

### 參數類型

| 函數 | 用途 | 必填參數 | 可選參數 |
|------|------|----------|----------|
| `int_param()` | 整數參數 | `default`, `description` | `range_min`, `range_max`, `step`, `category` |
| `float_param()` | 浮點數參數 | `default`, `description` | `range_min`, `range_max`, `step`, `category` |
| `choice_param()` | 選擇型參數 | `default`, `choices`, `description` | `category` |
| `bool_param()` | 布林值參數 | `default`, `description` | `category` |

### 參數類別 (ParamCategory)

| 類別 | 說明 | 優化建議 |
|------|------|----------|
| `SIGNAL` | 信號參數 - 影響進出場判斷 | 適合網格搜索優化 |
| `EXECUTION` | 執行參數 - 影響倉位和風控 | 建議固定或謹慎優化 |

### 完整參數定義範例

```python
from strategies.base import (
    OptimizableStrategyMixin,
    ParamCategory,
    int_param,
    float_param,
    choice_param,
    bool_param,
)

OPTIMIZABLE_PARAMS = {
    # 信號參數
    "ma_short": int_param(
        default=10,
        description="短期均線週期",
        range_min=5,
        range_max=30,
        step=5,
        category=ParamCategory.SIGNAL,
    ),
    "ma_long": int_param(
        default=50,
        description="長期均線週期",
        range_min=20,
        range_max=100,
        step=10,
        category=ParamCategory.SIGNAL,
    ),
    "threshold": float_param(
        default=0.015,
        description="均線密集判定閾值",
        range_min=0.005,
        range_max=0.030,
        step=0.005,
        category=ParamCategory.SIGNAL,
    ),

    # 執行參數
    "leverage": int_param(
        default=10,
        description="槓桿倍數",
        range_min=1,
        range_max=20,
        step=1,
        category=ParamCategory.EXECUTION,
    ),
    "position_size_pct": float_param(
        default=0.10,
        description="單次建倉比例",
        range_min=0.05,
        range_max=0.30,
        step=0.05,
        category=ParamCategory.EXECUTION,
    ),

    # 選擇型參數
    "add_position_mode": choice_param(
        default="fixed_50",
        choices=["none", "fixed_50", "martingale"],
        description="加倉模式",
        category=ParamCategory.EXECUTION,
    ),
    "take_profit_mode": choice_param(
        default="ma20_break",
        choices=["fixed", "trailing", "ma20_break"],
        description="止盈模式",
        category=ParamCategory.EXECUTION,
    ),

    # 布林值參數
    "enable_short": bool_param(
        default=True,
        description="啟用做空",
        category=ParamCategory.SIGNAL,
    ),
}
```

---

## 策略類別結構

### 必要繼承

```python
from engine.base_strategy import BaseStrategy
from strategies.base import OptimizableStrategyMixin

class MyStrategy(BaseStrategy, OptimizableStrategyMixin):
    ...
```

### 必要類別變數

```python
OPTIMIZABLE_PARAMS = {
    # 參數定義
}
```

### 必要方法

#### `__init__(self, broker, data, params=None)`

初始化策略。

```python
def __init__(self, broker, data, params=None):
    super().__init__(broker, data)

    # 1. 合併參數
    defaults = self.get_default_params()
    self.params = {**defaults, **(params or {})}

    # 2. 初始化狀態
    self._position_open = False
    self._entry_price = None

    # 3. 預計算指標 (可選)
    self._setup_indicators()
```

#### `on_bar(self, bar)`

每根K線觸發的交易邏輯。

```python
def on_bar(self, bar):
    """
    bar 結構:
    {
        'open': float,
        'high': float,
        'low': float,
        'close': float,
        'volume': float,
        'timestamp': datetime,
    }
    """
    close = bar["close"]

    # 交易邏輯
    ...
```

---

## Broker API

策略通過 `self.broker` 進行交易操作。

### 基本交易方法

| 方法 | 說明 | 參數 |
|------|------|------|
| `buy(size, price)` | 開多倉 | `size`: 數量, `price`: 價格 |
| `sell(size, price)` | 開空倉 | `size`: 數量, `price`: 價格 |
| `close_position()` | 平倉 | 無 |

### 帳戶資訊

| 屬性/方法 | 說明 |
|-----------|------|
| `broker.equity` | 當前權益 |
| `broker.cash` | 可用現金 |
| `broker.position` | 當前持倉 |
| `broker.position.size` | 持倉數量 (正=多, 負=空) |
| `broker.position.avg_price` | 平均成本 |

### 計算建議倉位

```python
def calculate_position_size(self, price):
    """根據比例計算建議倉位"""
    equity = self.broker.equity
    leverage = self.params.get("leverage", 10)
    size_pct = self.params.get("position_size_pct", 0.10)

    notional = equity * leverage * size_pct
    size = notional / price
    return size
```

---

## 策略註冊

策略文件放置於 `strategies/` 目錄後，系統會自動發現。

### 檔案命名規範

- 使用小寫加底線：`my_strategy.py`
- 類別名使用駝峰式：`MyStrategy`

### 手動註冊 (可選)

如果策略未被自動發現，可在 `strategies/__init__.py` 中註冊：

```python
from strategies.my_strategy import MyStrategy

__all__ = [
    "MyStrategy",
]
```

---

## 執行回測

### 使用 RunConfig

```python
from execution.runner import RunConfig, run_single

config = RunConfig(
    strategy="mystrategy",          # 策略名 (小寫)
    symbol="BTCUSDT",
    timeframe="4h",
    start="2023-01-01",
    end="2024-12-31",
    initial_cash=1000,
    fee_rate=0.0005,
    strategy_params={
        "ma_short": 10,
        "ma_long": 50,
        "leverage": 10,
    },
)

result = run_single(config)
print(f"總收益: {result.total_return:.2%}")
```

### 使用 CLI

```bash
python superdog.py backtest \
    --strategy mystrategy \
    --symbol BTCUSDT \
    --timeframe 4h \
    --start 2023-01-01 \
    --end 2024-12-31
```

---

## 參數優化

策略繼承 `OptimizableStrategyMixin` 後，可使用以下方法：

### 獲取搜索空間

```python
# 獲取所有參數的搜索空間
space = MyStrategy.get_param_search_space()
# {'ma_short': [5, 10, 15, 20, 25, 30], 'ma_long': [20, 30, 40, ...], ...}

# 只獲取特定參數
space = MyStrategy.get_param_search_space(["ma_short", "ma_long"])
```

### 生成參數組合

```python
# 生成所有組合
combos = MyStrategy.generate_param_combinations()

# 限制最大組合數
combos = MyStrategy.generate_param_combinations(max_combinations=100)

# 只組合特定參數
combos = MyStrategy.generate_param_combinations(param_names=["ma_short", "ma_long"])
```

### 驗證參數

```python
errors = MyStrategy.validate_params({
    "ma_short": 10,
    "ma_long": 5,  # 錯誤：短均線不應大於長均線（需自行驗證）
})
```

---

## 完整策略範例

```python
"""
雙均線交叉策略

策略邏輯：
- 短均線上穿長均線時做多
- 短均線下穿長均線時做空
- 使用止損保護
"""
from engine.base_strategy import BaseStrategy
from strategies.base import (
    OptimizableStrategyMixin,
    ParamCategory,
    int_param,
    float_param,
    bool_param,
)
import numpy as np


class DualMAStrategy(BaseStrategy, OptimizableStrategyMixin):
    """雙均線交叉策略"""

    OPTIMIZABLE_PARAMS = {
        "ma_short": int_param(
            default=10,
            description="短期均線週期",
            range_min=5,
            range_max=30,
            step=5,
            category=ParamCategory.SIGNAL,
        ),
        "ma_long": int_param(
            default=50,
            description="長期均線週期",
            range_min=20,
            range_max=100,
            step=10,
            category=ParamCategory.SIGNAL,
        ),
        "leverage": int_param(
            default=10,
            description="槓桿倍數",
            range_min=1,
            range_max=20,
            step=1,
            category=ParamCategory.EXECUTION,
        ),
        "stop_loss_pct": float_param(
            default=0.05,
            description="停損比例",
            range_min=0.02,
            range_max=0.10,
            step=0.01,
            category=ParamCategory.EXECUTION,
        ),
        "enable_short": bool_param(
            default=True,
            description="啟用做空",
            category=ParamCategory.SIGNAL,
        ),
    }

    def __init__(self, broker, data, params=None):
        super().__init__(broker, data)

        # 合併參數
        defaults = self.get_default_params()
        self.params = {**defaults, **(params or {})}

        # 狀態
        self._position_open = False
        self._entry_price = None
        self._position_side = None  # "long" or "short"

        # 預計算均線
        self._setup_indicators()

    def _setup_indicators(self):
        """預計算技術指標"""
        close = self.data["close"].values
        short = self.params["ma_short"]
        long = self.params["ma_long"]

        self._ma_short = self._rolling_mean(close, short)
        self._ma_long = self._rolling_mean(close, long)

    def _rolling_mean(self, arr, window):
        """計算滾動平均"""
        result = np.full_like(arr, np.nan, dtype=float)
        for i in range(window - 1, len(arr)):
            result[i] = np.mean(arr[i - window + 1:i + 1])
        return result

    def on_bar(self, bar):
        """交易邏輯"""
        idx = bar.get("_index", 0)
        close = bar["close"]

        # 確保有足夠數據
        if idx < self.params["ma_long"]:
            return

        ma_short = self._ma_short[idx]
        ma_long = self._ma_long[idx]

        # 檢查止損
        if self._position_open:
            self._check_stop_loss(close)

        # 無持倉時尋找入場信號
        if not self._position_open:
            # 金叉做多
            if ma_short > ma_long:
                size = self._calculate_size(close)
                self.broker.buy(size=size, price=close)
                self._entry_price = close
                self._position_side = "long"
                self._position_open = True

            # 死叉做空
            elif ma_short < ma_long and self.params["enable_short"]:
                size = self._calculate_size(close)
                self.broker.sell(size=size, price=close)
                self._entry_price = close
                self._position_side = "short"
                self._position_open = True

        # 有持倉時尋找出場信號
        else:
            should_exit = False

            if self._position_side == "long" and ma_short < ma_long:
                should_exit = True
            elif self._position_side == "short" and ma_short > ma_long:
                should_exit = True

            if should_exit:
                self.broker.close_position()
                self._reset_position()

    def _calculate_size(self, price):
        """計算建倉數量"""
        equity = self.broker.equity
        leverage = self.params["leverage"]
        notional = equity * leverage * 0.95  # 95% 資金使用率
        return notional / price

    def _check_stop_loss(self, current_price):
        """檢查止損"""
        if self._entry_price is None:
            return

        stop_pct = self.params["stop_loss_pct"]

        if self._position_side == "long":
            loss_pct = (self._entry_price - current_price) / self._entry_price
            if loss_pct >= stop_pct:
                self.broker.close_position()
                self._reset_position()

        elif self._position_side == "short":
            loss_pct = (current_price - self._entry_price) / self._entry_price
            if loss_pct >= stop_pct:
                self.broker.close_position()
                self._reset_position()

    def _reset_position(self):
        """重置持倉狀態"""
        self._position_open = False
        self._entry_price = None
        self._position_side = None
```

---

## 常見問題

### Q: 如何存取歷史K線數據？

A: 使用 `self.data`，這是一個包含 OHLCV 的 DataFrame。

```python
close_series = self.data["close"]
current_close = self.data["close"].iloc[bar["_index"]]
```

### Q: 如何在策略中計算技術指標？

A: 建議在 `__init__` 中預計算，避免重複計算。

```python
def __init__(self, broker, data, params=None):
    super().__init__(broker, data)
    # ...
    self._rsi = self._calculate_rsi(data["close"].values, 14)
```

### Q: 如何處理多幣種回測？

A: 使用 `run_portfolio()` 批量執行。

```python
from execution.runner import RunConfig, run_portfolio

configs = [
    RunConfig(strategy="mystrategy", symbol=sym, ...)
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
]

result = run_portfolio(configs)
df = result.to_dataframe()
```

### Q: 參數優化時如何限制組合數？

A: 使用 `max_combinations` 參數或只優化關鍵參數。

```python
# 限制組合數
combos = MyStrategy.generate_param_combinations(max_combinations=500)

# 只優化信號參數
signal_params = [
    name for name, spec in MyStrategy.OPTIMIZABLE_PARAMS.items()
    if spec.get("category") == "signal"
]
combos = MyStrategy.generate_param_combinations(param_names=signal_params)
```

---

## 版本歷史

| 版本 | 日期 | 變更 |
|------|------|------|
| v1.0 | 2024-12 | 初始版本，基於 OPTIMIZABLE_PARAMS 系統 |

---

*SuperDog Quant Framework - Strategy API Documentation*
