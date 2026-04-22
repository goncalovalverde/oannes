"""Rate limiting utilities for API connectors.

Handles rate limit responses and automatically retries with configurable delays.
"""

import time
import logging
from typing import Optional, Callable, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and retries are exhausted."""
    pass


def handle_rate_limit(
    error_response: dict,
    retry_delay: Optional[float] = None,
    max_retries: int = 3
) -> float:
    """Extract and respect rate limit information from API response.
    
    Args:
        error_response: Response headers or body containing rate limit info
        retry_delay: User-configured retry delay (overrides API suggestion)
        max_retries: Maximum number of retries
        
    Returns:
        Delay in seconds before retry
        
    Raises:
        RateLimitExceeded: If max retries exceeded
    """
    if retry_delay is not None:
        logger.warning(f"Rate limited. Retrying in {retry_delay}s (user-configured)")
        return retry_delay
    
    # Extract delay from Jira rate limit header
    # Example: "Request should be retried after 7 seconds"
    if isinstance(error_response, dict):
        if "retry_after" in error_response:
            delay = float(error_response["retry_after"])
            logger.warning(f"Rate limited. Retrying in {delay}s (API-provided)")
            return delay
    
    # Default exponential backoff: 2s, 4s, 8s
    delay = min(2 ** (max_retries - 1), 30)  # Cap at 30s
    logger.warning(f"Rate limited. Retrying in {delay}s (exponential backoff)")
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
