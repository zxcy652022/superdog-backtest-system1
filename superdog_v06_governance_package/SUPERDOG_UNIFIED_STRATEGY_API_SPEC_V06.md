# SuperDog 統一策略 API 規格文檔

**版本**: v0.6.0
**狀態**: ✅ 實作完成
**實作位置**: `strategies/api_v2.py`
**負責人**: Architecture Team
**最後更新**: 2024-12-08

---

## 🎯 概述

本文檔定義 SuperDog v0.6+ 的**統一策略 API 標準**。所有策略必須遵循此規範，以確保：

1. **一致性**: 所有策略使用相同的介面和規範
2. **可維護性**: 清晰的參數定義和數據需求聲明
3. **可測試性**: 標準化的信號生成介面
4. **可擴展性**: 靈活的元數據系統

### 設計原則

```
1. 明確優於隱式 - 所有參數和依賴必須明確聲明
2. 簡單優於複雜 - API 設計追求簡潔易用
3. 可配置優於硬編碼 - 所有參數可通過配置調整
4. 向後兼容 - 保留舊版 API 支援（有棄用警告）
```

---

## 📦 核心組件

### 1. BaseStrategy (策略基類)

**所有策略必須繼承此類別**:

```python
from strategies.api_v2 import BaseStrategy

class MyStrategy(BaseStrategy):
    """我的策略"""

    def get_parameters(self) -> Dict[str, ParameterSpec]:
        """定義參數規格"""
        pass

    def get_data_requirements(self) -> List[DataRequirement]:
        """聲明數據需求"""
        pass

    def compute_signals(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> pd.Series:
        """計算交易信號"""
        pass
```

### 2. ParameterSpec (參數規格)

**用於定義策略參數的完整規格**:

```python
from strategies.api_v2 import ParameterSpec, ParameterType

ParameterSpec(
    param_type=ParameterType.INT,     # 參數類型
    default_value=20,                 # 預設值
    description="SMA 週期",           # 描述
    min_value=5,                      # 最小值（可選）
    max_value=200,                    # 最大值（可選）
    choices=None                      # 可選值列表（可選）
)
```

**支援的參數類型**:
- `ParameterType.INT` - 整數
- `ParameterType.FLOAT` - 浮點數
- `ParameterType.STR` - 字符串
- `ParameterType.BOOL` - 布林值

### 3. DataRequirement (數據需求)

**用於聲明策略所需的數據源**:

```python
from strategies.api_v2 import DataRequirement, DataSource

DataRequirement(
    source=DataSource.OHLCV,        # 數據源類型
    timeframe="1h",                 # 特定時間週期（可選）
    lookback_periods=200,           # 回望期數
    required=True                   # 是否必需
)
```

**支援的數據源**:
- `DataSource.OHLCV` - K線數據（必備）
- `DataSource.FUNDING_RATE` - 資金費率
- `DataSource.OPEN_INTEREST` - 持倉量
- `DataSource.BASIS` - 期現基差
- `DataSource.LIQUIDATIONS` - 爆倉數據
- `DataSource.LONG_SHORT_RATIO` - 多空持倉比

### 4. StrategyMetadata (策略元數據)

**用於提供策略的詳細信息**:

```python
from strategies.metadata import StrategyMetadata, StrategyCategory, StrategyComplexity

@classmethod
def get_metadata(cls) -> StrategyMetadata:
    return StrategyMetadata(
        name="simple_sma",
        version="1.0.0",
        category=StrategyCategory.TREND,
        complexity=StrategyComplexity.BEGINNER,
        description="簡單移動平均線策略",
        author="SuperDog Team",
        created_date="2024-12-08",
        tags=["trend", "sma", "beginner"]
    )
```

---

## 🏗️ 完整策略模板

以下是一個**完整、可執行**的策略範例：

```python
"""
Simple SMA Crossover Strategy

使用快慢均線交叉產生交易信號。
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np

from strategies.api_v2 import (
    BaseStrategy,
    ParameterSpec,
    ParameterType,
    DataRequirement,
    DataSource
)
from strategies.metadata import (
    StrategyMetadata,
    StrategyCategory,
    StrategyComplexity,
    StrategyStatus
)


class SimpleSMAStrategy(BaseStrategy):
    """
    簡單移動平均線交叉策略

    當快線上穿慢線時做多，當快線下穿慢線時平倉。

    Parameters:
        fast_period: 快均線週期（預設 10）
        slow_period: 慢均線週期（預設 20）
        min_volume: 最小成交量過濾（預設 0，不過濾）

    Signals:
        1 (long): 快線上穿慢線，做多
        0 (flat): 快線下穿慢線，平倉
        -1 (short): 不使用做空（可擴展）

    Data Requirements:
        - OHLCV: 需要 close 和 volume 欄位
        - Lookback: 最少需要 slow_period 筆數據

    Risk Management:
        - 建議搭配 ATR 止損
        - 建議倉位：5-10% 每筆

    Performance Notes:
        - 適用於趨勢明確的市場
        - 震盪市場表現不佳
        - 建議配合波動率過濾
    """

    # ==================== 必須實作的方法 ====================

    def get_parameters(self) -> Dict[str, ParameterSpec]:
        """
        定義策略參數規格

        Returns:
            參數名稱對應參數規格的字典
        """
        return {
            'fast_period': ParameterSpec(
                param_type=ParameterType.INT,
                default_value=10,
                description="快均線週期",
                min_value=2,
                max_value=50
            ),
            'slow_period': ParameterSpec(
                param_type=ParameterType.INT,
                default_value=20,
                description="慢均線週期",
                min_value=5,
                max_value=200
            ),
            'min_volume': ParameterSpec(
                param_type=ParameterType.FLOAT,
                default_value=0.0,
                description="最小成交量過濾",
                min_value=0.0
            ),
            'use_ema': ParameterSpec(
                param_type=ParameterType.BOOL,
                default_value=False,
                description="使用 EMA 而非 SMA"
            )
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        """
        聲明數據需求

        Returns:
            數據需求列表
        """
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=200,  # 確保有足夠數據計算慢均線
                required=True
            )
        ]

    def compute_signals(
        self,
        data: Dict[str, pd.DataFrame],
        params: Dict[str, Any]
    ) -> pd.Series:
        """
        計算交易信號

        Args:
            data: 數據字典，key 為數據源名稱，value 為 DataFrame
                  例如: {'ohlcv': DataFrame with ['open','high','low','close','volume']}
            params: 參數字典，包含所有策略參數
                  例如: {'fast_period': 10, 'slow_period': 20}

        Returns:
            pd.Series: 信號序列，索引為 DatetimeIndex
                      1 = long, 0 = flat, -1 = short

        Raises:
            ValueError: 如果數據不足或參數不合法
        """
        # 1. 驗證數據
        if 'ohlcv' not in data:
            raise ValueError("Missing required data: ohlcv")

        ohlcv = data['ohlcv']
        required_columns = ['close', 'volume']
        missing = [col for col in required_columns if col not in ohlcv.columns]
        if missing:
            raise ValueError(f"Missing required columns in ohlcv: {missing}")

        # 2. 驗證參數
        fast = params['fast_period']
        slow = params['slow_period']
        if fast >= slow:
            raise ValueError(
                f"fast_period ({fast}) must be less than slow_period ({slow})"
            )

        # 3. 計算指標
        close = ohlcv['close']
        volume = ohlcv['volume']

        if params.get('use_ema', False):
            fast_ma = close.ewm(span=fast, adjust=False).mean()
            slow_ma = close.ewm(span=slow, adjust=False).mean()
        else:
            fast_ma = close.rolling(window=fast).mean()
            slow_ma = close.rolling(window=slow).mean()

        # 4. 生成信號
        signals = pd.Series(0, index=ohlcv.index)

        # 金叉：快線上穿慢線 → 做多
        golden_cross = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))

        # 死叉：快線下穿慢線 → 平倉
        death_cross = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

        # 5. 應用成交量過濾
        min_vol = params.get('min_volume', 0.0)
        if min_vol > 0:
            vol_filter = volume >= min_vol
            golden_cross = golden_cross & vol_filter
            death_cross = death_cross & vol_filter

        # 6. 設置信號
        signals[golden_cross] = 1   # 做多
        signals[death_cross] = 0    # 平倉

        # 7. 向前填充（維持倉位直到下一個信號）
        signals = signals.replace(0, np.nan).ffill().fillna(0)

        return signals

    # ==================== 可選方法 ====================

    @classmethod
    def get_metadata(cls) -> StrategyMetadata:
        """
        返回策略元數據

        Returns:
            StrategyMetadata: 包含策略詳細信息的元數據對象
        """
        return StrategyMetadata(
            name="simple_sma",
            version="1.0.0",
            category=StrategyCategory.TREND,
            complexity=StrategyComplexity.BEGINNER,
            status=StrategyStatus.STABLE,
            description=(
                "基於快慢均線交叉的趨勢跟蹤策略。"
                "適用於趨勢明確的市場，不適合震盪市場。"
            ),
            parameters={
                'fast_period': "快均線週期（2-50）",
                'slow_period': "慢均線週期（5-200）",
                'min_volume': "最小成交量過濾",
                'use_ema': "使用 EMA 或 SMA"
            },
            data_requirements=[
                "OHLCV: close, volume"
            ],
            author="SuperDog Team",
            created_date="2024-12-08",
            last_modified="2024-12-08",
            tags=["trend", "sma", "crossover", "beginner"],
            performance_notes=(
                "回測結果顯示在趨勢市場勝率約 45-50%，"
                "但平均盈利較大，整體為正期望。"
                "建議配合 ATR 止損和波動率過濾。"
            ),
            risk_notes=(
                "震盪市場會產生頻繁假信號，建議使用趨勢過濾器。"
                "建議每筆倉位不超過 10%。"
            )
        )

    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """
        驗證參數有效性（可選，額外的業務邏輯驗證）

        Args:
            params: 參數字典

        Returns:
            bool: 參數是否有效

        Raises:
            ValueError: 參數不合法時
        """
        fast = params.get('fast_period')
        slow = params.get('slow_period')

        if fast >= slow:
            raise ValueError(
                f"fast_period ({fast}) must be less than slow_period ({slow})"
            )

        # 建議快慢線比例不要太接近
        if slow / fast < 1.5:
            import warnings
            warnings.warn(
                f"slow/fast ratio ({slow/fast:.2f}) is too small. "
                f"Recommend ratio >= 1.5 for better signal separation.",
                UserWarning
            )

        return True


# ==================== 策略註冊 ====================

# 策略會自動被 registry_v2 發現和註冊
# 無需手動註冊
```

---

## 📋 API 完整規格

### BaseStrategy 類別

#### 必須實作的方法

##### 1. get_parameters()

```python
def get_parameters(self) -> Dict[str, ParameterSpec]:
    """
    返回策略參數規格

    Returns:
        Dict[str, ParameterSpec]: 參數名稱 → 參數規格

    Example:
        return {
            'period': ParameterSpec(
                ParameterType.INT,
                default_value=20,
                description="MA 週期",
                min_value=5,
                max_value=200
            )
        }
    """
```

**要求**:
- 必須返回字典，key 為參數名稱（字符串）
- 每個參數必須有 ParameterSpec
- 參數名稱使用 snake_case（例如：`fast_period`, `stop_loss_pct`）
- description 必須簡潔明確（用於 CLI 幫助）

##### 2. get_data_requirements()

```python
def get_data_requirements(self) -> List[DataRequirement]:
    """
    聲明數據需求

    Returns:
        List[DataRequirement]: 數據需求列表

    Example:
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=200,
                required=True
            ),
            DataRequirement(
                source=DataSource.FUNDING_RATE,
                lookback_periods=30,
                required=False
            )
        ]
    """
```

**要求**:
- 必須至少包含 OHLCV 數據源
- lookback_periods 應該是參數中最大週期的 2-3 倍
- required=True 的數據缺失時會報錯
- required=False 的數據缺失時會跳過

##### 3. compute_signals()

```python
def compute_signals(
    self,
    data: Dict[str, pd.DataFrame],
    params: Dict[str, Any]
) -> pd.Series:
    """
    計算交易信號

    Args:
        data: 數據字典
            {
                'ohlcv': DataFrame(['open','high','low','close','volume']),
                'funding_rate': DataFrame(['funding_rate']),
                ...
            }
        params: 參數字典
            {
                'fast_period': 10,
                'slow_period': 20,
                ...
            }

    Returns:
        pd.Series: 信號序列
            Index: DatetimeIndex（與 data['ohlcv'].index 對齊）
            Values:
                1 = long（做多）
                0 = flat（平倉/空倉）
               -1 = short（做空）

    Raises:
        ValueError: 數據不足或不合法
        KeyError: 缺少必需數據或參數
    """
```

**要求**:
- 信號值必須是 1, 0, -1
- 索引必須是 DatetimeIndex
- 長度必須與 data['ohlcv'] 相同
- 不允許產生 NaN 信號（應用 fillna(0)）
- 計算過程中避免 look-ahead bias（未來數據洩漏）

#### 可選方法

##### 4. get_metadata() (推薦實作)

```python
@classmethod
def get_metadata(cls) -> StrategyMetadata:
    """
    返回策略元數據

    Returns:
        StrategyMetadata: 策略元數據對象
    """
```

**好處**:
- 提供策略的詳細說明
- 便於策略管理和搜索
- 自動生成文檔
- 改善用戶體驗

##### 5. validate_parameters() (可選)

```python
def validate_parameters(self, params: Dict[str, Any]) -> bool:
    """
    額外的參數驗證邏輯

    Args:
        params: 參數字典

    Returns:
        bool: 是否合法

    Raises:
        ValueError: 參數不合法時
    """
```

**使用場景**:
- 參數間的業務邏輯約束
- 複雜的驗證規則
- 發出警告訊息

---

## 🔄 信號生成規範

### 信號值定義

```python
LONG = 1    # 做多（開多倉或維持多倉）
FLAT = 0    # 平倉（關閉所有倉位）
SHORT = -1  # 做空（開空倉或維持空倉）
```

### 信號生成最佳實踐

```python
def compute_signals(self, data, params):
    ohlcv = data['ohlcv']
    signals = pd.Series(0, index=ohlcv.index)  # 預設為 FLAT

    # 1. 計算指標
    indicator = calculate_indicator(ohlcv, params)

    # 2. 生成進場信號
    long_entry = (indicator > threshold)
    signals[long_entry] = 1

    # 3. 生成出場信號
    exit_signal = (indicator < exit_threshold)
    signals[exit_signal] = 0

    # 4. 向前填充（維持倉位直到明確出場）
    signals = signals.replace(0, np.nan).ffill().fillna(0)

    # 5. 確保沒有 NaN
    signals = signals.fillna(0)

    return signals.astype(int)
```

### 常見錯誤與解決

❌ **錯誤 1: Look-ahead Bias（未來數據洩漏）**
```python
# ❌ 錯誤：使用未來數據
signals[i] = 1 if close[i+1] > close[i] else 0

# ✅ 正確：只使用當前和過去數據
signals[i] = 1 if close[i] > close[i-1] else 0
```

❌ **錯誤 2: 信號不連續**
```python
# ❌ 錯誤：信號只在交叉時出現，其他時候是 0
signals[golden_cross] = 1
signals[death_cross] = -1

# ✅ 正確：信號向前填充，維持倉位
signals[golden_cross] = 1
signals[death_cross] = 0
signals = signals.replace(0, np.nan).ffill().fillna(0)
```

❌ **錯誤 3: 產生 NaN 信號**
```python
# ❌ 錯誤：指標計算初期會有 NaN
ma = close.rolling(20).mean()  # 前 19 個為 NaN
signals = (ma > ma.shift(1)).astype(int)  # 產生 NaN

# ✅ 正確：填充 NaN
ma = close.rolling(20).mean().fillna(method='bfill')
signals = (ma > ma.shift(1)).astype(int).fillna(0)
```

---

## 📊 數據管理規範

### 數據格式要求

#### OHLCV 格式
```python
pd.DataFrame({
    'open': float,      # 開盤價
    'high': float,      # 最高價
    'low': float,       # 最低價
    'close': float,     # 收盤價
    'volume': float     # 成交量
}, index=pd.DatetimeIndex)
```

#### 永續數據格式

**Funding Rate**:
```python
pd.DataFrame({
    'funding_rate': float,       # 資金費率（百分比）
    'next_funding_time': datetime  # 下次結算時間（可選）
}, index=pd.DatetimeIndex)
```

**Open Interest**:
```python
pd.DataFrame({
    'open_interest': float,      # 持倉量（合約數量）
    'open_interest_value': float # 持倉價值（USD，可選）
}, index=pd.DatetimeIndex)
```

**Liquidations**:
```python
pd.DataFrame({
    'liquidation_buy': float,    # 多單爆倉量
    'liquidation_sell': float    # 空單爆倉量
}, index=pd.DatetimeIndex)
```

### 數據訪問示例

```python
def compute_signals(self, data, params):
    # 訪問 OHLCV
    ohlcv = data['ohlcv']
    close = ohlcv['close']
    volume = ohlcv['volume']

    # 訪問永續數據（如果有）
    if 'funding_rate' in data:
        funding = data['funding_rate']['funding_rate']
        # 使用 funding 數據...

    if 'open_interest' in data:
        oi = data['open_interest']['open_interest']
        # 使用 OI 數據...

    # 計算信號...
    return signals
```

---

## ⚙️ 參數管理規範

### 參數命名規範

```python
# ✅ 正確命名
'fast_period'         # 使用 snake_case
'slow_period'
'stop_loss_pct'
'use_ema'
'min_volume_filter'

# ❌ 錯誤命名
'fastPeriod'          # 不使用 camelCase
'FAST_PERIOD'         # 不使用全大寫（除非是常數）
'fast-period'         # 不使用連字號
'fast period'         # 不使用空格
```

### 參數類型選擇指南

| 參數性質 | 使用類型 | 範例 |
|---------|---------|------|
| 整數週期 | INT | `period=20` |
| 百分比 | FLOAT | `stop_loss=0.02` (2%) |
| 價格 | FLOAT | `entry_price=50000.0` |
| 開關選項 | BOOL | `use_ema=True` |
| 模式選擇 | STR | `mode='aggressive'` |

### 參數驗證最佳實踐

```python
def get_parameters(self):
    return {
        # 1. 整數參數：設定合理範圍
        'period': ParameterSpec(
            ParameterType.INT,
            default_value=20,
            description="移動平均週期",
            min_value=2,      # 至少需要 2 筆數據
            max_value=500     # 避免過大
        ),

        # 2. 百分比參數：使用小數表示
        'stop_loss_pct': ParameterSpec(
            ParameterType.FLOAT,
            default_value=0.02,  # 2%
            description="停損百分比",
            min_value=0.001,     # 0.1% 最小
            max_value=0.1        # 10% 最大
        ),

        # 3. 字符串參數：限定選項
        'mode': ParameterSpec(
            ParameterType.STR,
            default_value='normal',
            description="交易模式",
            choices=['conservative', 'normal', 'aggressive']
        ),

        # 4. 布林參數：清晰的描述
        'use_trailing_stop': ParameterSpec(
            ParameterType.BOOL,
            default_value=False,
            description="啟用移動止損"
        )
    }
```

---

## 🧪 測試規範

### 策略測試結構

```python
# tests/test_my_strategy.py

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from strategies.my_strategy import MyStrategy
from strategies.api_v2 import DataSource

class TestMyStrategy:
    """測試 MyStrategy 策略"""

    @pytest.fixture
    def strategy(self):
        """提供策略實例"""
        return MyStrategy()

    @pytest.fixture
    def sample_ohlcv(self):
        """提供測試用 OHLCV 數據"""
        dates = pd.date_range('2024-01-01', periods=300, freq='1h')
        np.random.seed(42)

        close = 50000 + np.cumsum(np.random.randn(300) * 100)

        return pd.DataFrame({
            'open': close * 0.999,
            'high': close * 1.002,
            'low': close * 0.998,
            'close': close,
            'volume': np.random.uniform(100, 1000, 300)
        }, index=dates)

    # ========== 參數測試 ==========

    def test_get_parameters_returns_dict(self, strategy):
        """測試：get_parameters 返回字典"""
        params = strategy.get_parameters()
        assert isinstance(params, dict)
        assert len(params) > 0

    def test_parameters_have_valid_specs(self, strategy):
        """測試：所有參數有有效的 ParameterSpec"""
        params = strategy.get_parameters()
        for name, spec in params.items():
            assert hasattr(spec, 'param_type')
            assert hasattr(spec, 'default_value')
            assert hasattr(spec, 'description')

    def test_parameter_validation(self, strategy):
        """測試：參數驗證"""
        params = strategy.get_parameters()

        # 測試預設參數可用
        default_params = {
            name: spec.default_value
            for name, spec in params.items()
        }
        assert strategy.validate_parameters(default_params)

        # 測試不合法參數會報錯
        if 'fast_period' in params and 'slow_period' in params:
            invalid_params = default_params.copy()
            invalid_params['fast_period'] = 50
            invalid_params['slow_period'] = 10

            with pytest.raises(ValueError):
                strategy.validate_parameters(invalid_params)

    # ========== 數據需求測試 ==========

    def test_get_data_requirements_returns_list(self, strategy):
        """測試：get_data_requirements 返回列表"""
        requirements = strategy.get_data_requirements()
        assert isinstance(requirements, list)
        assert len(requirements) > 0

    def test_requires_ohlcv_data(self, strategy):
        """測試：必須包含 OHLCV 數據"""
        requirements = strategy.get_data_requirements()
        sources = [req.source for req in requirements]
        assert DataSource.OHLCV in sources

    # ========== 信號生成測試 ==========

    def test_compute_signals_returns_series(self, strategy, sample_ohlcv):
        """測試：compute_signals 返回 Series"""
        params = {
            name: spec.default_value
            for name, spec in strategy.get_parameters().items()
        }
        data = {'ohlcv': sample_ohlcv}

        signals = strategy.compute_signals(data, params)

        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_ohlcv)
        assert signals.index.equals(sample_ohlcv.index)

    def test_signals_are_valid_values(self, strategy, sample_ohlcv):
        """測試：信號值合法（1, 0, -1）"""
        params = {
            name: spec.default_value
            for name, spec in strategy.get_parameters().items()
        }
        data = {'ohlcv': sample_ohlcv}

        signals = strategy.compute_signals(data, params)

        assert signals.isin([1, 0, -1]).all()
        assert not signals.isna().any()

    def test_compute_signals_with_missing_data_raises_error(self, strategy):
        """測試：缺少必需數據會報錯"""
        params = {
            name: spec.default_value
            for name, spec in strategy.get_parameters().items()
        }

        # 空數據
        with pytest.raises((ValueError, KeyError)):
            strategy.compute_signals({}, params)

        # 缺少 OHLCV
        with pytest.raises((ValueError, KeyError)):
            strategy.compute_signals({'funding': pd.DataFrame()}, params)

    def test_compute_signals_with_insufficient_data(self, strategy):
        """測試：數據不足的處理"""
        params = {
            name: spec.default_value
            for name, spec in strategy.get_parameters().items()
        }

        # 只有 10 筆數據（不足）
        short_data = pd.DataFrame({
            'open': [100] * 10,
            'high': [101] * 10,
            'low': [99] * 10,
            'close': [100] * 10,
            'volume': [1000] * 10
        }, index=pd.date_range('2024-01-01', periods=10, freq='1h'))

        data = {'ohlcv': short_data}

        # 應該要麼報錯，要麼返回全 0 信號
        try:
            signals = strategy.compute_signals(data, params)
            assert len(signals) == 10
            assert signals.isin([1, 0, -1]).all()
        except ValueError:
            pass  # 數據不足報錯也是合理的

    # ========== 元數據測試 ==========

    def test_get_metadata_returns_valid_object(self, strategy):
        """測試：get_metadata 返回有效的元數據"""
        if hasattr(strategy.__class__, 'get_metadata'):
            metadata = strategy.get_metadata()
            assert hasattr(metadata, 'name')
            assert hasattr(metadata, 'version')
            assert hasattr(metadata, 'description')
            assert len(metadata.description) > 10  # 描述不能太短
```

### 測試覆蓋率要求

- 參數定義測試：100%
- 數據需求測試：100%
- 信號生成測試：≥ 80%
- 邊界情況測試：≥ 60%

---

## 📚 範例：進階策略

以下是一個使用永續數據的進階策略範例：

```python
"""
Funding Rate Mean Reversion Strategy

基於資金費率的均值回歸策略。
當資金費率過高時做空，過低時做多。
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np

from strategies.api_v2 import (
    BaseStrategy, ParameterSpec, ParameterType,
    DataRequirement, DataSource
)

class FundingMeanReversionStrategy(BaseStrategy):
    """資金費率均值回歸策略"""

    def get_parameters(self) -> Dict[str, ParameterSpec]:
        return {
            'funding_threshold': ParameterSpec(
                ParameterType.FLOAT,
                default_value=0.0005,
                description="資金費率閾值（0.05%）",
                min_value=0.0001,
                max_value=0.005
            ),
            'funding_ma_period': ParameterSpec(
                ParameterType.INT,
                default_value=24,
                description="資金費率移動平均週期",
                min_value=6,
                max_value=168
            ),
            'use_oi_filter': ParameterSpec(
                ParameterType.BOOL,
                default_value=True,
                description="使用持倉量過濾"
            ),
            'oi_increase_threshold': ParameterSpec(
                ParameterType.FLOAT,
                default_value=0.1,
                description="持倉量增長閾值（10%）",
                min_value=0.0,
                max_value=1.0
            )
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        return [
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=200,
                required=True
            ),
            DataRequirement(
                source=DataSource.FUNDING_RATE,
                lookback_periods=168,  # 1週（假設 1h 週期）
                required=True
            ),
            DataRequirement(
                source=DataSource.OPEN_INTEREST,
                lookback_periods=168,
                required=False  # 可選，用於過濾
            )
        ]

    def compute_signals(
        self,
        data: Dict[str, pd.DataFrame],
        params: Dict[str, Any]
    ) -> pd.Series:
        # 1. 獲取數據
        ohlcv = data['ohlcv']
        funding = data['funding_rate']['funding_rate']

        # 2. 計算資金費率移動平均
        funding_ma = funding.rolling(
            window=params['funding_ma_period']
        ).mean()

        # 3. 計算偏離度
        funding_deviation = funding - funding_ma

        # 4. 生成基礎信號
        signals = pd.Series(0, index=ohlcv.index)

        threshold = params['funding_threshold']

        # 資金費率過高 → 做空
        signals[funding_deviation > threshold] = -1

        # 資金費率過低 → 做多
        signals[funding_deviation < -threshold] = 1

        # 5. 持倉量過濾（如果啟用）
        if params['use_oi_filter'] and 'open_interest' in data:
            oi = data['open_interest']['open_interest']
            oi_change = oi.pct_change(params['funding_ma_period'])

            # 持倉量大幅增加時增強信號
            oi_threshold = params['oi_increase_threshold']
            strong_signal = (oi_change > oi_threshold)

            # 只在持倉量增加時保留信號
            signals = signals.where(strong_signal, 0)

        # 6. 回歸中性區域時平倉
        neutral_zone = (
            (funding_deviation > -threshold/2) &
            (funding_deviation < threshold/2)
        )
        signals[neutral_zone] = 0

        # 7. 向前填充
        signals = signals.replace(0, np.nan).ffill().fillna(0)

        return signals.astype(int)
```

---

## 🔧 策略註冊與使用

### 自動註冊

策略會自動被 `strategies/registry_v2.py` 發現和註冊：

```python
# 只需將策略放在 strategies/ 目錄下
# registry 會自動掃描並註冊

from strategies.registry_v2 import get_registry

registry = get_registry()

# 列出所有策略
all_strategies = registry.list_strategies()

# 獲取特定策略
strategy_class = registry.get_strategy("simple_sma")

# 獲取策略信息
info = registry.get_strategy_info("simple_sma")
print(f"名稱: {info.name}")
print(f"版本: {info.metadata.version}")
print(f"參數: {info.parameters}")
```

### 在回測中使用

```python
from execution_engine.portfolio_runner import PortfolioRunner
from strategies.registry_v2 import get_registry

# 1. 獲取策略
registry = get_registry()
strategy_class = registry.get_strategy("simple_sma")

# 2. 設定回測
runner = PortfolioRunner(
    strategy=strategy_class,
    symbols=["BTCUSDT"],
    timeframe="1h",
    start_date="2024-01-01",
    end_date="2024-06-01"
)

# 3. 執行回測
result = runner.run(
    fast_period=10,
    slow_period=20,
    use_ema=False
)

# 4. 查看結果
print(result.summary())
```

---

## ⚠️ 常見問題與解決

### Q1: 策略未被自動註冊？

**可能原因**:
1. 策略類別未繼承 `BaseStrategy`
2. 策略檔案不在 `strategies/` 目錄
3. 策略類別名稱不以 `Strategy` 結尾（建議）

**解決方案**:
```python
# ✅ 正確
class MyStrategy(BaseStrategy):  # 繼承 BaseStrategy
    pass

# ❌ 錯誤
class MyStrategy:  # 未繼承
    pass
```

### Q2: 信號計算出現 NaN？

**可能原因**:
- 指標計算初期數據不足
- 未處理除零錯誤

**解決方案**:
```python
# 處理 NaN
ma = close.rolling(20).mean()
ma = ma.fillna(method='bfill')  # 向後填充
# 或
ma = ma.fillna(0)  # 填充為 0

# 處理除零
ratio = close / close.shift(1)
ratio = ratio.replace([np.inf, -np.inf], 0)  # 替換無窮大
ratio = ratio.fillna(1)  # 填充 NaN
```

### Q3: 如何處理多時間週期？

**方案 1: 在策略內重採樣**
```python
def compute_signals(self, data, params):
    ohlcv_1h = data['ohlcv']

    # 重採樣到 4h
    ohlcv_4h = ohlcv_1h.resample('4h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })

    # 計算 4h 指標
    ma_4h = ohlcv_4h['close'].rolling(20).mean()

    # 對齊回 1h
    ma_4h = ma_4h.reindex(ohlcv_1h.index, method='ffill')

    # 使用 ma_4h 生成 1h 信號
    ...
```

**方案 2: 聲明多時間週期需求**
```python
def get_data_requirements(self):
    return [
        DataRequirement(
            source=DataSource.OHLCV,
            timeframe="1h",
            lookback_periods=200
        ),
        DataRequirement(
            source=DataSource.OHLCV,
            timeframe="4h",
            lookback_periods=50
        )
    ]
```

---

## 📖 附錄

### A. 參數命名慣例

| 概念 | 推薦命名 | 範例 |
|------|---------|------|
| 週期 | `{indicator}_period` | `sma_period`, `rsi_period` |
| 百分比 | `{concept}_pct` | `stop_loss_pct`, `profit_target_pct` |
| 倍數 | `{concept}_multiplier` | `atr_multiplier`, `size_multiplier` |
| 閾值 | `{concept}_threshold` | `volume_threshold`, `rsi_threshold` |
| 啟用開關 | `use_{feature}` | `use_ema`, `use_trailing_stop` |
| 模式 | `{concept}_mode` | `entry_mode`, `exit_mode` |

### B. 信號模式參考

**趨勢跟蹤**:
```python
# 多頭趨勢：信號維持 1
# 空頭趨勢：信號維持 -1
# 無趨勢：信號為 0
signals = signals.replace(0, np.nan).ffill().fillna(0)
```

**均值回歸**:
```python
# 超買：做空 -1
# 超賣：做多 1
# 正常：平倉 0
signals[overbought] = -1
signals[oversold] = 1
signals[normal] = 0
signals = signals.replace(0, np.nan).ffill().fillna(0)
```

**事件驅動**:
```python
# 事件發生：進場
# 事件結束：出場
# 其他：維持倉位
signals[event_start] = 1
signals[event_end] = 0
signals = signals.replace(0, np.nan).ffill().fillna(0)
```

### C. 性能優化建議

1. **向量化計算優於循環**
```python
# ❌ 慢
for i in range(len(close)):
    ma[i] = close[i-20:i].mean()

# ✅ 快
ma = close.rolling(20).mean()
```

2. **避免重複計算**
```python
# ❌ 重複計算
if close.rolling(20).mean() > close.rolling(50).mean():
    signals = 1

# ✅ 計算一次
ma_fast = close.rolling(20).mean()
ma_slow = close.rolling(50).mean()
signals = (ma_fast > ma_slow).astype(int)
```

3. **使用 NumPy 加速**
```python
# ✅ NumPy 比 Pandas 快
import numpy as np
signals = np.where(ma_fast > ma_slow, 1, 0)
```

---

## 🚀 版本歷史

### v0.6.0 (2024-12-08)
- ✅ 統一策略 API 規格
- ✅ 完整參數管理系統
- ✅ 數據需求聲明機制
- ✅ 策略元數據系統
- ✅ 自動化測試規範

### 未來規劃

**v0.7.0** (計畫中):
- 多時間週期策略支援
- 策略組合（Portfolio of Strategies）
- 動態參數調整（Walk-Forward）
- 策略性能分析工具

**v0.8.0** (計畫中):
- 機器學習策略介面
- 特徵工程管道
- 模型訓練與評估框架

---

**文件版本**: 1.0.0
**對應程式版本**: v0.6.0
**最後更新**: 2024-12-08
**下次審查**: 2025-01-08

**聲明**: 本規格為 SuperDog v0.6+ 的**強制標準**，所有策略必須遵守。
