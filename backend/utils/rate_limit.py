"""Rate limiting utilities for API connectors.

Handles rate limit responses and automatically retries with exponential backoff and jitter.
"""

import time
import logging
import random
from typing import Optional, Callable, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and retries are exhausted."""
    pass


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 300.0,
    use_jitter: bool = True
) -> float:
    """Calculate exponential backoff delay with optional jitter.
    
    Implements: delay = min(base_delay * (2 ^ attempt) + jitter, max_delay)
    
    Args:
        attempt: Retry attempt number (0-indexed)
        base_delay: Initial delay in seconds (default: 1s)
        max_delay: Maximum delay cap in seconds (default: 5 minutes)
        use_jitter: Add random jitter to prevent thundering herd (default: True)
        
    Returns:
        Delay in seconds before retry
        
    Example:
        >>> calculate_backoff_delay(0)  # First retry: ~1s + jitter
        >>> calculate_backoff_delay(1)  # Second retry: ~2s + jitter
        >>> calculate_backoff_delay(5)  # Capped at 300s
    """
    exponential_delay = base_delay * (2 ** attempt)
    capped_delay = min(exponential_delay, max_delay)
    
    if use_jitter:
        # Add jitter: random value between 0 and capped_delay
        jitter = random.uniform(0, capped_delay)
        final_delay = capped_delay + jitter
    else:
        final_delay = capped_delay
    
    return final_delay


def handle_rate_limit(
    error_response: dict,
    attempt: int,
    retry_delay: Optional[float] = None,
    api_provided_delay: Optional[float] = None,
) -> float:
    """Extract and respect rate limit information from API response.
    
    Priority:
    1. User-configured retry_delay (if provided)
    2. API-provided Retry-After header
    3. Exponential backoff with jitter
    
    Args:
        error_response: Response headers or body containing rate limit info
        attempt: Current retry attempt (0-indexed)
        retry_delay: User-configured retry delay (overrides everything)
        api_provided_delay: Server-provided retry-after delay
        
    Returns:
        Delay in seconds before retry
    """
    # Priority 1: User override
    if retry_delay is not None:
        logger.warning(f"Rate limited. Retrying in {retry_delay}s (user-configured)")
        return retry_delay
    
    # Priority 2: API-provided delay (Retry-After header)
    if api_provided_delay is not None:
        logger.warning(f"Rate limited. Retrying in {api_provided_delay}s (API-provided)")
        return api_provided_delay
    
    # Priority 3: Exponential backoff with jitter
    delay = calculate_backoff_delay(attempt, base_delay=1.0, max_delay=300.0)
    logger.warning(f"Rate limited. Retrying in {delay:.1f}s (exponential backoff with jitter)")
    return delay


def with_rate_limit_handling(
    max_retries: int = 3,
    retry_delay: Optional[float] = None,
    error_key: str = "status_code"
):
    """Decorator for functions that may encounter rate limiting.
    
    Automatically retries on 429 responses with configurable delays.
    
    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Fixed delay override (ignores API-provided delay)
        error_key: Key to check for status code in response
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if it's a rate limit error (429)
                    if hasattr(e, 'status_code') and e.status_code == 429:
                        last_exception = e
                        if attempt < max_retries:
                            delay = handle_rate_limit(
                                getattr(e, '__dict__', {}),
                                retry_delay=retry_delay,
                                max_retries=max_retries - attempt
                            )
                            time.sleep(delay)
                            continue
                    raise
            
            if last_exception:
                raise RateLimitExceeded(
                    f"Rate limit exceeded after {max_retries} retries"
                ) from last_exception
            raise
        
        return wrapper
    return decorator
