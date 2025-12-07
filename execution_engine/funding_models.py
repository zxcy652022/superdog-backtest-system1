"""
Funding Models v0.6 Phase 3

資金費用模型 - 永續合約Funding Rate計算與模擬

核心功能:
- Funding Rate 費用計算
- 8小時結算週期模擬
- 持倉期間總費用累計
- 多空方向費用差異

Version: v0.6.0-phase3
Design Reference: docs/specs/v0.6/superdog_v06_execution_model_spec.md
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


@dataclass
class FundingConfig:
    """資金費率配置

    定義 Funding Rate 的結算週期和時間點
    """

    # Funding 結算間隔（小時）
    funding_interval_hours: int = 8

    # Funding 時間點（UTC）
    funding_times_utc: List[int] = None

    # 是否啟用負費率（反向收費）
    enable_negative_funding: bool = True

    # 費率上下限
    max_funding_rate: float = 0.0075    # 0.75%
    min_funding_rate: float = -0.0075   # -0.75%

    def __post_init__(self):
        """初始化默認 Funding 時間"""
        if self.funding_times_utc is None:
            # Binance 標準: UTC 00:00, 08:00, 16:00
            self.funding_times_utc = [0, 8, 16]


@dataclass
class FundingEvent:
    """單次 Funding 事件記錄"""
    timestamp: datetime            # 結算時間
    funding_rate: float           # 費率
    position_value: float         # 持倉價值
    position_side: str            # 持倉方向 ('long'/'short')
    funding_cost: float           # 費用（正=支付，負=收取）
    mark_price: float             # 標記價格


@dataclass
class FundingResult:
    """Funding 費用計算結果"""
    total_funding_cost: float      # 總費用
    num_funding_events: int        # Funding 次數
    avg_funding_rate: float        # 平均費率
    funding_events: List[FundingEvent]  # 詳細事件列表


class FundingModel:
    """永續合約資金費用模型

    模擬真實的 Funding Rate 結算機制

    Example:
        >>> model = FundingModel()
        >>> result = model.calculate_funding_cost(
        ...     position_size=1.0,
        ...     position_side='long',
        ...     entry_time=datetime(2024, 1, 1, 10, 0),
        ...     exit_time=datetime(2024, 1, 2, 18, 0),
        ...     entry_price=50000,
        ...     funding_rate_data=funding_df
        ... )
        >>> result.total_funding_cost
        -15.2  # 持倉期間支付的總 Funding 費用
    """

    def __init__(self, config: Optional[FundingConfig] = None):
        """初始化 Funding 模型

        Args:
            config: Funding 配置（可選）
        """
        self.config = config or FundingConfig()

        # 統計信息
        self.total_funding_paid = 0.0
        self.total_funding_received = 0.0
        self.funding_event_count = 0

    def calculate_funding_cost(
        self,
        position_size: float,
        position_side: str,
        entry_time: datetime,
        exit_time: datetime,
        entry_price: float,
        funding_rate_data: Optional[pd.DataFrame] = None,
        use_simulated_rates: bool = False
    ) -> FundingResult:
        """計算持倉期間的總 Funding 費用

        Args:
            position_size: 持倉數量
            position_side: 持倉方向 ('long' or 'short')
            entry_time: 開倉時間
            exit_time: 平倉時間
            entry_price: 開倉價格
            funding_rate_data: 歷史 Funding Rate 數據（DataFrame）
            use_simulated_rates: 是否使用模擬費率

        Returns:
            FundingResult: Funding 費用計算結果

        Example:
            >>> model = FundingModel()
            >>> result = model.calculate_funding_cost(
            ...     position_size=1.0,
            ...     position_side='long',
            ...     entry_time=datetime(2024, 1, 1, 10, 0),
            ...     exit_time=datetime(2024, 1, 3, 10, 0),
            ...     entry_price=50000
            ... )
        """
        funding_events = []
        total_cost = 0.0

        # 獲取所有 Funding 時間點
        funding_times = self._get_funding_times_in_range(entry_time, exit_time)

        for funding_time in funding_times:
            # 獲取該時點的 Funding Rate
            if use_simulated_rates or funding_rate_data is None:
                funding_rate = self._simulate_funding_rate()
            else:
                funding_rate = self._get_funding_rate_at_time(
                    funding_rate_data, funding_time
                )

            # 計算標記價格（簡化：使用入場價格）
            mark_price = entry_price

            # 計算持倉價值
            position_value = position_size * mark_price

            # 計算 Funding 費用
            # Long: 支付正費率，收取負費率
            # Short: 收取正費率，支付負費率
            direction_multiplier = 1 if position_side == 'long' else -1
            funding_cost = position_value * funding_rate * direction_multiplier

            # 記錄事件
            event = FundingEvent(
                timestamp=funding_time,
                funding_rate=funding_rate,
                position_value=position_value,
                position_side=position_side,
                funding_cost=funding_cost,
                mark_price=mark_price
            )
            funding_events.append(event)
            total_cost += funding_cost

            # 更新統計
            if funding_cost > 0:
                self.total_funding_paid += funding_cost
            else:
                self.total_funding_received += abs(funding_cost)
            self.funding_event_count += 1

        # 計算平均費率
        avg_rate = (
            np.mean([e.funding_rate for e in funding_events])
            if funding_events else 0.0
        )

        return FundingResult(
            total_funding_cost=total_cost,
            num_funding_events=len(funding_events),
            avg_funding_rate=avg_rate,
            funding_events=funding_events
        )

    def _get_funding_times_in_range(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[datetime]:
        """獲取時間範圍內的所有 Funding 時間點

        Args:
            start_time: 開始時間
            end_time: 結束時間

        Returns:
            List[datetime]: Funding 時間點列表
        """
        funding_times = []
        current_time = self._get_next_funding_time(start_time)

        while current_time <= end_time:
            funding_times.append(current_time)
            current_time = self._get_next_funding_time(current_time + timedelta(minutes=1))

        return funding_times

    def _get_next_funding_time(self, current_time: datetime) -> datetime:
        """獲取下一個 Funding 時間點

        Args:
            current_time: 當前時間

        Returns:
            datetime: 下一個 Funding 時間
        """
        # 找到當天的所有 Funding 時間
        current_date = current_time.date()
        today_funding_times = [
            datetime.combine(current_date, datetime.min.time()).replace(hour=h)
            for h in self.config.funding_times_utc
        ]

        # 找到下一個時間點
        for ft in today_funding_times:
            if ft > current_time:
                return ft

        # 如果當天沒有了，返回明天第一個
        next_day = current_date + timedelta(days=1)
        return datetime.combine(
            next_day,
            datetime.min.time()
        ).replace(hour=self.config.funding_times_utc[0])

    def _get_funding_rate_at_time(
        self,
        funding_rate_data: pd.DataFrame,
        timestamp: datetime
    ) -> float:
        """從歷史數據獲取指定時間的 Funding Rate

        Args:
            funding_rate_data: Funding Rate DataFrame
            timestamp: 時間點

        Returns:
            float: Funding Rate
        """
        # 確保有 'timestamp' 和 'funding_rate' 列
        if 'timestamp' not in funding_rate_data.columns:
            # 嘗試使用索引
            if isinstance(funding_rate_data.index, pd.DatetimeIndex):
                funding_rate_data = funding_rate_data.copy()
                funding_rate_data['timestamp'] = funding_rate_data.index

        # 找到最接近的時間點
        if 'timestamp' in funding_rate_data.columns:
            funding_rate_data['time_diff'] = abs(
                pd.to_datetime(funding_rate_data['timestamp']) - pd.Timestamp(timestamp)
            )
            closest_idx = funding_rate_data['time_diff'].idxmin()

            if 'funding_rate' in funding_rate_data.columns:
                rate = funding_rate_data.loc[closest_idx, 'funding_rate']
            elif 'fundingRate' in funding_rate_data.columns:
                rate = funding_rate_data.loc[closest_idx, 'fundingRate']
            else:
                rate = 0.0001  # 默認費率

            # 限制在合理範圍
            return np.clip(rate, self.config.min_funding_rate, self.config.max_funding_rate)

        # 如果沒有數據，使用模擬費率
        return self._simulate_funding_rate()

    def _simulate_funding_rate(self) -> float:
        """模擬 Funding Rate

        使用正態分佈生成合理的費率

        Returns:
            float: 模擬的 Funding Rate
        """
        # Binance 永續合約的典型 Funding Rate 分佈
        # 均值: 0.01% (略微正向，多頭支付)
        # 標準差: 0.05%
        mean_rate = 0.0001
        std_rate = 0.0005

        rate = np.random.normal(mean_rate, std_rate)

        # 限制範圍
        return np.clip(rate, self.config.min_funding_rate, self.config.max_funding_rate)

    def calculate_annual_funding_cost(
        self,
        avg_funding_rate: float,
        position_value: float,
        position_side: str
    ) -> float:
        """計算年化 Funding 成本

        Args:
            avg_funding_rate: 平均 Funding Rate
            position_value: 持倉價值
            position_side: 持倉方向

        Returns:
            float: 年化 Funding 成本

        Example:
            >>> model = FundingModel()
            >>> annual_cost = model.calculate_annual_funding_cost(
            ...     avg_funding_rate=0.0001,
            ...     position_value=10000,
            ...     position_side='long'
            ... )
            >>> annual_cost
            109.5  # 10000 * 0.0001 * (365 * 24 / 8)
        """
        # 每年的 Funding 次數
        fundings_per_year = (365 * 24) / self.config.funding_interval_hours

        # 計算年化成本
        direction_multiplier = 1 if position_side == 'long' else -1
        annual_cost = position_value * avg_funding_rate * fundings_per_year * direction_multiplier

        return annual_cost

    def estimate_funding_cost_for_strategy(
        self,
        avg_position_value: float,
        avg_holding_hours: float,
        position_side_distribution: Dict[str, float],
        avg_funding_rate: float = 0.0001
    ) -> Dict[str, float]:
        """估算策略的 Funding 成本

        Args:
            avg_position_value: 平均持倉價值
            avg_holding_hours: 平均持倉小時數
            position_side_distribution: 多空分佈 {'long': 0.6, 'short': 0.4}
            avg_funding_rate: 平均 Funding Rate

        Returns:
            Dict: 成本估算
        """
        # 計算平均 Funding 次數
        avg_funding_events = avg_holding_hours / self.config.funding_interval_hours

        # Long 和 Short 的費用
        long_ratio = position_side_distribution.get('long', 0.5)
        short_ratio = position_side_distribution.get('short', 0.5)

        long_cost = avg_position_value * avg_funding_rate * avg_funding_events * long_ratio
        short_cost = -avg_position_value * avg_funding_rate * avg_funding_events * short_ratio

        total_cost = long_cost + short_cost

        return {
            'avg_position_value': avg_position_value,
            'avg_holding_hours': avg_holding_hours,
            'avg_funding_events': avg_funding_events,
            'long_funding_cost': long_cost,
            'short_funding_cost': short_cost,
            'net_funding_cost': total_cost,
            'funding_cost_per_trade': total_cost,
            'annual_funding_cost': total_cost * (365 * 24 / avg_holding_hours) if avg_holding_hours > 0 else 0
        }

    def get_statistics(self) -> Dict[str, float]:
        """獲取 Funding 統計信息

        Returns:
            Dict: 統計信息
        """
        return {
            'total_funding_paid': self.total_funding_paid,
            'total_funding_received': self.total_funding_received,
            'net_funding_cost': self.total_funding_paid - self.total_funding_received,
            'funding_event_count': self.funding_event_count,
            'avg_funding_paid': (
                self.total_funding_paid / self.funding_event_count
                if self.funding_event_count > 0 else 0
            )
        }

    def reset_statistics(self):
        """重置統計信息"""
        self.total_funding_paid = 0.0
        self.total_funding_received = 0.0
        self.funding_event_count = 0


# ===== 便捷函數 =====

def calculate_simple_funding_cost(
    position_value: float,
    holding_hours: float,
    funding_rate: float = 0.0001,
    funding_interval: int = 8,
    position_side: str = 'long'
) -> float:
    """簡化的 Funding 成本計算

    Args:
        position_value: 持倉價值
        holding_hours: 持倉小時數
        funding_rate: Funding Rate
        funding_interval: Funding 間隔（小時）
        position_side: 持倉方向

    Returns:
        float: Funding 成本

    Example:
        >>> cost = calculate_simple_funding_cost(10000, 24, 0.0001)
        >>> cost
        3.0  # 10000 * 0.0001 * (24/8)
    """
    num_fundings = holding_hours / funding_interval
    direction = 1 if position_side == 'long' else -1
    return position_value * funding_rate * num_fundings * direction


def get_typical_funding_rates() -> Dict[str, float]:
    """獲取典型的 Funding Rate 範圍

    Returns:
        Dict: 不同市場狀況的典型費率
    """
    return {
        'bull_market': 0.0002,      # 牛市: 多頭支付較高
        'bear_market': -0.0001,     # 熊市: 空頭支付
        'neutral': 0.0001,          # 中性: 略微正向
        'high_volatility': 0.0003,  # 高波動: 費率較高
        'extreme': 0.005,           # 極端情況: 接近上限
    }
