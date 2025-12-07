"""
Risk Calculator v0.6 Phase 4

風險指標計算器 - VaR、Sharpe、Sortino、最大回撤等

核心功能:
- 投資組合風險指標（VaR, CVaR, Sharpe, Sortino）
- 單筆交易風險評估
- 最大回撤分析
- 風險調整收益計算
- 相關性分析

Version: v0.6.0-phase4
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats


@dataclass
class RiskMetrics:
    """風險指標結果

    Example:
        >>> metrics = calculator.calculate_portfolio_risk(returns)
        >>> print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        >>> print(f"Max Drawdown: {metrics.max_drawdown_pct:.2%}")
    """

    # 收益指標
    total_return: float = 0.0
    annualized_return: float = 0.0
    avg_daily_return: float = 0.0

    # 波動性指標
    volatility: float = 0.0
    annualized_volatility: float = 0.0
    downside_volatility: float = 0.0

    # 風險調整收益
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # 風險指標
    var_95: float = 0.0  # 95% VaR
    var_99: float = 0.0  # 99% VaR
    cvar_95: float = 0.0  # 95% CVaR (Expected Shortfall)
    cvar_99: float = 0.0  # 99% CVaR

    # 回撤指標
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration: int = 0

    # 勝率指標
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    # 其他
    skewness: float = 0.0
    kurtosis: float = 0.0


@dataclass
class PositionRisk:
    """單筆持倉風險評估"""
    position_value: float
    risk_amount: float  # 風險金額
    risk_pct: float  # 風險百分比
    position_size_pct: float  # 倉位占比
    leverage: float
    stop_loss_distance: float  # 止損距離
    liquidation_distance: Optional[float] = None  # 強平距離
    correlation_risk: float = 0.0  # 相關性風險


class RiskCalculator:
    """風險計算器

    提供完整的風險分析功能

    Example:
        >>> calculator = RiskCalculator()
        >>> metrics = calculator.calculate_portfolio_risk(returns_df)
        >>> print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
        >>> print(f"Max DD: {metrics.max_drawdown_pct:.2%}")
    """

    def __init__(
        self,
        risk_free_rate: float = 0.02,  # 無風險利率（年化）
        trading_days: int = 365  # 每年交易日數
    ):
        """初始化風險計算器

        Args:
            risk_free_rate: 無風險利率（年化）
            trading_days: 每年交易日數
        """
        self.risk_free_rate = risk_free_rate
        self.trading_days = trading_days

    def calculate_portfolio_risk(
        self,
        returns: pd.Series,
        equity_curve: Optional[pd.Series] = None
    ) -> RiskMetrics:
        """計算投資組合風險指標

        Args:
            returns: 收益率序列（日收益率）
            equity_curve: 權益曲線（可選）

        Returns:
            RiskMetrics: 風險指標

        Example:
            >>> returns = pd.Series([0.01, -0.02, 0.015, ...])
            >>> metrics = calculator.calculate_portfolio_risk(returns)
        """
        if len(returns) == 0:
            return RiskMetrics()

        # 基本收益指標
        total_return = (1 + returns).prod() - 1
        avg_daily_return = returns.mean()
        annualized_return = (1 + avg_daily_return) ** self.trading_days - 1

        # 波動性
        volatility = returns.std()
        annualized_volatility = volatility * np.sqrt(self.trading_days)

        # 下行波動性（只計算負收益）
        negative_returns = returns[returns < 0]
        downside_volatility = negative_returns.std() if len(negative_returns) > 0 else 0

        # Sharpe Ratio
        daily_rf_rate = (1 + self.risk_free_rate) ** (1 / self.trading_days) - 1
        excess_returns = returns - daily_rf_rate
        sharpe_ratio = (
            excess_returns.mean() / excess_returns.std() * np.sqrt(self.trading_days)
            if excess_returns.std() > 0 else 0
        )

        # Sortino Ratio
        sortino_ratio = (
            excess_returns.mean() / downside_volatility * np.sqrt(self.trading_days)
            if downside_volatility > 0 else 0
        )

        # VaR 和 CVaR
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else var_95
        cvar_99 = returns[returns <= var_99].mean() if len(returns[returns <= var_99]) > 0 else var_99

        # 回撤分析
        if equity_curve is not None:
            dd_metrics = self._calculate_drawdown_metrics(equity_curve)
        else:
            # 從收益率構建權益曲線
            equity = (1 + returns).cumprod()
            dd_metrics = self._calculate_drawdown_metrics(equity)

        # Calmar Ratio
        calmar_ratio = (
            annualized_return / abs(dd_metrics['max_drawdown_pct'])
            if dd_metrics['max_drawdown_pct'] != 0 else 0
        )

        # 勝率分析
        win_rate_metrics = self._calculate_win_rate_metrics(returns)

        # 偏度和峰度
        skewness = returns.skew()
        kurtosis = returns.kurtosis()

        return RiskMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            avg_daily_return=avg_daily_return,
            volatility=volatility,
            annualized_volatility=annualized_volatility,
            downside_volatility=downside_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            max_drawdown=dd_metrics['max_drawdown'],
            max_drawdown_pct=dd_metrics['max_drawdown_pct'],
            avg_drawdown=dd_metrics['avg_drawdown'],
            max_drawdown_duration=dd_metrics['max_drawdown_duration'],
            win_rate=win_rate_metrics['win_rate'],
            profit_factor=win_rate_metrics['profit_factor'],
            avg_win=win_rate_metrics['avg_win'],
            avg_loss=win_rate_metrics['avg_loss'],
            skewness=skewness,
            kurtosis=kurtosis
        )

    def _calculate_drawdown_metrics(self, equity_curve: pd.Series) -> Dict:
        """計算回撤指標

        Args:
            equity_curve: 權益曲線

        Returns:
            Dict: 回撤指標
        """
        # 計算累計最高點
        cumulative_max = equity_curve.expanding().max()

        # 計算回撤
        drawdown = equity_curve - cumulative_max
        drawdown_pct = drawdown / cumulative_max

        # 最大回撤
        max_drawdown = drawdown.min()
        max_drawdown_pct = drawdown_pct.min()

        # 平均回撤
        avg_drawdown = drawdown[drawdown < 0].mean() if len(drawdown[drawdown < 0]) > 0 else 0

        # 最大回撤持續時間
        max_dd_duration = self._calculate_max_drawdown_duration(drawdown)

        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_drawdown': avg_drawdown,
            'max_drawdown_duration': max_dd_duration
        }

    def _calculate_max_drawdown_duration(self, drawdown: pd.Series) -> int:
        """計算最大回撤持續時間

        Args:
            drawdown: 回撤序列

        Returns:
            int: 最大持續天數
        """
        in_drawdown = drawdown < 0

        if not in_drawdown.any():
            return 0

        # 找出回撤區間
        drawdown_periods = []
        start_idx = None

        for i, is_dd in enumerate(in_drawdown):
            if is_dd and start_idx is None:
                start_idx = i
            elif not is_dd and start_idx is not None:
                drawdown_periods.append(i - start_idx)
                start_idx = None

        # 如果最後還在回撤中
        if start_idx is not None:
            drawdown_periods.append(len(in_drawdown) - start_idx)

        return max(drawdown_periods) if drawdown_periods else 0

    def _calculate_win_rate_metrics(self, returns: pd.Series) -> Dict:
        """計算勝率相關指標

        Args:
            returns: 收益率序列

        Returns:
            Dict: 勝率指標
        """
        wins = returns[returns > 0]
        losses = returns[returns < 0]

        win_rate = len(wins) / len(returns) if len(returns) > 0 else 0
        avg_win = wins.mean() if len(wins) > 0 else 0
        avg_loss = abs(losses.mean()) if len(losses) > 0 else 0

        # Profit Factor = 總盈利 / 總虧損
        total_wins = wins.sum() if len(wins) > 0 else 0
        total_losses = abs(losses.sum()) if len(losses) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }

    def calculate_position_risk(
        self,
        entry_price: float,
        stop_loss: float,
        position_size: float,
        account_balance: float,
        current_price: Optional[float] = None,
        leverage: float = 1.0,
        liquidation_price: Optional[float] = None
    ) -> PositionRisk:
        """計算單筆持倉風險

        Args:
            entry_price: 入場價格
            stop_loss: 止損價格
            position_size: 持倉數量
            account_balance: 賬戶餘額
            current_price: 當前價格（可選，默認為入場價）
            leverage: 槓桿倍數
            liquidation_price: 強平價格（可選）

        Returns:
            PositionRisk: 持倉風險評估

        Example:
            >>> risk = calculator.calculate_position_risk(
            ...     entry_price=50000,
            ...     stop_loss=49000,
            ...     position_size=0.1,
            ...     account_balance=10000
            ... )
            >>> print(f"Risk: {risk.risk_pct:.2%}")
        """
        current_price = current_price or entry_price

        # 計算持倉價值
        position_value = position_size * current_price

        # 計算風險金額（到止損的損失）
        risk_amount = abs(entry_price - stop_loss) * position_size

        # 風險百分比
        risk_pct = risk_amount / account_balance if account_balance > 0 else 0

        # 倉位占比
        position_size_pct = position_value / (account_balance * leverage) if account_balance > 0 else 0

        # 止損距離
        stop_loss_distance = abs(current_price - stop_loss) / current_price

        # 強平距離
        liquidation_distance = None
        if liquidation_price is not None:
            liquidation_distance = abs(current_price - liquidation_price) / current_price

        return PositionRisk(
            position_value=position_value,
            risk_amount=risk_amount,
            risk_pct=risk_pct,
            position_size_pct=position_size_pct,
            leverage=leverage,
            stop_loss_distance=stop_loss_distance,
            liquidation_distance=liquidation_distance
        )

    def calculate_var(
        self,
        returns: pd.Series,
        confidence_level: float = 0.95,
        method: str = 'historical'
    ) -> float:
        """計算 VaR (Value at Risk)

        Args:
            returns: 收益率序列
            confidence_level: 信心水平（0.95 或 0.99）
            method: 計算方法 ('historical', 'parametric', 'monte_carlo')

        Returns:
            float: VaR 值

        Example:
            >>> var = calculator.calculate_var(returns, confidence_level=0.95)
            >>> print(f"95% VaR: {var:.4f}")
        """
        if method == 'historical':
            # 歷史模擬法
            return np.percentile(returns, (1 - confidence_level) * 100)

        elif method == 'parametric':
            # 參數法（假設正態分佈）
            mean = returns.mean()
            std = returns.std()
            z_score = stats.norm.ppf(1 - confidence_level)
            return mean + z_score * std

        elif method == 'monte_carlo':
            # 蒙特卡羅模擬
            mean = returns.mean()
            std = returns.std()
            simulated_returns = np.random.normal(mean, std, 10000)
            return np.percentile(simulated_returns, (1 - confidence_level) * 100)

        else:
            raise ValueError(f"Unknown method: {method}")

    def calculate_cvar(
        self,
        returns: pd.Series,
        confidence_level: float = 0.95
    ) -> float:
        """計算 CVaR (Conditional VaR / Expected Shortfall)

        Args:
            returns: 收益率序列
            confidence_level: 信心水平

        Returns:
            float: CVaR 值
        """
        var = self.calculate_var(returns, confidence_level, method='historical')
        # CVaR 是超過 VaR 的損失的期望值
        tail_losses = returns[returns <= var]
        return tail_losses.mean() if len(tail_losses) > 0 else var

    def calculate_correlation_matrix(
        self,
        returns_dict: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """計算多資產相關性矩陣

        Args:
            returns_dict: 資產收益率字典 {symbol: returns}

        Returns:
            pd.DataFrame: 相關性矩陣

        Example:
            >>> returns_dict = {
            ...     'BTC': btc_returns,
            ...     'ETH': eth_returns
            ... }
            >>> corr_matrix = calculator.calculate_correlation_matrix(returns_dict)
        """
        # 將字典轉換為 DataFrame
        df = pd.DataFrame(returns_dict)
        return df.corr()

    def calculate_portfolio_volatility(
        self,
        weights: Dict[str, float],
        returns_dict: Dict[str, pd.Series]
    ) -> float:
        """計算投資組合波動率

        考慮資產間的相關性

        Args:
            weights: 資產權重 {symbol: weight}
            returns_dict: 資產收益率 {symbol: returns}

        Returns:
            float: 投資組合波動率
        """
        # 構建協方差矩陣
        df = pd.DataFrame(returns_dict)
        cov_matrix = df.cov()

        # 權重向量
        weight_vector = np.array([weights.get(symbol, 0) for symbol in df.columns])

        # 組合方差
        portfolio_variance = np.dot(weight_vector, np.dot(cov_matrix, weight_vector))

        return np.sqrt(portfolio_variance)

    def calculate_beta(
        self,
        asset_returns: pd.Series,
        market_returns: pd.Series
    ) -> float:
        """計算 Beta 係數

        Args:
            asset_returns: 資產收益率
            market_returns: 市場收益率

        Returns:
            float: Beta 值
        """
        covariance = asset_returns.cov(market_returns)
        market_variance = market_returns.var()

        return covariance / market_variance if market_variance > 0 else 0

    def calculate_information_ratio(
        self,
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """計算信息比率 (Information Ratio)

        衡量相對於基準的超額收益

        Args:
            strategy_returns: 策略收益率
            benchmark_returns: 基準收益率

        Returns:
            float: 信息比率
        """
        excess_returns = strategy_returns - benchmark_returns
        tracking_error = excess_returns.std()

        return excess_returns.mean() / tracking_error if tracking_error > 0 else 0


# ===== 便捷函數 =====

def calculate_position_risk(
    entry_price: float,
    stop_loss: float,
    position_size: float,
    account_balance: float,
    **kwargs
) -> PositionRisk:
    """快速計算持倉風險

    Args:
        entry_price: 入場價格
        stop_loss: 止損價格
        position_size: 持倉數量
        account_balance: 賬戶餘額
        **kwargs: 其他參數傳遞給 RiskCalculator

    Returns:
        PositionRisk: 風險評估結果

    Example:
        >>> risk = calculate_position_risk(
        ...     entry_price=50000,
        ...     stop_loss=49000,
        ...     position_size=0.1,
        ...     account_balance=10000
        ... )
    """
    calculator = RiskCalculator()
    return calculator.calculate_position_risk(
        entry_price, stop_loss, position_size, account_balance, **kwargs
    )


def calculate_portfolio_risk(
    returns: pd.Series,
    equity_curve: Optional[pd.Series] = None,
    **kwargs
) -> RiskMetrics:
    """快速計算投資組合風險

    Args:
        returns: 收益率序列
        equity_curve: 權益曲線（可選）
        **kwargs: 其他參數傳遞給 RiskCalculator

    Returns:
        RiskMetrics: 風險指標

    Example:
        >>> metrics = calculate_portfolio_risk(returns)
        >>> print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
    """
    calculator = RiskCalculator(**kwargs)
    return calculator.calculate_portfolio_risk(returns, equity_curve)
