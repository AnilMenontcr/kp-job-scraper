"""
Rate Limiter Module
~~~~~~~~~~~~~~~~~~~

Implements token bucket algorithm for request rate limiting.
"""

import random
import time
from typing import Optional


class RateLimiter:
    """Token bucket rate limiter for HTTP requests."""

    def __init__(
        self,
        max_requests_per_hour: int = 50,
        min_delay_seconds: float = 3.0,
        max_delay_seconds: float = 8.0,
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests_per_hour: Maximum requests allowed per hour
            min_delay_seconds: Minimum delay between requests
            max_delay_seconds: Maximum delay between requests
        """
        self.max_requests_per_hour = max_requests_per_hour
        self.min_delay = min_delay_seconds
        self.max_delay = max_delay_seconds

        # Token bucket state
        self.tokens = float(max_requests_per_hour)
        self.last_refill = time.time()
        self.last_request: Optional[float] = None

        # Refill rate: tokens per second
        self.refill_rate = max_requests_per_hour / 3600.0

    def wait_if_needed(self) -> float:
        """
        Block until a request token is available and enforce delay.

        Returns:
            Actual wait time in seconds
        """
        start_time = time.time()

        # Refill tokens based on elapsed time
        self._refill_tokens()

        # Wait if no tokens available
        while self.tokens < 1:
            time.sleep(0.1)  # Check every 100ms
            self._refill_tokens()

        # Consume a token
        self.tokens -= 1

        # Enforce minimum delay between requests
        if self.last_request is not None:
            elapsed = time.time() - self.last_request
            required_delay = random.uniform(self.min_delay, self.max_delay)

            if elapsed < required_delay:
                sleep_time = required_delay - elapsed
                time.sleep(sleep_time)

        self.last_request = time.time()

        return time.time() - start_time

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on refill rate
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.max_requests_per_hour, self.tokens + tokens_to_add)
        self.last_refill = now

    def get_status(self) -> dict:
        """
        Get current rate limiter status.

        Returns:
            Dictionary with tokens available and time until next refill
        """
        self._refill_tokens()
        return {
            "tokens_available": int(self.tokens),
            "max_tokens": self.max_requests_per_hour,
            "refill_rate_per_second": self.refill_rate,
        }

    def reset(self) -> None:
        """Reset rate limiter to initial state."""
        self.tokens = float(self.max_requests_per_hour)
        self.last_refill = time.time()
        self.last_request = None

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RateLimiter(max_requests_per_hour={self.max_requests_per_hour}, "
            f"tokens={self.tokens:.2f})"
        )
