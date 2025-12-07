"""
SuperDog v0.6 Phase 4: Risk Management System Tests

測試動態風控系統的所有核心功能

Version: v0.6.0-phase4
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from risk_management import (  # Support/Resistance; Dynamic Stops; Risk Calculator; Position Sizer
    DynamicStopManager,
    PositionSizer,
    RiskCalculator,
    SizingMethod,
    SRType,
    StopLossType,
    SupportResistanceDetector,
    TakeProfitType,
    calculate_fixed_risk_size,
    calculate_kelly_size,
    calculate_portfolio_risk,
    create_atr_stops,
    create_resistance_stops,
    detect_support_resistance,
)

# ===== Fixtures =====


@pytest.fixture
def sample_ohlcv():
    """生成樣本 OHLCV 數據"""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="1h")

    # 生成價格數據（帶趨勢和波動）
    np.random.seed(42)
    base_price = 50000
    trend = np.linspace(0, 2000, 200)
    noise = np.random.randn(200) * 200

    close = base_price + trend + noise
    high = close + np.abs(np.random.randn(200) * 150)
    low = close - np.abs(np.random.randn(200) * 150)
    open_ = close + np.random.randn(200) * 100
    volume = np.random.uniform(100, 1000, 200)

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=dates
    )


@pytest.fixture
def sample_returns():
    """生成樣本收益率數據"""
    np.random.seed(42)
    # 生成正態分佈收益率（略微正偏）
    returns = np.random.normal(0.001, 0.02, 252)  # 一年的交易日
    return pd.Series(returns)


# ===== Support/Resistance Tests =====


def test_sr_detector_basic(sample_ohlcv):
    """測試基本支撐壓力檢測"""
    detector = SupportResistanceDetector()
    levels = detector.detect(sample_ohlcv)

    assert isinstance(levels, list)
    assert len(levels) > 0

    for level in levels:
        assert level.price > 0
        assert level.sr_type in [SRType.SUPPORT, SRType.RESISTANCE]
        assert 0 <= level.strength <= 1
        assert level.touches >= detector.min_touches


def test_sr_detector_with_volume(sample_ohlcv):
    """測試帶成交量的支撐壓力檢測"""
    detector = SupportResistanceDetector()
    levels = detector.detect(sample_ohlcv, include_volume=True)

    assert len(levels) > 0
    # 檢查是否有成交量得分
    assert any(level.volume_score > 0 for level in levels)


def test_sr_get_nearest_support(sample_ohlcv):
    """測試獲取最近支撐位"""
    detector = SupportResistanceDetector()
    levels = detector.detect(sample_ohlcv)

    current_price = sample_ohlcv["close"].iloc[-1]
    nearest_support = detector.get_nearest_support(current_price, levels)

    if nearest_support:
        assert nearest_support.price < current_price
        assert nearest_support.sr_type in [SRType.SUPPORT, SRType.BOTH]


def test_sr_get_nearest_resistance(sample_ohlcv):
    """測試獲取最近壓力位"""
    detector = SupportResistanceDetector()
    levels = detector.detect(sample_ohlcv)

    current_price = sample_ohlcv["close"].iloc[-1]
    nearest_resistance = detector.get_nearest_resistance(current_price, levels)

    if nearest_resistance:
        assert nearest_resistance.price > current_price
        assert nearest_resistance.sr_type in [SRType.RESISTANCE, SRType.BOTH]


def test_detect_support_resistance_convenience(sample_ohlcv):
    """測試便捷函數"""
    levels = detect_support_resistance(sample_ohlcv)
    assert isinstance(levels, list)


# ===== Dynamic Stops Tests =====


def test_dynamic_stops_atr(sample_ohlcv):
    """測試 ATR 動態止損"""
    manager = DynamicStopManager()

    entry_price = 50000
    current_price = 51000

    update = manager.update_stops(
        entry_price=entry_price,
        current_price=current_price,
        position_side="long",
        ohlcv=sample_ohlcv,
        stop_loss_type=StopLossType.ATR,
    )

    assert update.new_stop_loss is not None
    assert update.new_stop_loss < current_price
    assert update.new_take_profit is not None


def test_dynamic_stops_trailing(sample_ohlcv):
    """測試移動止損"""
    manager = DynamicStopManager(trailing_activation_pct=0.02, trailing_distance_pct=0.01)

    entry_price = 50000
    current_price = 51500  # +3% 盈利，應激活移動止損

    update = manager.update_stops(
        entry_price=entry_price,
        current_price=current_price,
        position_side="long",
        ohlcv=sample_ohlcv,
        stop_loss_type=StopLossType.TRAILING,
        current_stop_loss=49500,
    )

    # 移動止損應該上移
    assert update.new_stop_loss >= 49500


def test_dynamic_stops_exit_conditions(sample_ohlcv):
    """測試止損/止盈觸發"""
    manager = DynamicStopManager()

    entry_price = 50000
    current_price = 48000  # 價格下跌

    update = manager.update_stops(
        entry_price=entry_price,
        current_price=current_price,
        position_side="long",
        ohlcv=sample_ohlcv,
        stop_loss_type=StopLossType.ATR,
    )

    # 檢查是否應該平倉
    if update.should_exit:
        assert update.exit_reason != ""


def test_create_atr_stops():
    """測試 ATR 止損創建函數"""
    stops = create_atr_stops(
        entry_price=50000,
        position_side="long",
        atr_value=500,
        atr_multiplier=2.0,
        risk_reward_ratio=2.0,
    )

    assert "stop_loss" in stops
    assert "take_profit" in stops
    assert stops["stop_loss"] < 50000
    assert stops["take_profit"] > 50000


def test_create_resistance_stops():
    """測試支撐壓力止損創建函數"""
    stops = create_resistance_stops(
        entry_price=50000, position_side="long", support_level=49000, resistance_level=52000
    )

    assert stops["stop_loss"] == 49000
    assert stops["take_profit"] == 52000


# ===== Risk Calculator Tests =====


def test_risk_calculator_portfolio_metrics(sample_returns):
    """測試投資組合風險指標計算"""
    calculator = RiskCalculator()
    metrics = calculator.calculate_portfolio_risk(sample_returns)

    assert metrics.total_return != 0
    assert metrics.volatility > 0
    assert metrics.annualized_volatility > 0
    assert -5 <= metrics.sharpe_ratio <= 10  # 合理範圍
    assert -1 <= metrics.max_drawdown_pct <= 0


def test_risk_calculator_position_risk():
    """測試單筆持倉風險計算"""
    calculator = RiskCalculator()

    risk = calculator.calculate_position_risk(
        entry_price=50000, stop_loss=49000, position_size=0.1, account_balance=10000
    )

    assert risk.position_value == 5000  # 0.1 * 50000
    assert risk.risk_amount == 100  # 0.1 * (50000 - 49000)
    assert risk.risk_pct == 0.01  # 100 / 10000 = 1%


def test_risk_calculator_var(sample_returns):
    """測試 VaR 計算"""
    calculator = RiskCalculator()

    var_95 = calculator.calculate_var(sample_returns, confidence_level=0.95)
    var_99 = calculator.calculate_var(sample_returns, confidence_level=0.99)

    assert var_95 < 0  # VaR 應該是負數（損失）
    assert var_99 < var_95  # 99% VaR 應該更極端


def test_risk_calculator_cvar(sample_returns):
    """測試 CVaR 計算"""
    calculator = RiskCalculator()

    cvar_95 = calculator.calculate_cvar(sample_returns, confidence_level=0.95)
    var_95 = calculator.calculate_var(sample_returns, confidence_level=0.95)

    assert cvar_95 <= var_95  # CVaR 應該 <= VaR


def test_risk_calculator_correlation():
    """測試相關性計算"""
    calculator = RiskCalculator()

    # 生成兩個相關的收益率序列
    np.random.seed(42)
    btc_returns = pd.Series(np.random.normal(0.001, 0.02, 100))
    eth_returns = btc_returns * 0.8 + pd.Series(np.random.normal(0, 0.01, 100))

    returns_dict = {"BTC": btc_returns, "ETH": eth_returns}

    corr_matrix = calculator.calculate_correlation_matrix(returns_dict)

    assert corr_matrix.shape == (2, 2)
    assert corr_matrix.loc["BTC", "BTC"] == 1.0
    assert 0 <= corr_matrix.loc["BTC", "ETH"] <= 1.0


def test_risk_calculator_beta(sample_returns):
    """測試 Beta 計算"""
    calculator = RiskCalculator()

    # 生成市場收益率
    np.random.seed(42)
    market_returns = pd.Series(np.random.normal(0.001, 0.015, len(sample_returns)))

    beta = calculator.calculate_beta(sample_returns, market_returns)

    assert isinstance(beta, float)


def test_calculate_portfolio_risk_convenience(sample_returns):
    """測試便捷函數"""
    metrics = calculate_portfolio_risk(sample_returns)
    assert metrics.sharpe_ratio != 0


# ===== Position Sizer Tests =====


def test_position_sizer_fixed_risk():
    """測試固定風險倉位計算"""
    sizer = PositionSizer(default_risk_pct=0.02)

    size = sizer.calculate_position_size(
        account_balance=10000, entry_price=50000, stop_loss=49000, method=SizingMethod.FIXED_RISK
    )

    # 風險 2% = $200
    # 止損距離 = $1000
    # 倉位 = 200 / 1000 = 0.2 BTC
    assert abs(size.position_size - 0.2) < 0.01
    assert abs(size.risk_pct - 0.02) < 0.001


def test_position_sizer_kelly():
    """測試 Kelly Criterion 倉位計算"""
    sizer = PositionSizer(kelly_fraction=0.25)

    size = sizer.calculate_position_size(
        account_balance=10000,
        entry_price=50000,
        stop_loss=49000,
        method=SizingMethod.KELLY,
        win_rate=0.6,
        avg_win=0.04,
        avg_loss=0.02,
    )

    assert size.position_size > 0
    assert size.sizing_method == SizingMethod.KELLY


def test_position_sizer_volatility_adjusted():
    """測試波動率調整倉位"""
    sizer = PositionSizer()

    # 高波動 -> 小倉位
    high_vol_size = sizer.calculate_position_size(
        account_balance=10000,
        entry_price=50000,
        stop_loss=49000,
        method=SizingMethod.VOLATILITY_ADJUSTED,
        volatility=0.04,  # 高波動
        risk_pct=0.02,
    )

    # 低波動 -> 大倉位
    low_vol_size = sizer.calculate_position_size(
        account_balance=10000,
        entry_price=50000,
        stop_loss=49000,
        method=SizingMethod.VOLATILITY_ADJUSTED,
        volatility=0.01,  # 低波動
        risk_pct=0.02,
    )

    assert low_vol_size.position_size > high_vol_size.position_size


def test_position_sizer_max_position_limit():
    """測試最大倉位限制"""
    sizer = PositionSizer(max_position_pct=0.3)

    size = sizer.calculate_position_size(
        account_balance=10000,
        entry_price=50000,
        stop_loss=48000,  # 大止損距離
        method=SizingMethod.FIXED_RISK,
        risk_pct=0.1,  # 高風險
    )

    # 應該被限制在最大倉位
    assert size.position_value <= 10000 * 0.3


def test_position_sizer_allocate_capital():
    """測試資金分配"""
    sizer = PositionSizer()

    strategies = [
        {"name": "Strategy A", "weight": 0.6, "sharpe": 1.5},
        {"name": "Strategy B", "weight": 0.4, "sharpe": 1.2},
    ]

    # 測試加權分配
    allocation = sizer.allocate_capital(100000, strategies, method="weighted")

    assert len(allocation) == 2
    assert abs(sum(allocation.values()) - 100000) < 0.01
    assert allocation["Strategy A"] == 60000
    assert allocation["Strategy B"] == 40000

    # 測試平均分配
    equal_allocation = sizer.allocate_capital(100000, strategies, method="equal")
    assert equal_allocation["Strategy A"] == equal_allocation["Strategy B"] == 50000


def test_position_sizer_optimal_leverage():
    """測試最優槓桿計算"""
    sizer = PositionSizer(max_leverage=10)

    optimal = sizer.calculate_optimal_leverage(
        expected_return=0.15, volatility=0.30, max_drawdown_tolerance=0.20
    )

    assert 1 <= optimal <= 10


def test_calculate_kelly_size_convenience():
    """測試 Kelly 便捷函數"""
    kelly_pct = calculate_kelly_size(
        account_balance=10000, win_rate=0.6, avg_win=0.04, avg_loss=0.02, kelly_fraction=0.25
    )

    assert 0 <= kelly_pct <= 1


def test_calculate_fixed_risk_size_convenience():
    """測試固定風險便捷函數"""
    size = calculate_fixed_risk_size(
        account_balance=10000, entry_price=50000, stop_loss=49000, risk_pct=0.02
    )

    assert abs(size - 0.2) < 0.01


# ===== Integration Tests =====


def test_integrated_risk_workflow(sample_ohlcv):
    """測試完整風控流程"""
    # 1. 檢測支撐壓力位
    sr_detector = SupportResistanceDetector()
    levels = sr_detector.detect(sample_ohlcv)

    current_price = sample_ohlcv["close"].iloc[-1]
    support = sr_detector.get_nearest_support(current_price, levels)
    resistance = sr_detector.get_nearest_resistance(current_price, levels)

    # 2. 設置動態止損
    stop_manager = DynamicStopManager()

    if support and resistance:
        # 3. 計算倉位
        sizer = PositionSizer(default_risk_pct=0.02)

        position_size = sizer.calculate_position_size(
            account_balance=10000,
            entry_price=current_price,
            stop_loss=support.price,
            method=SizingMethod.FIXED_RISK,
        )

        # 4. 計算風險指標
        calculator = RiskCalculator()
        position_risk = calculator.calculate_position_risk(
            entry_price=current_price,
            stop_loss=support.price,
            position_size=position_size.position_size,
            account_balance=10000,
        )

        assert position_risk.risk_pct <= 0.02  # 風險不超過 2%


def test_module_imports():
    """測試模組導入"""
    from risk_management import (
        DynamicStopManager,
        PositionSizer,
        RiskCalculator,
        SupportResistanceDetector,
    )

    assert SupportResistanceDetector is not None
    assert DynamicStopManager is not None
    assert RiskCalculator is not None
    assert PositionSizer is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
