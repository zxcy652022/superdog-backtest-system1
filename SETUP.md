# SuperDog v0.5 安裝指南

## 🚀 快速開始

SuperDog v0.5 Phase A 已經完成！這份文檔將指導你完成環境設置。

---

## 📋 系統需求

- **Python:** 3.8 或更高版本
- **操作系統:** macOS, Linux, 或 Windows
- **磁碟空間:** 至少 1GB 用於依賴和數據
- **網絡:** 需要訪問 Binance API（用於獲取數據）

---

## 🔧 安裝步驟

### 選項 1: 使用虛擬環境（推薦）

虛擬環境可以隔離項目依賴，避免與系統 Python 衝突。

```bash
# 1. 進入項目目錄
cd /Users/ddragon/Projects/superdog-quant

# 2. 創建虛擬環境
python3 -m venv venv

# 3. 激活虛擬環境
source venv/bin/activate

# 4. 升級 pip
pip install --upgrade pip

# 5. 安裝依賴
pip install -r requirements.txt

# 6. 驗證安裝
python verify_v05_phase_a.py
```

**注意：** 每次使用時都需要激活虛擬環境：
```bash
source venv/bin/activate
```

### 選項 2: 使用 Conda（如果已安裝）

```bash
# 1. 創建 conda 環境
conda create -n superdog python=3.10

# 2. 激活環境
conda activate superdog

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 驗證安裝
python verify_v05_phase_a.py
```

### 選項 3: 使用 --break-system-packages（不推薦）

⚠️ **警告：** 這可能會影響系統 Python，僅在你知道自己在做什麼時使用。

```bash
pip3 install --break-system-packages -r requirements.txt
```

---

## ✅ 驗證安裝

### 1. 運行驗證腳本

```bash
python3 verify_v05_phase_a.py
```

**預期輸出：**
```
╔════════════════════════════════════════════════════════════════════╗
║               SuperDog v0.5 Phase A 驗證                           ║
╚════════════════════════════════════════════════════════════════════╝

======================================================================
驗證 v0.5 Phase A 模組導入
======================================================================

1. Exchange Connectors...
   ✓ Exchange connectors imported successfully

2. Perpetual Data Processing...
   ✓ Perpetual data modules imported successfully

3. Quality Control...
   ✓ Quality control modules imported successfully

4. DataPipeline v0.5...
   ✓ DataPipeline v0.5 loaded successfully

======================================================================
SuperDog v0.5 Phase A 驗證總結
======================================================================

模組導入: 4/4 通過
功能測試: 5/5 通過
文件結構: 11/11 存在

🎉 Phase A 驗證完全通過！
```

### 2. 測試實際功能（需要網絡）

```bash
# 測試 API 連接和數據獲取
python3 examples/test_perpetual_data.py
```

這將實際連接 Binance API 並獲取數據。

### 3. 運行單元測試

```bash
# 運行完整的測試套件
python3 tests/test_perpetual_v05.py
```

---

## 📦 依賴列表

以下是 SuperDog v0.5 所需的 Python 包：

| 包名 | 版本 | 用途 |
|------|------|------|
| pandas | ≥2.0.0 | 數據處理和分析 |
| numpy | ≥1.24.0 | 數值計算 |
| requests | ≥2.31.0 | HTTP API 請求 |
| pyarrow | ≥12.0.0 | Parquet 文件支援 |

**可選依賴（Phase C）：**
- matplotlib ≥3.7.0 - 數據可視化
- scipy ≥1.10.0 - 高級統計分析

---

## 🎯 快速測試

安裝完成後，你可以運行以下代碼快速測試功能：

### Python 交互式測試

```bash
python3
```

然後在 Python 交互式環境中：

```python
# 測試導入
from data.perpetual import get_latest_funding_rate
from data.exchanges import BinanceConnector
from data.quality import DataQualityController

# 測試 Binance 連接器
connector = BinanceConnector()
print(f"✓ Binance Connector: {connector.name}")

# 測試獲取最新資金費率（需要網絡）
try:
    latest = get_latest_funding_rate('BTCUSDT')
    print(f"✓ 當前 BTC 資金費率: {latest['funding_rate']:.6f}")
    print(f"✓ 年化費率: {latest['annual_rate']:.2f}%")
except Exception as e:
    print(f"⚠ API 請求失敗（可能是網絡問題）: {e}")

# 測試品質控制
import pandas as pd
import numpy as np

qc = DataQualityController()
test_df = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=10, freq='8H'),
    'symbol': 'BTCUSDT',
    'funding_rate': np.random.normal(0.0001, 0.0001, 10)
})

result = qc.check_funding_rate(test_df)
print(f"✓ 品質檢查: {result.passed}")

print("\n🎉 所有組件正常工作！")
```

---

## 🐛 故障排除

### 問題 1: ModuleNotFoundError: No module named 'pandas'

**解決方案：**
- 確保已經安裝了依賴
- 檢查是否在正確的虛擬環境中
- 嘗試重新安裝：`pip install pandas numpy requests pyarrow`

### 問題 2: Permission denied 或 externally-managed-environment

**解決方案：**
- 使用虛擬環境（推薦）
- 或使用 `pip install --user`
- 或使用 conda 環境

### 問題 3: API 請求失敗

**可能原因：**
- 網絡連接問題
- Binance API 暫時不可用
- 達到 API 限流

**解決方案：**
- 檢查網絡連接
- 稍後重試
- 查看 Binance API 狀態頁面

### 問題 4: Parquet 文件錯誤

**解決方案：**
```bash
pip install pyarrow --upgrade
```

---

## 📂 SSD 數據存儲配置

SuperDog v0.5 使用 SSD 來存儲永續合約數據以獲得更好的性能。

**默認存儲位置：**
```
/Volumes/權志龍的寶藏/SuperDogData/perpetual/
├── funding_rate/
│   └── binance/
│       └── BTCUSDT_funding_rate_YYYYMMDD_YYYYMMDD.parquet
└── open_interest/
    └── binance/
        └── BTCUSDT_open_interest_1h_YYYYMMDD_YYYYMMDD.parquet
```

**如果 SSD 路徑不存在：**

數據將自動存儲到項目目錄下的臨時位置。你可以在代碼中自定義存儲路徑：

```python
from data.perpetual import FundingRateData
from pathlib import Path

# 使用自定義路徑
custom_path = Path.home() / "superdog_data" / "perpetual" / "funding_rate"
fr = FundingRateData(storage_path=custom_path)
```

---

## 🚀 下一步

安裝完成後，你可以：

1. **閱讀文檔**
   - [README_v05_PHASE_A.md](README_v05_PHASE_A.md) - 快速入門
   - [PHASE_A_DELIVERY.md](PHASE_A_DELIVERY.md) - 完整功能清單
   - [docs/v0.5_phase_a_completion.md](docs/v0.5_phase_a_completion.md) - 詳細報告

2. **運行示例**
   - [examples/test_perpetual_data.py](examples/test_perpetual_data.py) - 實際 API 測試

3. **開始使用**
   ```python
   # 獲取資金費率
   from data.perpetual import get_latest_funding_rate
   latest = get_latest_funding_rate('BTCUSDT')

   # 分析持倉量
   from data.perpetual import analyze_oi_trend
   trend = analyze_oi_trend('BTCUSDT')
   ```

4. **整合到策略**
   ```python
   # 在你的策略中使用永續數據
   from data.pipeline import get_pipeline

   pipeline = get_pipeline()  # 現在是 v0.5
   result = pipeline.load_strategy_data(strategy, 'BTCUSDT', '1h')
   ```

---

## 📞 獲取幫助

如果遇到問題：

1. 查看 [故障排除](#-故障排除) 部分
2. 閱讀完整文檔
3. 檢查測試文件中的使用示例
4. 查看日誌輸出（使用 `logging` 模組）

---

## ✅ 安裝檢查清單

使用此清單確保一切正確設置：

- [ ] Python 3.8+ 已安裝
- [ ] 虛擬環境已創建並激活
- [ ] 所有依賴已安裝（pandas, numpy, requests, pyarrow）
- [ ] 驗證腳本通過（`python3 verify_v05_phase_a.py`）
- [ ] 可以成功導入模組
- [ ] API 測試腳本可以運行（需要網絡）
- [ ] 了解數據存儲位置

---

**版本：** v0.5 Phase A
**最後更新：** 2025-12-07
**狀態：** ✅ 準備使用
