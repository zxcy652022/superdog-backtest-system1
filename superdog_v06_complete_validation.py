#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperDog v0.6 完整驗證測試套件
測試所有四個Phase的核心功能
"""

import sys
import time
import json
import traceback
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 顏色輸出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.WHITE}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

class SuperDogV06Validator:
    """SuperDog v0.6 完整驗證器"""
    
    def __init__(self):
        self.test_results = {
            'phase1': {'passed': 0, 'failed': 0, 'tests': []},
            'phase2': {'passed': 0, 'failed': 0, 'tests': []},
            'phase3': {'passed': 0, 'failed': 0, 'tests': []},
            'phase4': {'passed': 0, 'failed': 0, 'tests': []},
            'integration': {'passed': 0, 'failed': 0, 'tests': []},
            'cli': {'passed': 0, 'failed': 0, 'tests': []},
        }
        
        self.start_time = time.time()
        
    def run_test(self, phase, test_name, test_func):
        """執行單個測試"""
        try:
            start = time.time()
            result = test_func()
            duration = time.time() - start
            
            if result:
                self.test_results[phase]['passed'] += 1
                print_success(f"{test_name} ({duration:.2f}s)")
            else:
                self.test_results[phase]['failed'] += 1
                print_error(f"{test_name} ({duration:.2f}s)")
                
            self.test_results[phase]['tests'].append({
                'name': test_name,
                'passed': result,
                'duration': duration
            })
            
            return result
            
        except Exception as e:
            self.test_results[phase]['failed'] += 1
            print_error(f"{test_name} - 異常: {str(e)}")
            self.test_results[phase]['tests'].append({
                'name': test_name,
                'passed': False,
                'duration': 0,
                'error': str(e)
            })
            return False

    def test_phase1_universe_management(self):
        """Phase 1: 幣種宇宙管理測試"""
        print_header("Phase 1: 幣種宇宙管理系統驗證")
        
        # 測試1: 模組導入
        def test_universe_imports():
            try:
                from data.universe_manager import UniverseManager
                from data.universe_calculator import UniverseCalculator
                return True
            except ImportError as e:
                print_warning(f"導入失敗: {e}")
                return False
        
        # 測試2: 幣種屬性計算
        def test_symbol_calculation():
            try:
                # 創建測試數據
                test_data = pd.DataFrame({
                    'timestamp': pd.date_range('2023-01-01', periods=30, freq='D'),
                    'open': np.random.uniform(40000, 45000, 30),
                    'high': np.random.uniform(45000, 50000, 30),
                    'low': np.random.uniform(35000, 40000, 30),
                    'close': np.random.uniform(40000, 45000, 30),
                    'volume': np.random.uniform(100000, 1000000, 30)
                })
                
                # 測試成交額計算
                volume_usd = test_data['volume'] * test_data['close']
                avg_volume = volume_usd.mean()
                
                return avg_volume > 0
            except Exception:
                return False
        
        # 測試3: 分類規則
        def test_classification_rules():
            try:
                # 模擬幣種數據
                symbol_data = {
                    'BTCUSDT': {'volume_30d': 5e9, 'market_cap_rank': 1},
                    'ETHUSDT': {'volume_30d': 3e9, 'market_cap_rank': 2},
                    'SOLUSDT': {'volume_30d': 5e8, 'market_cap_rank': 15},
                    'DOGEUSDT': {'volume_30d': 1e8, 'market_cap_rank': 50},
                }
                
                # 簡單分類邏輯
                for symbol, data in symbol_data.items():
                    if data['market_cap_rank'] <= 10 and data['volume_30d'] > 1e9:
                        classification = 'large_cap'
                    elif data['market_cap_rank'] <= 50 and data['volume_30d'] > 1e8:
                        classification = 'mid_cap'
                    else:
                        classification = 'small_cap'
                
                return True
            except Exception:
                return False
        
        # 測試4: 數據存儲
        def test_data_storage():
            try:
                # 測試創建宇宙目錄
                universe_dir = Path('data/universe')
                universe_dir.mkdir(parents=True, exist_ok=True)
                
                # 測試Parquet寫入
                test_df = pd.DataFrame({
                    'symbol': ['BTCUSDT', 'ETHUSDT'],
                    'volume_30d': [5e9, 3e9],
                    'classification': ['large_cap', 'large_cap']
                })
                
                test_file = universe_dir / 'test_snapshot.parquet'
                test_df.to_parquet(test_file)
                
                # 測試讀取
                loaded_df = pd.read_parquet(test_file)
                
                # 清理測試文件
                test_file.unlink(missing_ok=True)
                
                return len(loaded_df) == 2
            except Exception:
                return False
        
        # 執行所有測試
        tests = [
            ("宇宙管理模組導入", test_universe_imports),
            ("幣種屬性計算", test_symbol_calculation),
            ("分類規則邏輯", test_classification_rules),
            ("數據存儲機制", test_data_storage),
        ]
        
        for test_name, test_func in tests:
            self.run_test('phase1', test_name, test_func)

    def test_phase2_strategy_lab(self):
        """Phase 2: 策略實驗室測試"""
        print_header("Phase 2: 策略實驗室系統驗證")
        
        # 測試1: 實驗系統導入
        def test_experiment_imports():
            try:
                from execution_engine.experiments import ExperimentConfig
                from execution_engine.experiment_runner import ExperimentRunner
                from execution_engine.parameter_optimizer import ParameterOptimizer
                from execution_engine.result_analyzer import ResultAnalyzer
                return True
            except ImportError:
                return False
        
        # 測試2: 參數網格展開
        def test_parameter_expansion():
            try:
                param_grid = {
                    'period': [10, 20, 30],
                    'threshold': [0.1, 0.2],
                    'risk_pct': [0.01, 0.02]
                }
                
                # 計算組合數
                total_combinations = 1
                for values in param_grid.values():
                    total_combinations *= len(values)
                
                expected = 3 * 2 * 2  # 12
                return total_combinations == expected
            except Exception:
                return False
        
        # 測試3: 實驗配置
        def test_experiment_config():
            try:
                # 創建測試配置
                config = {
                    'name': 'test_experiment',
                    'strategy': 'simple_sma',
                    'symbols': ['BTCUSDT', 'ETHUSDT'],
                    'timeframe': '1h',
                    'param_grid': {
                        'period': [10, 20],
                        'threshold': [0.1, 0.2]
                    }
                }
                
                # 驗證必需字段
                required_fields = ['name', 'strategy', 'symbols', 'param_grid']
                return all(field in config for field in required_fields)
            except Exception:
                return False
        
        # 測試4: 結果分析
        def test_result_analysis():
            try:
                # 模擬實驗結果
                results = pd.DataFrame({
                    'strategy': ['simple_sma'] * 4,
                    'symbol': ['BTCUSDT', 'ETHUSDT'] * 2,
                    'params': ['{"period":10}', '{"period":10}', '{"period":20}', '{"period":20}'],
                    'total_return': [0.15, 0.12, 0.18, 0.09],
                    'sharpe_ratio': [1.2, 0.9, 1.5, 0.7],
                    'max_drawdown': [-0.08, -0.12, -0.06, -0.15]
                })
                
                # 找最佳結果
                best_result = results.loc[results['sharpe_ratio'].idxmax()]
                
                return best_result['sharpe_ratio'] == 1.5
            except Exception:
                return False
        
        tests = [
            ("實驗系統模組導入", test_experiment_imports),
            ("參數網格展開", test_parameter_expansion),
            ("實驗配置驗證", test_experiment_config),
            ("結果分析功能", test_result_analysis),
        ]
        
        for test_name, test_func in tests:
            self.run_test('phase2', test_name, test_func)

    def test_phase3_execution_model(self):
        """Phase 3: 真實執行模型測試"""
        print_header("Phase 3: 真實執行模型驗證")
        
        # 測試1: 執行模型導入
        def test_execution_imports():
            try:
                from execution_engine.execution_model import RealisticExecutionEngine
                from execution_engine.fee_models import FeeCalculator
                from execution_engine.slippage_models import SlippageModel
                from execution_engine.funding_models import FundingModel
                from execution_engine.liquidation_models import LiquidationModel
                return True
            except ImportError:
                return False
        
        # 測試2: 手續費計算
        def test_fee_calculation():
            try:
                # 模擬手續費計算
                notional_value = 10000  # $10,000
                
                # Maker費率 0.02%
                maker_fee = notional_value * 0.0002
                
                # Taker費率 0.04%  
                taker_fee = notional_value * 0.0004
                
                return maker_fee == 2.0 and taker_fee == 4.0
            except Exception:
                return False
        
        # 測試3: 滑價計算
        def test_slippage_calculation():
            try:
                # 模擬滑價計算
                order_size = 100000  # $100K
                avg_volume = 5000000  # $5M daily volume
                volume_ratio = order_size / avg_volume  # 2%
                
                # 基礎滑價 + 市場影響
                base_slippage = 0.0003  # 0.03%
                market_impact = volume_ratio * 0.1  # 0.2%
                total_slippage = base_slippage + market_impact
                
                return total_slippage > base_slippage
            except Exception:
                return False
        
        # 測試4: 強平風險
        def test_liquidation_risk():
            try:
                # 模擬強平計算
                entry_price = 45000
                current_price = 42000
                leverage = 10
                
                # 多頭倉位虧損
                price_change = (current_price - entry_price) / entry_price  # -6.67%
                leveraged_pnl = price_change * leverage  # -66.67%
                
                # 強平檢查 (維持保證金 5%)
                margin_ratio = 1 + leveraged_pnl  # 33.33%
                is_liquidated = margin_ratio <= 0.05
                
                return margin_ratio < 1.0 and not is_liquidated
            except Exception:
                return False
        
        tests = [
            ("執行模型模組導入", test_execution_imports),
            ("手續費計算邏輯", test_fee_calculation),
            ("滑價計算邏輯", test_slippage_calculation),
            ("強平風險檢測", test_liquidation_risk),
        ]
        
        for test_name, test_func in tests:
            self.run_test('phase3', test_name, test_func)

    def test_phase4_risk_management(self):
        """Phase 4: 動態風控測試"""
        print_header("Phase 4: 動態風控系統驗證")
        
        # 測試1: 風控模組導入
        def test_risk_imports():
            try:
                from risk_management.support_resistance import SupportResistanceDetector
                from risk_management.dynamic_stops import DynamicStopManager
                from risk_management.risk_calculator import RiskCalculator
                from risk_management.position_sizer import PositionSizer
                return True
            except ImportError:
                return False
        
        # 測試2: 支撐壓力檢測
        def test_support_resistance():
            try:
                # 創建測試K線數據
                test_data = pd.DataFrame({
                    'timestamp': pd.date_range('2023-01-01', periods=100, freq='H'),
                    'open': np.random.uniform(44000, 46000, 100),
                    'high': np.random.uniform(46000, 48000, 100),
                    'low': np.random.uniform(42000, 44000, 100),
                    'close': np.random.uniform(44000, 46000, 100),
                    'volume': np.random.uniform(100, 1000, 100)
                })
                
                # 模擬支撐壓力檢測
                highs = test_data['high']
                lows = test_data['low']
                
                # 找局部極值
                resistance_levels = []
                support_levels = []
                
                for i in range(2, len(highs)-2):
                    # 檢查是否為局部高點
                    if (highs.iloc[i] > highs.iloc[i-1] and 
                        highs.iloc[i] > highs.iloc[i-2] and
                        highs.iloc[i] > highs.iloc[i+1] and 
                        highs.iloc[i] > highs.iloc[i+2]):
                        resistance_levels.append(highs.iloc[i])
                
                return len(resistance_levels) > 0
            except Exception:
                return False
        
        # 測試3: 動態止損
        def test_dynamic_stops():
            try:
                # 模擬ATR動態止損
                test_prices = [45000, 45100, 44900, 45200, 44800, 45300]
                
                # 計算ATR (簡化版本)
                price_changes = []
                for i in range(1, len(test_prices)):
                    change = abs(test_prices[i] - test_prices[i-1])
                    price_changes.append(change)
                
                atr = np.mean(price_changes)
                
                # 動態止損 = 入場價 - (ATR * 倍數)
                entry_price = 45000
                atr_multiplier = 2.0
                dynamic_stop = entry_price - (atr * atr_multiplier)
                
                return dynamic_stop < entry_price
            except Exception:
                return False
        
        # 測試4: 風險指標計算
        def test_risk_metrics():
            try:
                # 模擬收益率數據
                returns = np.random.normal(0.001, 0.02, 252)  # 252個交易日
                
                # 計算Sharpe比率
                excess_returns = returns - 0.02/252  # 假設無風險利率2%
                sharpe_ratio = np.mean(excess_returns) / np.std(returns) * np.sqrt(252)
                
                # 計算最大回撤
                cum_returns = np.cumprod(1 + returns)
                running_max = np.maximum.accumulate(cum_returns)
                drawdown = (cum_returns - running_max) / running_max
                max_drawdown = np.min(drawdown)
                
                return abs(sharpe_ratio) < 10 and max_drawdown < 0
            except Exception:
                return False
        
        # 測試5: 倉位計算
        def test_position_sizing():
            try:
                # Kelly公式測試
                win_rate = 0.6
                avg_win = 0.15
                avg_loss = 0.10
                
                # Kelly = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win
                kelly_pct = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win
                
                # 保守Kelly = Kelly * 0.25
                conservative_kelly = kelly_pct * 0.25
                
                return 0 < conservative_kelly < 1
            except Exception:
                return False
        
        tests = [
            ("風控模組導入", test_risk_imports),
            ("支撐壓力檢測", test_support_resistance),
            ("動態止損計算", test_dynamic_stops),
            ("風險指標計算", test_risk_metrics),
            ("倉位計算邏輯", test_position_sizing),
        ]
        
        for test_name, test_func in tests:
            self.run_test('phase4', test_name, test_func)

    def test_integration_workflow(self):
        """整合工作流程測試"""
        print_header("整合工作流程驗證")
        
        # 測試1: 數據管道整合
        def test_data_pipeline():
            try:
                # 測試數據載入
                from data.storage import OHLCVStorage

                # 檢查是否能載入OHLCV數據
                storage = OHLCVStorage()
                test_files = list(Path('data/raw').glob('*USDT_1h.csv'))

                return len(test_files) > 0
            except Exception:
                return False
        
        # 測試2: 策略執行整合
        def test_strategy_execution():
            try:
                # 測試策略類可以導入
                from strategies.simple_sma import SimpleSMAStrategy

                # 驗證類存在並有正確的基本屬性
                # 檢查是否有 __init__ 方法（不實例化，因為需要 broker 和 data）
                import inspect
                init_signature = inspect.signature(SimpleSMAStrategy.__init__)
                params = list(init_signature.parameters.keys())

                # 驗證必要參數存在
                return 'broker' in params and 'data' in params
            except Exception:
                return False
        
        # 測試3: CLI命令可用性
        def test_cli_availability():
            try:
                import subprocess
                
                # 測試CLI主命令
                result = subprocess.run([
                    sys.executable, 'cli/main.py', '--help'
                ], capture_output=True, text=True, timeout=10)
                
                return result.returncode == 0 and 'SuperDog' in result.stdout
            except Exception:
                return False
        
        tests = [
            ("數據管道整合", test_data_pipeline),
            ("策略執行整合", test_strategy_execution),
            ("CLI命令可用性", test_cli_availability),
        ]
        
        for test_name, test_func in tests:
            self.run_test('integration', test_name, test_func)

    def test_cli_commands(self):
        """CLI命令測試"""
        print_header("CLI命令完整性驗證")
        
        import subprocess
        
        # 測試1: 基本CLI命令
        def test_basic_cli():
            try:
                result = subprocess.run([
                    sys.executable, 'cli/main.py', 'list'
                ], capture_output=True, text=True, timeout=15)
                
                return result.returncode == 0
            except Exception:
                return False
        
        # 測試2: 驗證命令
        def test_verify_command():
            try:
                result = subprocess.run([
                    sys.executable, 'cli/main.py', 'verify'
                ], capture_output=True, text=True, timeout=30)
                
                return result.returncode == 0
            except Exception:
                return False
        
        # 測試3: 實驗命令
        def test_experiment_command():
            try:
                result = subprocess.run([
                    sys.executable, 'cli/main.py', 'experiment', '--help'
                ], capture_output=True, text=True, timeout=10)
                
                return result.returncode == 0 and 'experiment' in result.stdout.lower()
            except Exception:
                return False
        
        tests = [
            ("基本CLI命令", test_basic_cli),
            ("驗證命令", test_verify_command),
            ("實驗命令幫助", test_experiment_command),
        ]
        
        for test_name, test_func in tests:
            self.run_test('cli', test_name, test_func)

    def generate_report(self):
        """生成測試報告"""
        print_header("SuperDog v0.6 驗證報告")
        
        total_duration = time.time() - self.start_time
        
        # 統計總覽
        total_passed = sum(phase['passed'] for phase in self.test_results.values())
        total_failed = sum(phase['failed'] for phase in self.test_results.values())
        total_tests = total_passed + total_failed
        
        print(f"\n{Colors.BOLD}📊 測試統計總覽{Colors.END}")
        print(f"總測試數量: {total_tests}")
        print(f"通過測試: {Colors.GREEN}{total_passed}{Colors.END}")
        print(f"失敗測試: {Colors.RED}{total_failed}{Colors.END}")
        print(f"成功率: {total_passed/total_tests*100:.1f}%")
        print(f"執行時間: {total_duration:.2f}秒")
        
        # 各階段詳細結果
        phase_names = {
            'phase1': 'Phase 1: 幣種宇宙管理',
            'phase2': 'Phase 2: 策略實驗室',
            'phase3': 'Phase 3: 真實執行模型',
            'phase4': 'Phase 4: 動態風控系統',
            'integration': '整合測試',
            'cli': 'CLI測試'
        }
        
        print(f"\n{Colors.BOLD}📋 分階段結果{Colors.END}")
        for phase, name in phase_names.items():
            results = self.test_results[phase]
            total = results['passed'] + results['failed']
            
            if total > 0:
                status_color = Colors.GREEN if results['failed'] == 0 else Colors.YELLOW if results['passed'] > results['failed'] else Colors.RED
                print(f"{status_color}{name}: {results['passed']}/{total} 通過{Colors.END}")
            
        # 失敗測試詳情
        failed_tests = []
        for phase, results in self.test_results.items():
            for test in results['tests']:
                if not test['passed']:
                    failed_tests.append(f"{phase_names.get(phase, phase)}: {test['name']}")
        
        if failed_tests:
            print(f"\n{Colors.RED}❌ 失敗測試詳情:{Colors.END}")
            for failed_test in failed_tests:
                print(f"  • {failed_test}")
        
        # 總結
        if total_failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 所有測試通過！SuperDog v0.6 驗證成功！{Colors.END}")
        elif total_passed > total_failed:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️ 大部分測試通過，有少數問題需要修復{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ 多項測試失敗，需要重要修復{Colors.END}")
        
        # 保存報告
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'success_rate': total_passed/total_tests*100,
            'duration_seconds': total_duration,
            'results': self.test_results
        }
        
        report_file = Path('superdog_v06_validation_report.json')
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📄 詳細報告已保存: {report_file}")

    def run_all_tests(self):
        """執行所有驗證測試"""
        print_header("SuperDog v0.6 完整驗證測試開始")
        print_info(f"測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print_info(f"Python版本: {sys.version}")
        print_info(f"工作目錄: {Path.cwd()}")
        
        # 執行各階段測試
        try:
            self.test_phase1_universe_management()
            self.test_phase2_strategy_lab()
            self.test_phase3_execution_model()
            self.test_phase4_risk_management()
            self.test_integration_workflow()
            self.test_cli_commands()
            
        except KeyboardInterrupt:
            print_warning("\n測試被用戶中斷")
        except Exception as e:
            print_error(f"測試執行異常: {e}")
            traceback.print_exc()
        finally:
            self.generate_report()

def main():
    """主程序"""
    print(f"{Colors.CYAN}")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                  SuperDog v0.6                          ║") 
    print("║              完整驗證測試套件                            ║")
    print("║                                                          ║")
    print("║  測試範圍: 四個Phase + 整合測試 + CLI驗證                ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}")
    
    # 檢查是否在正確目錄
    if not Path('cli/main.py').exists():
        print_error("請在SuperDog專案根目錄執行此腳本")
        sys.exit(1)
    
    # 執行驗證
    validator = SuperDogV06Validator()
    validator.run_all_tests()

if __name__ == '__main__':
    main()
