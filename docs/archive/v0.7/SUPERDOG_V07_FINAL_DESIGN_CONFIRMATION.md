# SuperDog v0.7 智能數據抓取系統 - 最終設計確認

**文檔版本**: v1.0
**日期**: 2025-12-08
**狀態**: 待用戶確認

---

## 📋 執行摘要

SuperDog v0.7 將新增智能數據抓取系統，解決以下核心問題：

1. ✅ **自動獲取 Top 100 幣種** - 從 Binance API 動態抓取
2. ✅ **多時間週期並行下載** - 100 幣種 × 4 時間週期，從 8 小時縮短至 15 分鐘
3. ✅ **智能符號映射** - 自動處理 BTC/USDT ↔ BTCUSDT 轉換
4. ✅ **配置化管理** - YAML 配置文件，無需改代碼
5. ✅ **斷點續傳** - 下載中斷後可從斷點繼續

---

## 🎯 用戶決策總結（11 項確認）

### 1. 存儲結構
**決策**: A - 按目錄組織
**實現**: `data/raw/binance/BTCUSDT/1h.csv`

### 2. Top 100 來源
**決策**: 簡化為 **僅從 Binance** 獲取
**實現**: 使用 Binance Spot 24h ticker 按成交量排序
**放棄**: CoinGecko 整合（過於複雜）

### 3. 下載策略
**決策**: C - 混合優先（先重要時間週期）
**實現**:
- 優先下載 1h, 1d (Priority 1)
- 後下載 4h, 15m (Priority 2)

### 4. 並行工作數
**決策**: B - 5 個工作執行緒
**理由**: 平衡速度與穩定性

### 5. 1m/5m 數據
**決策**: B - 可選支持（默認關閉）
**實現**: 配置文件中可啟用，但不包含在默認下載列表

### 6. 數據覆蓋策略
**決策**: C - 檢查後決定
**實現**:
- 若檔案存在且完整 → 跳過
- 若檔案不完整或損壞 → 重新下載

### 7. Binance 速率限制
**決策**: B - 1100 請求/分鐘
**理由**: 留 8% 安全餘量（官方限制 1200）

### 8. 幣種過濾邏輯
**決策**: B - 按成交量過濾（採用我的建議）
**實現**:
- ✅ 使用 Binance Spot Top 100（按 24h 成交量）
- ✅ 排除穩定幣（USDC, BUSD, DAI, TUSD, USDT）
- ✅ 排除槓桿代幣（*UP, *DOWN, *BULL, *BEAR）
- ✅ 最低成交量：$1M USD
- ❌ 不驗證永續合約（信任 Top 100 多數有期貨）

### 9. 斷點續傳
**決策**: A - 啟用
**實現**: 使用 JSON checkpoint 檔案記錄進度

### 10. 配置檔位置
**決策**: A - `config/data_download.yaml`
**實現**: 與其他配置文件統一管理

### 11. CoinGecko API
**決策**: 不需要
**理由**: Binance API 已足夠，簡化依賴

---

## 🏗️ 技術架構

### 核心組件

```
data/downloaders/
├── symbol_mapper.py        # 符號映射器
├── top_symbols_fetcher.py  # Top 100 抓取器
├── rate_limiter.py         # 速率限制器
├── multi_tf_downloader.py  # 多時間週期下載器
└── robust_downloader.py    # 健壯下載器（主入口）
```

### 配置檔結構

**config/data_download.yaml**:
```yaml
# 幣種設定
symbols:
  source: binance_top         # 來源：Binance Top 100
  count: 100                  # 數量
  quote_currency: USDT        # 報價幣種
  filters:
    exclude_stablecoins: true
    exclude_leveraged: true
    min_volume_24h: 1000000   # $1M USD

# 時間週期設定
timeframes:
  enabled: [1d, 4h, 1h, 15m]  # 默認啟用
  optional: [1m, 5m]          # 可選（默認不下載）
  priority:
    1d: 1                     # 優先級 1（先下載）
    1h: 1
    4h: 2                     # 優先級 2（後下載）
    15m: 2

# 下載設定
download:
  parallel_workers: 5         # 並行工作數
  checkpoint_enabled: true    # 啟用斷點續傳
  overwrite_strategy: check   # 檢查後決定是否覆蓋

# 速率限制
rate_limiting:
  exchange: binance
  requests_per_minute: 1100   # 留 8% 安全餘量

# 存儲設定
storage:
  base_path: data/raw
  structure: by_symbol        # 按符號組織目錄
  format: csv
```

---

## 📦 存儲結構

```
data/raw/
└── binance/
    ├── BTCUSDT/
    │   ├── 1d.csv
    │   ├── 4h.csv
    │   ├── 1h.csv
    │   └── 15m.csv
    ├── ETHUSDT/
    │   ├── 1d.csv
    │   ├── 4h.csv
    │   ├── 1h.csv
    │   └── 15m.csv
    └── ...（98 個幣種）
```

**CSV 格式**（與現有格式兼容）:
```
timestamp,open,high,low,close,volume
2024-01-01 00:00:00,42000.0,42500.0,41800.0,42300.0,1234.56
...
```

---

## 🔄 下載流程

### Phase 1: 符號發現
1. 從 Binance API 獲取 24h ticker
2. 過濾：quote = USDT, volume > $1M
3. 排除穩定幣和槓桿代幣
4. 按成交量排序，取 Top 100

### Phase 2: 多時間週期下載
1. 讀取配置檔 `config/data_download.yaml`
2. 創建 5 個工作執行緒
3. 按優先級排序任務：
   - Priority 1: 1h, 1d（先下載）
   - Priority 2: 4h, 15m（後下載）
4. 每個任務：
   - 檢查本地檔案是否存在且完整
   - 若不存在或損壞 → 下載
   - 若存在且完整 → 跳過
5. 定期保存 checkpoint（每 10 個符號）

### Phase 3: 驗證與報告
1. 檢查所有下載檔案的完整性
2. 生成下載報告：
   - 成功數量
   - 失敗數量
   - 跳過數量（已存在）
3. 記錄到日誌

---

## ⏱️ 性能預估

### 單線程（現狀）
- 100 幣種 × 4 時間週期 = 400 個下載任務
- 每個任務 ~1 分鐘（含 API 等待）
- **總時間**: 6-8 小時

### 5 線程並行（v0.7）
- 400 個任務 ÷ 5 執行緒 = 80 個任務/執行緒
- 每個任務 ~30 秒（優化後）
- **總時間**: 10-15 分鐘

**性能提升**: ~30x

---

## 🛡️ 錯誤處理

### 1. API 錯誤
- 429 Too Many Requests → 自動降速，等待後重試
- 500 Server Error → 指數退避重試（最多 3 次）
- 404 Symbol Not Found → 記錄日誌，跳過該幣種

### 2. 網絡錯誤
- 連接超時 → 重試（最多 3 次）
- 連接中斷 → 保存 checkpoint，下次從斷點繼續

### 3. 數據驗證錯誤
- 檔案大小 < 1KB → 視為損壞，重新下載
- CSV 格式錯誤 → 記錄日誌，重新下載
- 時間戳不連續 → 警告但保留檔案

---

## 🔗 整合計劃

### 1. UniverseManager 整合
**修改檔案**: `data/universe_manager.py`

**增強 `_discover_symbols()` 方法**:
```python
def _discover_symbols(
    self,
    source: str = 'local',  # 新增參數：'local' 或 'binance'
    count: int = 100
) -> List[str]:
    """
    發現可用幣種

    Args:
        source: 'local'（掃描本地檔案） 或 'binance'（從 API 獲取）
        count: 若 source='binance'，返回 Top N 個幣種
    """
    if source == 'binance':
        from data.downloaders.top_symbols_fetcher import TopSymbolsFetcher
        fetcher = TopSymbolsFetcher()
        return fetcher.get_top_symbols(n=count, quote='USDT')
    else:
        # 現有邏輯：掃描 data/raw/*_1d.csv
        ...
```

**向後兼容**: 默認 `source='local'`，不影響現有代碼

### 2. CLI 整合
**新增命令**: `python -m cli.main download`

```bash
# 下載 Top 100（使用配置檔默認值）
python -m cli.main download

# 下載指定數量
python -m cli.main download --count 50

# 下載指定時間週期
python -m cli.main download --timeframes 1d,1h

# 強制覆蓋
python -m cli.main download --force-overwrite

# 從斷點繼續
python -m cli.main download --resume
```

### 3. 現有 Fetcher 保留
**data/fetcher.py** 保持不變，用於：
- 下載單一幣種
- 自定義時間範圍
- 測試和調試

---

## 📂 新增檔案清單

### 核心模組（5 個）
1. `data/downloaders/symbol_mapper.py` (~150 行)
2. `data/downloaders/top_symbols_fetcher.py` (~200 行)
3. `data/downloaders/rate_limiter.py` (~100 行)
4. `data/downloaders/multi_tf_downloader.py` (~300 行)
5. `data/downloaders/robust_downloader.py` (~250 行)

### 配置檔（1 個）
6. `config/data_download.yaml` (~50 行)

### 測試檔案（5 個）
7. `tests/test_symbol_mapper.py` (~150 行)
8. `tests/test_top_symbols_fetcher.py` (~200 行)
9. `tests/test_rate_limiter.py` (~100 行)
10. `tests/test_multi_tf_downloader.py` (~200 行)
11. `tests/test_robust_downloader.py` (~150 行)

### 文檔（2 個）
12. `docs/v0.7/SUPERDOG_V07_DATA_DOWNLOAD_DESIGN.md` (已完成 - 1,755 行)
13. `docs/v0.7/SUPERDOG_V07_USER_GUIDE.md` (~300 行)

**總代碼量**: ~2,000 行（不含註釋和文檔）

---

## 🕐 開發估時

### Phase 1: 基礎組件（8 小時）
- SymbolMapper: 2 小時
- RateLimiter: 2 小時
- ConfigLoader: 1 小時
- TopSymbolsFetcher: 3 小時

### Phase 2: 下載器（10 小時）
- MultiTimeframeDownloader: 5 小時
- RobustDownloader: 5 小時

### Phase 3: 整合與測試（7 小時）
- UniverseManager 整合: 2 小時
- CLI 命令: 2 小時
- 單元測試: 3 小時

**總開發時間**: 25 小時（約 3-4 個工作日）

---

## ✅ 測試計劃

### 單元測試
1. SymbolMapper: 測試 10+ 交易所的符號轉換
2. TopSymbolsFetcher: 測試過濾邏輯（穩定幣、槓桿代幣）
3. RateLimiter: 測試速率限制和並發安全性
4. MultiTimeframeDownloader: 測試優先級排序和斷點續傳
5. RobustDownloader: 測試錯誤處理和重試邏輯

### 整合測試
1. 下載 10 個幣種（小規模測試）
2. 驗證檔案格式和完整性
3. 測試斷點續傳（模擬中斷）
4. 測試覆蓋策略
5. 驗證 UniverseManager 整合

### 真實環境測試
1. 下載 Top 100 幣種，4 個時間週期
2. 驗證性能（目標：15 分鐘內完成）
3. 驗證所有檔案可被 UniverseManager 讀取
4. 運行 `universe_manager.build_universe()` 確認無錯誤

---

## 📊 成功標準

### 功能性標準
- ✅ 能自動獲取 Binance Top 100 幣種
- ✅ 能並行下載 4 個時間週期（1d, 4h, 1h, 15m）
- ✅ 能正確過濾穩定幣和槓桿代幣
- ✅ 能保存為 UniverseManager 兼容的格式
- ✅ 支持斷點續傳

### 性能標準
- ✅ 100 幣種 × 4 時間週期 < 20 分鐘
- ✅ 無速率限制錯誤（429 Too Many Requests）
- ✅ 成功率 > 95%

### 品質標準
- ✅ 單元測試覆蓋率 > 80%
- ✅ 所有測試通過
- ✅ 無 linting 錯誤（black, isort, flake8）
- ✅ 完整的用戶文檔

---

## 🎯 v0.7 vs v0.6 對比

| 功能 | v0.6 | v0.7 |
|------|------|------|
| **幣種來源** | 手動指定 | 自動從 Binance Top 100 |
| **符號映射** | 手動轉換 | 自動映射（SymbolMapper） |
| **下載方式** | 單線程 | 5 線程並行 |
| **下載時間** | 6-8 小時 | 10-15 分鐘 |
| **配置管理** | 硬編碼 | YAML 配置檔 |
| **斷點續傳** | 不支持 | 支持 |
| **錯誤處理** | 基本重試 | 智能重試 + 降速 |
| **過濾邏輯** | 無 | 穩定幣、槓桿代幣、成交量過濾 |

---

## ⚠️  已知限制

### 1. 單一交易所
- **限制**: 僅支持 Binance
- **影響**: 無法獲取 Bybit、OKX 獨有幣種
- **未來**: v0.8 可擴展多交易所

### 2. 無歷史快照
- **限制**: 只抓取當前 Top 100，不保存歷史排名
- **影響**: 無法分析排名變化
- **未來**: v0.8 可新增 snapshot 功能

### 3. 無市值數據
- **限制**: 未整合 CoinGecko 市值數據
- **影響**: UniverseCalculator 的市值分類功能受限
- **解決方案**: 用成交量分類代替市值分類

### 4. 固定時間範圍
- **限制**: 默認下載最近 365 天數據（配置檔可調整）
- **影響**: 無法靈活指定開始/結束日期
- **解決方案**: 保留 `data/fetcher.py` 用於自定義下載

---

## 📝 開發準則（遵循用戶要求）

### Git 提交前檢查清單
- [ ] 已閱讀所有相關文檔
- [ ] 已更新 CHANGELOG.md
- [ ] 未創建重複模組
- [ ] 已更新所有引用
- [ ] 已運行 pre-commit hooks
- [ ] 所有測試通過
- [ ] 代碼已格式化（black, isort）

### Git 提交格式
```
feat: SuperDog v0.7 智能數據抓取系統

新增功能:
• 自動獲取 Binance Top 100 幣種
• 多時間週期並行下載（5 workers）
• 智能符號映射與速率限制
• YAML 配置管理與斷點續傳

技術實現:
• data/downloaders/: 5 個核心模組
• config/data_download.yaml: 配置檔
• tests/: 5 個測試檔案
• 性能提升 30x（8h → 15min）

🤖 Generated with Claude Code
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## 🚀 下一步行動

### 待用戶確認
請確認以下內容無誤：

1. ✅ 11 項技術決策是否符合預期？
2. ✅ 配置檔結構是否合理？
3. ✅ 過濾邏輯是否正確（排除穩定幣、槓桿代幣、成交量 > $1M）？
4. ✅ 開發估時（25 小時）是否可接受？
5. ✅ 已知限制（單一交易所、無市值數據）是否可接受？

### 確認後開發流程
1. 更新 CHANGELOG.md（新增 v0.7 條目）
2. Phase 1: 開發基礎組件（8 小時）
3. Phase 2: 開發下載器（10 小時）
4. Phase 3: 整合與測試（7 小時）
5. 運行完整驗證測試
6. Git commit（遵循開發準則）

---

## 📞 待回覆

**請用戶回覆**:
1. "確認，開始開發" → 我將立即開始 Phase 1
2. "有疑問：[具體問題]" → 我將解答並修改設計
3. "需要調整：[具體調整]" → 我將更新設計文檔

---

**文檔結束**
**等待用戶最終確認...**
