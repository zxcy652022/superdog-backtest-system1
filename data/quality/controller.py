"""
Data Quality Controller for SuperDog v0.5

數據品質控制器 - 統一的數據品質檢查和清理介面

Features:
- Multi-level quality checks (critical, warning, info)
- Data validation and cleaning
- Anomaly detection
- Quality reporting
- Auto-correction capabilities

Version: v0.5
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """問題嚴重程度"""

    CRITICAL = "critical"  # 嚴重問題，數據不可用
    WARNING = "warning"  # 警告，可能影響分析
    INFO = "info"  # 信息，輕微問題


@dataclass
class QualityIssue:
    """數據品質問題"""

    severity: IssueSeverity
    category: str  # 問題類別（missing_data, outlier, inconsistency, etc.）
    description: str
    affected_rows: List[int] = field(default_factory=list)
    affected_columns: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self):
        return f"[{self.severity.value.upper()}] {self.category}: {self.description}"


@dataclass
class QualityCheckResult:
    """品質檢查結果"""

    passed: bool
    issues: List[QualityIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def critical_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == IssueSeverity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == IssueSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == IssueSeverity.INFO)

    def get_summary(self) -> str:
        """獲取檢查結果摘要"""
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Quality Check {status}\n"
            f"  Critical: {self.critical_count}\n"
            f"  Warning: {self.warning_count}\n"
            f"  Info: {self.info_count}\n"
            f"  Total Issues: {len(self.issues)}"
        )


class DataQualityController:
    """數據品質控制器

    統一管理所有數據品質檢查和清理邏輯

    Example:
        >>> controller = DataQualityController()
        >>> result = controller.check_ohlcv(df)
        >>> if not result.passed:
        >>>     print(result.get_summary())
        >>>     cleaned_df = controller.clean_ohlcv(df)
    """

    def __init__(self, strict_mode: bool = False):
        """初始化品質控制器

        Args:
            strict_mode: 嚴格模式（True = 任何問題都視為失敗）
        """
        self.strict_mode = strict_mode
        self.check_history: List[QualityCheckResult] = []

    def check_ohlcv(self, df: pd.DataFrame) -> QualityCheckResult:
        """檢查 OHLCV 數據品質

        檢查項目：
        1. 缺失值
        2. 價格邏輯（high >= low, high >= open/close, low <= open/close）
        3. 負值
        4. 零值
        5. 異常值（統計方法）
        6. 時間序列連續性

        Args:
            df: OHLCV DataFrame

        Returns:
            QualityCheckResult
        """
        issues = []

        # 1. 檢查必要欄位
        required_columns = ["open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="missing_columns",
                    description=f"Missing required columns: {missing_columns}",
                    affected_columns=missing_columns,
                )
            )
            # 如果缺少必要欄位，無法繼續檢查
            return QualityCheckResult(passed=False, issues=issues, metadata={"total_rows": len(df)})

        # 2. 檢查缺失值
        for col in required_columns:
            null_count = df[col].isnull().sum()
            if null_count > 0:
                null_rows = df[df[col].isnull()].index.tolist()
                issues.append(
                    QualityIssue(
                        severity=IssueSeverity.CRITICAL
                        if col != "volume"
                        else IssueSeverity.WARNING,
                        category="missing_data",
                        description=f"Found {null_count} null values in {col}",
                        affected_rows=null_rows,
                        affected_columns=[col],
                        metadata={"null_count": null_count},
                    )
                )

        # 3. 檢查價格邏輯
        # high >= low
        invalid_high_low = df[df["high"] < df["low"]]
        if len(invalid_high_low) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="price_logic",
                    description=f"Found {len(invalid_high_low)} bars where high < low",
                    affected_rows=invalid_high_low.index.tolist(),
                    affected_columns=["high", "low"],
                )
            )

        # high >= open
        invalid_high_open = df[df["high"] < df["open"]]
        if len(invalid_high_open) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="price_logic",
                    description=f"Found {len(invalid_high_open)} bars where high < open",
                    affected_rows=invalid_high_open.index.tolist(),
                    affected_columns=["high", "open"],
                )
            )

        # high >= close
        invalid_high_close = df[df["high"] < df["close"]]
        if len(invalid_high_close) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="price_logic",
                    description=f"Found {len(invalid_high_close)} bars where high < close",
                    affected_rows=invalid_high_close.index.tolist(),
                    affected_columns=["high", "close"],
                )
            )

        # low <= open
        invalid_low_open = df[df["low"] > df["open"]]
        if len(invalid_low_open) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="price_logic",
                    description=f"Found {len(invalid_low_open)} bars where low > open",
                    affected_rows=invalid_low_open.index.tolist(),
                    affected_columns=["low", "open"],
                )
            )

        # low <= close
        invalid_low_close = df[df["low"] > df["close"]]
        if len(invalid_low_close) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="price_logic",
                    description=f"Found {len(invalid_low_close)} bars where low > close",
                    affected_rows=invalid_low_close.index.tolist(),
                    affected_columns=["low", "close"],
                )
            )

        # 4. 檢查負值
        for col in ["open", "high", "low", "close", "volume"]:
            negative_values = df[df[col] < 0]
            if len(negative_values) > 0:
                issues.append(
                    QualityIssue(
                        severity=IssueSeverity.CRITICAL,
                        category="negative_value",
                        description=f"Found {len(negative_values)} negative values in {col}",
                        affected_rows=negative_values.index.tolist(),
                        affected_columns=[col],
                    )
                )

        # 5. 檢查零值
        for col in ["open", "high", "low", "close"]:
            zero_values = df[df[col] == 0]
            if len(zero_values) > 0:
                issues.append(
                    QualityIssue(
                        severity=IssueSeverity.WARNING,
                        category="zero_value",
                        description=f"Found {len(zero_values)} zero values in {col}",
                        affected_rows=zero_values.index.tolist(),
                        affected_columns=[col],
                    )
                )

        # 6. 檢查異常值（使用 IQR 方法）
        for col in ["open", "high", "low", "close"]:
            outliers = self._detect_outliers_iqr(df[col])
            if len(outliers) > 0:
                issues.append(
                    QualityIssue(
                        severity=IssueSeverity.WARNING,
                        category="outlier",
                        description=f"Found {len(outliers)} potential outliers in {col}",
                        affected_rows=outliers.index.tolist(),
                        affected_columns=[col],
                        metadata={"outlier_count": len(outliers)},
                    )
                )

        # 7. 檢查時間序列連續性（如果有時間索引）
        if isinstance(df.index, pd.DatetimeIndex):
            gaps = self._detect_time_gaps(df.index)
            if len(gaps) > 0:
                issues.append(
                    QualityIssue(
                        severity=IssueSeverity.INFO,
                        category="time_gap",
                        description=f"Found {len(gaps)} time gaps in data",
                        metadata={"gaps": gaps[:10]},  # 只記錄前10個
                    )
                )

        # 判斷是否通過
        has_critical = any(issue.severity == IssueSeverity.CRITICAL for issue in issues)
        passed = not has_critical if not self.strict_mode else len(issues) == 0

        result = QualityCheckResult(
            passed=passed,
            issues=issues,
            metadata={
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "strict_mode": self.strict_mode,
            },
        )

        self.check_history.append(result)

        return result

    def check_funding_rate(self, df: pd.DataFrame) -> QualityCheckResult:
        """檢查資金費率數據品質

        檢查項目：
        1. 缺失值
        2. 異常值（極端資金費率）
        3. 時間間隔（應該是8小時）
        4. 資金費率範圍

        Args:
            df: 資金費率 DataFrame

        Returns:
            QualityCheckResult
        """
        issues = []

        # 1. 檢查必要欄位
        required_columns = ["timestamp", "funding_rate"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="missing_columns",
                    description=f"Missing required columns: {missing_columns}",
                    affected_columns=missing_columns,
                )
            )
            return QualityCheckResult(passed=False, issues=issues)

        # 2. 檢查缺失值
        null_count = df["funding_rate"].isnull().sum()
        if null_count > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="missing_data",
                    description=f"Found {null_count} null funding rates",
                    affected_rows=df[df["funding_rate"].isnull()].index.tolist(),
                    affected_columns=["funding_rate"],
                )
            )

        # 3. 檢查極端資金費率（|rate| > 1%）
        extreme_rates = df[df["funding_rate"].abs() > 0.01]
        if len(extreme_rates) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.WARNING,
                    category="extreme_value",
                    description=f"Found {len(extreme_rates)} extreme funding rates (|rate| > 1%)",
                    affected_rows=extreme_rates.index.tolist(),
                    affected_columns=["funding_rate"],
                    metadata={
                        "max_rate": extreme_rates["funding_rate"].max(),
                        "min_rate": extreme_rates["funding_rate"].min(),
                    },
                )
            )

        # 4. 檢查資金費率範圍（正常範圍 -0.5% ~ 0.5%）
        unusual_rates = df[(df["funding_rate"] > 0.005) | (df["funding_rate"] < -0.005)]
        if len(unusual_rates) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.INFO,
                    category="unusual_value",
                    description=f"Found {len(unusual_rates)} unusual funding rates (outside -0.5% ~ 0.5%)",
                    affected_rows=unusual_rates.index.tolist(),
                    affected_columns=["funding_rate"],
                )
            )

        # 判斷是否通過
        has_critical = any(issue.severity == IssueSeverity.CRITICAL for issue in issues)
        passed = not has_critical if not self.strict_mode else len(issues) == 0

        result = QualityCheckResult(passed=passed, issues=issues, metadata={"total_rows": len(df)})

        self.check_history.append(result)

        return result

    def check_open_interest(self, df: pd.DataFrame) -> QualityCheckResult:
        """檢查持倉量數據品質

        Args:
            df: 持倉量 DataFrame

        Returns:
            QualityCheckResult
        """
        issues = []

        # 1. 檢查必要欄位
        required_columns = ["timestamp", "open_interest"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="missing_columns",
                    description=f"Missing required columns: {missing_columns}",
                    affected_columns=missing_columns,
                )
            )
            return QualityCheckResult(passed=False, issues=issues)

        # 2. 檢查缺失值
        null_count = df["open_interest"].isnull().sum()
        if null_count > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="missing_data",
                    description=f"Found {null_count} null open interest values",
                    affected_rows=df[df["open_interest"].isnull()].index.tolist(),
                    affected_columns=["open_interest"],
                )
            )

        # 3. 檢查負值
        negative_oi = df[df["open_interest"] < 0]
        if len(negative_oi) > 0:
            issues.append(
                QualityIssue(
                    severity=IssueSeverity.CRITICAL,
                    category="negative_value",
                    description=f"Found {len(negative_oi)} negative open interest values",
                    affected_rows=negative_oi.index.tolist(),
                    affected_columns=["open_interest"],
                )
            )

        # 4. 檢查異常突增/突減（變化超過50%）
        if "oi_change_pct" in df.columns:
            large_changes = df[df["oi_change_pct"].abs() > 50]
            if len(large_changes) > 0:
                issues.append(
                    QualityIssue(
                        severity=IssueSeverity.WARNING,
                        category="large_change",
                        description=f"Found {len(large_changes)} large OI changes (>50%)",
                        affected_rows=large_changes.index.tolist(),
                        affected_columns=["open_interest", "oi_change_pct"],
                    )
                )

        # 判斷是否通過
        has_critical = any(issue.severity == IssueSeverity.CRITICAL for issue in issues)
        passed = not has_critical if not self.strict_mode else len(issues) == 0

        result = QualityCheckResult(passed=passed, issues=issues, metadata={"total_rows": len(df)})

        self.check_history.append(result)

        return result

    def clean_ohlcv(self, df: pd.DataFrame, auto_fix: bool = True) -> pd.DataFrame:
        """清理 OHLCV 數據

        清理操作：
        1. 移除缺失值
        2. 修復價格邏輯問題（如果 auto_fix=True）
        3. 移除異常值（可選）
        4. 移除重複時間

        Args:
            df: OHLCV DataFrame
            auto_fix: 是否自動修復問題

        Returns:
            清理後的 DataFrame
        """
        df = df.copy()
        original_len = len(df)

        # 1. 移除缺失值
        df = df.dropna(subset=["open", "high", "low", "close"])

        # 2. 修復價格邏輯問題
        if auto_fix:
            # 確保 high 是最高價
            df["high"] = df[["open", "high", "close"]].max(axis=1)

            # 確保 low 是最低價
            df["low"] = df[["open", "low", "close"]].min(axis=1)

        # 3. 移除負值
        df = df[(df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0)]

        # 4. 移除零值
        df = df[(df["open"] != 0) & (df["high"] != 0) & (df["low"] != 0) & (df["close"] != 0)]

        # 5. 移除重複時間（如果有時間索引）
        if isinstance(df.index, pd.DatetimeIndex):
            df = df[~df.index.duplicated(keep="first")]

        removed = original_len - len(df)
        if removed > 0:
            logger.info(
                f"Cleaned OHLCV data: removed {removed} rows ({removed/original_len*100:.2f}%)"
            )

        return df

    def _detect_outliers_iqr(self, series: pd.Series, multiplier: float = 3.0) -> pd.Series:
        """使用 IQR 方法檢測異常值

        Args:
            series: 數據序列
            multiplier: IQR 倍數（默認3.0，更保守）

        Returns:
            異常值序列
        """
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR

        outliers = series[(series < lower_bound) | (series > upper_bound)]

        return outliers

    def _detect_time_gaps(
        self, time_index: pd.DatetimeIndex, expected_freq: Optional[str] = None
    ) -> List[tuple]:
        """檢測時間序列中的間隙

        Args:
            time_index: 時間索引
            expected_freq: 預期頻率（如 '1H'）

        Returns:
            間隙列表 [(gap_start, gap_end, gap_duration), ...]
        """
        if len(time_index) < 2:
            return []

        # 計算時間差
        time_diffs = time_index[1:] - time_index[:-1]

        # 如果沒有指定頻率，使用中位數作為預期間隔
        if expected_freq is None:
            expected_interval = time_diffs.median()
        else:
            expected_interval = pd.Timedelta(expected_freq)

        # 檢測異常大的間隙（超過預期間隔的2倍）
        gaps = []
        for i, diff in enumerate(time_diffs):
            if diff > expected_interval * 2:
                gaps.append((time_index[i], time_index[i + 1], diff))

        return gaps

    def get_check_history(self, limit: int = 10) -> List[QualityCheckResult]:
        """獲取檢查歷史"""
        return self.check_history[-limit:]

    def clear_history(self):
        """清除檢查歷史"""
        self.check_history.clear()
        logger.info("Quality check history cleared")
