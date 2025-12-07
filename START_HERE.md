# 🚀 START HERE - SuperDog v0.5 Phase A

> **兩步驟開始使用永續合約數據！**

---

## 步驟 1: 安裝（1 分鐘）

```bash
./install_v05.sh
```

這會自動完成：
- ✅ 創建虛擬環境
- ✅ 安裝所有依賴
- ✅ 驗證系統正常

---

## 步驟 2: 測試（1 分鐘）

```bash
python3 examples/test_perpetual_data.py
```

你將看到：
- ✅ BTC 當前資金費率
- ✅ 歷史資金費率統計
- ✅ 持倉量趨勢分析
- ✅ 數據品質檢查

---

## 🎯 核心功能速覽

### 1️⃣ 獲取最新資金費率

```python
from data.perpetual import get_latest_funding_rate

latest = get_latest_funding_rate('BTCUSDT')
print(f"費率: {latest['funding_rate']:.6f}")
print(f"年化: {latest['annual_rate']:.2f}%")
```

### 2️⃣ 分析持倉量趨勢

```python
from data.perpetual import analyze_oi_trend

trend = analyze_oi_trend('BTCUSDT')
print(f"趨勢: {trend['trend']}")
print(f"24h變化: {trend['change_24h_pct']:.2f}%")
```

### 3️⃣ 使用 DataPipeline v0.5

```python
from data.pipeline import get_pipeline

pipeline = get_pipeline()  # 現在是 v0.5
result = pipeline.load_strategy_data(strategy, 'BTCUSDT', '1h')

# 自動載入 OHLCV + 資金費率 + 持倉量
```

---

## 📚 完整文檔

| 需求 | 文檔 |
|------|------|
| 快速開始 | [QUICKSTART.md](QUICKSTART.md) |
| 詳細指南 | [README_v05_PHASE_A.md](README_v05_PHASE_A.md) |
| 安裝問題 | [SETUP.md](SETUP.md) |
| 完整報告 | [V05_PHASE_A_SUMMARY.md](V05_PHASE_A_SUMMARY.md) |

---

## 💡 常用命令

```bash
# 激活虛擬環境
source venv/bin/activate

# 驗證安裝
python3 verify_v05_phase_a.py

# 運行測試
python3 tests/test_perpetual_v05.py

# Python 交互式
python3
>>> from data.perpetual import get_latest_funding_rate
>>> latest = get_latest_funding_rate('BTCUSDT')
```

---

## ❓ 遇到問題？

### 依賴安裝失敗
```bash
# 檢查 Python 版本（需要 3.8+）
python3 --version

# 手動安裝
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### API 測試失敗
- 檢查網絡連接
- 確認可以訪問 Binance API
- 稍後重試（可能是 API 限流）

### 其他問題
查看完整安裝指南：`cat SETUP.md`

---

## 🎊 Phase A 完成內容

✅ **Binance API 連接器** - 完整實現
✅ **資金費率處理** - 統計、異常檢測、存儲
✅ **持倉量處理** - 趨勢分析、突增檢測
✅ **數據品質控制** - 多層級檢查、自動清理
✅ **DataPipeline v0.5** - 完全向後兼容
✅ **16 個測試用例** - 完整測試覆蓋

---

**準備好了嗎？執行 `./install_v05.sh` 開始吧！** 🚀

---

**版本：** v0.5 Phase A
**狀態：** ✅ 準備使用
**日期：** 2025-12-07
