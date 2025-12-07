# 🚀 SuperDog v0.5 Phase A - 快速開始

## 一鍵安裝

```bash
# 運行自動安裝腳本
./install_v05.sh
```

這將自動：
- ✅ 創建虛擬環境
- ✅ 安裝所有依賴
- ✅ 運行驗證測試

---

## 手動安裝

```bash
# 1. 創建虛擬環境
python3 -m venv venv

# 2. 激活虛擬環境
source venv/bin/activate

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 驗證安裝
python3 verify_v05_phase_a.py
```

---

## 快速測試

### 1. 獲取最新資金費率

```python
from data.perpetual import get_latest_funding_rate

latest = get_latest_funding_rate('BTCUSDT')
print(f"費率: {latest['funding_rate']:.6f}")
print(f"年化: {latest['annual_rate']:.2f}%")
```

### 2. 分析持倉量趨勢

```python
from data.perpetual import analyze_oi_trend

trend = analyze_oi_trend('BTCUSDT', interval='1h')
print(f"趨勢: {trend['trend']}")
print(f"24h變化: {trend['change_24h_pct']:.2f}%")
```

### 3. 數據品質檢查

```python
from data.quality import DataQualityController
import pandas as pd
import numpy as np

# 創建測試數據
df = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=10, freq='8H'),
    'symbol': 'BTCUSDT',
    'funding_rate': np.random.normal(0.0001, 0.0001, 10)
})

# 檢查品質
qc = DataQualityController()
result = qc.check_funding_rate(df)
print(result.get_summary())
```

---

## 運行測試

```bash
# 驗證 Phase A 安裝
python3 verify_v05_phase_a.py

# 測試實際 API（需要網絡）
python3 examples/test_perpetual_data.py

# 運行單元測試
python3 tests/test_perpetual_v05.py
```

---

## 使用 DataPipeline v0.5

```python
from data.pipeline import get_pipeline
from strategies.kawamoku_demo import KawamokuStrategy

# 獲取管道（現在是 v0.5）
pipeline = get_pipeline()

# 創建策略
strategy = KawamokuStrategy()

# 載入數據（自動包含 OHLCV、資金費率、持倉量）
result = pipeline.load_strategy_data(
    strategy=strategy,
    symbol='BTCUSDT',
    timeframe='1h',
    start_date='2024-01-01',
    end_date='2024-12-31'
)

if result.success:
    # 獲取所有數據
    ohlcv = result.data['ohlcv']
    funding = result.data.get('funding_rate')
    oi = result.data.get('open_interest')

    # 執行策略
    signals = strategy.compute_signals(result.data, params)
```

---

## 常用命令

```bash
# 激活虛擬環境
source venv/bin/activate

# 停用虛擬環境
deactivate

# 查看已安裝的包
pip list

# 更新依賴
pip install --upgrade -r requirements.txt
```

---

## 文檔索引

| 文檔 | 用途 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 本文件 - 快速開始 |
| [README_v05_PHASE_A.md](README_v05_PHASE_A.md) | 詳細使用指南 |
| [SETUP.md](SETUP.md) | 完整安裝說明 |
| [PHASE_A_DELIVERY.md](PHASE_A_DELIVERY.md) | 交付清單 |
| [V05_PHASE_A_SUMMARY.md](V05_PHASE_A_SUMMARY.md) | 總結報告 |

---

## API 快速參考

### Binance Connector

```python
from data.exchanges import BinanceConnector

connector = BinanceConnector()

# 資金費率
df = connector.get_funding_rate('BTCUSDT', start_time, end_time)

# 持倉量
df = connector.get_open_interest('BTCUSDT', interval='1h')

# 標記價格
price = connector.get_mark_price('BTCUSDT')

# 多空比
ratio = connector.get_long_short_ratio('BTCUSDT', interval='1h')
```

### Funding Rate Data

```python
from data.perpetual import FundingRateData

fr = FundingRateData()

# 獲取數據
df = fr.fetch('BTCUSDT', start_time, end_time)

# 統計分析
stats = fr.calculate_statistics(df)

# 異常檢測
anomalies = fr.detect_anomalies(df, threshold=0.005)

# 保存/載入
fr.save(df, 'BTCUSDT', 'binance')
loaded = fr.load('BTCUSDT', 'binance')
```

### Open Interest Data

```python
from data.perpetual import OpenInterestData

oi = OpenInterestData()

# 獲取數據
df = oi.fetch('BTCUSDT', interval='1h')

# 趨勢分析
trend = oi.analyze_trend(df, window=24)

# 突增檢測
spikes = oi.detect_spikes(df, threshold=2.0)

# 統計分析
stats = oi.calculate_statistics(df)
```

### Quality Control

```python
from data.quality import DataQualityController

qc = DataQualityController(strict_mode=False)

# OHLCV 檢查
result = qc.check_ohlcv(ohlcv_df)

# 資金費率檢查
result = qc.check_funding_rate(funding_df)

# 持倉量檢查
result = qc.check_open_interest(oi_df)

# 自動清理
cleaned = qc.clean_ohlcv(ohlcv_df, auto_fix=True)
```

---

## 故障排除

### 問題：ModuleNotFoundError

**解決：**
```bash
# 確保在虛擬環境中
source venv/bin/activate

# 重新安裝依賴
pip install -r requirements.txt
```

### 問題：API 請求失敗

**原因：** 網絡問題或 API 限流

**解決：**
- 檢查網絡連接
- 稍後重試
- 查看日誌輸出

### 問題：Permission denied

**解決：**
```bash
# 給腳本執行權限
chmod +x install_v05.sh
```

---

## 獲取幫助

1. 查看完整文檔：`cat README_v05_PHASE_A.md`
2. 查看安裝指南：`cat SETUP.md`
3. 查看示例代碼：`cat examples/test_perpetual_data.py`
4. 運行驗證腳本：`python3 verify_v05_phase_a.py`

---

**版本：** v0.5 Phase A
**狀態：** ✅ 準備使用
**日期：** 2025-12-07
