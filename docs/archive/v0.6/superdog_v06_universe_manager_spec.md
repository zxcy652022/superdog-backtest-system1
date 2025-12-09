# SuperDog v0.6 幣種宇宙管理技術規格
**Universe Management System Technical Specification**

---

## 📊 系統概述

幣種宇宙管理系統負責自動分類和管理加密貨幣，為策略實驗提供智能化的幣種選擇。

### 核心職責
- 計算幣種屬性指標
- 執行自動分類規則
- 生成宇宙配置文件
- 提供CLI管理接口

---

## 🏗️ 架構設計

### 模組結構
```
data/
├── universe_manager.py              # 核心管理器
├── universe/                        # 數據存儲
│   ├── metadata/                   # 幣種元數據
│   ├── snapshots/                  # 宇宙快照
│   └── configs/                    # 生成的配置
└── universe_calculator.py          # 屬性計算器
```

### 類結構設計
```python
class UniverseManager:
    """幣種宇宙核心管理器"""

    def __init__(self, data_sources: List[str])
    def build_universe(self, date: str = None) -> UniverseSnapshot
    def load_universe(self, date: str) -> UniverseSnapshot
    def export_config(self, universe_type: str, top_n: int) -> str
    def get_available_dates(self) -> List[str]

class UniverseCalculator:
    """幣種屬性計算器"""

    def calculate_volume_metrics(symbol: str, days: int) -> Dict
    def calculate_history_days(symbol: str) -> int
    def calculate_oi_metrics(symbol: str, days: int) -> Dict
    def detect_perpetual_support(symbol: str) -> bool
    def classify_asset_type(symbol: str) -> str

class UniverseSnapshot:
    """宇宙快照數據結構"""

    date: str
    symbols: Dict[str, SymbolMetadata]
    classification: Dict[str, List[str]]
    statistics: Dict[str, int]

@dataclass
class SymbolMetadata:
    """幣種元數據結構"""

    symbol: str
    volume_30d_usd: float           # 30日平均成交額
    volume_7d_usd: float            # 7日平均成交額
    history_days: int               # 上市天數
    market_cap_rank: int            # 市值排名
    oi_avg_usd: float              # 平均持倉量
    oi_trend: float                # 持倉量趨勢(-1到1)
    has_perpetual: bool            # 是否有永續合約
    is_stablecoin: bool            # 是否穩定幣
    classification: str            # 分類結果
    last_updated: str              # 最後更新時間
```

---

## 📈 屬性計算邏輯

### 1. 成交額計算
```python
def calculate_volume_metrics(symbol: str, days: int = 30) -> Dict:
    """計算成交額相關指標"""

    # 獲取歷史K線數據
    ohlcv_data = load_ohlcv(symbol, timeframe='1d', days=days)

    # 計算成交額 (以USD計價)
    volume_usd = ohlcv_data['volume'] * ohlcv_data['close']

    return {
        'volume_30d_avg': volume_usd.tail(30).mean(),
        'volume_7d_avg': volume_usd.tail(7).mean(),
        'volume_30d_total': volume_usd.tail(30).sum(),
        'volume_trend': calculate_volume_trend(volume_usd),
        'volume_volatility': volume_usd.tail(30).std() / volume_usd.tail(30).mean()
    }

def calculate_volume_trend(volume_series: pd.Series) -> float:
    """計算成交量趨勢 (-1到1)"""
    recent_avg = volume_series.tail(7).mean()
    historical_avg = volume_series.tail(30).mean()

    trend = (recent_avg - historical_avg) / historical_avg
    return np.clip(trend, -1, 1)
```

### 2. 上市天數計算
```python
def calculate_history_days(symbol: str) -> int:
    """計算上市天數"""

    # 查詢交易所API獲取上市時間
    exchange_info = binance_connector.get_exchange_info()
    symbol_info = next(s for s in exchange_info['symbols'] if s['symbol'] == symbol)

    list_date = pd.to_datetime(symbol_info['onboardDate'])
    current_date = pd.Timestamp.now()

    return (current_date - list_date).days
```

### 3. 持倉量指標
```python
def calculate_oi_metrics(symbol: str, days: int = 30) -> Dict:
    """計算持倉量相關指標"""

    if not has_perpetual_contract(symbol):
        return {'oi_avg_usd': 0, 'oi_trend': 0}

    oi_data = load_open_interest(symbol, days=days)

    # 轉換為USD價值
    price_data = load_ohlcv(symbol, timeframe='1d', days=days)
    oi_usd = oi_data['open_interest'] * price_data['close']

    return {
        'oi_avg_usd': oi_usd.mean(),
        'oi_trend': calculate_oi_trend(oi_usd),
        'oi_volatility': oi_usd.std() / oi_usd.mean(),
        'oi_growth_rate': (oi_usd.iloc[-1] / oi_usd.iloc[0] - 1) * 365 / days
    }

def calculate_oi_trend(oi_series: pd.Series) -> float:
    """計算持倉量趨勢"""
    # 使用線性回歸斜率
    x = np.arange(len(oi_series))
    slope, _ = np.polyfit(x, oi_series.values, 1)

    # 標準化到-1到1範圍
    normalized_slope = np.tanh(slope / oi_series.mean() * 100)
    return normalized_slope
```

### 4. 資產類型檢測
```python
def detect_asset_type(symbol: str) -> Dict[str, bool]:
    """檢測資產類型"""

    # 穩定幣檢測
    stablecoin_patterns = ['USDT', 'USDC', 'BUSD', 'DAI', 'TUSD']
    is_stablecoin = any(pattern in symbol for pattern in stablecoin_patterns)

    # 永續合約檢測
    has_perpetual = check_perpetual_availability(symbol)

    # DeFi代幣檢測
    defi_tokens = ['UNI', 'SUSHI', 'AAVE', 'COMP', 'CRV', 'YFI']
    is_defi = symbol.replace('USDT', '') in defi_tokens

    return {
        'is_stablecoin': is_stablecoin,
        'has_perpetual': has_perpetual,
        'is_defi': is_defi
    }

def check_perpetual_availability(symbol: str) -> bool:
    """檢查永續合約可用性"""
    try:
        funding_data = load_funding_rate(symbol, days=1)
        return len(funding_data) > 0
    except:
        return False
```

---

## 🏷️ 分類規則系統

### 分類標準
```python
class ClassificationRules:
    """幣種分類規則"""

    @staticmethod
    def classify_by_market_cap(metadata: SymbolMetadata) -> str:
        """基於市值和成交額的分類"""

        volume_30d = metadata.volume_30d_usd
        market_cap_rank = metadata.market_cap_rank

        # 大盤股: 前30名 + 日均成交額>1億USD
        if market_cap_rank <= 30 and volume_30d > 1e8:
            return 'large_cap'

        # 中盤股: 前100名 + 日均成交額>1000萬USD
        elif market_cap_rank <= 100 and volume_30d > 1e7:
            return 'mid_cap'

        # 小盤股: 前500名 + 日均成交額>100萬USD
        elif market_cap_rank <= 500 and volume_30d > 1e6:
            return 'small_cap'

        # 微盤股: 其他
        else:
            return 'micro_cap'

    @staticmethod
    def apply_additional_filters(metadata: SymbolMetadata) -> Dict[str, bool]:
        """應用額外篩選條件"""

        return {
            'exclude_stablecoin': metadata.is_stablecoin,
            'require_perpetual': not metadata.has_perpetual,
            'min_history_days': metadata.history_days < 90,
            'min_volume': metadata.volume_30d_usd < 1e5,  # 10萬USD最低門檻
            'oi_too_low': metadata.oi_avg_usd < 1e6,      # 100萬USD持倉量門檻
        }

class UniverseFilter:
    """宇宙篩選器"""

    def __init__(self, rules: ClassificationRules):
        self.rules = rules

    def filter_universe(self, raw_data: Dict[str, SymbolMetadata],
                       filters: Dict[str, bool] = None) -> Dict[str, SymbolMetadata]:
        """應用篩選規則"""

        if filters is None:
            filters = {
                'exclude_stablecoin': True,
                'require_perpetual': True,
                'min_history_days': True,
                'min_volume': True
            }

        filtered_data = {}

        for symbol, metadata in raw_data.items():
            filter_results = self.rules.apply_additional_filters(metadata)

            # 檢查是否通過所有篩選條件
            should_exclude = any(
                filters.get(filter_name, False) and filter_result
                for filter_name, filter_result in filter_results.items()
            )

            if not should_exclude:
                filtered_data[symbol] = metadata

        return filtered_data
```

---

## 💾 數據存儲格式

### Parquet檔案結構
```python
# universe/snapshots/binance_20231201.parquet
DataFrame({
    'symbol': str,              # 交易對符號
    'volume_30d_usd': float,    # 30日平均成交額
    'volume_7d_usd': float,     # 7日平均成交額
    'history_days': int,        # 上市天數
    'market_cap_rank': int,     # 市值排名
    'oi_avg_usd': float,       # 平均持倉量
    'oi_trend': float,         # 持倉量趨勢
    'has_perpetual': bool,     # 永續合約支援
    'is_stablecoin': bool,     # 穩定幣標記
    'classification': str,     # 分類結果
    'last_updated': datetime   # 更新時間
})
```

### YAML配置格式
```yaml
# configs/universe/small_cap_top200.yml
universe:
  name: "小盤股前200名"
  description: "小盤幣種，適合高風險策略測試"
  date_created: "2023-12-01"
  total_symbols: 200

classification:
  type: "small_cap"
  min_volume_usd: 1000000     # 最小日均成交額
  min_history_days: 90        # 最小上市天數
  require_perpetual: true     # 需要永續合約
  exclude_stablecoin: true    # 排除穩定幣

symbols:
  - "SOLUSDT"
  - "ADAUSDT"
  - "DOTUSDT"
  # ... 其他197個

metadata:
  data_source: "binance"
  snapshot_date: "2023-12-01"
  next_update: "2023-12-08"   # 建議每週更新
```

---

## 🔧 CLI接口設計

### 命令結構
```bash
superdog data universe <command> [options]

Commands:
  build     構建新的幣種宇宙
  show      顯示宇宙內容
  export    匯出配置文件
  update    更新現有宇宙
  list      列出所有可用宇宙
  stats     顯示宇宙統計信息
```

### 詳細命令規格
```python
@click.group(name='universe')
def universe_commands():
    """幣種宇宙管理命令"""
    pass

@universe_commands.command()
@click.option('--date', default=None, help='指定日期(YYYY-MM-DD)')
@click.option('--force', is_flag=True, help='強制重建')
@click.option('--exchanges', default='binance', help='交易所列表')
def build(date, force, exchanges):
    """構建幣種宇宙

    Examples:
        superdog data universe build
        superdog data universe build --date 2023-12-01 --force
    """

@universe_commands.command()
@click.argument('classification', type=click.Choice(['large_cap', 'mid_cap', 'small_cap', 'micro_cap']))
@click.option('--top', default=100, help='顯示前N個')
@click.option('--date', default=None, help='指定日期')
@click.option('--format', type=click.Choice(['table', 'json', 'csv']), default='table')
def show(classification, top, date, format):
    """顯示宇宙內容

    Examples:
        superdog data universe show small_cap --top 50
        superdog data universe show large_cap --format json
    """

@universe_commands.command()
@click.argument('classification')
@click.option('--top', default=200, help='匯出前N個')
@click.option('--output', help='輸出檔案路徑')
@click.option('--format', type=click.Choice(['yaml', 'json']), default='yaml')
def export(classification, top, output, format):
    """匯出宇宙配置

    Examples:
        superdog data universe export small_cap --top 200 --output small_cap.yml
    """
```

---

## ⚡ 性能優化

### 快取機制
```python
class UniverseCacheManager:
    """宇宙快取管理"""

    def __init__(self, cache_dir: str = 'data/universe/cache'):
        self.cache_dir = Path(cache_dir)
        self.cache_ttl = 3600  # 1小時快取

    def get_cached_universe(self, date: str) -> Optional[UniverseSnapshot]:
        """獲取快取的宇宙"""
        cache_file = self.cache_dir / f"{date}.pkl"

        if cache_file.exists():
            # 檢查快取是否過期
            file_time = cache_file.stat().st_mtime
            if time.time() - file_time < self.cache_ttl:
                return pickle.load(open(cache_file, 'rb'))

        return None

    def save_to_cache(self, universe: UniverseSnapshot) -> None:
        """保存到快取"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_dir / f"{universe.date}.pkl"
        pickle.dump(universe, open(cache_file, 'wb'))
```

### 並行計算
```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

class ParallelUniverseBuilder:
    """並行宇宙構建器"""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers

    async def build_universe_parallel(self, symbols: List[str]) -> Dict[str, SymbolMetadata]:
        """並行計算所有幣種屬性"""

        async def calculate_symbol_metadata(symbol: str) -> Tuple[str, SymbolMetadata]:
            loop = asyncio.get_event_loop()

            # 並行計算各項指標
            volume_task = loop.run_in_executor(None, calculate_volume_metrics, symbol)
            history_task = loop.run_in_executor(None, calculate_history_days, symbol)
            oi_task = loop.run_in_executor(None, calculate_oi_metrics, symbol)

            volume_metrics, history_days, oi_metrics = await asyncio.gather(
                volume_task, history_task, oi_task
            )

            metadata = SymbolMetadata(
                symbol=symbol,
                volume_30d_usd=volume_metrics['volume_30d_avg'],
                history_days=history_days,
                oi_avg_usd=oi_metrics['oi_avg_usd'],
                # ... 其他屬性
            )

            return symbol, metadata

        # 並行處理所有符號
        tasks = [calculate_symbol_metadata(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        return dict(results)
```

---

## 🧪 測試策略

### 單元測試
```python
class TestUniverseManager:
    """宇宙管理器測試"""

    def test_build_universe_basic(self):
        """測試基本宇宙構建"""
        manager = UniverseManager(['binance'])
        universe = manager.build_universe()

        assert len(universe.symbols) > 0
        assert 'large_cap' in universe.classification

    def test_volume_calculation_accuracy(self):
        """測試成交額計算準確性"""
        # 使用已知數據測試計算結果
        pass

    def test_classification_rules(self):
        """測試分類規則正確性"""
        # 測試邊界條件和分類邏輯
        pass

class TestPerformance:
    """性能測試"""

    def test_build_time_under_limit(self):
        """測試構建時間限制"""
        start_time = time.time()
        manager = UniverseManager(['binance'])
        universe = manager.build_universe()
        build_time = time.time() - start_time

        # 構建時間應該在5分鐘內
        assert build_time < 300
```

### 集成測試
```python
class TestUniverseIntegration:
    """集成測試"""

    def test_full_workflow(self):
        """測試完整工作流程"""
        # 1. 構建宇宙
        # 2. 匯出配置
        # 3. 在實驗中使用
        # 4. 驗證結果
        pass

    def test_cli_commands(self):
        """測試CLI命令"""
        # 測試所有CLI命令的正確性
        pass
```

---

## 📈 監控與維護

### 數據品質監控
```python
class UniverseQualityMonitor:
    """宇宙品質監控"""

    def validate_universe_quality(self, universe: UniverseSnapshot) -> Dict:
        """驗證宇宙品質"""

        issues = []

        # 檢查數據完整性
        for symbol, metadata in universe.symbols.items():
            if metadata.volume_30d_usd == 0:
                issues.append(f"{symbol}: 成交額為0")

            if metadata.history_days < 30:
                issues.append(f"{symbol}: 上市時間過短")

        # 檢查分類合理性
        classification_counts = {
            cls: len(symbols)
            for cls, symbols in universe.classification.items()
        }

        if classification_counts.get('large_cap', 0) > 50:
            issues.append("大盤股數量過多")

        return {
            'total_issues': len(issues),
            'issues': issues,
            'quality_score': max(0, 100 - len(issues) * 5)
        }
```

### 自動更新機制
```python
class UniverseAutoUpdater:
    """自動更新機制"""

    def schedule_weekly_update(self):
        """排程每週更新"""
        # 使用cron job或任務調度器
        pass

    def update_if_stale(self, max_age_days: int = 7):
        """如果數據過期則更新"""
        latest_universe = self.get_latest_universe()

        if self.is_universe_stale(latest_universe, max_age_days):
            self.build_new_universe()
```

這個技術規格為幣種宇宙管理系統提供了完整的設計藍圖，確保實作的一致性和品質。
