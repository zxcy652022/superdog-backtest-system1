# SuperDog v0.6 策略實驗室技術規格  
**Strategy Laboratory System Technical Specification**

---

## 🧪 系統概述

策略實驗室是SuperDog v0.6的核心組件，提供大規模策略實驗、參數優化和結果分析功能。支援批量回測、參數網格搜索、多指標評估和智能結果篩選。

### 核心價值
- **效率提升**: 單次配置執行數百個回測
- **參數優化**: 自動找出最佳參數組合
- **結果分析**: 多維度指標比較和排序
- **失敗容錯**: 單個失敗不影響整體實驗

---

## 🏗️ 架構設計

### 核心組件
```
execution_engine/
├── experiments.py              # 實驗配置與管理
├── experiment_runner.py        # 批量執行引擎
├── parameter_optimizer.py      # 參數優化器
└── result_analyzer.py          # 結果分析器

reports/
├── experiment_store.py         # 實驗結果存儲
├── experiment_reporter.py      # 報告生成器  
└── performance_metrics.py      # 績效指標計算
```

### 數據流架構
```
ExperimentConfig → ParameterExpansion → BatchExecution → ResultStorage → Analysis
     ↓                    ↓                  ↓             ↓           ↓
   配置解析          參數組合展開        批量回測執行      結果存儲     分析報告
```

---

## 📋 核心數據結構

### 實驗配置
```python
@dataclass
class ExperimentConfig:
    """實驗配置完整定義"""
    
    # 基本信息
    name: str                           # 實驗名稱
    description: str = ""               # 實驗描述
    created_by: str = "system"          # 創建者
    created_at: datetime = field(default_factory=datetime.now)
    
    # 策略設置
    strategy: str                       # 策略名稱
    strategy_params_base: Dict = field(default_factory=dict)  # 基礎參數
    
    # 幣種設置
    symbol_source: str = "explicit"     # "explicit" | "universe" 
    symbols: List[str] = field(default_factory=list)          # 明確指定
    universe_type: str = None           # "large_cap" | "mid_cap" | "small_cap"
    universe_top_n: int = 100           # 從宇宙取前N個
    universe_filters: Dict = field(default_factory=dict)      # 額外篩選條件
    
    # 時間設置
    timeframe: str = "1h"               # 時間週期
    start_date: str = None              # 回測開始日期
    end_date: str = None                # 回測結束日期
    lookback_days: int = 365            # 回測天數（如果未指定日期）
    
    # 參數優化設置
    param_grid: Dict[str, List] = field(default_factory=dict)  # 參數網格
    optimization_metric: str = "sharpe_ratio"                  # 優化目標
    max_combinations: int = 1000        # 最大參數組合數
    
    # 執行設置
    parallel_workers: int = 4           # 並行執行數量
    timeout_seconds: int = 300          # 單次回測超時
    fail_fast: bool = False             # 是否遇錯立即停止
    
    # 輸出設置
    output_metrics: List[str] = field(default_factory=lambda: [
        'total_return', 'sharpe_ratio', 'max_drawdown', 
        'win_rate', 'profit_factor', 'total_trades'
    ])
    save_detailed_results: bool = False  # 是否保存詳細交易記錄

@dataclass
class ParameterCombination:
    """參數組合"""
    
    combination_id: str                 # 組合唯一ID
    base_params: Dict                   # 基礎參數  
    variable_params: Dict               # 變量參數
    combined_params: Dict               # 合併後參數
    priority: int = 0                   # 執行優先級

@dataclass  
class ExperimentTask:
    """單個實驗任務"""
    
    task_id: str                        # 任務ID
    experiment_name: str                # 實驗名稱
    symbol: str                         # 交易對
    param_combination: ParameterCombination  # 參數組合
    config: ExperimentConfig            # 實驗配置
    status: str = "pending"             # pending | running | completed | failed
    start_time: datetime = None         # 開始時間
    end_time: datetime = None           # 結束時間
    error_message: str = None           # 錯誤信息

@dataclass
class ExperimentResult:
    """實驗結果"""
    
    # 任務信息
    task_id: str
    experiment_name: str
    symbol: str
    timeframe: str
    start_date: str  
    end_date: str
    
    # 參數信息
    strategy: str
    params_json: str                    # JSON格式的參數
    param_combination_id: str
    
    # 績效指標
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    
    # 交易統計
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    
    # 風險指標
    var_95: float                       # 95% VaR
    expected_shortfall: float           # 期望短缺
    downside_deviation: float           # 下行偏差
    
    # 執行信息
    execution_time_seconds: float
    data_points: int
    data_snapshot_id: str               # 數據快照ID
    created_at: datetime
    
    # 可選詳細結果
    detailed_trades: List[Dict] = None  # 詳細交易記錄
    daily_returns: List[float] = None   # 日回報率序列
```

---

## 🔧 核心功能模組

### 1. 實驗管理器
```python
class ExperimentManager:
    """實驗管理核心類"""
    
    def __init__(self, data_dir: str = "data/experiments"):
        self.data_dir = Path(data_dir)
        self.universe_manager = UniverseManager()
        self.result_store = ExperimentResultStore()
    
    def create_experiment(self, config: ExperimentConfig) -> str:
        """創建新實驗"""
        
        # 驗證配置
        self._validate_config(config)
        
        # 生成實驗ID
        experiment_id = self._generate_experiment_id(config)
        
        # 保存配置
        config_path = self.data_dir / "configs" / f"{experiment_id}.yml" 
        self._save_config(config, config_path)
        
        return experiment_id
    
    def load_experiment(self, experiment_id: str) -> ExperimentConfig:
        """載入實驗配置"""
        config_path = self.data_dir / "configs" / f"{experiment_id}.yml"
        return self._load_config(config_path)
    
    def list_experiments(self, status: str = None) -> List[Dict]:
        """列出實驗"""
        experiments = []
        
        for config_file in (self.data_dir / "configs").glob("*.yml"):
            config = self._load_config(config_file)
            experiment_info = {
                'id': config_file.stem,
                'name': config.name,
                'strategy': config.strategy,
                'created_at': config.created_at,
                'status': self._get_experiment_status(config_file.stem)
            }
            experiments.append(experiment_info)
        
        if status:
            experiments = [e for e in experiments if e['status'] == status]
            
        return sorted(experiments, key=lambda x: x['created_at'], reverse=True)
    
    def _validate_config(self, config: ExperimentConfig) -> None:
        """驗證實驗配置"""
        
        # 驗證策略存在
        available_strategies = list_strategies()
        if config.strategy not in available_strategies:
            raise ValueError(f"策略 {config.strategy} 不存在")
        
        # 驗證幣種設置
        if config.symbol_source == "explicit" and not config.symbols:
            raise ValueError("明確模式必須提供symbols列表")
            
        if config.symbol_source == "universe" and not config.universe_type:
            raise ValueError("宇宙模式必須指定universe_type")
        
        # 驗證參數網格
        if not config.param_grid:
            raise ValueError("必須提供param_grid參數網格")
        
        # 計算參數組合總數
        total_combinations = 1
        for param_values in config.param_grid.values():
            total_combinations *= len(param_values)
            
        if total_combinations > config.max_combinations:
            raise ValueError(f"參數組合數量 {total_combinations} 超過限制 {config.max_combinations}")
```

### 2. 參數展開器
```python
class ParameterExpander:
    """參數組合展開器"""
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
    
    def expand_symbols(self) -> List[str]:
        """展開幣種列表"""
        
        if self.config.symbol_source == "explicit":
            return self.config.symbols
            
        elif self.config.symbol_source == "universe":
            universe_manager = UniverseManager()
            universe = universe_manager.load_latest_universe()
            
            symbols = universe.get_symbols_by_classification(
                self.config.universe_type, 
                top_n=self.config.universe_top_n
            )
            
            # 應用額外篩選
            if self.config.universe_filters:
                symbols = self._apply_universe_filters(symbols)
                
            return symbols
        
        else:
            raise ValueError(f"不支援的symbol_source: {self.config.symbol_source}")
    
    def expand_parameter_combinations(self) -> List[ParameterCombination]:
        """展開參數組合"""
        
        # 獲取所有參數名和值
        param_names = list(self.config.param_grid.keys())
        param_values = list(self.config.param_grid.values())
        
        # 生成所有組合
        combinations = []
        for i, combo in enumerate(itertools.product(*param_values)):
            variable_params = dict(zip(param_names, combo))
            combined_params = {**self.config.strategy_params_base, **variable_params}
            
            combination = ParameterCombination(
                combination_id=f"combo_{i:04d}",
                base_params=self.config.strategy_params_base,
                variable_params=variable_params,
                combined_params=combined_params
            )
            combinations.append(combination)
        
        # 限制組合數量
        if len(combinations) > self.config.max_combinations:
            # 隨機採樣或智能採樣
            combinations = self._sample_combinations(combinations)
        
        return combinations
    
    def expand_experiment_tasks(self) -> List[ExperimentTask]:
        """展開所有實驗任務"""
        
        symbols = self.expand_symbols()
        param_combinations = self.expand_parameter_combinations()
        
        tasks = []
        task_id = 0
        
        for symbol in symbols:
            for param_combo in param_combinations:
                task = ExperimentTask(
                    task_id=f"{self.config.name}_{task_id:06d}",
                    experiment_name=self.config.name,
                    symbol=symbol,
                    param_combination=param_combo,
                    config=self.config
                )
                tasks.append(task)
                task_id += 1
        
        return tasks
    
    def _sample_combinations(self, combinations: List[ParameterCombination]) -> List[ParameterCombination]:
        """智能採樣參數組合"""
        
        if self.config.optimization_metric == "random":
            # 隨機採樣
            return random.sample(combinations, self.config.max_combinations)
        else:
            # 網格採樣：確保參數空間均勻覆蓋
            return self._grid_sample(combinations)
```

### 3. 批量執行引擎
```python
class ExperimentRunner:
    """實驗批量執行引擎"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.result_store = ExperimentResultStore()
        
    async def run_experiment(self, config: ExperimentConfig) -> ExperimentSummary:
        """執行完整實驗"""
        
        print(f"🚀 開始實驗: {config.name}")
        start_time = datetime.now()
        
        # 展開實驗任務
        expander = ParameterExpander(config)
        tasks = expander.expand_experiment_tasks()
        
        print(f"📋 總任務數: {len(tasks)}")
        print(f"💰 幣種數: {len(set(task.symbol for task in tasks))}")
        print(f"⚙️ 參數組合數: {len(set(task.param_combination.combination_id for task in tasks))}")
        
        # 並行執行任務
        results = []
        failed_tasks = []
        
        async with aiofiles.TemporaryDirectory() as temp_dir:
            semaphore = asyncio.Semaphore(self.max_workers)
            
            async def run_single_task(task: ExperimentTask) -> Optional[ExperimentResult]:
                async with semaphore:
                    try:
                        return await self._execute_task(task)
                    except Exception as e:
                        failed_tasks.append((task, str(e)))
                        if config.fail_fast:
                            raise
                        return None
            
            # 執行所有任務
            task_results = await asyncio.gather(*[
                run_single_task(task) for task in tasks
            ], return_exceptions=True)
            
            # 篩選成功結果
            results = [r for r in task_results if isinstance(r, ExperimentResult)]
        
        # 保存結果
        experiment_summary = self._save_experiment_results(config, results, failed_tasks)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        print(f"✅ 實驗完成!")
        print(f"⏱️ 執行時間: {execution_time:.1f} 秒")
        print(f"✅ 成功任務: {len(results)}")
        print(f"❌ 失敗任務: {len(failed_tasks)}")
        
        return experiment_summary
    
    async def _execute_task(self, task: ExperimentTask) -> ExperimentResult:
        """執行單個任務"""
        
        task.status = "running"
        task.start_time = datetime.now()
        
        try:
            # 載入策略
            strategy_cls = get_strategy(task.config.strategy)
            
            # 載入數據
            data = await self._load_task_data(task)
            
            # 執行回測
            backtest_result = await self._run_backtest(
                strategy_cls, data, task.param_combination.combined_params, task.config
            )
            
            # 計算績效指標
            metrics = self._calculate_metrics(backtest_result)
            
            # 生成結果
            result = ExperimentResult(
                task_id=task.task_id,
                experiment_name=task.experiment_name,
                symbol=task.symbol,
                timeframe=task.config.timeframe,
                start_date=task.config.start_date,
                end_date=task.config.end_date,
                strategy=task.config.strategy,
                params_json=json.dumps(task.param_combination.combined_params),
                param_combination_id=task.param_combination.combination_id,
                **metrics,
                execution_time_seconds=(datetime.now() - task.start_time).total_seconds(),
                data_points=len(data),
                created_at=datetime.now()
            )
            
            task.status = "completed"
            task.end_time = datetime.now()
            
            return result
            
        except Exception as e:
            task.status = "failed"
            task.end_time = datetime.now()
            task.error_message = str(e)
            raise
    
    async def _load_task_data(self, task: ExperimentTask) -> Dict:
        """載入任務數據"""
        
        # 使用現有的數據管道
        pipeline = get_data_pipeline()
        
        strategy_cls = get_strategy(task.config.strategy)
        strategy_instance = strategy_cls()
        
        # 獲取策略數據需求
        data_requirements = strategy_instance.get_data_requirements()
        
        # 載入數據
        data = pipeline.load_strategy_data(
            strategy_instance,
            task.symbol,
            task.config.timeframe,
            start_date=task.config.start_date,
            end_date=task.config.end_date
        )
        
        return data
    
    def _calculate_metrics(self, backtest_result) -> Dict[str, float]:
        """計算績效指標"""
        
        from reports.performance_metrics import PerformanceCalculator
        
        calculator = PerformanceCalculator(backtest_result)
        
        return {
            'total_return': calculator.total_return(),
            'annualized_return': calculator.annualized_return(),
            'volatility': calculator.volatility(),
            'sharpe_ratio': calculator.sharpe_ratio(),
            'max_drawdown': calculator.max_drawdown(),
            'calmar_ratio': calculator.calmar_ratio(),
            'total_trades': calculator.total_trades(),
            'win_rate': calculator.win_rate(),
            'profit_factor': calculator.profit_factor(),
            'avg_win': calculator.avg_win(),
            'avg_loss': calculator.avg_loss(),
            'var_95': calculator.var_95(),
            'expected_shortfall': calculator.expected_shortfall()
        }
```

---

## 💾 結果存儲系統

### 存儲架構
```python
class ExperimentResultStore:
    """實驗結果存儲管理"""
    
    def __init__(self, storage_dir: str = "data/experiments/results"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_experiment_results(self, experiment_name: str, 
                              results: List[ExperimentResult]) -> str:
        """保存實驗結果"""
        
        # 轉換為DataFrame
        df = pd.DataFrame([asdict(result) for result in results])
        
        # 生成檔案名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{experiment_name}_{timestamp}.parquet"
        filepath = self.storage_dir / filename
        
        # 保存為Parquet
        df.to_parquet(filepath, compression='snappy')
        
        # 更新索引
        self._update_experiment_index(experiment_name, filename)
        
        return str(filepath)
    
    def load_experiment_results(self, experiment_name: str, 
                              run_id: str = None) -> pd.DataFrame:
        """載入實驗結果"""
        
        if run_id:
            filepath = self.storage_dir / f"{experiment_name}_{run_id}.parquet"
        else:
            # 載入最新結果
            filepath = self._get_latest_result_file(experiment_name)
        
        return pd.read_parquet(filepath)
    
    def query_results(self, filters: Dict = None, 
                     sort_by: str = None, limit: int = None) -> pd.DataFrame:
        """查詢實驗結果"""
        
        # 載入所有結果文件
        all_results = []
        
        for result_file in self.storage_dir.glob("*.parquet"):
            df = pd.read_parquet(result_file)
            all_results.append(df)
        
        if not all_results:
            return pd.DataFrame()
        
        # 合併所有結果
        combined_df = pd.concat(all_results, ignore_index=True)
        
        # 應用篩選條件
        if filters:
            for column, condition in filters.items():
                if isinstance(condition, dict):
                    # 範圍條件 {'min': 0.1, 'max': 0.5}
                    if 'min' in condition:
                        combined_df = combined_df[combined_df[column] >= condition['min']]
                    if 'max' in condition:
                        combined_df = combined_df[combined_df[column] <= condition['max']]
                else:
                    # 等值條件
                    combined_df = combined_df[combined_df[column] == condition]
        
        # 排序
        if sort_by:
            ascending = not sort_by.startswith('-')
            sort_column = sort_by.lstrip('-')
            combined_df = combined_df.sort_values(sort_column, ascending=ascending)
        
        # 限制結果數量
        if limit:
            combined_df = combined_df.head(limit)
        
        return combined_df
```

---

## 📊 結果分析器

### 分析功能
```python
class ExperimentAnalyzer:
    """實驗結果分析器"""
    
    def __init__(self, result_store: ExperimentResultStore):
        self.result_store = result_store
    
    def find_best_parameters(self, experiment_name: str, 
                           metric: str = 'sharpe_ratio',
                           top_n: int = 10) -> pd.DataFrame:
        """找出最佳參數組合"""
        
        results = self.result_store.load_experiment_results(experiment_name)
        
        # 按指標排序
        ascending = metric in ['max_drawdown', 'volatility']  # 這些指標越小越好
        best_results = results.nlargest(top_n, metric) if not ascending else results.nsmallest(top_n, metric)
        
        return best_results[['symbol', 'params_json', metric, 'total_return', 'win_rate']]
    
    def analyze_parameter_sensitivity(self, experiment_name: str, 
                                    target_metric: str = 'sharpe_ratio') -> Dict:
        """分析參數敏感性"""
        
        results = self.result_store.load_experiment_results(experiment_name)
        
        # 解析參數JSON
        results['params'] = results['params_json'].apply(json.loads)
        
        sensitivity_analysis = {}
        
        # 分析每個參數的影響
        for result in results.itertuples():
            params = result.params
            metric_value = getattr(result, target_metric)
            
            for param_name, param_value in params.items():
                if param_name not in sensitivity_analysis:
                    sensitivity_analysis[param_name] = []
                
                sensitivity_analysis[param_name].append({
                    'value': param_value,
                    'metric': metric_value
                })
        
        # 計算相關性
        correlations = {}
        for param_name, data in sensitivity_analysis.items():
            df = pd.DataFrame(data)
            if df['value'].dtype in ['int64', 'float64']:
                correlation = df['value'].corr(df['metric'])
                correlations[param_name] = correlation
        
        return {
            'correlations': correlations,
            'sensitivity_data': sensitivity_analysis
        }
    
    def compare_strategies(self, experiment_names: List[str], 
                          metric: str = 'sharpe_ratio') -> pd.DataFrame:
        """比較不同策略表現"""
        
        comparison_data = []
        
        for exp_name in experiment_names:
            results = self.result_store.load_experiment_results(exp_name)
            
            summary = {
                'experiment': exp_name,
                'strategy': results['strategy'].iloc[0],
                'total_combinations': len(results),
                f'best_{metric}': results[metric].max(),
                f'avg_{metric}': results[metric].mean(),
                f'std_{metric}': results[metric].std(),
                'success_rate': (results[metric] > 0).sum() / len(results) * 100
            }
            
            comparison_data.append(summary)
        
        return pd.DataFrame(comparison_data)
```

---

## 🖥️ CLI接口設計

### 命令結構
```python
@click.group(name='experiment')
def experiment_commands():
    """策略實驗室命令"""
    pass

@experiment_commands.command()
@click.argument('config_file', type=click.Path(exists=True))
@click.option('--dry-run', is_flag=True, help='僅驗證配置，不執行')
@click.option('--parallel', default=4, help='並行執行數量')
def run(config_file, dry_run, parallel):
    """執行策略實驗
    
    Examples:
        superdog experiment run experiments/kawamoku_optimization.yml
        superdog experiment run config.yml --dry-run
    """
    
@experiment_commands.command()
@click.argument('experiment_name')
@click.option('--metric', default='sharpe_ratio', help='排序指標')
@click.option('--top', default=10, help='顯示前N個結果')
@click.option('--format', type=click.Choice(['table', 'json']), default='table')
def best(experiment_name, metric, top, format):
    """顯示最佳參數組合
    
    Examples:
        superdog experiment best kawamoku_opt --metric sharpe_ratio --top 5
        superdog experiment best myexp --format json
    """

@experiment_commands.command()  
@click.option('--experiment', help='實驗名稱篩選')
@click.option('--strategy', help='策略名稱篩選')
@click.option('--symbol', help='交易對篩選(支援通配符)')
@click.option('--metric', help='指標篩選 (格式: metric:min:max)')
def filter(experiment, strategy, symbol, metric):
    """篩選實驗結果
    
    Examples:
        superdog experiment filter --experiment kawamoku* --symbol BTC*
        superdog experiment filter --metric sharpe_ratio:0.5:2.0
    """

@experiment_commands.command()
@click.argument('experiment_name')
@click.option('--detailed', is_flag=True, help='顯示詳細統計')
def show(experiment_name, detailed):
    """顯示實驗摘要
    
    Examples:
        superdog experiment show kawamoku_optimization
        superdog experiment show myexp --detailed
    """
```

---

## ⚡ 性能優化

### 並行執行優化
```python
class OptimizedExperimentRunner(ExperimentRunner):
    """優化的實驗執行器"""
    
    def __init__(self, max_workers: int = 8):
        super().__init__(max_workers)
        self.data_cache = LRUCache(maxsize=100)  # 數據快取
        self.strategy_cache = {}                 # 策略實例快取
    
    async def _load_task_data_optimized(self, task: ExperimentTask) -> Dict:
        """優化的數據載入"""
        
        cache_key = f"{task.symbol}_{task.config.timeframe}_{task.config.start_date}_{task.config.end_date}"
        
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]
        
        data = await self._load_task_data(task)
        self.data_cache[cache_key] = data
        
        return data
    
    def _batch_similar_tasks(self, tasks: List[ExperimentTask]) -> List[List[ExperimentTask]]:
        """將相似任務分批處理"""
        
        # 按(symbol, timeframe)分組
        grouped_tasks = defaultdict(list)
        
        for task in tasks:
            key = (task.symbol, task.config.timeframe)
            grouped_tasks[key].append(task)
        
        # 每批最多處理同一資產的10個參數組合
        batches = []
        for group_tasks in grouped_tasks.values():
            for i in range(0, len(group_tasks), 10):
                batches.append(group_tasks[i:i+10])
        
        return batches
```

### 記憶體管理
```python
class MemoryEfficientRunner:
    """記憶體高效的執行器"""
    
    def __init__(self, max_memory_gb: float = 4.0):
        self.max_memory_gb = max_memory_gb
        self.current_memory_usage = 0
    
    async def run_with_memory_limit(self, tasks: List[ExperimentTask]):
        """在記憶體限制下執行任務"""
        
        task_queue = deque(tasks)
        running_tasks = []
        
        while task_queue or running_tasks:
            # 檢查記憶體使用量
            current_memory = self._get_memory_usage()
            
            if current_memory < self.max_memory_gb and task_queue:
                # 啟動新任務
                task = task_queue.popleft()
                task_coroutine = self._run_memory_tracked_task(task)
                running_tasks.append(asyncio.create_task(task_coroutine))
            
            # 等待任一任務完成
            if running_tasks:
                done, pending = await asyncio.wait(
                    running_tasks, return_when=asyncio.FIRST_COMPLETED
                )
                
                # 處理完成的任務
                for task in done:
                    result = await task
                    self._save_result(result)
                
                running_tasks = list(pending)
            
            await asyncio.sleep(0.1)  # 短暫休息
```

這個技術規格提供了策略實驗室的完整設計藍圖，確保v0.6能夠提供強大的批量實驗和參數優化功能。
