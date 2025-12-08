"""
Rate Limiter v0.7

速率限制器 - 控制 API 請求頻率

功能:
- 令牌桶算法實現
- 線程安全設計
- 自動降速機制

Version: v0.7
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制配置"""

    requests_per_minute: int = 1100
    burst_size: int = 20
    slowdown_factor: float = 0.5
    recovery_time: float = 60.0


class RateLimiter:
    """速率限制器（令牌桶算法）"""

    def __init__(
        self,
        requests_per_minute: int = 1100,
        burst_size: int = 20,
        name: str = "default",
    ):
        """初始化速率限制器"""
        self.name = name
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size

        self.tokens = float(burst_size)
        self.fill_rate = requests_per_minute / 60.0
        self.last_update = time.time()

        self.is_slowed = False
        self.slowdown_until = 0.0

        self._lock = threading.Lock()

        self.total_requests = 0
        self.total_waits = 0
        self.total_wait_time = 0.0

        logger.info(
            f"速率限制器 [{name}] 初始化: {requests_per_minute} req/min, "
            f"burst={burst_size}"
        )

    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """獲取令牌"""
        with self._lock:
            self._refill()

            if self.is_slowed and time.time() < self.slowdown_until:
                wait_time = self.slowdown_until - time.time()
                logger.debug(f"[{self.name}] 降速中，等待 {wait_time:.2f}s")
            else:
                self.is_slowed = False

            if self.tokens >= tokens:
                self.tokens -= tokens
                self.total_requests += 1
                return True

            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.fill_rate

            if timeout is not None and wait_time > timeout:
                return False

        if wait_time > 0:
            logger.debug(f"[{self.name}] 等待 {wait_time:.2f}s 獲取令牌")
            time.sleep(wait_time)
            self.total_waits += 1
            self.total_wait_time += wait_time

        with self._lock:
            self._refill()
            self.tokens = max(0, self.tokens - tokens)
            self.total_requests += 1

        return True

    def _refill(self):
        """補充令牌"""
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        new_tokens = elapsed * self.fill_rate

        if self.is_slowed:
            new_tokens *= 0.5

        self.tokens = min(self.burst_size, self.tokens + new_tokens)

    def slowdown(self, duration: float = 60.0):
        """觸發降速"""
        with self._lock:
            self.is_slowed = True
            self.slowdown_until = time.time() + duration
            logger.warning(f"[{self.name}] 觸發降速，持續 {duration}s")

    def reset(self):
        """重置限制器狀態"""
        with self._lock:
            self.tokens = float(self.burst_size)
            self.is_slowed = False
            self.slowdown_until = 0.0
            self.last_update = time.time()
            logger.info(f"[{self.name}] 已重置")

    def get_stats(self) -> dict:
        """獲取統計信息"""
        with self._lock:
            return {
                "name": self.name,
                "total_requests": self.total_requests,
                "total_waits": self.total_waits,
                "total_wait_time": round(self.total_wait_time, 2),
                "avg_wait_time": (
                    round(self.total_wait_time / self.total_waits, 3)
                    if self.total_waits > 0
                    else 0
                ),
                "current_tokens": round(self.tokens, 2),
                "is_slowed": self.is_slowed,
            }

    @property
    def available_tokens(self) -> float:
        """當前可用令牌數"""
        with self._lock:
            self._refill()
            return self.tokens


class MultiExchangeRateLimiter:
    """多交易所速率限制器"""

    EXCHANGE_LIMITS = {
        "binance": 1100,
        "bybit": 100,
        "okx": 80,
    }

    def __init__(self, custom_limits: Optional[dict] = None):
        """初始化多交易所限制器"""
        limits = self.EXCHANGE_LIMITS.copy()
        if custom_limits:
            limits.update(custom_limits)

        self.limiters = {
            exchange: RateLimiter(rpm, name=exchange)
            for exchange, rpm in limits.items()
        }

    def acquire(self, exchange: str, tokens: int = 1) -> bool:
        """獲取指定交易所的令牌"""
        if exchange not in self.limiters:
            logger.warning(f"未知交易所: {exchange}，使用默認限制")
            self.limiters[exchange] = RateLimiter(60, name=exchange)

        return self.limiters[exchange].acquire(tokens)

    def slowdown(self, exchange: str, duration: float = 60.0):
        """觸發指定交易所降速"""
        if exchange in self.limiters:
            self.limiters[exchange].slowdown(duration)

    def get_all_stats(self) -> dict:
        """獲取所有交易所統計"""
        return {
            exchange: limiter.get_stats() for exchange, limiter in self.limiters.items()
        }


# ===== 便捷函數 =====

_global_limiter: Optional[RateLimiter] = None


def get_global_limiter(requests_per_minute: int = 1100) -> RateLimiter:
    """獲取全局限制器"""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter(requests_per_minute, name="global")
    return _global_limiter


def rate_limited(func):
    """速率限制裝飾器"""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        limiter = get_global_limiter()
        limiter.acquire()
        return func(*args, **kwargs)

    return wrapper
