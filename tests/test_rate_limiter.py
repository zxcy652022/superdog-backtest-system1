"""
Rate Limiter 測試

測試速率限制器的各種功能
"""

import threading
import time

import pytest

from data.downloaders.rate_limiter import (MultiExchangeRateLimiter,
                                           RateLimitConfig, RateLimiter,
                                           get_global_limiter, rate_limited)


class TestRateLimiter:
    """RateLimiter 測試類"""

    @pytest.fixture
    def limiter(self):
        """創建 RateLimiter 實例"""
        return RateLimiter(requests_per_minute=60, burst_size=5, name="test")

    def test_initialization(self, limiter):
        """測試初始化"""
        assert limiter.name == "test"
        assert limiter.requests_per_minute == 60
        assert limiter.burst_size == 5
        assert limiter.tokens == 5.0

    def test_acquire_single_token(self, limiter):
        """測試獲取單個令牌"""
        result = limiter.acquire(tokens=1)
        assert result is True
        assert limiter.tokens < 5.0

    def test_acquire_multiple_tokens(self, limiter):
        """測試獲取多個令牌"""
        result = limiter.acquire(tokens=3)
        assert result is True

    def test_acquire_with_timeout_success(self, limiter):
        """測試帶超時的獲取 - 成功"""
        result = limiter.acquire(tokens=1, timeout=1.0)
        assert result is True

    def test_acquire_with_timeout_fail(self, limiter):
        """測試帶超時的獲取 - 失敗"""
        # 消耗所有令牌
        limiter.tokens = 0
        result = limiter.acquire(tokens=10, timeout=0.01)
        assert result is False

    def test_slowdown(self, limiter):
        """測試降速機制"""
        limiter.slowdown(duration=1.0)
        assert limiter.is_slowed is True

    def test_reset(self, limiter):
        """測試重置"""
        limiter.tokens = 0
        limiter.is_slowed = True
        limiter.reset()
        assert limiter.tokens == 5.0
        assert limiter.is_slowed is False

    def test_get_stats(self, limiter):
        """測試獲取統計"""
        limiter.acquire(tokens=1)
        stats = limiter.get_stats()
        assert stats["name"] == "test"
        assert stats["total_requests"] == 1
        assert "current_tokens" in stats

    def test_available_tokens(self, limiter):
        """測試可用令牌屬性"""
        available = limiter.available_tokens
        assert available > 0

    def test_thread_safety(self, limiter):
        """測試線程安全"""
        results = []

        def acquire_token():
            result = limiter.acquire(tokens=1)
            results.append(result)

        threads = [threading.Thread(target=acquire_token) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        assert all(r is True for r in results)

    def test_refill_over_time(self):
        """測試令牌隨時間補充"""
        limiter = RateLimiter(
            requests_per_minute=600, burst_size=10, name="refill_test"
        )
        limiter.tokens = 0
        time.sleep(0.15)  # 等待約 1.5 個令牌補充
        available = limiter.available_tokens
        assert available > 1


class TestRateLimitConfig:
    """RateLimitConfig 測試類"""

    def test_default_config(self):
        """測試默認配置"""
        config = RateLimitConfig()
        assert config.requests_per_minute == 1100
        assert config.burst_size == 20
        assert config.slowdown_factor == 0.5

    def test_custom_config(self):
        """測試自定義配置"""
        config = RateLimitConfig(
            requests_per_minute=500,
            burst_size=10,
            slowdown_factor=0.3,
        )
        assert config.requests_per_minute == 500
        assert config.burst_size == 10


class TestMultiExchangeRateLimiter:
    """MultiExchangeRateLimiter 測試類"""

    @pytest.fixture
    def multi_limiter(self):
        """創建 MultiExchangeRateLimiter 實例"""
        return MultiExchangeRateLimiter()

    def test_default_exchanges(self, multi_limiter):
        """測試默認交易所"""
        assert "binance" in multi_limiter.limiters
        assert "bybit" in multi_limiter.limiters
        assert "okx" in multi_limiter.limiters

    def test_acquire_binance(self, multi_limiter):
        """測試獲取 Binance 令牌"""
        result = multi_limiter.acquire("binance")
        assert result is True

    def test_acquire_unknown_exchange(self, multi_limiter):
        """測試獲取未知交易所令牌"""
        result = multi_limiter.acquire("unknown_exchange")
        assert result is True
        assert "unknown_exchange" in multi_limiter.limiters

    def test_slowdown_exchange(self, multi_limiter):
        """測試交易所降速"""
        multi_limiter.slowdown("binance", duration=1.0)
        assert multi_limiter.limiters["binance"].is_slowed is True

    def test_get_all_stats(self, multi_limiter):
        """測試獲取所有統計"""
        multi_limiter.acquire("binance")
        stats = multi_limiter.get_all_stats()
        assert "binance" in stats
        assert stats["binance"]["total_requests"] == 1

    def test_custom_limits(self):
        """測試自定義限制"""
        custom = {"custom_exchange": 200}
        limiter = MultiExchangeRateLimiter(custom_limits=custom)
        assert "custom_exchange" in limiter.limiters
        assert limiter.limiters["custom_exchange"].requests_per_minute == 200


class TestConvenienceFunctions:
    """便捷函數測試"""

    def test_get_global_limiter(self):
        """測試獲取全局限制器"""
        limiter1 = get_global_limiter()
        limiter2 = get_global_limiter()
        assert limiter1 is limiter2

    def test_rate_limited_decorator(self):
        """測試速率限制裝飾器"""
        call_count = 0

        @rate_limited
        def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = test_func()
        assert result == "success"
        assert call_count == 1
