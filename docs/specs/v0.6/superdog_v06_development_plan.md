# SuperDog v0.6 開發計劃
**專業量化交易研發平台完整升級**

---

## 🎯 總體目標

將SuperDog從策略開發工具升級為**企業級量化交易研發平台**，支援完整的量化交易研發工作流程。

### 核心價值主張
- **效率提升**: 批量實驗取代手動測試
- **精準優化**: 自動找出最佳參數組合
- **真實模擬**: 接近實盤的回測結果  
- **智能風控**: 動態支撐壓力位管理

---

## 📊 v0.6 vs v0.5 對比

| 維度 | v0.5 | v0.6 | 提升 |
|------|------|------|------|
| **定位** | 策略開發工具 | 企業級研發平台 | 質的飛躍 |
| **工作流程** | 手動測試 | 自動化實驗 | 10x效率 |
| **幣種管理** | 手動選擇 | 智能分類宇宙 | 系統化 |
| **參數優化** | 單次測試 | 批量掃描 | 大規模優化 |
| **回測精度** | 基礎模型 | 真實交易成本 | 實盤級準確 |
| **風險管理** | 固定止損 | 動態支撐壓力 | 智能化 |

---

## 🏗️ 四大核心系統

### 1. 🌌 幣種宇宙管理系統 (Universe Management)
**目標**: 智能化幣種分類與管理

#### 核心功能
- **幣種屬性計算**
  - 30日平均成交額 (volume_30d_usd)
  - 上市天數 (history_days)  
  - 持倉量平均與趨勢
  - 永續合約支援度
  - 穩定幣識別

- **自動分類系統**
  ```
  large_cap:  市值前30, 成交額>$1B
  mid_cap:    市值31-100, 成交額$100M-$1B  
  small_cap:  市值101-500, 成交額$10M-$100M
  micro_cap:  市值500+, 成交額<$10M
  ```

- **輸出格式**
  - Parquet檔案: `universe/binance_{date}.parquet`
  - YAML預設: `configs/universe_smallcap_top200.yml`

#### CLI接口
```bash
superdog data universe build           # 構建幣種宇宙
superdog data universe show small_cap  # 查看小幣池
superdog data universe export --top 200 --type yaml  # 匯出配置
```

---

### 2. 🧪 策略實驗室系統 (Strategy Laboratory)  
**目標**: 大規模策略實驗與參數優化

#### 核心組件

##### ExperimentConfig (實驗配置)
```python
@dataclass
class ExperimentConfig:
    name: str                    # 實驗名稱
    strategy: str               # 策略名稱
    symbol_source: str          # 'explicit' | 'universe'
    universe_type: str          # 'large_cap' | 'small_cap'
    universe_top_n: int         # 取前N名
    symbols: List[str]          # 明確指定幣種
    timeframe: str             # 時間週期
    start_date: str            # 回測開始
    end_date: str              # 回測結束  
    param_grid: Dict           # 參數網格
    metrics: List[str]         # 輸出指標
```

##### ExperimentRunner (實驗執行器)
```python
class ExperimentRunner:
    def run_experiment(config: ExperimentConfig) -> ExperimentResult
    def expand_symbol_universe(config) -> List[str]  # 動態展開幣種
    def expand_param_grid(config) -> List[Dict]      # 展開參數組合
    def execute_backtest_batch(batch) -> List[Result]  # 批量回測
    def handle_failures(failures) -> None           # 失敗處理
```

#### 實驗結果存儲
```python
# 輸出格式: experiment_results_{timestamp}.parquet
columns = [
    'experiment_name', 'strategy', 'symbol', 'timeframe',
    'start_date', 'end_date', 'params_json',
    'total_return', 'sharpe_ratio', 'max_drawdown', 
    'win_rate', 'profit_factor', 'expectancy',
    'total_trades', 'execution_time', 'data_snapshot_id'
]
```

#### CLI接口
```bash
superdog experiment run config.yml         # 執行實驗
superdog experiment best --metric sharpe   # 最佳參數
superdog experiment filter --symbol BTC*   # 篩選結果  
superdog experiment show exp_20231201      # 實驗摘要
```

---

### 3. 💰 真實執行模型 (Execution Model)
**目標**: 接近實盤的回測精度

#### 手續費模型
```python
class FeeModel:
    maker_fee: float = 0.0002      # Maker費率 0.02%
    taker_fee: float = 0.0004      # Taker費率 0.04%
    
    def calculate_fee(order_type, volume, price):
        if order_type == 'limit':
            return volume * price * maker_fee
        else:  # market
            return volume * price * taker_fee
```

#### 滑價模型  
```python
class SlippageModel:
    # v1: 固定滑點
    fixed_slippage_pct: float = 0.0005  # 0.05%
    
    # v2: 動態滑點 (未來版本)
    def calculate_dynamic_slippage(order_size, bar_volume):
        impact_ratio = order_size / bar_volume
        return min(0.002, impact_ratio * 0.1)  # 最大0.2%滑點
```

#### Funding費用模擬
```python
class FundingModel:
    def apply_funding_cost(position, funding_rate, duration_hours):
        funding_periods = duration_hours // 8  # 每8小時結算
        total_funding = position.size * funding_rate * funding_periods
        return total_funding
```

#### 強平風險模型
```python
class LiquidationModel:
    def check_liquidation(position, unrealized_pnl, initial_margin):
        margin_ratio = (initial_margin + unrealized_pnl) / position.notional
        if margin_ratio < 0.1:  # 10%強平線
            return True
        return False
```

---

### 4. 🛡️ 動態支撐壓力系統 (Dynamic Support/Resistance)
**目標**: 智能化風險管理

#### 支撐壓力識別算法
```python
class SupportResistanceDetector:
    def identify_levels(ohlcv_data, perpetual_data):
        # 1. 技術分析法
        swing_levels = find_swing_highs_lows(ohlcv_data, lookback=20)
        pivot_points = calculate_pivot_points(ohlcv_data)
        fibonacci_levels = calculate_fibonacci_retracements(ohlcv_data)
        
        # 2. 永續合約增強法
        funding_extremes = find_funding_rate_extremes(perpetual_data)
        liquidation_clusters = find_liquidation_clusters(perpetual_data)
        oi_resistance = find_oi_resistance_levels(perpetual_data)
        
        # 3. 多因子融合
        final_levels = merge_and_rank_levels([
            swing_levels, pivot_points, funding_extremes, 
            liquidation_clusters, oi_resistance
        ])
        
        return final_levels
```

#### 動態止損止盈
```python
class DynamicRiskManager:
    def calculate_stops(entry_price, entry_signal, market_data):
        sr_levels = get_support_resistance(market_data)
        atr = calculate_atr(market_data, period=14)
        
        if entry_signal == 'LONG':
            stop_loss = sr_levels['nearest_support'] 
            take_profit = sr_levels['nearest_resistance']
        else:  # SHORT
            stop_loss = sr_levels['nearest_resistance']
            take_profit = sr_levels['nearest_support']
            
        # ATR動態調整
        min_stop = entry_price * (1 - 2 * atr / entry_price)
        stop_loss = max(stop_loss, min_stop)
        
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_reward_ratio': abs(take_profit - entry_price) / abs(entry_price - stop_loss)
        }
```

---

## 📋 開發階段規劃

### Phase 1: 幣種宇宙系統 (Week 1-2)
- [ ] `data/universe_manager.py` - 核心宇宙管理器
- [ ] `data/universe/` - 數據存儲目錄結構
- [ ] `configs/universe/` - YAML預設模板
- [ ] CLI命令整合
- [ ] 單元測試 (15+ 測試案例)

### Phase 2: 策略實驗室 (Week 3-4)  
- [ ] `execution_engine/experiments.py` - 實驗配置與執行
- [ ] `execution_engine/experiment_runner.py` - 批量執行器
- [ ] `reports/experiment_store.py` - 結果存儲與查詢
- [ ] CLI實驗命令
- [ ] 整合測試 (20+ 測試案例)

### Phase 3: 真實執行模型 (Week 5)
- [ ] `execution_engine/execution_model.py` - 交易成本模型
- [ ] `execution_engine/fee_models.py` - 手續費計算
- [ ] `execution_engine/slippage_models.py` - 滑價模擬
- [ ] 回測引擎整合
- [ ] 模型驗證測試

### Phase 4: 動態風控系統 (Week 6)  
- [ ] `risk_management/support_resistance.py` - 支撐壓力檢測
- [ ] `risk_management/dynamic_stops.py` - 動態止損
- [ ] 策略API整合
- [ ] 風控策略測試

### Phase 5: 整合與優化 (Week 7)
- [ ] 端到端工作流程測試
- [ ] 性能優化 
- [ ] 用戶文檔完善
- [ ] 最終驗收測試

---

## 🎯 成功標準

### 功能標準
- [ ] 幣種自動分類準確率 >95%
- [ ] 實驗執行成功率 >90% (含失敗容錯)
- [ ] 批量測試效率 >10x單次測試
- [ ] 回測精度提升 >20% (vs v0.5)

### 技術標準  
- [ ] 測試覆蓋率 >85%
- [ ] 文檔完整性 100%
- [ ] API向後兼容 100% 
- [ ] 性能回歸 <10%

### 用戶體驗標準
- [ ] 工作流程時間 <30分鐘 (從數據同步到參數優化)
- [ ] CLI命令學習成本 <1小時
- [ ] 錯誤訊息清晰度 >90%用戶理解
- [ ] 實驗結果可視化完整

---

## 🔧 技術架構升級

### 新增模組結構
```
superdog-quant/
├── data/
│   ├── universe_manager.py          # 🆕 幣種宇宙管理
│   └── universe/                    # 🆕 宇宙數據存儲
├── execution_engine/
│   ├── experiments.py               # 🆕 實驗系統
│   ├── experiment_runner.py         # 🆕 批量執行
│   └── execution_model.py           # 🆕 真實執行模型
├── risk_management/                 # 🆕 風險管理模組
│   ├── support_resistance.py        
│   └── dynamic_stops.py             
└── reports/
    └── experiment_store.py          # 🆕 實驗結果存儲
```

### API升級
- 策略API保持向後兼容
- 新增實驗配置API
- 擴展CLI命令體系
- 增強數據管道接口

---

## 📚 文檔交付清單

### 技術文檔
- [ ] 宇宙管理器API參考
- [ ] 實驗室配置指南  
- [ ] 執行模型參數說明
- [ ] 支撐壓力算法文檔

### 用戶文檔
- [ ] v0.6完整工作流程指南
- [ ] 實驗配置最佳實踐
- [ ] 進階回測指南
- [ ] 故障排除手冊

### 開發文檔  
- [ ] v0.6架構設計文檔
- [ ] API升級指南
- [ ] 測試策略文檔
- [ ] 部署指南

---

## 🚀 預期用戶體驗

完成後的v0.6工作流程：

```bash
# 1. 數據同步
superdog data sync --all

# 2. 構建幣種宇宙  
superdog data universe build

# 3. 查看並選擇宇宙
superdog data universe show small_cap --top 100

# 4. 配置策略實驗
superdog experiment create kawamoku_opt.yml

# 5. 執行批量實驗
superdog experiment run kawamoku_opt.yml

# 6. 分析最佳結果
superdog experiment best --metric sharpe --top 10

# 7. 嚴格回測驗證
superdog run -s kawamoku --params optimal.json --execution-model realistic
```

SuperDog v0.6將成為真正的**企業級量化交易研發平台**！
