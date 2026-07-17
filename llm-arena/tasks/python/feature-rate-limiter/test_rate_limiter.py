import pytest
import time
from rate_limiter import TokenBucket, RateLimiter


class TestTokenBucket:
    """Tests for the TokenBucket class."""

    def test_initial_capacity(self):
        """Test that bucket starts at full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.tokens == 10

    def test_consume_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume(5) is True
        assert bucket.tokens == 5

    def test_consume_failure(self):
        """Test failed consumption when not enough tokens."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.consume(10) is False

    def test_refill(self):
        """Test token refilling over time."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        bucket.consume(5)
        time.sleep(1)  # Wait for refill
        assert bucket.consume(1) is True  # Should have refilled

    def test_capacity_limit(self):
        """Test that tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=5, refill_rate=10.0)
        bucket.consume(3)
        time.sleep(1)
        bucket._refill()
        assert bucket.tokens <= 5


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_is_allowed_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(default_rate=10.0, default_burst=5)
        assert limiter.is_allowed("user1") is True

    def test_rate_limiting(self):
        """Test that rate limiting works."""
        limiter = RateLimiter(default_rate=1.0, default_burst=2)
        key = "user2"

        # Should allow first 2 requests
        assert limiter.is_allowed(key) is True
        assert limiter.is_allowed(key) is True

        # Third request should fail (no tokens left)
        assert limiter.is_allowed(key) is False

    def test_different_keys(self):
        """Test that different keys have separate buckets."""
        limiter = RateLimiter(default_rate=10.0, default_burst=5)
        assert limiter.is_allowed("user3") is True
        assert limiter.is_allowed("user4") is True

    def test_get_remaining(self):
        """Test getting remaining tokens."""
        limiter = RateLimiter(default_rate=10.0, default_burst=5)
        key = "user5"
        limiter.is_allowed(key)  # Consume 1 token
        remaining = limiter.get_remaining(key)
        assert remaining == 4

    def test_burst_capacity(self):
        """Test burst capacity handling."""
        limiter = RateLimiter(default_rate=1.0, default_burst=3)
        key = "user6"

        # Should allow all burst requests
        for _ in range(3):
            assert limiter.is_allowed(key) is True

        # Fourth request should fail
        assert limiter.is_allowed(key) is False
