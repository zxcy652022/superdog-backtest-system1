# SuperDog v0.7 Strategy API Guide

## 策略編寫標準規範

本文檔定義 SuperDog v0.7 量化交易框架的策略 API 標準。

---

## 目錄

1. [快速開始](#1-快速開始)
2. [核心概念](#2-核心概念)
3. [API 詳細說明](#3-api-詳細說明)
4. [完整範例](#4-完整範例)
5. [最佳實踐](#5-最佳實踐)
6. [API 參考](#6-api-參考)

---

## 1. 快速開始

### 1.1 最小策略模板

```python
"""
MyStrategy - 自定義策略模板
"""
from typing import Any, Dict, List
import pandas as pd

from strategies.api_v2 import (
    BaseStrategy,
    DataRequirement,
    DataSource,
    ParameterSpec,
    int_param,
    float_param,
    bool_param,
)


class MyStrategy(BaseStrategy):
    """我的自定義策略"""

    def __init__(self):
        super().__init__()
        self.name = "MyStrategy"
        self.version = "1.0"
        self.author = "Your Name"
        self.description = "策略描述"

    def get_parameters(self) -> Dict[str, ParameterSpec]:
        """定義策略參數"""
        return {
            "period": int_param(
                default=20,
                description="計算週期",
                min_val=5,
                max_val=200
            ),
            "threshold": float_param(
                default=0.02,
                description="觸發閾值",
                min_val=0.001,
                max_val=0.1
            ),
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        """聲明數據需求"""
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=100,
                required=True
            ),
        ]

    def compute_signals(
        self,
        data: Dict[str, pd.DataFrame],
        params: Dict[str, Any]
    ) -> pd.Series:
        """計算交易信號"""
        ohlcv = data["ohlcv"]
        close = ohlcv["close"]

        # 計算指標
        sma = close.rolling(window=params["period"]).mean()

        # 生成信號
        signals = pd.Series(0, index=close.index)
        signals[close > sma * (1 + params["threshold"])] = 1   # 買入
        signals[close < sma * (1 - params["threshold"])] = -1  # 賣出

        return signals
```

### 1.2 策略文件位置

將策略文件保存到 `strategies/` 目錄：
```
strategies/
├── api_v2.py           # API 基類（勿修改）
├── registry_v2.py      # 註冊器（勿修改）
├── kawamoku.py         # 內建策略
├── simple_sma.py       # 內建策略
└── my_strategy.py      # 你的策略 ← 放這裡
```

策略會被**自動發現和註冊**，無需手動配置。

---

## 2. 核心概念

### 2.1 策略生命週期

```
┌─────────────────────────────────────────────────────────────┐
│                     策略生命週期                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. __init__()           初始化策略元數據                    │
│         ↓                                                   │
│  2. get_parameters()     定義可調參數                        │
│         ↓                                                   │
│  3. get_data_requirements()  聲明數據需求                    │
│         ↓                                                   │
│  4. compute_signals()    計算交易信號 (主邏輯)               │
│         ↓                                                   │
│  5. get_metadata()       返回策略描述 (自動生成)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 信號定義

| 信號值 | 含義 | 動作 |
|--------|------|------|
| `1` | 買入/做多 | 開多單 |
| `-1` | 賣出/做空 | 開空單 |
| `0` | 持有/無信號 | 維持現狀 |

信號轉換規則：
- `0 → 1`: 開多倉
- `1 → 0`: 平多倉
- `0 → -1`: 開空倉
- `-1 → 0`: 平空倉
- `1 → -1`: 平多 + 開空
- `-1 → 1`: 平空 + 開多

### 2.3 數據格式

`compute_signals()` 接收的 `data` 字典格式：

```python
data = {
    'ohlcv': pd.DataFrame({
        'open': [...],
        'high': [...],
        'low': [...],
        'close': [...],
        'volume': [...]
    }),  # index 為 DatetimeIndex

    # 可選數據源（v0.5 規劃）
    'funding_rate': pd.DataFrame(...),
    'open_interest': pd.DataFrame(...),
    'basis': pd.DataFrame(...),
}
```

---

## 3. API 詳細說明

### 3.1 BaseStrategy 抽象類

繼承自 `strategies.api_v2.BaseStrategy`

#### 必須實現的方法

| 方法 | 返回類型 | 說明 |
|------|---------|------|
| `get_parameters()` | `Dict[str, ParameterSpec]` | 定義策略參數 |
| `get_data_requirements()` | `List[DataRequirement]` | 聲明數據需求 |
| `compute_signals()` | `pd.Series` | 計算交易信號 |

#### 可選方法

| 方法 | 返回類型 | 說明 |
|------|---------|------|
| `__init__()` | `None` | 設置策略元數據 |
| `get_metadata()` | `Dict[str, Any]` | 返回策略描述 (有默認實現) |
| `validate_parameters()` | `Dict[str, Any]` | 驗證參數 (有默認實現) |

### 3.2 參數定義系統

#### ParameterSpec 結構

```python
@dataclass
class ParameterSpec:
    param_type: ParameterType    # FLOAT, INT, STR, BOOL
    default_value: Any           # 預設值
    description: str             # 描述 (CLI 幫助信息)
    min_value: Optional[float]   # 最小值 (數值類型)
    max_value: Optional[float]   # 最大值 (數值類型)
    choices: Optional[List[str]] # 可選值 (字符串類型)
```

#### 快捷函數

```python
# 整數參數
int_param(default=20, description="週期", min_val=5, max_val=200)

# 浮點數參數
float_param(default=0.02, description="閾值", min_val=0.001, max_val=0.1)

# 字符串參數
str_param(default="buy", description="模式", choices=["buy", "sell", "both"])

# 布林參數
bool_param(default=True, description="啟用過濾")
```

### 3.3 數據需求系統

#### DataSource 枚舉

```python
class DataSource(Enum):
    OHLCV = "ohlcv"                    # K線數據 (v0.4 ✓)
    FUNDING_RATE = "funding_rate"      # 資金費率 (v0.5 規劃)
    OPEN_INTEREST = "open_interest"    # 持倉量 (v0.5 規劃)
    BASIS = "basis"                    # 期現基差 (v0.5 規劃)
    LIQUIDATIONS = "liquidations"      # 爆倉數據 (v0.5 規劃)
    LONG_SHORT_RATIO = "long_short"    # 多空比 (v0.5 規劃)
```

#### DataRequirement 結構

```python
@dataclass
class DataRequirement:
    source: DataSource              # 數據源類型
    timeframe: Optional[str] = None # 時間週期 (默認跟隨回測)
    lookback_periods: int = 100     # 回望期數
    required: bool = True           # 是否必需 (False=缺少時不報錯)
```

---

## 4. 完整範例

### 4.1 RSI 策略

```python
"""
RSI 超買超賣策略
"""
from typing import Any, Dict, List
import pandas as pd

from strategies.api_v2 import (
    BaseStrategy,
    DataRequirement,
    DataSource,
    float_param,
    int_param,
)


class RSIStrategy(BaseStrategy):
    """RSI 超買超賣策略"""

    def __init__(self):
        super().__init__()
        self.name = "RSI"
        self.version = "1.0"
        self.author = "DDragon"
        self.description = "基於 RSI 指標的超買超賣策略"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "rsi_period": int_param(
                default=14,
                description="RSI 計算週期",
                min_val=5,
                max_val=50
            ),
            "oversold": float_param(
                default=30.0,
                description="超賣閾值",
                min_val=10.0,
                max_val=40.0
            ),
            "overbought": float_param(
                default=70.0,
                description="超買閾值",
                min_val=60.0,
                max_val=90.0
            ),
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=100,
                required=True
            ),
        ]

    def compute_signals(
        self,
        data: Dict[str, pd.DataFrame],
        params: Dict[str, Any]
    ) -> pd.Series:
        """計算 RSI 信號"""
        ohlcv = data["ohlcv"]
        close = ohlcv["close"]

        # 計算 RSI
        rsi = self._calculate_rsi(close, params["rsi_period"])

        # 生成信號
        signals = pd.Series(0, index=close.index)
        signals[rsi < params["oversold"]] = 1    # 超賣 → 買入
        signals[rsi > params["overbought"]] = -1  # 超買 → 賣出

        return signals

    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """計算 RSI 指標"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))
```

### 4.2 雙均線策略

```python
"""
雙均線交叉策略
"""
from typing import Any, Dict, List
import pandas as pd

from strategies.api_v2 import (
    BaseStrategy,
    DataRequirement,
    DataSource,
    int_param,
)


class DualSMAStrategy(BaseStrategy):
    """雙均線交叉策略"""

    def __init__(self):
        super().__init__()
        self.name = "DualSMA"
        self.version = "1.0"
        self.description = "基於快慢均線交叉的趨勢跟隨策略"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "fast_period": int_param(
                default=10,
                description="快線週期",
                min_val=5,
                max_val=50
            ),
            "slow_period": int_param(
                default=30,
                description="慢線週期",
                min_val=20,
                max_val=200
            ),
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=200,
                required=True
            ),
        ]

    def compute_signals(
        self,
        data: Dict[str, pd.DataFrame],
        params: Dict[str, Any]
    ) -> pd.Series:
        """計算雙均線信號"""
        ohlcv = data["ohlcv"]
        close = ohlcv["close"]

        # 計算均線
        fast_sma = close.rolling(window=params["fast_period"]).mean()
        slow_sma = close.rolling(window=params["slow_period"]).mean()

        # 生成信號
        signals = pd.Series(0, index=close.index)
        signals[fast_sma > slow_sma] = 1   # 金叉 → 做多
        signals[fast_sma < slow_sma] = -1  # 死叉 → 做空

        return signals
```

### 4.3 布林帶策略 (帶成交量過濾)

```python
"""
布林帶突破策略
"""
from typing import Any, Dict, List
import pandas as pd

from strategies.api_v2 import (
    BaseStrategy,
    DataRequirement,
    DataSource,
    bool_param,
    float_param,
    int_param,
)


class BollingerStrategy(BaseStrategy):
    """布林帶突破策略"""

    def __init__(self):
        super().__init__()
        self.name = "Bollinger"
        self.version = "1.0"
        self.description = "布林帶突破 + 成交量確認策略"

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "bb_period": int_param(
                default=20,
                description="布林帶週期",
                min_val=10,
                max_val=50
            ),
            "bb_std": float_param(
                default=2.0,
                description="標準差倍數",
                min_val=1.0,
                max_val=3.0
            ),
            "volume_ma_period": int_param(
                default=20,
                description="成交量均線週期",
                min_val=5,
                max_val=50
            ),
            "volume_threshold": float_param(
                default=1.5,
                description="成交量放大閾值",
                min_val=1.0,
                max_val=3.0
            ),
            "enable_volume_filter": bool_param(
                default=True,
                description="啟用成交量過濾"
            ),
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=100,
                required=True
            ),
        ]

    def compute_signals(
        self,
        data: Dict[str, pd.DataFrame],
        params: Dict[str, Any]
    ) -> pd.Series:
        """計算布林帶突破信號"""
        ohlcv = data["ohlcv"]
        close = ohlcv["close"]
        volume = ohlcv["volume"]

        # 計算布林帶
        sma = close.rolling(window=params["bb_period"]).mean()
        std = close.rolling(window=params["bb_period"]).std()
        upper = sma + params["bb_std"] * std
        lower = sma - params["bb_std"] * std

        # 計算成交量比率
        volume_ma = volume.rolling(window=params["volume_ma_period"]).mean()
        volume_ratio = volume / volume_ma

        # 生成信號
        signals = pd.Series(0, index=close.index)

        # 突破下軌 → 買入
        buy_condition = close < lower
        if params["enable_volume_filter"]:
            buy_condition = buy_condition & (volume_ratio > params["volume_threshold"])
        signals[buy_condition] = 1

        # 突破上軌 → 賣出
        sell_condition = close > upper
        if params["enable_volume_filter"]:
            sell_condition = sell_condition & (volume_ratio > params["volume_threshold"])
        signals[sell_condition] = -1

        return signals
```

---

## 5. 最佳實踐

### 5.1 參數設計原則

```python
# ✅ 好的參數設計
def get_parameters(self):
    return {
        # 1. 明確的描述
        "period": int_param(
            default=20,
            description="SMA 計算週期（建議 10-50）",
            min_val=5,
            max_val=200
        ),

        # 2. 合理的範圍限制
        "threshold": float_param(
            default=0.02,
            description="觸發閾值（0.01 = 1%）",
            min_val=0.001,
            max_val=0.1
        ),
    }

# ❌ 不好的參數設計
def get_parameters(self):
    return {
        "p": int_param(default=20, description="period"),  # 名稱太短
        "t": float_param(default=0.02, description=""),    # 無描述
    }
```

### 5.2 信號生成原則

```python
# ✅ 好的信號生成
def compute_signals(self, data, params):
    ohlcv = data["ohlcv"]
    close = ohlcv["close"]

    # 1. 預先計算所有指標（向量化）
    sma = close.rolling(window=params["period"]).mean()

    # 2. 初始化為 0
    signals = pd.Series(0, index=close.index)

    # 3. 使用布林索引設置信號
    signals[close > sma] = 1
    signals[close < sma] = -1

    return signals

# ❌ 不好的信號生成
def compute_signals(self, data, params):
    ohlcv = data["ohlcv"]
    signals = []

    # 逐行遍歷（效率低）
    for i in range(len(ohlcv)):
        if ohlcv["close"].iloc[i] > some_condition:
            signals.append(1)
        else:
            signals.append(0)

    return pd.Series(signals)
```

### 5.3 數據驗證

```python
def compute_signals(self, data, params):
    # ✅ 驗證必需數據
    if "ohlcv" not in data:
        raise ValueError("Missing required data source: ohlcv")

    ohlcv = data["ohlcv"]

    # ✅ 驗證數據長度
    min_periods = max(params["fast_period"], params["slow_period"])
    if len(ohlcv) < min_periods:
        raise ValueError(f"Insufficient data: need at least {min_periods} bars")

    # ... 繼續計算
```

### 5.4 處理 NaN 值

```python
def compute_signals(self, data, params):
    ohlcv = data["ohlcv"]
    close = ohlcv["close"]

    # 計算指標（前 N 個值為 NaN）
    sma = close.rolling(window=params["period"]).mean()

    # ✅ 初始化為 0，NaN 區域自動為 0
    signals = pd.Series(0, index=close.index)

    # ✅ 只在有效區域設置信號
    valid = ~sma.isna()
    signals.loc[valid & (close > sma)] = 1
    signals.loc[valid & (close < sma)] = -1

    return signals
```

---

## 6. API 參考

### 6.1 導入語句

```python
# 基本導入
from strategies.api_v2 import (
    BaseStrategy,           # 策略基類
    DataRequirement,        # 數據需求
    DataSource,            # 數據源枚舉
    ParameterSpec,         # 參數規格
    ParameterType,         # 參數類型枚舉
    int_param,             # 整數參數快捷函數
    float_param,           # 浮點參數快捷函數
    str_param,             # 字符串參數快捷函數
    bool_param,            # 布林參數快捷函數
)

# 註冊表（用於獲取策略）
from strategies.registry_v2 import (
    get_registry,          # 獲取全局註冊表
    StrategyRegistryV2,    # 註冊表類
)
```

### 6.2 使用策略

```python
from strategies.registry_v2 import get_registry
from backtest.engine import run_backtest
from data.storage import load_ohlcv
from data.paths import get_ohlcv_path

# 1. 獲取註冊表
registry = get_registry()

# 2. 列出所有策略
strategies = registry.list_strategies()
print(strategies)  # ['kawamoku', 'simplesma', ...]

# 3. 獲取策略類
strategy_cls = registry.get_strategy("kawamoku")

# 4. 載入數據
df = load_ohlcv(str(get_ohlcv_path("BTCUSDT", "1h")))

# 5. 執行回測
result = run_backtest(
    data=df,
    strategy_cls=strategy_cls,
    initial_cash=10000,
    fee_rate=0.001,
    stop_loss_pct=0.02,    # 2% 止損
    take_profit_pct=0.05,  # 5% 止盈
    leverage=1.0           # 無槓桿
)

# 6. 查看結果
print(result.metrics)
```

### 6.3 回測結果

```python
@dataclass
class BacktestResult:
    equity_curve: pd.Series      # 權益曲線
    trades: List[Trade]          # 交易記錄列表
    metrics: Dict[str, float]    # 績效指標
    trade_log: pd.DataFrame      # 詳細交易日誌

# metrics 包含的指標
{
    'total_return': float,       # 總收益率
    'max_drawdown': float,       # 最大回撤
    'num_trades': int,           # 交易次數
    'win_rate': float,           # 勝率
    'avg_trade_return': float,   # 平均交易收益
    'total_pnl': float,          # 總損益
    'avg_pnl': float,            # 平均損益
    'profit_factor': float,      # 盈虧比
    'avg_win': float,            # 平均盈利
    'avg_loss': float,           # 平均虧損
    'expectancy': float,         # 期望值
    'max_consecutive_win': int,  # 最大連勝
    'max_consecutive_loss': int, # 最大連敗
}
```

---

## 附錄

### A. 策略版本對照

| 特性 | v0.3 API | v2.0 API (當前) |
|------|---------|----------------|
| 初始化 | `__init__(broker, data)` | `__init__()` |
| 信號生成 | `on_bar(i, row)` | `compute_signals(data, params)` |
| 參數定義 | 無 | `get_parameters()` |
| 數據需求 | 無 | `get_data_requirements()` |
| Broker 訪問 | `self.broker` | 無 (向量化) |
| 數據訪問 | `self.data` | `data['ohlcv']` |

### B. 文件結構

```
strategies/
├── __init__.py          # 包初始化
├── api_v2.py           # API v2.0 定義 ⭐
├── registry_v2.py      # 策略註冊表 ⭐
├── kawamoku.py         # 川沐多因子策略
├── kawamoku_demo.py    # 策略範例
├── simple_sma.py       # 簡單 SMA 策略
├── dependency_checker.py # 相依性檢查
└── metadata.py         # 元數據管理
```

---

**版本**: v0.7
**最後更新**: 2025-12-08
**作者**: DDragon
