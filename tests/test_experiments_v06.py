"""
Unit Tests for SuperDog v0.6 Phase 2: Strategy Lab System

測試覆蓋:
- ExperimentConfig 和數據結構
- ExperimentRunner 批量執行
- ParameterOptimizer 參數優化
- ResultAnalyzer 結果分析

Test Coverage Target: >85%
Test Count Target: 15+

Author: SuperDog Development Team
Version: v0.6.0-phase2
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from execution_engine import (
    AnalysisReport,
    ExperimentResult,
    ExperimentRun,
    ExperimentRunner,
    ExperimentStatus,
    OptimizationConfig,
    OptimizationMode,
    ParameterExpander,
    ParameterOptimizer,
    ParameterRange,
    ResultAnalyzer,
    create_experiment_config,
    load_experiment_config,
)


class TestParameterRange(unittest.TestCase):
    """測試 ParameterRange 類"""

    def test_expand_list_values(self):
        """測試列表值展開"""
        param = ParameterRange(name="period", values=[10, 20, 30, 50])
        result = param.expand()

        self.assertEqual(result, [10, 20, 30, 50])
        self.assertEqual(len(result), 4)

    def test_expand_range_with_step(self):
        """測試範圍步長展開"""
        param = ParameterRange(name="period", start=10, stop=50, step=10)
        result = param.expand()

        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], 10)
        self.assertEqual(result[-1], 50)

    def test_expand_range_with_num(self):
        """測試範圍數量展開"""
        param = ParameterRange(name="threshold", start=0.1, stop=1.0, num=10)
        result = param.expand()

        self.assertEqual(len(result), 10)
        self.assertAlmostEqual(result[0], 0.1, places=2)
        self.assertAlmostEqual(result[-1], 1.0, places=2)

    def test_expand_log_scale(self):
        """測試對數刻度展開"""
        param = ParameterRange(name="learning_rate", start=0.001, stop=0.1, num=5, log_scale=True)
        result = param.expand()

        self.assertEqual(len(result), 5)
        # 驗證對數分布
        self.assertAlmostEqual(result[0], 0.001, places=3)
        self.assertAlmostEqual(result[-1], 0.1, places=3)

    def test_invalid_parameter_range(self):
        """測試無效參數範圍"""
        param = ParameterRange(name="invalid")

        with self.assertRaises(ValueError):
            param.expand()


class TestExperimentConfig(unittest.TestCase):
    """測試 ExperimentConfig 類"""

    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """測試後清理"""
        shutil.rmtree(self.temp_dir)

    def test_create_config(self):
        """測試創建配置"""
        config = create_experiment_config(
            name="Test_Experiment",
            strategy="simple_sma",
            symbols=["BTCUSDT", "ETHUSDT"],
            parameters={
                "sma_short": [5, 10, 15],
                "sma_long": {"start": 20, "stop": 100, "step": 20},
            },
            timeframe="1h",
        )

        self.assertEqual(config.name, "Test_Experiment")
        self.assertEqual(config.strategy, "simple_sma")
        self.assertEqual(len(config.symbols), 2)
        self.assertIn("sma_short", config.parameters)
        self.assertIn("sma_long", config.parameters)

    def test_config_to_dict(self):
        """測試配置轉字典"""
        config = create_experiment_config(
            name="Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10, 20]},
            timeframe="1h",
        )

        config_dict = config.to_dict()

        self.assertIsInstance(config_dict, dict)
        self.assertEqual(config_dict["name"], "Test")
        self.assertEqual(config_dict["expansion_mode"], "grid")

    def test_config_save_and_load_yaml(self):
        """測試 YAML 保存和加載"""
        config = create_experiment_config(
            name="YAML_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10, 20, 30]},
            timeframe="1h",
        )

        # 保存
        yaml_path = f"{self.temp_dir}/test_config.yaml"
        config.save(yaml_path)

        # 加載
        loaded_config = load_experiment_config(yaml_path)

        self.assertEqual(loaded_config.name, "YAML_Test")
        self.assertEqual(loaded_config.strategy, "simple_sma")
        self.assertEqual(len(loaded_config.symbols), 1)

    def test_config_save_and_load_json(self):
        """測試 JSON 保存和加載"""
        config = create_experiment_config(
            name="JSON_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10, 20]},
            timeframe="1h",
        )

        # 保存
        json_path = f"{self.temp_dir}/test_config.json"
        config.save(json_path)

        # 加載
        loaded_config = load_experiment_config(json_path)

        self.assertEqual(loaded_config.name, "JSON_Test")

    def test_experiment_id_generation(self):
        """測試實驗ID生成"""
        config1 = create_experiment_config(
            name="Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10]},
            timeframe="1h",
        )

        config2 = create_experiment_config(
            name="Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10]},
            timeframe="1h",
        )

        # 相同配置應該生成相同ID
        self.assertEqual(config1.get_experiment_id(), config2.get_experiment_id())

        # 不同配置應該生成不同ID
        config3 = create_experiment_config(
            name="Test",
            strategy="simple_sma",
            symbols=["ETHUSDT"],  # 不同幣種
            parameters={"period": [10]},
            timeframe="1h",
        )
        self.assertNotEqual(config1.get_experiment_id(), config3.get_experiment_id())


class TestParameterExpander(unittest.TestCase):
    """測試 ParameterExpander 類"""

    def test_expand_combinations_grid(self):
        """測試網格組合展開"""
        config = create_experiment_config(
            name="Grid_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"param1": [1, 2, 3], "param2": [10, 20]},
            timeframe="1h",
            expansion_mode="grid",
        )

        expander = ParameterExpander(config)
        combinations = expander.expand_combinations()

        # 應該有 3 * 2 = 6 種組合
        self.assertEqual(len(combinations), 6)

    def test_expand_tasks(self):
        """測試任務展開"""
        config = create_experiment_config(
            name="Task_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT", "ETHUSDT"],
            parameters={"param1": [1, 2], "param2": [10, 20]},
            timeframe="1h",
        )

        expander = ParameterExpander(config)
        tasks = expander.expand_tasks()

        # 應該有 2 symbols * 2 * 2 = 8 個任務
        self.assertEqual(len(tasks), 8)

        # 驗證任務結構
        task = tasks[0]
        self.assertIn("symbol", task)
        self.assertIn("parameters", task)

    def test_max_combinations_limit(self):
        """測試最大組合數限制"""
        config = create_experiment_config(
            name="Limit_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={
                "param1": list(range(10)),
                "param2": list(range(10)),
                "param3": list(range(10)),
            },
            timeframe="1h",
            max_combinations=50,  # 限制最大組合數
        )

        expander = ParameterExpander(config)
        combinations = expander.expand_combinations()

        # 應該不超過限制
        self.assertLessEqual(len(combinations), 50)


class TestExperimentRunner(unittest.TestCase):
    """測試 ExperimentRunner 類"""

    def setUp(self):
        """測試前準備"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """測試後清理"""
        shutil.rmtree(self.temp_dir)

    def test_runner_initialization(self):
        """測試運行器初始化"""
        runner = ExperimentRunner(max_workers=4)

        self.assertEqual(runner.max_workers, 4)
        self.assertTrue(runner.retry_failed)

    def test_execute_single_run(self):
        """測試單個運行執行"""

        def mock_backtest(symbol, timeframe, params, config):
            return {
                "total_return": 0.15,
                "sharpe_ratio": 1.5,
                "max_drawdown": -0.10,
                "num_trades": 100,
                "win_rate": 0.6,
                "profit_factor": 2.0,
            }

        config = create_experiment_config(
            name="Single_Run_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10]},
            timeframe="1h",
        )

        runner = ExperimentRunner(max_workers=1)
        run = runner._execute_single_run(
            run_id="test_run_001",
            experiment_id="test_exp",
            symbol="BTCUSDT",
            parameters={"period": 10},
            config=config,
            backtest_func=mock_backtest,
        )

        self.assertEqual(run.status, ExperimentStatus.COMPLETED)
        self.assertIsNotNone(run.total_return)
        self.assertEqual(run.total_return, 0.15)
        self.assertEqual(run.sharpe_ratio, 1.5)

    def test_runner_with_failing_backtest(self):
        """測試失敗回測處理"""

        def failing_backtest(symbol, timeframe, params, config):
            raise ValueError("Mock backtest failure")

        config = create_experiment_config(
            name="Fail_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10]},
            timeframe="1h",
        )

        runner = ExperimentRunner(max_workers=1, retry_failed=False)
        run = runner._execute_single_run(
            run_id="test_run_fail",
            experiment_id="test_exp",
            symbol="BTCUSDT",
            parameters={"period": 10},
            config=config,
            backtest_func=failing_backtest,
        )

        self.assertEqual(run.status, ExperimentStatus.FAILED)
        self.assertIsNotNone(run.error_message)


class TestExperimentResult(unittest.TestCase):
    """測試 ExperimentResult 類"""

    def setUp(self):
        """創建測試數據"""
        self.config = create_experiment_config(
            name="Result_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10, 20, 30]},
            timeframe="1h",
        )

        # 創建模擬運行記錄
        self.runs = []
        for i, period in enumerate([10, 20, 30]):
            run = ExperimentRun(
                experiment_id="test_exp",
                run_id=f"run_{i:03d}",
                symbol="BTCUSDT",
                parameters={"period": period},
                status=ExperimentStatus.COMPLETED,
                total_return=0.1 + i * 0.05,
                sharpe_ratio=1.0 + i * 0.3,
                max_drawdown=-0.1,
                num_trades=100,
                win_rate=0.6,
                profit_factor=2.0,
            )
            self.runs.append(run)

    def test_get_best_run(self):
        """測試獲取最佳運行"""
        result = ExperimentResult(
            experiment_id="test_exp",
            config=self.config,
            runs=self.runs,
            total_runs=3,
            completed_runs=3,
            failed_runs=0,
        )

        best_run = result.get_best_run(metric="sharpe_ratio", ascending=False)

        self.assertIsNotNone(best_run)
        self.assertEqual(best_run.parameters["period"], 30)  # 最後一個應該最好

    def test_get_statistics(self):
        """測試統計信息"""
        result = ExperimentResult(
            experiment_id="test_exp",
            config=self.config,
            runs=self.runs,
            total_runs=3,
            completed_runs=3,
            failed_runs=0,
        )

        stats = result.get_statistics()

        self.assertIn("total_runs", stats)
        self.assertIn("avg_return", stats)
        self.assertIn("avg_sharpe", stats)
        self.assertEqual(stats["completed"], 3)


class TestResultAnalyzer(unittest.TestCase):
    """測試 ResultAnalyzer 類"""

    def setUp(self):
        """創建測試數據"""
        self.config = create_experiment_config(
            name="Analyzer_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT", "ETHUSDT"],
            parameters={"sma_short": [5, 10], "sma_long": [20, 40]},
            timeframe="1h",
        )

        # 創建多個運行記錄
        self.runs = []
        idx = 0
        for symbol in ["BTCUSDT", "ETHUSDT"]:
            for short in [5, 10]:
                for long in [20, 40]:
                    run = ExperimentRun(
                        experiment_id="test_exp",
                        run_id=f"run_{idx:03d}",
                        symbol=symbol,
                        parameters={"sma_short": short, "sma_long": long},
                        status=ExperimentStatus.COMPLETED,
                        total_return=np.random.uniform(-0.1, 0.3),
                        sharpe_ratio=np.random.uniform(0.5, 2.5),
                        max_drawdown=-np.random.uniform(0.05, 0.2),
                        num_trades=np.random.randint(50, 200),
                        win_rate=np.random.uniform(0.4, 0.7),
                        profit_factor=np.random.uniform(1.0, 3.0),
                    )
                    self.runs.append(run)
                    idx += 1

        self.result = ExperimentResult(
            experiment_id="test_exp",
            config=self.config,
            runs=self.runs,
            total_runs=len(self.runs),
            completed_runs=len(self.runs),
            failed_runs=0,
        )

    def test_analyzer_initialization(self):
        """測試分析器初始化"""
        analyzer = ResultAnalyzer(self.result)

        self.assertIsNotNone(analyzer.df)
        self.assertEqual(len(analyzer.df), len(self.runs))

    def test_generate_report(self):
        """測試生成報告"""
        analyzer = ResultAnalyzer(self.result)
        report = analyzer.generate_report(top_n=5)

        self.assertIsInstance(report, AnalysisReport)
        self.assertEqual(report.experiment_name, "Analyzer_Test")
        self.assertEqual(report.total_runs, len(self.runs))
        self.assertIsNotNone(report.best_run)
        self.assertEqual(len(report.top_runs), 5)

    def test_parameter_importance_analysis(self):
        """測試參數重要性分析"""
        analyzer = ResultAnalyzer(self.result)
        importance = analyzer.analyze_parameter_importance(metric="sharpe_ratio")

        self.assertIsInstance(importance, dict)
        self.assertIn("sma_short", importance)
        self.assertIn("sma_long", importance)

        # 歸一化後總和應該接近1
        total = sum(importance.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_parameter_correlations(self):
        """測試參數相關性分析"""
        analyzer = ResultAnalyzer(self.result)
        correlations = analyzer.analyze_parameter_correlations(metric="sharpe_ratio")

        self.assertIsInstance(correlations, dict)
        self.assertIn("sma_short", correlations)
        self.assertIn("sma_long", correlations)

        # 相關係數應該在 -1 到 1 之間
        for corr in correlations.values():
            self.assertGreaterEqual(corr, -1.0)
            self.assertLessEqual(corr, 1.0)

    def test_save_markdown_report(self):
        """測試保存 Markdown 報告"""
        temp_dir = tempfile.mkdtemp()
        try:
            analyzer = ResultAnalyzer(self.result)
            report = analyzer.generate_report()

            output_path = f"{temp_dir}/report.md"
            analyzer.save_report(report, output_path, format="markdown")

            # 驗證文件存在
            self.assertTrue(Path(output_path).exists())

            # 驗證內容
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("實驗分析報告", content)
                self.assertIn("Analyzer_Test", content)

        finally:
            shutil.rmtree(temp_dir)

    def test_save_json_report(self):
        """測試保存 JSON 報告"""
        temp_dir = tempfile.mkdtemp()
        try:
            analyzer = ResultAnalyzer(self.result)
            report = analyzer.generate_report()

            output_path = f"{temp_dir}/report.json"
            analyzer.save_report(report, output_path, format="json")

            # 驗證文件存在
            self.assertTrue(Path(output_path).exists())

            # 驗證 JSON 格式
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(data["experiment_name"], "Analyzer_Test")

        finally:
            shutil.rmtree(temp_dir)


class TestParameterOptimizer(unittest.TestCase):
    """測試 ParameterOptimizer 類"""

    def setUp(self):
        """測試前準備"""
        self.config = create_experiment_config(
            name="Optimizer_Test",
            strategy="simple_sma",
            symbols=["BTCUSDT"],
            parameters={"period": [10, 20, 30, 40, 50]},
            timeframe="1h",
        )

        # Mock 回測函數
        def mock_backtest(symbol, timeframe, params, config):
            # 簡單的模擬：period 越大，Sharpe 越高
            period = params.get("period", 10)
            sharpe = 0.5 + (period / 100.0) * 2.0

            return {
                "total_return": 0.1 + period * 0.002,
                "sharpe_ratio": sharpe,
                "max_drawdown": -0.1,
                "num_trades": 100,
                "win_rate": 0.6,
                "profit_factor": 2.0,
            }

        self.backtest_func = mock_backtest

    def test_optimizer_initialization(self):
        """測試優化器初始化"""
        optimizer = ParameterOptimizer(
            self.config, self.backtest_func, OptimizationConfig(mode=OptimizationMode.GRID)
        )

        self.assertIsNotNone(optimizer)
        self.assertEqual(optimizer.opt_config.mode, OptimizationMode.GRID)

    def test_grid_search_optimization(self):
        """測試網格搜索優化"""
        opt_config = OptimizationConfig(
            mode=OptimizationMode.GRID, metric="sharpe_ratio", maximize=True, max_workers=2
        )

        optimizer = ParameterOptimizer(self.config, self.backtest_func, opt_config)
        result = optimizer.optimize()

        self.assertIsNotNone(result.best_run)
        # Period 50 應該有最高的 Sharpe
        self.assertEqual(result.best_run.parameters["period"], 50)


# ===== Test Runner =====


def run_tests():
    """運行所有測試"""
    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類
    suite.addTests(loader.loadTestsFromTestCase(TestParameterRange))
    suite.addTests(loader.loadTestsFromTestCase(TestExperimentConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestParameterExpander))
    suite.addTests(loader.loadTestsFromTestCase(TestExperimentRunner))
    suite.addTests(loader.loadTestsFromTestCase(TestExperimentResult))
    suite.addTests(loader.loadTestsFromTestCase(TestResultAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestParameterOptimizer))

    # 運行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回結果
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("SuperDog v0.6 Phase 2: Strategy Lab System Tests")
    print("=" * 70)
    print()

    result = run_tests()

    print()
    print("=" * 70)
    print("測試摘要")
    print("=" * 70)
    print(f"總測試數: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"錯誤: {len(result.errors)}")
    print()

    if result.wasSuccessful():
        print("✅ 所有測試通過！")
        exit(0)
    else:
        print("❌ 部分測試失敗")
        exit(1)
