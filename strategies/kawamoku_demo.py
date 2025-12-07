"""
Kawamoku Demo Strategy v1.0

川沐多因子量化策略示範 - 展示 Strategy API v2.0 進階特性

策略說明：
這是一個展示 v2.0 API 能力的示範策略。
v0.4 版本使用簡化邏輯（僅基於 OHLCV），
v0.5 將整合資金費率、持倉量等高級數據源。

策略邏輯（v0.4 簡化版）：
- 價格動量 + 成交量確認的多因子系統
- 買入：價格動量 > 閾值 且 成交量放大
- 賣出：價格動量 < 負閾值 且 成交量放大

Version: v1.0
Author: DDragon
Design Reference: docs/specs/planned/v0.4_strategy_api_spec.md
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np
from strategies.api_v2 import (
    BaseStrategy,
    ParameterSpec,
    DataRequirement,
    DataSource,
    float_param,
    int_param,
    bool_param
)


class KawamokuStrategy(BaseStrategy):
    """川沐多因子量化策略

    這是一個展示 Strategy API v2.0 進階特性的示範策略：
    - 多個可調參數（浮點、整數、布林）
    - 複雜的參數驗證（範圍限制）
    - 可選數據源聲明（為 v0.5 做準備）
    - 多因子組合邏輯

    v0.4 實作：
        基於 OHLCV 的簡化版，使用價格動量 + 成交量分析

    v0.5 規劃：
        整合資金費率、持倉量、基差等高級數據源

    參數：
        momentum_period: 價格動量計算週期（預設 5）
        momentum_threshold: 動量觸發閾值（預設 0.02 = 2%）
        volume_ma_period: 成交量均線週期（預設 20）
        volume_threshold: 成交量放大閾值（預設 1.5）
        funding_weight: 資金費率權重（v0.5，預設 0.5）
        oi_threshold: 持倉量變化閾值（v0.5，預設 1.0）
        basis_lookback: 基差計算回望期（v0.5，預設 7）
        enable_volume_filter: 啟用成交量過濾（預設 True）
    """

    def __init__(self):
        """初始化策略"""
        super().__init__()
        self.name = "Kawamoku"
        self.version = "1.0"
        self.author = "DDragon"
        self.description = (
            "川沐多因子量化策略 - 整合價格動量、成交量、資金費率等多維度分析"
            "（v0.4 簡化版，v0.5 完整版）"
        )

    def get_parameters(self) -> Dict[str, ParameterSpec]:
        """返回策略參數規格

        展示各種參數類型和驗證規則

        Returns:
            參數規格字典，包含：
                - 整數參數（週期設定）
                - 浮點參數（閾值設定）
                - 布林參數（功能開關）
        """
        return {
            # === 價格動量參數 ===
            'momentum_period': int_param(
                default=5,
                description="價格動量計算週期",
                min_val=1,
                max_val=20
            ),
            'momentum_threshold': float_param(
                default=0.02,
                description="動量觸發閾值（比例）",
                min_val=0.001,
                max_val=0.1
            ),

            # === 成交量參數 ===
            'volume_ma_period': int_param(
                default=20,
                description="成交量均線週期",
                min_val=5,
                max_val=100
            ),
            'volume_threshold': float_param(
                default=1.5,
                description="成交量放大閾值（倍數）",
                min_val=1.0,
                max_val=5.0
            ),
            'enable_volume_filter': bool_param(
                default=True,
                description="啟用成交量過濾"
            ),

            # === 高級因子參數（v0.5 規劃）===
            'funding_weight': float_param(
                default=0.5,
                description="資金費率權重（v0.5）",
                min_val=0.0,
                max_val=1.0
            ),
            'oi_threshold': float_param(
                default=1.0,
                description="持倉量變化閾值（v0.5）",
                min_val=0.1,
                max_val=5.0
            ),
            'basis_lookback': int_param(
                default=7,
                description="基差計算回望期（v0.5）",
                min_val=1,
                max_val=30
            ),
        }

    def get_data_requirements(self) -> List[DataRequirement]:
        """聲明數據需求

        展示必需和可選數據源的聲明

        Returns:
            數據需求列表：
                - OHLCV: 必需（v0.4 支援）
                - FUNDING: 可選（v0.5 規劃）
                - OPEN_INTEREST: 可選（v0.5 規劃）
                - BASIS: 可選（v0.5 規劃）
        """
        return [
            # v0.4 支援的數據源
            DataRequirement(
                source=DataSource.OHLCV,
                lookback_periods=100,
                required=True
            ),

            # v0.5 規劃的數據源（目前標記為可選）
            DataRequirement(
                source=DataSource.FUNDING,
                lookback_periods=30,
                required=False  # v0.4 暫不支援，不報錯
            ),
            DataRequirement(
                source=DataSource.OPEN_INTEREST,
                lookback_periods=30,
                required=False
            ),
            DataRequirement(
                source=DataSource.BASIS,
                lookback_periods=30,
                required=False
            ),
        ]

    def compute_signals(self, data: Dict[str, pd.DataFrame], params: Dict[str, Any]) -> pd.Series:
        """計算交易信號

        v0.4 實作：基於 OHLCV 的簡化版多因子邏輯
        v0.5 規劃：整合資金費率、持倉量等高級因子

        Args:
            data: 數據字典，至少包含 'ohlcv'
            params: 策略參數字典

        Returns:
            pd.Series: 交易信號序列 (1=買入, -1=賣出, 0=持有)

        Raises:
            ValueError: 數據不足或參數無效
        """
        # 驗證數據
        if 'ohlcv' not in data:
            raise ValueError("Missing required data source: ohlcv")

        ohlcv = data['ohlcv']
        if len(ohlcv) < max(params['momentum_period'], params['volume_ma_period']):
            raise ValueError("Insufficient data for indicator calculation")

        # === 提取 OHLCV 數據 ===
        close_prices = ohlcv['close']
        volume = ohlcv['volume']

        # === 因子 1: 價格動量 ===
        # 計算 N 期收益率作為動量指標
        price_momentum = close_prices.pct_change(params['momentum_period'])

        # === 因子 2: 成交量分析 ===
        # 計算成交量均線
        volume_ma = volume.rolling(window=params['volume_ma_period']).mean()
        # 計算成交量比率（當前成交量 / 均線）
        volume_ratio = volume / volume_ma

        # === 信號生成 ===
        signals = pd.Series(0, index=close_prices.index)

        # 買入條件：
        # 1. 價格動量 > 閾值（強勁上漲）
        # 2. 成交量放大（如果啟用成交量過濾）
        buy_condition = price_momentum > params['momentum_threshold']
        if params['enable_volume_filter']:
            buy_condition = buy_condition & (volume_ratio > params['volume_threshold'])
        signals[buy_condition] = 1

        # 賣出條件：
        # 1. 價格動量 < 負閾值（強勁下跌）
        # 2. 成交量放大（如果啟用成交量過濾）
        sell_condition = price_momentum < -params['momentum_threshold']
        if params['enable_volume_filter']:
            sell_condition = sell_condition & (volume_ratio > params['volume_threshold'] * 0.8)
        signals[sell_condition] = -1

        # === v0.5 規劃：整合高級因子 ===
        # if 'funding' in data:
        #     funding_rate = data['funding']
        #     # 資金費率邏輯...
        #
        # if 'oi' in data:
        #     open_interest = data['oi']
        #     # 持倉量邏輯...
        #
        # if 'basis' in data:
        #     basis = data['basis']
        #     # 基差邏輯...

        return signals

    def _compute_momentum_score(self, prices: pd.Series, period: int) -> pd.Series:
        """計算動量得分（內部輔助方法）

        Args:
            prices: 價格序列
            period: 計算週期

        Returns:
            動量得分序列
        """
        return prices.pct_change(period)

    def _compute_volume_score(self, volume: pd.Series, ma_period: int) -> pd.Series:
        """計算成交量得分（內部輔助方法）

        Args:
            volume: 成交量序列
            ma_period: 均線週期

        Returns:
            成交量得分序列（相對於均線的比率）
        """
        volume_ma = volume.rolling(window=ma_period).mean()
        return volume / volume_ma
