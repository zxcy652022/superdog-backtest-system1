# SuperDog v0.7 - 智能數據抓取系統設計文檔

**版本**: v0.7.0
**狀態**: 設計階段 (待確認)
**創建日期**: 2025-12-08
**設計者**: Claude Sonnet 4.5

---

## 📋 目錄

1. [Phase 1: 現有系統調研](#phase-1-現有系統調研)
2. [Phase 2: 技術方案設計](#phase-2-技術方案設計)
3. [Phase 3: 配置系統設計](#phase-3-配置系統設計)
4. [Phase 4: 整合計劃](#phase-4-整合計劃)
5. [關鍵決策點](#關鍵決策點)
6. [文件清單](#文件清單)
7. [工作量預估](#工作量預估)

---

## Phase 1: 現有系統調研

### 1.1 現有架構分析

#### 數據模組結構
```
data/
├── __init__.py
├── fetcher.py                    # 基礎 OHLCV 下載器 (使用 ccxt)
├── storage.py                    # 數據存儲
├── validator.py                  # 數據驗證
├── universe_manager.py           # 幣種宇宙管理器
├── universe_calculator.py        # 幣種屬性計算
├── symbol_manager.py
├── timeframe_manager.py
├── pipeline.py
├── exchanges/                    # ✅ 已存在交易所連接器
│   ├── __init__.py
│   ├── base_connector.py         # 基底類別
│   ├── binance_connector.py      # Binance 永續合約連接器
│   ├── bybit_connector.py        # Bybit 連接器
│   └── okx_connector.py          # OKX 連接器
├── perpetual/                    # 永續合約數據
│   ├── funding_rate.py
│   ├── open_interest.py
│   ├── basis.py
│   ├── liquidations.py
│   └── long_short_ratio.py
├── aggregation/
│   └── multi_exchange.py
└── quality/
    └── controller.py
```

#### 當前數據存儲結構
```
data/raw/
├── BTCUSDT_1h.csv          # 扁平結構
├── ETHUSDT_1h.csv
├── BNBUSDT_1h.csv
└── BTCUSDT_1h_test.csv
```

### 1.2 現有限速機制

#### OHLCVFetcher (data/fetcher.py)
- **使用**: ccxt 庫
- **配置**: `enableRateLimit: True`
- **ccxt 內建限速**: 50ms 每請求 (Binance)
- **問題**:
  - ❌ 無全局限速控制
  - ❌ 無並行下載管理
  - ❌ 單線程下載慢

#### BinanceConnector (data/exchanges/binance_connector.py)
- **限制**: 1200 requests/minute
- **實現**:
  ```python
  self.request_count = 0
  self.last_request_time = time.time()
  self.rate_limit_interval = 60  # 秒
  self.max_requests_per_interval = 1200
  ```
- **優點**: ✅ 已實現基本限速
- **問題**: ❌ 未與 OHLCVFetcher 整合

#### BybitConnector (data/exchanges/bybit_connector.py)
- **限制**: 120 requests/minute
- **實現**:
  ```python
  self.rate_limit = 120
  self.rate_limit_window = 60
  def _check_rate_limit(self):
      # 90% 閾值檢查
      if len(self.request_times) >= self.rate_limit * 0.9:
          sleep_time = ...
  ```
- **優點**: ✅ 更智能的限速策略

### 1.3 支持的功能

| 功能 | OHLCVFetcher | BinanceConnector | 狀態 |
|------|--------------|------------------|------|
| 多時間框架 | ✅ 支持 | ❌ 不適用 | 部分支持 |
| 並行下載 | ❌ 無 | ❌ 無 | 不支持 |
| 限速控制 | ⚠️ ccxt 內建 | ✅ 手動實現 | 不統一 |
| 重試機制 | ✅ 3次重試 | ✅ 指數退避 | 已支持 |
| 斷點續傳 | ❌ 無 | ❌ 無 | 不支持 |
| 進度追蹤 | ⚠️ 日誌 | ⚠️ 日誌 | 基礎支持 |

### 1.4 發現的問題

#### 問題 1: 無統一的符號映射
- Binance: `BTCUSDT`
- ccxt: `BTC/USDT`
- 需要手動轉換

#### 問題 2: 無 Top 100 自動獲取
- UniverseManager 只能從本地掃描 `*_1d.csv`
- 無法自動從交易所獲取熱門幣種

#### 問題 3: 單時間框架下載效率低
- 下載 100 個幣種 × 4 個時間框架 = 400 次下載
- 單線程耗時: ~6-8 小時
- 無斷點續傳，中斷需重新開始

#### 問題 4: 配置管理缺失
- ❌ 無 `config/` 目錄
- ❌ 所有參數硬編碼
- ❌ 無法靈活配置下載策略

---

## Phase 2: 技術方案設計

### 2.1 交易所符號映射系統

#### 設計目標
- 統一符號格式為 `BTC/USDT`
- 支持多交易所格式轉換
- 自動處理特殊情況

#### 技術方案

**方案選擇**: **動態規則轉換** (推薦)

**理由**:
1. ✅ 無需維護大型映射表
2. ✅ 支持任意新幣種
3. ✅ 易於擴展新交易所
4. ⚠️ 需要處理特殊符號 (如 LUNA/LUNC)

**實現**:
```python
# data/symbol_mapper.py

class SymbolMapper:
    """統一符號映射器"""

    # 標準格式: BTC/USDT
    STANDARD_DELIMITER = '/'

    # 交易所格式規則
    EXCHANGE_RULES = {
        'binance': {
            'delimiter': '',  # BTCUSDT
            'quote_first': False
        },
        'okx': {
            'delimiter': '-',  # BTC-USDT
            'quote_first': False
        },
        'bybit': {
            'delimiter': '',  # BTCUSDT
            'quote_first': False
        },
        'coinbase': {
            'delimiter': '-',  # BTC-USD
            'quote_first': False
        }
    }

    # 特殊映射表 (僅用於特殊情況)
    SPECIAL_MAPPINGS = {
        'LUNA': {'binance': 'LUNA', 'okx': 'LUNA'},
        'LUNC': {'binance': 'LUNC', 'okx': 'LUNC'},
        # Terra 分叉等特殊情況
    }

    def to_exchange_format(self, symbol: str, exchange: str) -> str:
        """標準格式 → 交易所格式

        Args:
            symbol: BTC/USDT (標準格式)
            exchange: binance, okx, etc.

        Returns:
            交易所格式符號

        Example:
            >>> mapper.to_exchange_format('BTC/USDT', 'binance')
            'BTCUSDT'
            >>> mapper.to_exchange_format('BTC/USDT', 'okx')
            'BTC-USDT'
        """
        # 1. 檢查特殊映射
        base = symbol.split('/')[0]
        if base in self.SPECIAL_MAPPINGS:
            return self.SPECIAL_MAPPINGS[base].get(exchange, symbol)

        # 2. 應用規則轉換
        rule = self.EXCHANGE_RULES.get(exchange)
        if not rule:
            return symbol  # 未知交易所返回原格式

        base, quote = symbol.split('/')
        delimiter = rule['delimiter']
        return f"{base}{delimiter}{quote}"

    def to_standard_format(self, symbol: str, exchange: str) -> str:
        """交易所格式 → 標準格式

        Args:
            symbol: BTCUSDT (交易所格式)
            exchange: binance, okx, etc.

        Returns:
            BTC/USDT (標準格式)
        """
        # 1. 檢查是否已是標準格式
        if '/' in symbol:
            return symbol

        # 2. 應用規則轉換
        rule = self.EXCHANGE_RULES.get(exchange)
        if not rule:
            raise ValueError(f"Unknown exchange: {exchange}")

        delimiter = rule['delimiter']

        if delimiter:
            # 有分隔符，直接替換
            return symbol.replace(delimiter, '/')
        else:
            # 無分隔符，需要猜測分割點
            return self._guess_split_point(symbol)

    def _guess_split_point(self, symbol: str, quote_currencies=['USDT', 'USDC', 'BUSD', 'USD', 'BTC', 'ETH']) -> str:
        """猜測符號分割點

        Args:
            symbol: BTCUSDT
            quote_currencies: 可能的計價貨幣列表

        Returns:
            BTC/USDT
        """
        for quote in sorted(quote_currencies, key=len, reverse=True):
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f"{base}/{quote}"

        # 無法猜測，拋出錯誤
        raise ValueError(f"Cannot guess split point for: {symbol}")

    def get_all_formats(self, symbol: str) -> dict:
        """獲取所有交易所格式

        Args:
            symbol: BTC/USDT (標準格式)

        Returns:
            {'binance': 'BTCUSDT', 'okx': 'BTC-USDT', ...}
        """
        return {
            exchange: self.to_exchange_format(symbol, exchange)
            for exchange in self.EXCHANGE_RULES.keys()
        }
```

---

### 2.2 Top 100 幣種獲取系統

#### 方案比較

| 方案 | 優點 | 缺點 | 推薦度 |
|------|------|------|--------|
| **A: Binance API** | 實時數據、免費、無需額外API | 僅限Binance數據 | ⭐⭐⭐⭐ |
| **B: CoinGecko** | 市值排名權威、跨交易所 | 免費版限速嚴格、需額外API | ⭐⭐⭐ |
| **C: CoinMarketCap** | 最權威、數據全 | 需付費API Key | ⭐⭐ |
| **D: 結合A+B** | 最全面 | 複雜度高 | ⭐⭐⭐⭐⭐ |

**推薦方案**: **D - 結合 Binance + CoinGecko** (可選)

**理由**:
1. ✅ Binance API 免費且實時
2. ✅ CoinGecko 作為備選/補充
3. ✅ 可以交叉驗證數據
4. ✅ 降低對單一數據源的依賴

#### 實現方案

```python
# data/top_symbols_fetcher.py

from typing import List, Dict, Optional
import requests
import ccxt
from dataclasses import dataclass

@dataclass
class SymbolInfo:
    """幣種信息"""
    symbol: str  # 標準格式: BTC/USDT
    rank: int  # 排名
    volume_24h: float  # 24h 成交額 (USD)
    market_cap: Optional[float] = None  # 市值
    source: str = 'binance'  # 數據來源

class TopSymbolsFetcher:
    """Top 100 幣種獲取器"""

    def __init__(self, primary_source: str = 'binance'):
        """初始化

        Args:
            primary_source: 主要數據來源 ('binance' or 'coingecko')
        """
        self.primary_source = primary_source
        self.binance = ccxt.binance()
        self.symbol_mapper = SymbolMapper()

    def get_top_symbols(
        self,
        n: int = 100,
        quote: str = 'USDT',
        source: str = None,
        exclude_stablecoins: bool = True,
        exclude_leveraged: bool = True
    ) -> List[SymbolInfo]:
        """獲取 Top N 幣種

        Args:
            n: 獲取數量
            quote: 計價貨幣
            source: 數據來源 (None則使用primary_source)
            exclude_stablecoins: 排除穩定幣
            exclude_leveraged: 排除槓桿代幣

        Returns:
            List[SymbolInfo]: 排序後的幣種列表
        """
        source = source or self.primary_source

        if source == 'binance':
            return self._get_from_binance(n, quote, exclude_stablecoins, exclude_leveraged)
        elif source == 'coingecko':
            return self._get_from_coingecko(n, quote)
        else:
            raise ValueError(f"Unknown source: {source}")

    def _get_from_binance(
        self,
        n: int,
        quote: str,
        exclude_stablecoins: bool,
        exclude_leveraged: bool
    ) -> List[SymbolInfo]:
        """從 Binance 獲取 Top N

        使用 24h ticker API:
        - Endpoint: GET /api/v3/ticker/24hr
        - Weight: 40
        - 無需 API Key
        """
        # 獲取所有 ticker
        tickers = self.binance.fetch_tickers()

        # 篩選計價貨幣
        filtered = []
        for symbol, ticker in tickers.items():
            if not symbol.endswith(f'/{quote}'):
                continue

            base = symbol.split('/')[0]

            # 排除穩定幣
            if exclude_stablecoins and self._is_stablecoin(base):
                continue

            # 排除槓桿代幣
            if exclude_leveraged and self._is_leveraged_token(base):
                continue

            volume_24h = ticker.get('quoteVolume', 0) or 0  # USDT 成交額

            filtered.append(SymbolInfo(
                symbol=symbol,
                rank=0,  # 暫時填0
                volume_24h=volume_24h,
                source='binance'
            ))

        # 按成交額排序
        filtered.sort(key=lambda x: x.volume_24h, reverse=True)

        # 設置排名
        for i, info in enumerate(filtered[:n], 1):
            info.rank = i

        return filtered[:n]

    def _get_from_coingecko(self, n: int, quote: str) -> List[SymbolInfo]:
        """從 CoinGecko 獲取 Top N

        使用 CoinGecko API:
        - Endpoint: /coins/markets
        - Free tier: 10-50 calls/minute
        """
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            'vs_currency': quote.lower(),
            'order': 'market_cap_desc',  # 按市值排序
            'per_page': n,
            'page': 1,
            'sparkline': False
        }

        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        symbols = []
        for i, coin in enumerate(data, 1):
            symbol = f"{coin['symbol'].upper()}/{quote}"
            symbols.append(SymbolInfo(
                symbol=symbol,
                rank=i,
                volume_24h=coin.get('total_volume', 0),
                market_cap=coin.get('market_cap'),
                source='coingecko'
            ))

        return symbols

    def _is_stablecoin(self, base: str) -> bool:
        """判斷是否穩定幣"""
        stablecoins = {'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDD', 'FDUSD'}
        return base.upper() in stablecoins

    def _is_leveraged_token(self, base: str) -> bool:
        """判斷是否槓桿代幣"""
        # Binance 槓桿代幣: BTCUP, BTCDOWN, ETHUP, ETHDOWN, etc.
        leveraged_suffixes = ['UP', 'DOWN', 'BULL', 'BEAR']
        return any(base.endswith(suffix) for suffix in leveraged_suffixes)

    def get_combined_top(self, n: int = 100, quote: str = 'USDT') -> List[SymbolInfo]:
        """結合多數據源獲取 Top N

        策略:
        1. 從 Binance 獲取 Top 100 (按成交額)
        2. 從 CoinGecko 獲取市值排名
        3. 結合兩者，去重，重新排序
        """
        # Binance Top 100 by volume
        binance_top = self._get_from_binance(n, quote, True, True)

        # CoinGecko Top 50 by market cap (補充)
        try:
            cg_top = self._get_from_coingecko(50, quote)
        except Exception as e:
            logger.warning(f"CoinGecko API failed: {e}, using Binance only")
            return binance_top

        # 合併去重
        combined = {}
        for info in binance_top:
            combined[info.symbol] = info

        for info in cg_top:
            if info.symbol not in combined:
                combined[info.symbol] = info

        # 重新排序 (優先成交額)
        result = sorted(combined.values(), key=lambda x: x.volume_24h, reverse=True)

        # 更新排名
        for i, info in enumerate(result[:n], 1):
            info.rank = i

        return result[:n]
```

---

### 2.3 多時間框架抓取系統

#### 設計目標
- 支持 15m, 1h, 4h, 1d (核心)
- 可選 1m, 5m (高頻策略)
- 並行下載提升效率
- 優先級控制

#### 儲存結構選擇

**方案 A: 按幣種分目錄**
```
data/raw/
└── binance/
    ├── BTCUSDT/
    │   ├── 15m.csv
    │   ├── 1h.csv
    │   ├── 4h.csv
    │   └── 1d.csv
    ├── ETHUSDT/
    │   └── ...
    └── BNBUSDT/
        └── ...
```

**方案 B: 扁平結構 (當前)**
```
data/raw/
├── BTCUSDT_15m.csv
├── BTCUSDT_1h.csv
├── BTCUSDT_4h.csv
├── BTCUSDT_1d.csv
├── ETHUSDT_15m.csv
└── ...
```

**推薦**: **方案 A - 按幣種分目錄**

**理由**:
| 考慮因素 | 方案 A | 方案 B |
|---------|--------|--------|
| 組織性 | ⭐⭐⭐⭐⭐ 清晰 | ⭐⭐⭐ 可接受 |
| 擴展性 | ⭐⭐⭐⭐⭐ 易擴展 | ⭐⭐ 文件過多 |
| 多交易所 | ⭐⭐⭐⭐⭐ 易區分 | ⭐ 需複雜命名 |
| 向後兼容 | ⭐⭐⭐ 需遷移 | ⭐⭐⭐⭐⭐ 無需改動 |
| 性能 | ⭐⭐⭐⭐ 相同 | ⭐⭐⭐⭐ 相同 |

**遷移策略**:
- v0.7 支持兩種結構讀取
- 新下載使用方案 A
- 舊數據保留，逐步遷移

#### 實現方案

```python
# data/multi_timeframe_downloader.py

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Optional
import time
from pathlib import Path
from tqdm import tqdm

@dataclass
class DownloadTask:
    """下載任務"""
    symbol: str  # BTC/USDT
    timeframe: str  # 15m, 1h, 4h, 1d
    days: int  # 下載天數
    priority: int  # 優先級 (1=高, 2=中, 3=低)
    exchange: str = 'binance'

class MultiTimeframeDownloader:
    """多時間框架並行下載器"""

    # 時間框架配置
    TIMEFRAME_CONFIG = {
        '1m':  {'days': 90,   'priority': 3, 'enabled': False},  # 可選
        '5m':  {'days': 180,  'priority': 3, 'enabled': False},  # 可選
        '15m': {'days': 365,  'priority': 2, 'enabled': True},   # 中優先級
        '1h':  {'days': 1460, 'priority': 1, 'enabled': True},   # 高優先級 (4年)
        '4h':  {'days': 1460, 'priority': 2, 'enabled': True},   # 中優先級
        '1d':  {'days': 1460, 'priority': 1, 'enabled': True},   # 高優先級
    }

    def __init__(
        self,
        base_path: str = 'data/raw',
        max_workers: int = 5,
        rate_limiter: Optional['RateLimiter'] = None,
        exchange: str = 'binance'
    ):
        """初始化

        Args:
            base_path: 數據存儲根目錄
            max_workers: 並行線程數
            rate_limiter: 限速器
            exchange: 交易所名稱
        """
        self.base_path = Path(base_path)
        self.max_workers = max_workers
        self.rate_limiter = rate_limiter or RateLimiter()
        self.exchange = exchange
        self.fetcher = OHLCVFetcher(exchange_name=exchange)
        self.symbol_mapper = SymbolMapper()

    def download_all(
        self,
        symbols: List[str],
        timeframes: Optional[List[str]] = None,
        strategy: str = 'priority'  # 'priority', 'round_robin', 'by_symbol'
    ) -> Dict[str, any]:
        """批量下載多幣種多時間框架數據

        Args:
            symbols: 幣種列表 (標準格式: ['BTC/USDT', 'ETH/USDT', ...])
            timeframes: 時間框架列表 (None則使用啟用的時間框架)
            strategy: 下載策略

        Returns:
            下載結果統計
        """
        # 確定要下載的時間框架
        if timeframes is None:
            timeframes = [tf for tf, cfg in self.TIMEFRAME_CONFIG.items() if cfg['enabled']]

        # 創建任務列表
        tasks = self._create_tasks(symbols, timeframes)

        # 按策略排序任務
        tasks = self._sort_tasks(tasks, strategy)

        # 執行下載
        results = self._execute_downloads(tasks)

        return results

    def _create_tasks(self, symbols: List[str], timeframes: List[str]) -> List[DownloadTask]:
        """創建下載任務列表"""
        tasks = []
        for symbol in symbols:
            for tf in timeframes:
                config = self.TIMEFRAME_CONFIG.get(tf)
                if not config:
                    continue

                task = DownloadTask(
                    symbol=symbol,
                    timeframe=tf,
                    days=config['days'],
                    priority=config['priority'],
                    exchange=self.exchange
                )
                tasks.append(task)

        return tasks

    def _sort_tasks(self, tasks: List[DownloadTask], strategy: str) -> List[DownloadTask]:
        """按策略排序任務

        Strategies:
        - priority: 先完成高優先級時間框架 (所有幣種的1h, 1d)
        - round_robin: 輪流下載每個幣種的不同時間框架
        - by_symbol: 按幣種順序，完成一個幣種再下載下一個
        """
        if strategy == 'priority':
            # 優先級 → 幣種 → 時間框架
            return sorted(tasks, key=lambda t: (t.priority, t.symbol, t.timeframe))

        elif strategy == 'round_robin':
            # 幣種輪詢，每個幣種下載一個時間框架後切換
            # 實現: 按 (時間框架, 幣種) 排序
            return sorted(tasks, key=lambda t: (t.timeframe, t.symbol))

        elif strategy == 'by_symbol':
            # 幣種 → 優先級 → 時間框架
            return sorted(tasks, key=lambda t: (t.symbol, t.priority, t.timeframe))

        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _execute_downloads(self, tasks: List[DownloadTask]) -> Dict:
        """執行並行下載

        Returns:
            {
                'total': 400,
                'success': 395,
                'failed': 5,
                'skipped': 0,
                'elapsed': 3245.67,  # 秒
                'failed_tasks': [...]
            }
        """
        total = len(tasks)
        success = 0
        failed = 0
        skipped = 0
        failed_tasks = []

        start_time = time.time()

        # 使用 tqdm 顯示進度
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任務
            future_to_task = {
                executor.submit(self._download_single, task): task
                for task in tasks
            }

            # 使用 tqdm 追蹤進度
            with tqdm(total=total, desc="下載進度", unit="file") as pbar:
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        if result['status'] == 'success':
                            success += 1
                        elif result['status'] == 'skipped':
                            skipped += 1
                        else:
                            failed += 1
                            failed_tasks.append((task, result.get('error')))
                    except Exception as e:
                        failed += 1
                        failed_tasks.append((task, str(e)))

                    # 更新進度條
                    pbar.update(1)
                    pbar.set_postfix({
                        'success': success,
                        'failed': failed,
                        'current': f"{task.symbol} {task.timeframe}"
                    })

        elapsed = time.time() - start_time

        return {
            'total': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'elapsed': elapsed,
            'failed_tasks': failed_tasks
        }

    def _download_single(self, task: DownloadTask) -> Dict:
        """下載單個任務

        Returns:
            {'status': 'success'/'failed'/'skipped', 'error': ...}
        """
        # 檢查是否已存在
        save_path = self._get_save_path(task)
        if save_path.exists():
            # 檢查數據是否完整
            if self._is_data_complete(save_path, task.days):
                return {'status': 'skipped', 'reason': 'already_exists'}

        # 等待限速
        self.rate_limiter.wait_if_needed()

        # 轉換符號格式
        exchange_symbol = self.symbol_mapper.to_exchange_format(task.symbol, task.exchange)

        try:
            # 執行下載
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=task.days)).strftime('%Y-%m-%d')

            self.fetcher.fetch_ohlcv(
                symbol=exchange_symbol,
                timeframe=task.timeframe,
                start_date=start_date,
                end_date=end_date,
                save_path=str(save_path)
            )

            return {'status': 'success'}

        except Exception as e:
            return {'status': 'failed', 'error': str(e)}

    def _get_save_path(self, task: DownloadTask) -> Path:
        """獲取保存路徑

        Structure: data/raw/{exchange}/{symbol_name}/{timeframe}.csv
        Example: data/raw/binance/BTCUSDT/1h.csv
        """
        symbol_name = task.symbol.replace('/', '')  # BTC/USDT → BTCUSDT
        path = self.base_path / task.exchange / symbol_name / f"{task.timeframe}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _is_data_complete(self, file_path: Path, expected_days: int) -> bool:
        """檢查數據是否完整

        簡化版: 僅檢查文件大小
        完整版: 檢查數據記錄數、時間範圍
        """
        # 簡化檢查: 文件大於 10KB
        return file_path.stat().st_size > 10240
```

---

### 2.4 限速與分流系統

#### 設計目標
- 全局限速控制 (1100 req/min，留安全邊際)
- 智能分流策略
- 支持多交易所

#### 分流策略選擇

**推薦**: **方案 C - 混合策略 (優先級 + 輪詢)**

**理由**:
1. ✅ 優先完成高價值數據 (1h, 1d)
2. ✅ 避免單幣種阻塞
3. ✅ 最佳用戶體驗

**策略說明**:
```
Phase 1: 高優先級 (priority=1)
  - 所有幣種的 1h, 1d
  - 策略: 按幣種輪詢
  - Worker 1: BTC 1h → ETH 1h → BNB 1h → ...
  - Worker 2: BTC 1d → ETH 1d → BNB 1d → ...

Phase 2: 中優先級 (priority=2)
  - 所有幣種的 15m, 4h
  - 策略: 按幣種輪詢

Phase 3: 低優先級 (priority=3, 可選)
  - 所有幣種的 1m, 5m
  - 策略: 按幣種輪詢
```

#### 實現方案

```python
# data/rate_limiter.py

from collections import deque
import time
import threading
from typing import Optional

class RateLimiter:
    """全局限速器

    使用滑動窗口算法控制請求速率
    支持多線程安全
    """

    def __init__(
        self,
        requests_per_minute: int = 1100,  # 留100的安全邊際
        window_seconds: int = 60
    ):
        """初始化

        Args:
            requests_per_minute: 每分鐘最大請求數
            window_seconds: 時間窗口（秒）
        """
        self.rpm = requests_per_minute
        self.window = window_seconds
        self.request_times = deque()
        self.lock = threading.Lock()

    def wait_if_needed(self, weight: int = 1):
        """根據 weight 動態等待

        Args:
            weight: 請求權重 (ccxt klines weight=1, 24h ticker weight=40)
        """
        with self.lock:
            now = time.time()

            # 清理過期的請求記錄 (超出時間窗口)
            cutoff_time = now - self.window
            while self.request_times and self.request_times[0] < cutoff_time:
                self.request_times.popleft()

            # 計算當前窗口內的請求數
            current_requests = len(self.request_times)

            # 如果接近限制，計算需要等待的時間
            if current_requests + weight >= self.rpm:
                # 等待最早的請求超出時間窗口
                sleep_time = self.window - (now - self.request_times[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)

                # 重新清理
                now = time.time()
                cutoff_time = now - self.window
                while self.request_times and self.request_times[0] < cutoff_time:
                    self.request_times.popleft()

            # 記錄當前請求
            for _ in range(weight):
                self.request_times.append(now)

    def get_current_rate(self) -> float:
        """獲取當前請求速率 (requests/minute)"""
        with self.lock:
            now = time.time()
            cutoff_time = now - self.window

            # 計算窗口內的請求數
            recent_requests = sum(1 for t in self.request_times if t >= cutoff_time)

            return recent_requests * (60 / self.window)

    def reset(self):
        """重置限速器"""
        with self.lock:
            self.request_times.clear()
```

---

### 2.5 錯誤處理與重試

```python
# data/robust_downloader.py

import time
import json
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import asdict

class RobustDownloader:
    """健壯的下載器 - 支持重試、斷點續傳、錯誤記錄"""

    def __init__(
        self,
        downloader: MultiTimeframeDownloader,
        checkpoint_file: str = '.download_checkpoint.json',
        max_retries: int = 3,
        backoff_factor: int = 2
    ):
        """初始化

        Args:
            downloader: MultiTimeframeDownloader 實例
            checkpoint_file: 檢查點文件路徑
            max_retries: 最大重試次數
            backoff_factor: 退避因子 (2^retry * initial_delay)
        """
        self.downloader = downloader
        self.checkpoint_file = Path(checkpoint_file)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def download_with_retry(
        self,
        task: DownloadTask,
        retry_count: int = 0
    ) -> Dict:
        """帶重試的下載

        錯誤處理策略:
        1. 網絡錯誤 → 指數退避重試
        2. API 限速 → 等待後重試
        3. 數據不存在 → 記錄並跳過
        4. 其他錯誤 → 記錄詳細日誌
        """
        try:
            result = self.downloader._download_single(task)

            if result['status'] == 'success':
                return result

            # 處理失敗
            error = result.get('error', '')

            # 判斷錯誤類型
            if 'rate limit' in error.lower() or '429' in error:
                # API 限速，等待更長時間
                sleep_time = 60
                logger.warning(f"Rate limit hit, waiting {sleep_time}s")
                time.sleep(sleep_time)
                return self.download_with_retry(task, retry_count)

            elif 'not found' in error.lower() or '404' in error:
                # 數據不存在，跳過
                logger.warning(f"Symbol not found: {task.symbol} {task.timeframe}")
                return {'status': 'skipped', 'reason': 'not_found'}

            elif retry_count < self.max_retries:
                # 其他錯誤，重試
                sleep_time = (self.backoff_factor ** retry_count) * 1
                logger.warning(f"Retry {retry_count + 1}/{self.max_retries} after {sleep_time}s: {error}")
                time.sleep(sleep_time)
                return self.download_with_retry(task, retry_count + 1)

            else:
                # 超過重試次數
                logger.error(f"Failed after {self.max_retries} retries: {task.symbol} {task.timeframe}")
                return result

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if retry_count < self.max_retries:
                sleep_time = (self.backoff_factor ** retry_count) * 1
                time.sleep(sleep_time)
                return self.download_with_retry(task, retry_count + 1)
            else:
                return {'status': 'failed', 'error': str(e)}

    def save_checkpoint(self, completed_tasks: List[DownloadTask]):
        """保存檢查點

        檢查點格式:
        {
            "completed": [
                {"symbol": "BTC/USDT", "timeframe": "1h", "exchange": "binance"},
                ...
            ],
            "timestamp": "2025-12-08 12:34:56"
        }
        """
        checkpoint = {
            'completed': [asdict(task) for task in completed_tasks],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)

    def load_checkpoint(self) -> List[DownloadTask]:
        """加載檢查點

        Returns:
            已完成的任務列表
        """
        if not self.checkpoint_file.exists():
            return []

        with open(self.checkpoint_file, 'r') as f:
            checkpoint = json.load(f)

        tasks = []
        for task_dict in checkpoint.get('completed', []):
            tasks.append(DownloadTask(**task_dict))

        return tasks

    def resume_download(
        self,
        symbols: List[str],
        timeframes: List[str]
    ) -> Dict:
        """斷點續傳

        從檢查點恢復下載進度
        """
        # 加載已完成的任務
        completed = self.load_checkpoint()
        completed_set = {(t.symbol, t.timeframe) for t in completed}

        # 創建所有任務
        all_tasks = self.downloader._create_tasks(symbols, timeframes)

        # 過濾已完成的任務
        remaining_tasks = [
            t for t in all_tasks
            if (t.symbol, t.timeframe) not in completed_set
        ]

        logger.info(f"Resuming download: {len(remaining_tasks)} tasks remaining (out of {len(all_tasks)})")

        # 執行下載
        return self.downloader._execute_downloads(remaining_tasks)
```

---

### 2.6 進度追蹤與報告

已在 `MultiTimeframeDownloader._execute_downloads()` 中實現：
- ✅ 使用 `tqdm` 顯示進度條
- ✅ 實時更新成功/失敗數
- ✅ 顯示當前下載的幣種/時間框架

**輸出示例**:
```
下載進度: 45%|████▌     | 180/400 [15:23<18:47, 2.3 file/s]
success=175, failed=5, current=ETHUSDT 4h
```

---

## Phase 3: 配置系統設計

### 3.1 配置文件結構

創建 `config/data_download.yaml`:

```yaml
# SuperDog v0.7 數據下載配置
# ===================================

# 幣種選擇配置
symbols:
  # 數據來源: binance_top, coingecko, manual
  source: binance_top

  # Top N 數量
  count: 100

  # 計價貨幣
  quote_currency: USDT

  # 篩選條件
  filters:
    exclude_stablecoins: true      # 排除穩定幣
    exclude_leveraged: true        # 排除槓桿代幣 (BTCUP, BTCDOWN)
    min_volume_24h: 1000000        # 最小24h成交額 (USD)
    min_market_cap: null           # 最小市值 (null=不限制)

  # 手動添加的幣種 (會與 Top N 合併)
  custom_symbols:
    # - SOL/USDT
    # - DOGE/USDT

# 時間框架配置
timeframes:
  # 啟用的時間框架
  enabled:
    - 1h
    - 4h
    - 1d

  # 可選時間框架 (需手動啟用)
  optional:
    - 1m
    - 5m
    - 15m

  # 各時間框架的下載天數
  days_per_timeframe:
    1m: 90      # 3個月
    5m: 180     # 6個月
    15m: 365    # 1年
    1h: 1460    # 4年
    4h: 1460    # 4年
    1d: 1460    # 4年

  # 優先級 (1=高, 2=中, 3=低)
  priority:
    1m: 3
    5m: 3
    15m: 2
    1h: 1
    4h: 2
    1d: 1

# 限速配置
rate_limiting:
  enabled: true

  # 每分鐘最大請求數 (留安全邊際)
  requests_per_minute: 1100

  # 並行線程數
  max_workers: 5

  # 重試策略
  retry:
    max_retries: 3
    backoff_factor: 2  # 指數退避因子
    initial_delay: 1   # 初始延遲 (秒)

# 存儲配置
storage:
  # 數據根目錄
  base_path: data/raw

  # 目錄結構: by_symbol (推薦) 或 flat (向後兼容)
  structure: by_symbol

  # 是否壓縮 CSV
  compression: false  # true → .csv.gz

  # 下載時是否覆蓋現有數據
  overwrite_existing: false  # false → 跳過已存在的文件

# 交易所配置
exchanges:
  # 主要交易所
  primary: binance

  # 備用交易所 (主交易所失敗時嘗試)
  fallback:
    # - okx
    # - bybit

  # 交易所特定配置
  binance:
    api_key: null    # null 表示使用公開 API
    secret: null

  okx:
    api_key: null
    secret: null

# 進度追蹤配置
progress:
  # 檢查點文件 (用於斷點續傳)
  checkpoint_file: .download_checkpoint.json

  # 是否啟用斷點續傳
  enable_resume: true

  # 日誌級別: DEBUG, INFO, WARNING, ERROR
  log_level: INFO

  # 是否保存失敗任務清單
  save_failed_tasks: true
  failed_tasks_file: .download_failed.json

# 下載策略
download_strategy:
  # 任務排序策略: priority (推薦), round_robin, by_symbol
  task_order: priority

  # 是否跳過已存在且完整的數據
  skip_existing: true

  # 數據完整性檢查
  data_validation:
    enabled: true
    min_file_size_kb: 10  # 最小文件大小 (KB)
    check_record_count: false  # 是否檢查記錄數

# 通知配置 (可選)
notifications:
  enabled: false

  # 完成後通知
  on_complete:
    email: null  # user@example.com
    webhook: null  # https://hooks.slack.com/...

  # 錯誤通知
  on_error:
    email: null
    webhook: null
```

### 3.2 配置加載器

```python
# config/config_loader.py

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class DataDownloadConfig:
    """數據下載配置"""
    # 從 YAML 解析的配置字典
    raw_config: Dict[str, Any]

    @classmethod
    def from_yaml(cls, config_path: str = 'config/data_download.yaml'):
        """從 YAML 文件加載配置"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return cls(raw_config=config)

    def get(self, key_path: str, default: Any = None) -> Any:
        """獲取配置值

        Args:
            key_path: 點分隔的鍵路徑 (例如: 'symbols.count')
            default: 默認值

        Returns:
            配置值
        """
        keys = key_path.split('.')
        value = self.raw_config

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    # 便捷屬性
    @property
    def symbol_source(self) -> str:
        return self.get('symbols.source', 'binance_top')

    @property
    def symbol_count(self) -> int:
        return self.get('symbols.count', 100)

    @property
    def quote_currency(self) -> str:
        return self.get('symbols.quote_currency', 'USDT')

    @property
    def enabled_timeframes(self) -> list:
        return self.get('timeframes.enabled', ['1h', '4h', '1d'])

    @property
    def max_workers(self) -> int:
        return self.get('rate_limiting.max_workers', 5)

    @property
    def requests_per_minute(self) -> int:
        return self.get('rate_limiting.requests_per_minute', 1100)
```

---

## Phase 4: 整合計劃

### 4.1 修改 UniverseManager

```python
# data/universe_manager.py (修改部分)

from config.config_loader import DataDownloadConfig
from data.top_symbols_fetcher import TopSymbolsFetcher

class UniverseManager:
    def __init__(
        self,
        data_dir: Optional[str] = None,
        universe_dir: Optional[str] = None,
        config_file: Optional[str] = None  # 新增
    ):
        # 原有代碼...

        # 新增: 加載配置
        if config_file:
            self.config = DataDownloadConfig.from_yaml(config_file)
        else:
            self.config = None

        # 新增: Top 幣種獲取器
        self.top_fetcher = TopSymbolsFetcher()
        self.symbol_mapper = SymbolMapper()

    def _discover_symbols(self) -> List[str]:
        """改進的符號發現

        優先級:
        1. 從配置文件讀取 custom_symbols
        2. 從 Top Symbols API 獲取
        3. 掃描本地數據目錄
        """
        symbols = set()

        # 1. 從配置獲取
        if self.config:
            custom = self.config.get('symbols.custom_symbols', [])
            symbols.update(custom)

            # 2. 從 API 獲取 Top N
            source = self.config.symbol_source
            count = self.config.symbol_count
            quote = self.config.quote_currency

            try:
                top_symbols = self.top_fetcher.get_top_symbols(
                    n=count,
                    quote=quote,
                    source=source,
                    exclude_stablecoins=self.config.get('symbols.filters.exclude_stablecoins', True),
                    exclude_leveraged=self.config.get('symbols.filters.exclude_leveraged', True)
                )
                symbols.update([info.symbol for info in top_symbols])
            except Exception as e:
                logger.warning(f"Failed to fetch top symbols: {e}")

        # 3. 掃描本地目錄 (向後兼容)
        if not symbols:
            symbols = self._scan_local_data()

        return sorted(list(symbols))

    def _scan_local_data(self) -> set:
        """掃描本地數據目錄"""
        symbols = set()

        # 支持兩種結構
        # 結構 A: data/raw/binance/BTCUSDT/1d.csv
        for exchange_dir in self.data_dir.iterdir():
            if not exchange_dir.is_dir():
                continue
            for symbol_dir in exchange_dir.iterdir():
                if symbol_dir.is_dir():
                    # 檢查是否有 1d.csv
                    if (symbol_dir / '1d.csv').exists():
                        # BTCUSDT → BTC/USDT
                        symbol = self.symbol_mapper.to_standard_format(symbol_dir.name, 'binance')
                        symbols.add(symbol)

        # 結構 B: data/raw/BTCUSDT_1d.csv (向後兼容)
        for file in self.data_dir.glob("*_1d.csv"):
            symbol_name = file.stem.replace("_1d", "")
            symbol = self.symbol_mapper.to_standard_format(symbol_name, 'binance')
            symbols.add(symbol)

        return symbols

    def build_universe_auto(
        self,
        timeframe: str = '1d',
        download_if_missing: bool = False  # 新增: 缺失時自動下載
    ) -> UniverseSnapshot:
        """自動構建宇宙

        支持任意時間框架（不再強制要求 1d）

        Args:
            timeframe: 時間框架 ('15m', '1h', '4h', '1d')
            download_if_missing: 如果數據缺失是否自動下載
        """
        # 發現幣種
        symbols = self._discover_symbols()

        # 檢查數據可用性
        if download_if_missing:
            missing = self._check_missing_data(symbols, timeframe)
            if missing:
                logger.info(f"Found {len(missing)} symbols with missing data, downloading...")
                self._download_missing_data(missing, timeframe)

        # 構建宇宙 (使用指定時間框架)
        return self.build_universe(
            symbols=symbols,
            # ... 其他參數
        )

    def _check_missing_data(self, symbols: List[str], timeframe: str) -> List[str]:
        """檢查缺失的數據"""
        missing = []
        for symbol in symbols:
            # 檢查文件是否存在
            # (根據當前存儲結構檢查)
            ...
        return missing

    def _download_missing_data(self, symbols: List[str], timeframe: str):
        """下載缺失的數據"""
        from data.multi_timeframe_downloader import MultiTimeframeDownloader

        downloader = MultiTimeframeDownloader(
            base_path=self.data_dir,
            max_workers=self.config.max_workers if self.config else 5
        )

        downloader.download_all(
            symbols=symbols,
            timeframes=[timeframe]
        )
```

### 4.2 創建 CLI 入口

```python
# scripts/download_top100.py

#!/usr/bin/env python3
"""
SuperDog v0.7 - 下載 Top 100 幣種數據

使用方法:
    python scripts/download_top100.py
    python scripts/download_top100.py --config config/custom.yaml
    python scripts/download_top100.py --symbols BTC/USDT ETH/USDT --timeframes 1h 1d
"""

import argparse
from pathlib import Path
import sys

# 添加項目根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_loader import DataDownloadConfig
from data.top_symbols_fetcher import TopSymbolsFetcher
from data.multi_timeframe_downloader import MultiTimeframeDownloader
from data.rate_limiter import RateLimiter
from data.robust_downloader import RobustDownloader

def main():
    parser = argparse.ArgumentParser(description='下載 Top 100 幣種數據')
    parser.add_argument('--config', type=str, default='config/data_download.yaml',
                        help='配置文件路徑')
    parser.add_argument('--symbols', nargs='+', help='手動指定幣種列表 (覆蓋配置)')
    parser.add_argument('--timeframes', nargs='+', help='手動指定時間框架 (覆蓋配置)')
    parser.add_argument('--resume', action='store_true', help='斷點續傳')
    parser.add_argument('--dry-run', action='store_true', help='僅顯示計劃不實際下載')

    args = parser.parse_args()

    # 加載配置
    config = DataDownloadConfig.from_yaml(args.config)

    # 獲取幣種列表
    if args.symbols:
        symbols = args.symbols
    else:
        # 從配置或 API 獲取
        fetcher = TopSymbolsFetcher(primary_source=config.symbol_source)
        symbol_infos = fetcher.get_top_symbols(
            n=config.symbol_count,
            quote=config.quote_currency,
            exclude_stablecoins=config.get('symbols.filters.exclude_stablecoins', True),
            exclude_leveraged=config.get('symbols.filters.exclude_leveraged', True)
        )
        symbols = [info.symbol for info in symbol_infos]

    # 獲取時間框架
    timeframes = args.timeframes or config.enabled_timeframes

    # 顯示計劃
    print("="*70)
    print("SuperDog v0.7 - 數據下載計劃")
    print("="*70)
    print(f"幣種數量: {len(symbols)}")
    print(f"時間框架: {', '.join(timeframes)}")
    print(f"總任務數: {len(symbols) * len(timeframes)}")
    print(f"並行線程: {config.max_workers}")
    print(f"限速: {config.requests_per_minute} req/min")
    print("="*70)

    if args.dry_run:
        print("\n[Dry Run] 不實際下載，退出")
        return

    # 初始化下載器
    rate_limiter = RateLimiter(requests_per_minute=config.requests_per_minute)
    downloader = MultiTimeframeDownloader(
        base_path=config.get('storage.base_path', 'data/raw'),
        max_workers=config.max_workers,
        rate_limiter=rate_limiter
    )

    # 健壯下載器 (支持重試和斷點續傳)
    robust = RobustDownloader(
        downloader=downloader,
        checkpoint_file=config.get('progress.checkpoint_file', '.download_checkpoint.json'),
        max_retries=config.get('rate_limiting.retry.max_retries', 3)
    )

    # 執行下載
    if args.resume:
        print("\n📂 斷點續傳模式\n")
        results = robust.resume_download(symbols, timeframes)
    else:
        print("\n🚀 開始下載\n")
        results = downloader.download_all(
            symbols=symbols,
            timeframes=timeframes,
            strategy=config.get('download_strategy.task_order', 'priority')
        )

    # 顯示結果
    print("\n" + "="*70)
    print("下載完成")
    print("="*70)
    print(f"總任務: {results['total']}")
    print(f"成功: {results['success']} ({results['success']/results['total']*100:.1f}%)")
    print(f"失敗: {results['failed']}")
    print(f"跳過: {results['skipped']}")
    print(f"耗時: {results['elapsed']:.1f} 秒 ({results['elapsed']/60:.1f} 分鐘)")

    if results['failed'] > 0:
        print(f"\n⚠️  {results['failed']} 個任務失敗:")
        for task, error in results['failed_tasks'][:10]:  # 只顯示前10個
            print(f"  - {task.symbol} {task.timeframe}: {error}")

if __name__ == '__main__':
    main()
```

---

## 關鍵決策點

### 決策表

| 問題 | 方案 A | 方案 B | 方案 C | **推薦** | 理由 |
|------|--------|--------|--------|----------|------|
| **Top 100 來源** | Binance API | CoinGecko | 結合 A+B | **C** | 最全面、可交叉驗證、降低單點依賴 |
| **符號映射** | 維護映射表 | 動態規則轉換 | - | **B** | 易擴展、支持任意新幣種、無需維護 |
| **儲存結構** | 按幣種分目錄 | 扁平結構 | - | **A** | 組織性強、易擴展多交易所、可讀性高 |
| **分流策略** | 按幣種 | 按時間框架 | 混合優先級 | **C** | 先完成高價值數據、避免阻塞、最佳用戶體驗 |
| **1m/5m 數據** | 默認啟用 | 可選啟用 | - | **B** | 大多數策略不需要、減少存儲和下載時間 |
| **並行數** | 3 workers | 5 workers | 10 workers | **B (5)** | 平衡速度和API限制、避免觸發限速 |
| **配置格式** | YAML | JSON | Python | **A (YAML)** | 可讀性高、支持註釋、易於編輯 |

---

## 文件清單

### 新增文件

```
data/
├── symbol_mapper.py              # 交易所符號映射器 (NEW)
├── top_symbols_fetcher.py        # Top 100 幣種獲取器 (NEW)
├── downloaders/                  # 新目錄
│   ├── __init__.py
│   ├── multi_timeframe.py        # 多時間框架下載器 (NEW)
│   ├── rate_limiter.py           # 全局限速器 (NEW)
│   └── robust_downloader.py      # 健壯下載器 (NEW)

config/                           # 新目錄
├── __init__.py
├── config_loader.py              # 配置加載器 (NEW)
└── data_download.yaml            # 數據下載配置 (NEW)

scripts/
├── download_top100.py            # Top 100 下載腳本 (NEW)
└── migrate_data_structure.py    # 數據結構遷移腳本 (NEW, 可選)

docs/v0.7/
├── SUPERDOG_V07_DATA_DOWNLOAD_DESIGN.md  # 本設計文檔 (NEW)
└── DATA_DOWNLOAD_GUIDE.md                # 用戶使用指南 (NEW)
```

### 修改文件

```
data/
├── universe_manager.py           # 修改: 支持自動發現、自動下載
└── fetcher.py                    # 可選修改: 整合限速器

CHANGELOG.md                      # 添加 v0.7 計劃
README.md                         # 更新功能說明
```

---

## 工作量預估

| 模組 | 文件 | 預估時間 | 優先級 | 依賴 |
|------|------|---------|--------|------|
| **符號映射器** | `symbol_mapper.py` | 2h | 高 | 無 |
| **Top獲取器** | `top_symbols_fetcher.py` | 3h | 高 | SymbolMapper |
| **限速器** | `rate_limiter.py` | 2h | 高 | 無 |
| **多時間框架下載器** | `multi_timeframe.py` | 4h | 高 | RateLimiter, SymbolMapper |
| **健壯下載器** | `robust_downloader.py` | 3h | 中 | MultiTimeframeDownloader |
| **配置系統** | `config_loader.py`, `.yaml` | 1h | 高 | 無 |
| **CLI 腳本** | `download_top100.py` | 2h | 高 | 所有上述模組 |
| **UniverseManager整合** | 修改 `universe_manager.py` | 2h | 中 | TopSymbolsFetcher |
| **整合測試** | 測試腳本 + 調試 | 3h | 高 | 所有模組 |
| **文檔** | 設計文檔 + 使用指南 | 2h | 中 | 無 |
| **數據遷移** | `migrate_data_structure.py` | 1h | 低 | 可選 |
| **總計** | - | **25 小時** | - | - |

### 開發階段建議

**Phase 1: 核心基礎 (8h)**
1. SymbolMapper (2h)
2. RateLimiter (2h)
3. ConfigLoader + YAML (1h)
4. TopSymbolsFetcher (3h)

**Phase 2: 下載系統 (9h)**
5. MultiTimeframeDownloader (4h)
6. RobustDownloader (3h)
7. CLI 腳本 (2h)

**Phase 3: 整合測試 (5h)**
8. UniverseManager 整合 (2h)
9. 整合測試 (3h)

**Phase 4: 文檔與優化 (3h)**
10. 用戶文檔 (2h)
11. 代碼優化 (1h)

---

## 風險與限制

### 技術風險

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| **API 限速** | 下載失敗 | 智能限速器 + 重試機制 |
| **網絡不穩定** | 下載中斷 | 斷點續傳 + 檢查點 |
| **數據不完整** | 回測錯誤 | 數據驗證 + 完整性檢查 |
| **存儲空間** | 磁盤滿 | 壓縮選項 + 存儲預警 |

### 限制

1. **Binance API 限制**:
   - 1200 requests/minute (weight)
   - klines weight = 1-2
   - 實際下載速度: ~800-1000 requests/minute (安全邊際)

2. **預估下載時間**:
   - 100 幣種 × 4 時間框架 = 400 任務
   - 每任務平均 3-5 請求 = 1200-2000 requests
   - 下載時間: ~2-3 分鐘 (並行)

3. **存儲空間**:
   - 單幣種單時間框架: ~2MB
   - 100 幣種 × 4 時間框架 = ~800MB
   - 建議預留: 2-3GB

---

## 下一步行動

### 等待用戶確認

請確認以下關鍵決策：

1. ✅ **儲存結構**: 按幣種分目錄 (`data/raw/binance/BTCUSDT/1h.csv`)
2. ✅ **Top 100 來源**: Binance API + CoinGecko (可選)
3. ✅ **分流策略**: 混合優先級 (先完成 1h/1d)
4. ✅ **並行數**: 5 workers
5. ✅ **1m/5m 數據**: 可選啟用 (默認關閉)

### 確認後開始開發

收到確認後，將按以下順序開發：
1. Phase 1: 核心基礎 (8小時)
2. Phase 2: 下載系統 (9小時)
3. Phase 3: 整合測試 (5小時)
4. Phase 4: 文檔與優化 (3小時)

---

**設計文檔版本**: 1.0.0
**最後更新**: 2025-12-08
**待確認**: 是

