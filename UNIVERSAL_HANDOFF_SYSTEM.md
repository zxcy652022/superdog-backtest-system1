# Claude ↔ GPT 通用接力系統

## 🎯 系統目標

讓 GPT (Codex) 能夠無縫接續 Claude 的設計與實作，無論在任何開發階段。

---

## 📋 兩種接力場景

### 場景 A：設計已完成（有完整文件）
```
Claude：設計完成，生成了所有 spec 文件
你：Claude 額度用完了
GPT：接手實作
```

### 場景 B：設計討論完成（無文件）
```
Claude：和你討論完設計理念
你：Claude 額度用完了，還沒生成文件
GPT：接手生成文件 + 實作
```

---

# 場景 A：有完整設計文件時

## 📝 給 GPT 的提示詞範本

```markdown
# 接力開發任務

## 🎯 你的角色

你現在是 SuperDog Backtest System 的「實作工程師」。

**關鍵規則**：
- Claude 已完成所有設計決策
- 你的任務是「嚴格執行」，不是「重新設計」
- 遇到不清楚的地方：詢問，不要猜測
- 所有 API 定義、命名、邏輯都已確定

---

## 📚 設計文件位置

```
docs/specs/[當前版本]/
├── SUMMARY.md              ← 最重要，先讀這個
├── architecture.md         ← 整體架構
├── [feature]_spec.md       ← 各功能的詳細規格
└── test_plan.md            ← 測試案例
```

**你必須先閱讀**：
1. `SUMMARY.md`（整體概覽）
2. 你要實作的功能對應的 spec

---

## 🎯 當前任務

**功能**：[功能名稱，例如：Portfolio Runner]

**檔案**：[要建立/修改的檔案，例如：execution/portfolio_runner.py]

**參考文件**：[對應的 spec 檔案，例如：v0.3_portfolio_runner_api.md]

---

## 📐 完整的 API 定義

**從設計文件複製完整的 API**：

```python
# [完整的 class 定義]
# [完整的 function signatures]
# [完整的 docstrings]
# [完整的 type hints]

[例如]
@dataclass
class PortfolioResult:
    """批量回測結果

    Attributes:
        runs: 所有單次回測結果
        start_time: 開始時間
        end_time: 結束時間
    """
    runs: List[SingleRunResult]
    start_time: datetime
    end_time: datetime

    def to_dataframe(self) -> pd.DataFrame:
        """轉換為 DataFrame（用於排行）

        Returns:
            包含以下欄位的 DataFrame：
            - strategy: str
            - symbol: str
            - total_return: float
            - max_drawdown: float
            - profit_factor: float
            - num_trades: int
        """
        pass

    def get_best_by(self, metric: str) -> SingleRunResult:
        """找出某指標最好的回測

        Args:
            metric: 指標名稱（例如 "total_return"）

        Returns:
            表現最好的回測結果

        Raises:
            ValueError: 如果指標不存在
        """
        pass
```

---

## 🧪 測試案例（必須通過）

**從 test_plan.md 複製相關測試**：

```python
# tests/test_[功能名稱].py

def test_[具體功能]():
    """測試 [功能描述]"""
    # Arrange
    [設置測試資料]

    # Act
    [執行功能]

    # Assert
    [驗證結果]
    assert [條件]
```

**所有測試案例**：
- test_case_1: [描述]
- test_case_2: [描述]
- test_case_3: [描述]

---

## ⚠️ 嚴格遵守的規則

### 1. API 一致性
```
❌ 不允許：
- 改變函數名稱
- 改變參數順序或名稱
- 改變回傳值型別
- 加入設計中沒有的參數

✅ 必須：
- 完全按照 API 定義實作
- 保持所有命名一致
- 保持所有型別一致
```

### 2. 向後相容
```
❌ 不允許：
- 修改現有的 v0.X API
- 改變現有函數的行為
- 刪除或重命名現有變數

✅ 必須：
- 只新增，不修改
- 如果必須修改，先詢問
- 確保舊版本測試繼續通過
```

### 3. 程式碼風格
```
專案規範：
- Python 3.11+
- Type hints（強制）
- Docstring（Google style，強制）
- 不使用 sys.path.append
- 遵循現有的命名慣例

範例：
def function_name(param: Type) -> ReturnType:
    """簡短說明

    Args:
        param: 參數說明

    Returns:
        回傳值說明

    Raises:
        ExceptionType: 什麼情況會拋錯
    """
    pass
```

---

## 📊 實作步驟

### Step 1: 建立檔案骨架
```python
# [檔案路徑]

# Imports
from typing import [...]
import [...]

# Classes/Functions（先寫骨架）
class ClassName:
    """[Docstring]"""

    def method_name(self, param: Type) -> ReturnType:
        """[Docstring]"""
        pass  # TODO: 實作
```

### Step 2: 實作核心邏輯
```python
# 按照設計文件的邏輯實作
# 注意邊界條件處理
# 注意錯誤處理
```

### Step 3: 寫測試
```python
# tests/test_[模組].py
# 實作所有測試案例
```

### Step 4: 執行驗證
```bash
pytest tests/test_[模組].py -v
pytest  # 確保沒破壞其他測試
```

---

## 🚨 遇到問題時

### 如果設計不清楚
```
格式：
"設計文件中 [具體位置] 的 [問題] 不清楚。

 我的理解是：
 [你的理解]

 請確認是否正確。"
```

### 如果發現設計缺陷
```
格式：
"在實作 [功能] 時發現問題：

 問題：[具體描述]
 影響：[哪些地方受影響]
 建議：[你的建議方案]

 是否需要調整設計？"
```

### 預設行為
```
如果不確定：不要做

然後問：
"設計文件沒有提到 [事項]，我應該：
 A. 不實作（留給未來版本）
 B. 實作（理由：...）

 請選擇。"
```

---

## ✅ 完成檢查清單

```
□ API 定義與設計文件完全一致
□ 所有參數名稱、型別正確
□ 所有邊界條件已處理
□ 錯誤訊息清晰有用
□ 所有測試通過
□ 沒有破壞現有功能
□ 有完整的 docstring
□ 有完整的 type hints
```

---

## 🎯 立即開始

請：
1. 確認你已閱讀對應的設計文件
2. 確認你理解 API 定義
3. 開始實作 Step 1
4. 完成後回報

**準備好了嗎？** 🚀
```

---

# 場景 B：只有討論，無文件時

## 📝 給 GPT 的提示詞範本

```markdown
# 接力開發任務（從討論到實作）

## 🎯 你的角色

你現在要接手 SuperDog Backtest System 的開發。

**情況**：
- Claude 已與用戶討論完設計理念
- 但還沒生成完整的設計文件
- 你需要先生成文件，再實作

**關鍵規則**：
- 嚴格按照「討論摘要」中的決策
- 不要自己發揮或改變設計
- 遇到未決定的細節：詢問，不要猜

---

## 💬 討論摘要（從對話中提取）

### 功能目標
```
[簡短描述這次要做什麼]

例如：
v0.3 要新增批量回測功能，讓系統可以一次執行多個策略、多個商品的回測。
```

### 核心決策
```
[列出所有重要的設計決策]

例如：
1. 架構決策：
   - 新增 Portfolio Runner 作為統籌層
   - 不動 v0.2 的核心引擎
   - 使用 Strategy Registry 實現 plug-in

2. 做空/槓桿決策：
   - 使用 direction 欄位（"long"|"short"|"flat"）
   - 槓桿只影響資金占用，不檢查保證金
   - SL/TP 要方向感知

3. 執行模式：
   - v0.3 使用序列執行（不做平行）
   - 單個失敗不影響其他

4. 報表：
   - 純文字格式
   - 不做 ASCII 圖表
   - 提供排行表

5. 範圍限制：
   - 不支援 multi-timeframe
   - 不支援資金池
   - 完整模型留給 v0.4
```

### 模組清單
```
[列出要新增/修改的模組]

例如：
新增：
- execution/portfolio_runner.py
- strategies/registry.py
- reports/text_reporter.py
- cli/backtest.py

修改：
- backtest/broker.py（加入做空支援）
- backtest/engine.py（SL/TP 方向感知）
```

### 關鍵 API 概念
```
[列出重要的 API 設計概念，不用完整定義]

例如：
Portfolio Runner：
- 輸入：List[RunConfig]
- 輸出：PortfolioResult
- RunConfig 包含：strategy, symbol, timeframe, start, end, ...
- PortfolioResult 有 to_dataframe() 方法

Broker 做空：
- 新增 direction 欄位
- buy() 語義改為「開多 or 平空」
- sell() 語義改為「開空 or 平多」
```

### 測試要求
```
[測試的基本要求]

例如：
- 每個新功能至少 3 個測試
- 必須測試邊界條件
- 必須測試錯誤處理
- v0.2 的測試要繼續通過
```

---

## 🎯 你的任務（分兩階段）

### 階段 1：生成設計文件

**請生成以下文件**：

#### 1. [功能]_architecture.md
```
內容：
- 模組關係圖（用 Mermaid 或文字）
- 資料流圖
- 與現有系統的整合點
- 向後相容性分析
```

#### 2. [功能]_api_spec.md
```
內容：
- 所有新增 class 的完整定義
- 所有新增 function 的完整 signature
- 所有參數的說明
- 所有回傳值的說明
- 錯誤處理規則
```

#### 3. [功能]_test_plan.md
```
內容：
- 完整的測試案例清單（至少 20 個）
- 分類：單元測試、整合測試、E2E 測試
- 每個測試的輸入、預期輸出
```

**生成規範**：
```
1. Markdown 格式
2. 包含完整的 Python code blocks
3. 所有 API 都要有完整的 docstring
4. 所有決策都要有理由說明
5. 標註「待決策」的項目（如果有）
```

**生成順序**：
```
1. 先生成 architecture.md（讓我確認）
2. 確認後，生成 api_spec.md（讓我確認）
3. 確認後，生成 test_plan.md
4. 全部確認後，進入階段 2
```

---

### 階段 2：實作

（使用「場景 A」的流程）

---

## ⚠️ 設計文件的品質標準

### 1. API 定義必須完整
```
❌ 不夠好：
def process(data):
    """處理資料"""
    pass

✅ 好：
def process(data: pd.DataFrame, mode: str = "fast") -> dict:
    """處理資料並回傳統計結果

    Args:
        data: OHLCV DataFrame，必須包含 open/high/low/close/volume 欄位
        mode: 處理模式，可選 "fast" 或 "accurate"（預設 "fast"）

    Returns:
        包含以下鍵的字典：
        - "mean": 平均值
        - "std": 標準差
        - "count": 資料筆數

    Raises:
        ValueError: 如果 data 缺少必要欄位
        ValueError: 如果 mode 不是有效值

    Example:
        >>> df = load_ohlcv("BTC.csv")
        >>> result = process(df, mode="fast")
        >>> print(result["mean"])
        50123.45
    """
    pass
```

### 2. 決策必須有理由
```
❌ 不夠好：
使用 Click 作為 CLI 框架。

✅ 好：
使用 Click 作為 CLI 框架。

理由：
1. 比 argparse 更簡潔（decorator 風格）
2. 自動生成 help 訊息
3. 支援子命令（未來可能需要）
4. 專案規模小，不需要 Typer 的複雜功能

替代方案：
- argparse：內建但語法繁瑣
- Typer：功能強但過於複雜
```

### 3. 測試案例必須可執行
```
❌ 不夠好：
測試基本功能

✅ 好：
def test_portfolio_runner_single_backtest():
    """測試執行單一回測"""
    # Arrange
    config = RunConfig(
        strategy="simple_sma",
        symbol="BTCUSDT",
        timeframe="1h",
        initial_cash=10000
    )
    runner = PortfolioRunner()

    # Act
    result = runner.run([config])

    # Assert
    assert len(result.runs) == 1
    assert result.runs[0].strategy == "simple_sma"
    assert result.runs[0].error is None
    assert isinstance(result.runs[0].backtest_result, BacktestResult)
```

---

## 🔍 生成文件時的自我檢查

生成每個文件後，檢查：

```
□ 所有 class 都有完整定義
□ 所有 method 都有完整 signature
□ 所有參數都有型別標註
□ 所有參數都有說明
□ 所有回傳值都有說明
□ 所有可能的錯誤都有說明
□ 複雜邏輯有 pseudo code
□ 關鍵決策有理由說明
□ 測試案例可以直接執行
```

---

## 🚨 特別注意

### 不要自己「補充」設計
```
❌ 錯誤：
"討論中沒提到錯誤處理，我自己設計一個..."

✅ 正確：
"討論中沒提到錯誤處理，請問：
 A. 拋出 Exception（哪種？）
 B. 回傳 None
 C. 回傳錯誤物件
 請選擇並說明。"
```

### 不要改變已決定的事
```
❌ 錯誤：
"討論決定用序列執行，但我覺得平行比較好..."

✅ 正確：
"討論決定用序列執行，我將按此實作。"
```

---

## 🎯 立即開始

請：
1. 仔細閱讀「討論摘要」
2. 確認你理解所有決策
3. 開始生成「architecture.md」
4. 生成後給我確認

**準備好了嗎？** 🚀
```

---

# 通用的「討論摘要」產出器

## 📝 Claude 的任務（在額度用完前）

```markdown
在我的額度快用完時，請生成「GPT 接力包」：

## GPT 接力包內容

### 1. 討論摘要
```
功能目標：[1-2 句話]

核心決策：
- 架構決策：[列點]
- 技術選型：[列點]
- API 設計：[列點]
- 範圍限制：[列點]

模組清單：
新增：[列出]
修改：[列出]

關鍵 API 概念：[簡要說明]

測試要求：[基本要求]
```

### 2. 關鍵程式碼骨架
```python
# 給 GPT 參考的程式碼結構

[完整的 class/function 骨架]
[包含 docstring]
[不用實作細節，但結構要完整]
```

### 3. 示例對話
```
[貼上我們討論的關鍵片段]
[特別是做決策的部分]
```

---

請生成以上三個部分，讓 GPT 可以無縫接手。
```

---

# 最佳實踐總結

## ✅ 成功接力的關鍵

### 1. Claude 要做的事（額度用完前）
```
□ 生成完整的討論摘要
□ 列出所有核心決策
□ 給出 API 骨架（不用完整實作）
□ 說明測試要求
□ 標註未決定的項目
```

### 2. 你要做的事（交接時）
```
□ 把討論摘要完整複製給 GPT
□ 把 API 骨架完整複製給 GPT
□ 告訴 GPT「不要自己發揮」
□ 要求 GPT 先生成文件（如果沒有）
□ 確認文件後，再讓 GPT 實作
```

### 3. GPT 要做的事（接手後）
```
階段 1（如果沒文件）：
□ 生成 architecture.md
□ 生成 api_spec.md
□ 生成 test_plan.md
□ 每個文件都要讓你確認

階段 2（開始實作）：
□ 嚴格按照 API 定義實作
□ 寫測試
□ 執行測試
□ 回報結果
```

---

## 🎯 完整工作流程

```
[Claude 階段]
1. 和你討論設計
2. 做出所有核心決策
3. 生成「GPT 接力包」
4. 額度用完

[交接階段]
5. 你複製「接力包」
6. 開新 ChatGPT 對話
7. 貼上接力包 + 接力提示詞

[GPT 階段 1 - 文件生成]
8. GPT 生成 architecture.md
9. 你確認
10. GPT 生成 api_spec.md
11. 你確認
12. GPT 生成 test_plan.md
13. 你確認

[GPT 階段 2 - 實作]
14. GPT 按照文件實作
15. GPT 寫測試
16. 你執行測試
17. 如果失敗，把錯誤給 GPT
18. 重複直到完成

[Claude 復活]
19. Claude 額度恢復
20. Review GPT 的成果
21. 整合到主分支
```

---

## 🚀 實戰範例

### Claude 生成的「接力包」：

```markdown
# GPT 接力包 - v0.4 Multi-Timeframe 支援

## 功能目標
讓回測引擎支援多時間週期，例如在 1h 圖上看 4h 的 MA。

## 核心決策

### 架構決策
- 資料層：每個時間週期獨立載入
- 對齊：使用 pd.merge_asof() 對齊不同週期
- 策略層：提供 get_higher_tf() 方法

### 技術選型
- 不使用 resample（會產生 future leak）
- 使用預先計算好的多週期資料

### API 設計
```python
class MultiTimeframeData:
    primary_tf: pd.DataFrame
    higher_tfs: Dict[str, pd.DataFrame]

    def get_aligned(self, tf: str, bar_index: int) -> pd.Series:
        """獲取對齊後的高週期資料"""
        pass
```

### 範圍限制
- v0.4 只支援「往上看」（1h 看 4h）
- 不支援「往下看」（4h 看 1h）
- 最多支援 3 個時間週期

## 關鍵 API 骨架

[完整的程式碼骨架...]

## 測試要求
- 測試資料對齊正確性
- 測試不會 future leak
- 測試邊界情況（週期開始/結束）
```

### 給 GPT 的提示詞：

```markdown
# 接力任務：實作 Multi-Timeframe 支援

[貼上上面的「接力包」]

你的任務（分兩階段）：

階段 1：生成設計文件
1. v0.4_multi_tf_architecture.md
2. v0.4_multi_tf_api_spec.md
3. v0.4_multi_tf_test_plan.md

階段 2：按照文件實作

規則：
- 嚴格按照「核心決策」
- 不要自己加功能
- API 骨架不要改

準備好了嗎？先生成 architecture.md。
```

---

## ✅ 檢查清單

```
□ 場景 A 提示詞（有文件）已保存
□ 場景 B 提示詞（無文件）已保存
□ 理解兩種場景的差異
□ 知道 Claude 要生成「接力包」
□ 知道如何給 GPT 完整的 context
□ 知道如何要求 GPT 不要自己發揮
□ 知道如何分階段驗證
```

---

## 🎊 完成！

**你現在擁有**：
- ✅ 場景 A 的通用提示詞（有文件時）
- ✅ 場景 B 的通用提示詞（無文件時）
- ✅ Claude 的「接力包」產出器
- ✅ 完整的接力工作流程

**適用於**：
- ✅ 任何版本（v0.3, v0.4, v0.5...）
- ✅ 任何功能（新增模組、重構、修 bug...）
- ✅ 任何階段（設計、實作、測試...）

**核心原則**：
```
讓 GPT 成為「執行者」，不是「設計者」
```

🚀
