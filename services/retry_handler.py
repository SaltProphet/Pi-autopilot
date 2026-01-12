"""Retry logic with exponential backoff for API calls."""
from typing import Callable, Any, TypeVar
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryHandler:
    """Handle API failures with exponential backoff."""
    
    # Transient exceptions that should trigger retry
    TRANSIENT_EXCEPTIONS = (
        TimeoutError,
        ConnectionError,
        OSError,
    )
    
    # API-specific backoff strategies
    BACKOFF_STRATEGIES = {
        'reddit': {
            'max_attempts': 3,
            'min_wait': 2,
            'max_wait': 30,
            'multiplier': 2,
        },
        'openai': {
            'max_attempts': 4,
            'min_wait': 1,
            'max_wait': 60,
            'multiplier': 2,
        },
        'gumroad': {
            'max_attempts': 3,
            'min_wait': 2,
            'max_wait': 30,
            'multiplier': 2,
        },
    }
    
    def __init__(self):
        """Initialize retry handler."""
        self.retry_stats = {
            'total_attempts': 0,
            'successful_retries': 0,
            'failed_retries': 0,
        }
    
    def with_retry(self, func: Callable[..., T], api_type: str = 'openai', *args, **kwargs) -> T:
        """Execute function with retry logic.
        
        Args:
            func: Function to execute
            api_type: Type of API ('reddit', 'openai', 'gumroad')
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of func execution
        """
        strategy = self.BACKOFF_STRATEGIES.get(api_type, self.BACKOFF_STRATEGIES['openai'])
        
        @retry(
            stop=stop_after_attempt(strategy['max_attempts']),
            wait=wait_exponential(
                multiplier=strategy['multiplier'],
                min=strategy['min_wait'],
                max=strategy['max_wait']
            ),
            retry=retry_if_exception_type(self.TRANSIENT_EXCEPTIONS),
            before_sleep=before_sleep_log(logger, logging.INFO),
            reraise=True
        )
        def _retry_wrapper():
            try:
                self.retry_stats['total_attempts'] += 1
                return func(*args, **kwargs)
            except self.TRANSIENT_EXCEPTIONS as e:
                logger.warning(f"Transient error in {api_type} API call: {e}")
                raise
            except Exception as e:
                logger.error(f"Non-transient error in {api_type} API call: {e}")
                self.retry_stats['failed_retries'] += 1
                raise
        
        try:
            result = _retry_wrapper()
            if self.retry_stats['total_attempts'] > 1:
                self.retry_stats['successful_retries'] += 1
            return result
        except Exception as e:
            logger.error(f"Failed after {strategy['max_attempts']} attempts: {e}")
            raise
    
    def estimate_retry_cost(self, estimated_cost: float, max_attempts: int = 3) -> float:
        """Estimate worst-case token cost including retries.
        
        Args:
            estimated_cost: Base cost estimate (USD)
            max_attempts: Maximum retry attempts
        
        Returns:
            Worst-case cost if all retries occur
        """
        # Worst case: retry cost for each attempt
        return estimated_cost * max_attempts
    
    def get_retry_stats(self) -> dict:
        """Get retry statistics.
        
        Returns:
            Dictionary with retry stats
        """
        success_rate = 0
        if self.retry_stats['total_attempts'] > 0:
            success_rate = (
                (self.retry_stats['total_attempts'] - self.retry_stats['failed_retries']) /
                self.retry_stats['total_attempts']
            ) * 100
        
        return {
            'total_attempts': self.retry_stats['total_attempts'],
            'successful_retries': self.retry_stats['successful_retries'],
            'failed_retries': self.retry_stats['failed_retries'],
            'success_rate': round(success_rate, 2),
        }
    
    def reset_stats(self):
        """Reset retry statistics."""
        self.retry_stats = {
            'total_attempts': 0,
            'successful_retries': 0,
            'failed_retries': 0,
        }
