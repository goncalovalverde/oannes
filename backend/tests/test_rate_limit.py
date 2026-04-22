"""Tests for rate limiting functionality with exponential backoff and jitter."""

import pytest
import time
from unittest.mock import MagicMock
from utils.rate_limit import calculate_backoff_delay, handle_rate_limit, RateLimitExceeded


class TestCalculateBackoffDelay:
    """Test exponential backoff delay calculation."""
    
    def test_attempt_zero_no_jitter(self):
        """First retry (attempt 0) should return base_delay without jitter."""
        delay = calculate_backoff_delay(attempt=0, use_jitter=False)
        assert delay == 1.0  # base_delay * 2^0 = 1.0
    
    def test_attempt_one_no_jitter(self):
        """Second retry (attempt 1) should be 2x base_delay without jitter."""
        delay = calculate_backoff_delay(attempt=1, use_jitter=False)
        assert delay == 2.0  # base_delay * 2^1 = 2.0
    
    def test_attempt_five_no_jitter(self):
        """Sixth retry (attempt 5) should be 32x base_delay, but capped at max_delay."""
        delay = calculate_backoff_delay(attempt=5, use_jitter=False, max_delay=300.0)
        assert delay == 32.0  # base_delay * 2^5 = 32.0, below cap
    
    def test_cap_at_max_delay(self):
        """Delay should be capped at max_delay."""
        delay = calculate_backoff_delay(attempt=10, use_jitter=False, max_delay=300.0)
        assert delay == 300.0  # Would be 1024, but capped at 300
    
    def test_jitter_in_range(self):
        """With jitter, delay should be between capped_delay and 2*capped_delay."""
        # Run multiple times to verify jitter is working
        delays = [
            calculate_backoff_delay(attempt=1, use_jitter=True, max_delay=300.0)
            for _ in range(10)
        ]
        
        # All delays should be >= 2.0 (exponential) and <= 4.0 (exponential + jitter)
        for delay in delays:
            assert 2.0 <= delay <= 4.0
        
        # At least one delay should be different (proving randomness)
        assert len(set(delays)) > 1
    
    def test_custom_base_delay(self):
        """Should support custom base_delay."""
        delay = calculate_backoff_delay(attempt=0, base_delay=5.0, use_jitter=False)
        assert delay == 5.0  # 5 * 2^0
        
        delay = calculate_backoff_delay(attempt=1, base_delay=5.0, use_jitter=False)
        assert delay == 10.0  # 5 * 2^1
    
    def test_zero_attempt(self):
        """Attempt 0 should use 2^0 = 1 in exponent."""
        delay = calculate_backoff_delay(attempt=0, base_delay=1.0, use_jitter=False)
        assert delay == 1.0  # 1 * (2^0) = 1


class TestHandleRateLimit:
    """Test rate limit handling with priority-based delay selection."""
    
    def test_user_override_delay(self):
        """User-configured retry_delay should have highest priority."""
        delay = handle_rate_limit(
            error_response={},
            attempt=0,
            retry_delay=10.5
        )
        assert delay == 10.5
    
    def test_api_provided_delay(self):
        """API-provided delay should be used if no user override."""
        delay = handle_rate_limit(
            error_response={},
            attempt=0,
            api_provided_delay=15.0
        )
        assert delay == 15.0
    
    def test_exponential_backoff_fallback(self):
        """Exponential backoff should be used if no user or API delay."""
        delay = handle_rate_limit(
            error_response={},
            attempt=1
        )
        # With jitter, should be between 2.0 and 4.0
        assert 2.0 <= delay <= 4.0
    
    def test_priority_user_overrides_api(self):
        """User delay should override API-provided delay."""
        delay = handle_rate_limit(
            error_response={},
            attempt=5,
            retry_delay=5.0,
            api_provided_delay=15.0
        )
        assert delay == 5.0  # User override takes priority


class TestRateLimitIntegration:
    """Integration tests for rate limit handling in realistic scenarios."""
    
    def test_exponential_backoff_sequence(self):
        """Verify exponential backoff increases over attempts."""
        delays = []
        for attempt in range(5):
            delay = calculate_backoff_delay(
                attempt=attempt,
                use_jitter=False,
                base_delay=1.0
            )
            delays.append(delay)
        
        # Verify exponential growth: [1, 2, 4, 8, 16]
        expected = [1.0, 2.0, 4.0, 8.0, 16.0]
        assert delays == expected
    
    def test_max_delay_prevents_long_waits(self):
        """Max delay should prevent unreasonably long waits."""
        for attempt in range(20):
            delay = calculate_backoff_delay(
                attempt=attempt,
                use_jitter=False,
                max_delay=300.0
            )
            assert delay <= 300.0
    
    def test_jitter_prevents_thundering_herd(self):
        """Jitter should distribute retry timing to prevent thundering herd."""
        # Generate many retry delays for same attempt
        delays = [
            calculate_backoff_delay(attempt=5, use_jitter=True)
            for _ in range(50)
        ]
        
        # Should have good distribution (not all the same value)
        unique_delays = len(set(f"{d:.2f}" for d in delays))  # Round to 2 decimals
        assert unique_delays > 20  # At least 20 different values
