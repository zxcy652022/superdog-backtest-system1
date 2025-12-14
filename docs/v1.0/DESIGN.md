# SuperDog v1.0 設計文檔

> 自動化參數優化回測系統 - 完整設計規格

**版本**: v1.0
**日期**: 2025-12-11
**狀態**: 設計中

---

## 1. 專案目標

### 1.1 核心目標

建立一個**自動化、可重複、可驗證**的量化回測系統：

1. **互動式 CLI** - 數字選單式操作，無需記憶命令
2. **自動參數優化** - 策略內嵌可優化參數定義，系統自動搜索最佳組合
3. **Walk-Forward 驗證** - 避免過擬合，確保策略穩健性
4. **行情分類分析** - 找出適用於所有市場條件的參數
5. **真實成本模擬** - 滑點、爆倉、資金費率整合

### 1.2 使用者故事

```
作為一個量化交易者，我希望：
1. 選擇策略後，系統自動讀取該策略的可優化參數
2. 設定回測時間範圍和幣種
3. 系統自動執行 Walk-Forward 優化
4. 獲得在不同市場條件下都表現穩定的參數
5. 生成詳細的績效報告
```

---

## 2. 系統架構

### 2.1 模組架構圖

```
┌─────────────────────────────────────────────────────────────────────┐
│                        superdog.py (CLI 入口)                        │
│                     互動式數字選單主介面                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  數據管理   │         │  回測優化   │         │  報告生成   │
│  download   │         │  backtest   │         │  reports    │
└─────────────┘         └──────┬──────┘         └─────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
       ▼                       ▼                       ▼
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  策略層     │         │  執行層     │         │  風控層     │
│ strategies/ │         │ execution/  │         │   risk/     │
│             │         │             │         │             │
│ - base.py   │         │ - runner.py │         │ - broker.py │
│ - bige_*.py │         │ - walk_*.py │         │ - models/   │
│ - PARAMS    │         │ - optimizer │         │             │
└─────────────┘         └─────────────┘         └─────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │  數據層     │
                        │   data/     │
                        │             │
                        │ - paths.py  │
                        │ - storage   │
                        │ - universe  │
                        └─────────────┘
```

### 2.2 模組職責

| 模組 | 檔案 | 職責 |
|------|------|------|
| CLI 入口 | `superdog.py` | 互動式主選單 |
| 回測精靈 | `cli/backtest_wizard.py` | 引導式回測設定 |
| 策略基類 | `strategies/base.py` | OPTIMIZABLE_PARAMS 定義標準 |
| WF 驗證器 | `execution/walk_forward.py` | Walk-Forward 分割與驗證 |
| 行情分類 | `utils/market_classifier.py` | 牛熊震盪分類 |
| 報告生成 | `execution/report_generator.py` | WF 驗證報告 |

---

## 3. 策略參數定義標準

### 3.1 OPTIMIZABLE_PARAMS 格式

每個策略必須定義 `OPTIMIZABLE_PARAMS` 類變數：

```python
# strategies/bige_dual_ma.py

class BigeDualMAStrategy(BaseStrategy):
    """幣哥雙均線策略"""

    OPTIMIZABLE_PARAMS = {
        # 信號參數 - 影響進場判斷
        "cluster_threshold": {
            "type": "float",
            "default": 0.015,
            "range": [0.01, 0.03],
            "step": 0.005,
            "description": "均線密集判定閾值",
            "category": "signal",
        },
        "ma_period_short": {
            "type": "int",
            "default": 20,
            "range": [10, 30],
            "step": 5,
            "description": "短期均線週期",
            "category": "signal",
        },
        "ma_period_mid": {
            "type": "int",
            "default": 60,
            "range": [40, 80],
            "step": 10,
            "description": "中期均線週期",
            "category": "signal",
        },
        "ma_period_long": {
            "type": "int",
            "default": 120,
            "range": [100, 200],
            "step": 20,
            "description": "長期均線週期",
            "category": "signal",
        },

        # 執行參數 - 影響倉位和出場
        "add_position_mode": {
            "type": "choice",
            "default": "fixed_50",
            "choices": ["fixed_30", "fixed_50", "floating_pnl"],
            "description": "加倉模式",
            "category": "execution",
        },
        "take_profit_mode": {
            "type": "choice",
            "default": "ma20_break",
            "choices": ["fixed_r", "fibonacci", "ma20_break"],
            "description": "止盈模式",
            "category": "execution",
        },
        "position_size_pct": {
            "type": "float",
            "default": 0.10,
            "range": [0.05, 0.20],
            "step": 0.05,
            "description": "每筆倉位佔比",
            "category": "execution",
        },
    }
```

### 3.2 參數類型定義

| 類型 | 說明 | 必要欄位 |
|------|------|----------|
| `int` | 整數 | range, step |
| `float` | 浮點數 | range, step |
| `choice` | 選擇型 | choices |
| `bool` | 布林值 | (無額外欄位) |

### 3.3 通用參數 vs 策略參數

```python
# 通用參數 - 在 CLI 或 RunConfig 設定，不屬於策略
UNIVERSAL_PARAMS = {
    "leverage": [5, 10, 20, 50],        # 槓桿倍數
    "initial_cash": 500,                 # 初始資金
    "fee_rate": 0.0005,                  # 手續費率
    "timeframe": ["1h", "4h"],           # 時間週期
}

# 策略參數 - 內嵌於策略的 OPTIMIZABLE_PARAMS
# 只影響信號生成和策略內部邏輯
```

---

## 4. Walk-Forward 驗證系統

### 4.1 設計原理

Walk-Forward 驗證將數據分成多個滾動窗口：

```
總數據: 2023-01-01 ~ 2025-12-01 (約 3 年)

Window 1: [======Train======][=Test=]
Window 2:      [======Train======][=Test=]
Window 3:           [======Train======][=Test=]
Window 4:                [======Train======][=Test=]

每個窗口:
- Train: 用於參數優化 (如 6 個月)
- Test: 用於驗證優化結果 (如 2 個月)
```

### 4.2 WalkForwardValidator 類設計

```python
# execution/walk_forward.py

@dataclass
class WFWindow:
    """Walk-Forward 窗口"""
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: Dict[str, Any] = None
    train_metrics: Dict[str, float] = None
    test_metrics: Dict[str, float] = None


@dataclass
class WFConfig:
    """Walk-Forward 配置"""
    train_months: int = 6       # 訓練期長度（月）
    test_months: int = 2        # 測試期長度（月）
    step_months: int = 2        # 滾動步長（月）
    optimize_metric: str = "sharpe_ratio"
    min_trades: int = 10        # 最少交易次數要求


class WalkForwardValidator:
    """Walk-Forward 驗證器"""

    def __init__(
        self,
        strategy_cls: type,
        symbols: List[str],
        timeframes: List[str],
        start_date: str,
        end_date: str,
        config: WFConfig = None,
        universal_params: Dict = None,
    ):
        ...

    def generate_windows(self) -> List[WFWindow]:
        """生成所有滾動窗口"""
        ...

    def optimize_window(self, window: WFWindow) -> WFWindow:
        """對單一窗口執行參數優化"""
        # 使用現有的 optimizer.py
        ...

    def validate_window(self, window: WFWindow) -> WFWindow:
        """使用最佳參數在測試期驗證"""
        ...

    def run(self) -> WFResult:
        """執行完整 Walk-Forward 驗證"""
        windows = self.generate_windows()
        for window in windows:
            window = self.optimize_window(window)
            window = self.validate_window(window)
        return WFResult(windows=windows)

    def get_robust_params(self) -> Dict[str, Any]:
        """獲取所有窗口表現最穩定的參數"""
        ...
```

### 4.3 WF 結果分析

```python
@dataclass
class WFResult:
    """Walk-Forward 驗證結果"""
    windows: List[WFWindow]

    def get_oos_performance(self) -> pd.DataFrame:
        """獲取所有測試期（OOS）績效"""
        ...

    def get_param_stability(self) -> Dict[str, float]:
        """分析每個參數的穩定性"""
        # 計算各窗口最佳參數的標準差
        ...

    def get_robustness_score(self) -> float:
        """計算整體穩健度分數 (0-100)"""
        # 基於 OOS 績效一致性
        ...

    def to_report(self) -> str:
        """生成文字報告"""
        ...
```

---

## 5. 行情分類系統

### 5.1 分類標準

```python
# utils/market_classifier.py

class MarketRegime(Enum):
    """行情類型"""
    BULL = "bull"           # 牛市：MA20 > MA60 > MA120，且 MA20 斜率 > 0
    BEAR = "bear"           # 熊市：MA20 < MA60 < MA120，且 MA20 斜率 < 0
    SIDEWAYS = "sideways"   # 震盪：均線糾纏，ATR < 平均 ATR
    HIGH_VOL = "high_vol"   # 高波動：ATR > 1.5x 平均 ATR


class MarketClassifier:
    """行情分類器"""

    def classify_period(
        self,
        df: pd.DataFrame,
        lookback: int = 20
    ) -> MarketRegime:
        """分類單一時間點的行情"""
        ...

    def classify_range(
        self,
        df: pd.DataFrame,
        start: str,
        end: str,
    ) -> Dict[MarketRegime, float]:
        """分類時間範圍內各行情佔比"""
        ...

    def split_by_regime(
        self,
        df: pd.DataFrame
    ) -> Dict[MarketRegime, pd.DataFrame]:
        """按行情類型分割數據"""
        ...
```

### 5.2 行情分類報告

優化後的報告將包含各行情類型下的表現：

```
=== Walk-Forward 驗證報告 ===

整體績效 (OOS 測試期):
  - 平均收益: +15.3%
  - 平均 Sharpe: 1.24
  - 穩健度分數: 78/100

各行情表現:
  牛市 (佔 35%):  +42.5%, Sharpe 2.1
  熊市 (佔 25%):  -12.3%, Sharpe -0.4
  震盪 (佔 30%):  +8.2%, Sharpe 0.9
  高波動 (佔 10%): +18.7%, Sharpe 1.5

最佳參數 (穩健選擇):
  cluster_threshold: 0.015
  ma_period_short: 20
  add_position_mode: fixed_50
  take_profit_mode: ma20_break
```

---

## 6. 爆倉檢測整合

### 6.1 Broker 修改

```python
# backtest/broker.py

class SimulatedBroker:
    def __init__(
        self,
        initial_cash: float,
        fee_rate: float = 0.001,
        leverage: int = 1,
        maintenance_margin_rate: float = 0.005,  # 新增：維持保證金率
    ):
        self.maintenance_margin_rate = maintenance_margin_rate
        self.liquidation_events = []  # 新增：記錄爆倉事件

    def check_liquidation(self, current_price: float) -> bool:
        """檢查是否觸發爆倉"""
        if not self.position:
            return False

        # 計算爆倉價格
        if self.position.direction == "long":
            liq_price = self.position.entry_price * (
                1 - 1/self.leverage + self.maintenance_margin_rate
            )
            return current_price <= liq_price
        else:  # short
            liq_price = self.position.entry_price * (
                1 + 1/self.leverage - self.maintenance_margin_rate
            )
            return current_price >= liq_price

    def process_liquidation(self, bar: pd.Series) -> None:
        """處理爆倉"""
        self.liquidation_events.append({
            "timestamp": bar.name,
            "price": bar["close"],
            "position": self.position,
            "loss": self.get_unrealized_pnl(bar["close"]),
        })
        self.position = None
        # 爆倉後現金歸零（全部損失）
        self.cash = 0
```

### 6.2 滑點模型整合

```python
# execution/runner.py

from execution.models.slippage import AdaptiveSlippageModel

def run_backtest_with_slippage(
    config: RunConfig,
    slippage_model: SlippageModel = None,
) -> BacktestResult:
    """整合滑點模型的回測"""
    if slippage_model is None:
        slippage_model = AdaptiveSlippageModel()

    # 在 broker 執行買賣時應用滑點
    ...
```

---

## 7. CLI 設計

### 7.1 主選單結構

```
╔══════════════════════════════════════════════════════════════╗
║           SuperDog Quant v1.0 - 量化回測系統                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   1. 數據管理                                                 ║
║      - 下載歷史數據                                           ║
║      - 檢查數據完整性                                         ║
║                                                              ║
║   2. 快速回測                                                 ║
║      - 單策略單幣種回測                                       ║
║                                                              ║
║   3. 參數優化                                                 ║
║      - Walk-Forward 驗證                                      ║
║      - 網格搜索                                               ║
║                                                              ║
║   4. 查看報告                                                 ║
║      - 最近回測結果                                           ║
║      - 歷史優化報告                                           ║
║                                                              ║
║   5. 系統設定                                                 ║
║                                                              ║
║   0. 退出                                                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

請選擇 [0-5]:
```

### 7.2 回測精靈流程

```
[步驟 1/5] 選擇策略
───────────────────
  1. bigedualma - 幣哥雙均線策略
  2. dualma - 雙均線策略 v2

請選擇: 1

[步驟 2/5] 選擇幣種
───────────────────
  1. Top 10 幣種
  2. Top 20 幣種
  3. 全部可用幣種
  4. 自訂選擇

請選擇: 2

[步驟 3/5] 設定時間範圍
───────────────────────
  開始日期 [2023-01-01]:
  結束日期 [2025-12-01]:

[步驟 4/5] 設定通用參數
───────────────────────
  槓桿倍數 [10]:
  初始資金 [500]:
  手續費率 [0.0005]:

[步驟 5/5] 優化設定
───────────────────
  1. 快速回測（使用預設參數）
  2. 網格搜索優化
  3. Walk-Forward 驗證（推薦）

請選擇: 3

確認設定：
  策略: bigedualma
  幣種: 20 個
  時間: 2023-01-01 ~ 2025-12-01
  槓桿: 10x
  模式: Walk-Forward

開始執行? [Y/n]:
```

---

## 8. 實作計劃

### Phase 1: 基礎設施 (優先)

| 任務 | 檔案 | 說明 |
|------|------|------|
| 清理根目錄 | - | 移除 封存.zip, 幣哥雙均線.txt |
| 策略基類 | `strategies/base.py` | 定義 OPTIMIZABLE_PARAMS 標準 |
| 修改策略 | `strategies/bige_dual_ma.py` | 加入可優化參數 |

### Phase 2: Walk-Forward 系統

| 任務 | 檔案 | 說明 |
|------|------|------|
| WF 驗證器 | `execution/walk_forward.py` | 核心驗證邏輯 |
| 行情分類 | `utils/market_classifier.py` | 牛熊震盪分類 |
| 報告生成 | `execution/report_generator.py` | WF 報告 |

### Phase 3: 真實成本模型

| 任務 | 檔案 | 說明 |
|------|------|------|
| 爆倉檢測 | `backtest/broker.py` | 加入爆倉邏輯 |
| 滑點整合 | `execution/runner.py` | 整合現有滑點模型 |

### Phase 4: CLI 介面

| 任務 | 檔案 | 說明 |
|------|------|------|
| 主入口 | `superdog.py` | 互動式選單 |
| 回測精靈 | `cli/backtest_wizard.py` | 引導式設定 |

### Phase 5: 測試與文檔

| 任務 | 說明 |
|------|------|
| 端到端測試 | 完整流程測試 |
| 更新 CHANGELOG | 記錄 v1.0 變更 |

---

## 9. 預期成果

### 9.1 CLI 使用範例

```bash
# 啟動互動式介面
python superdog.py

# 或直接執行 Walk-Forward 優化
python superdog.py optimize \
  --strategy bigedualma \
  --symbols top20 \
  --start 2023-01-01 \
  --end 2025-12-01 \
  --leverage 10 \
  --mode walk-forward
```

### 9.2 輸出報告範例

```
══════════════════════════════════════════════════════════════
                Walk-Forward 驗證報告
══════════════════════════════════════════════════════════════

策略: BigeDualMA (幣哥雙均線)
期間: 2023-01-01 ~ 2025-12-01
幣種: 20 個
槓桿: 10x

──────────────────────────────────────────────────────────────
                    滾動窗口結果
──────────────────────────────────────────────────────────────

Window │ Train Period  │ Test Period   │ Train │ Test  │ Best Params
───────┼───────────────┼───────────────┼───────┼───────┼─────────────
   1   │ 23/01 - 23/06 │ 23/07 - 23/08 │ +32%  │ +12%  │ th=0.015
   2   │ 23/03 - 23/08 │ 23/09 - 23/10 │ +28%  │ +8%   │ th=0.020
   3   │ 23/05 - 23/10 │ 23/11 - 23/12 │ +18%  │ -5%   │ th=0.015
   ...

──────────────────────────────────────────────────────────────
                    行情分類表現
──────────────────────────────────────────────────────────────

行情類型   │ 佔比  │ 平均收益 │ Sharpe │ 勝率
───────────┼───────┼──────────┼────────┼──────
牛市       │ 35%   │ +42.5%   │ 2.10   │ 68%
熊市       │ 25%   │ -12.3%   │ -0.40  │ 32%
震盪       │ 30%   │ +8.2%    │ 0.90   │ 55%
高波動     │ 10%   │ +18.7%   │ 1.50   │ 60%

──────────────────────────────────────────────────────────────
                    穩健參數推薦
──────────────────────────────────────────────────────────────

參數名稱           │ 推薦值    │ 穩定度
───────────────────┼───────────┼────────
cluster_threshold  │ 0.015     │ 高
ma_period_short    │ 20        │ 高
add_position_mode  │ fixed_50  │ 中
take_profit_mode   │ ma20_break│ 高

整體穩健度分數: 78/100
推薦使用: 是 (分數 > 70)

══════════════════════════════════════════════════════════════
```

---

## 10. 注意事項

### 10.1 避免過擬合

- 永遠使用 Walk-Forward，不要用全樣本優化
- 關注 OOS (Out-of-Sample) 績效，而非訓練期
- 參數穩定性比最佳績效重要

### 10.2 開發規範

- 遵循 `docs/RULES.md` 的所有規範
- 策略只產生信號，執行參數傳給 runner
- 新模組先寫測試

### 10.3 檔案組織

- 不在根目錄放測試/臨時檔案
- 版本文檔放 `docs/v1.0/`
- 封存/暫存檔案放 `archive/` (gitignored)

---

**文檔版本**: v1.0
**最後更新**: 2025-12-11
**作者**: DDragon + Claude
