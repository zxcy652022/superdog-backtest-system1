"""
Strategy Configuration Interface v1.0

這個模組定義策略的「食譜」格式。

設計理念：
- 策略像食譜，只定義「需要什麼」和「怎麼做」
- 引擎像廚師，根據食譜使用正確的工具和材料
- 基礎模組像廚房器具，可以被不同食譜共用

使用方式：
```python
class MyStrategy(BaseStrategy):
    @classmethod
    def get_execution_config(cls) -> ExecutionConfig:
        return ExecutionConfig(
            stop_config=StopConfig(
                type="confirmed",
                confirm_bars=10,
                trailing=True,
                trailing_ma_key="avg20",
                trailing_buffer=0.02,
                emergency_atr_mult=3.5,
            ),
            add_position_config=AddPositionConfig(
                enabled=True,
                max_count=3,
                size_pct=0.5,
                min_interval=6,
                min_profit=0.03,
                pullback_tolerance=0.018,
            ),
            position_sizing_config=PositionSizingConfig(
                type="percent_of_equity",
                percent=0.15,
            ),
            take_profit_pct=0.10,
        )
```

Version: v1.0
Date: 2026-01-05
"""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class StopConfig:
    """止損配置

    type:
    - "simple": 觸及即止損
    - "confirmed": 連續 N 根確認
    - "atr_trailing": ATR 追蹤止損
    """

    type: Literal["simple", "confirmed", "atr_trailing"] = "simple"

    # 確認式止損參數
    confirm_bars: int = 10

    # 追蹤止損參數
    trailing: bool = True
    trailing_ma_key: str = "avg20"
    trailing_buffer: float = 0.02  # 2%

    # 緊急止損參數
    emergency_atr_mult: float = 3.5  # 0 = 禁用
    atr_key: str = "atr"

    # 固定止損百分比（如果策略不提供動態止損）
    fixed_stop_pct: Optional[float] = None  # e.g., 0.03 = 3%


@dataclass
class AddPositionConfig:
    """加倉配置"""

    enabled: bool = False
    max_count: int = 3
    size_pct: float = 0.5  # 每次加倉比例（相對當前持倉）
    min_interval: int = 6  # 最小加倉間隔（K 線數）
    min_profit: float = 0.03  # 最小盈利門檻 (0.03 = 3%)
    pullback_tolerance: float = 0.018  # 回踩容許 (0.018 = 1.8%)
    pullback_ma_key: str = "avg20"


@dataclass
class PositionSizingConfig:
    """倉位配置

    type:
    - "all_in": 全倉進場
    - "percent_of_equity": 權益百分比
    - "fixed_amount": 固定金額
    - "kelly": Kelly 公式
    """

    type: Literal["all_in", "percent_of_equity", "fixed_amount", "kelly"] = "all_in"

    # percent_of_equity 參數
    percent: float = 0.15  # 15%

    # fixed_amount 參數
    amount: float = 1000.0


@dataclass
class ExecutionConfig:
    """完整執行配置 - 策略的「食譜」"""

    # 止損配置
    stop_config: StopConfig = field(default_factory=StopConfig)

    # 加倉配置
    add_position_config: AddPositionConfig = field(default_factory=AddPositionConfig)

    # 倉位配置
    position_sizing_config: PositionSizingConfig = field(default_factory=PositionSizingConfig)

    # 止盈參數
    take_profit_pct: Optional[float] = None  # e.g., 0.10 = 10%

    # 槓桿
    leverage: float = 1.0

    # 手續費率
    fee_rate: float = 0.0005


# === 預設配置（便捷函數）===


def bige_execution_config() -> ExecutionConfig:
    """BiGe 策略的執行配置

    與 bige_dual_ma_v2.py v2.3 完全一致。
    """
    return ExecutionConfig(
        stop_config=StopConfig(
            type="confirmed",
            confirm_bars=10,
            trailing=True,
            trailing_ma_key="avg20",
            trailing_buffer=0.02,
            emergency_atr_mult=3.5,
            fixed_stop_pct=0.03,  # 進場價 -3%
        ),
        add_position_config=AddPositionConfig(
            enabled=True,
            max_count=3,
            size_pct=0.5,
            min_interval=6,
            min_profit=0.03,
            pullback_tolerance=0.018,
            pullback_ma_key="avg20",
        ),
        position_sizing_config=PositionSizingConfig(
            type="percent_of_equity",
            percent=0.15,
        ),
        take_profit_pct=0.10,
        leverage=7.0,
        fee_rate=0.0005,
    )


def simple_execution_config(
    leverage: float = 1.0,
    stop_loss_pct: Optional[float] = 0.02,
    take_profit_pct: Optional[float] = 0.05,
) -> ExecutionConfig:
    """簡單執行配置（適合大多數策略）"""
    return ExecutionConfig(
        stop_config=StopConfig(
            type="simple",
            fixed_stop_pct=stop_loss_pct,
        ),
        add_position_config=AddPositionConfig(enabled=False),
        position_sizing_config=PositionSizingConfig(type="all_in"),
        take_profit_pct=take_profit_pct,
        leverage=leverage,
    )
