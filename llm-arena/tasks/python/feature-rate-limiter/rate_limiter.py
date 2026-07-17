"""Token bucket rate limiter implementation.

This module provides a rate limiter using the token bucket algorithm
with Redis as the backend store.
"""

import time
from typing import Optional


class TokenBucket:
    """Token bucket for rate limiting.

    Attributes:
        capacity: Maximum number of tokens in the bucket
        tokens: Current number of tokens
        last_update: Timestamp of last token update
    """

    def __init__(self, capacity: int, refill_rate: float):
        """Initialize a token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_update = time.time()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False otherwise
        """
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    """Rate limiter using token bucket algorithm.

    Supports per-key rate limiting with configurable
    rate and burst capacity.
    """

    def __init__(self, default_rate: float = 10.0, default_burst: int = 5):
        """Initialize the rate limiter.

        Args:
            default_rate: Default requests per second
            default_burst: Default burst capacity
        """
        self.default_rate = default_rate
        self.default_burst = default_burst
        self.buckets: dict[str, TokenBucket] = {}

    def is_allowed(self, key: str, tokens: int = 1) -> bool:
        """Check if a request is allowed.

        Args:
            key: Unique identifier (e.g., IP address, API key)
            tokens: Number of tokens to consume

        Returns:
            True if request is allowed, False otherwise
        """
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(
                capacity=self.default_burst,
                refill_rate=self.default_rate,
            )

        return self.buckets[key].consume(tokens)

    def get_remaining(self, key: str) -> int:
        """Get remaining tokens for a key.

        Args:
            key: Unique identifier

        Returns:
            Number of remaining tokens
        """
        if key not in self.buckets:
            return self.default_burst

        bucket = self.buckets[key]
        bucket._refill()
        return int(bucket.tokens)
