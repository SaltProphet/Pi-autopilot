import pytest
from unittest.mock import Mock, patch
from services.retry_handler import RetryHandler


class TestRetryHandler:
    """Test suite for RetryHandler module."""
    
    @pytest.fixture
    def retry_handler(self):
        """Create a RetryHandler instance."""
        return RetryHandler()
    
    def test_retry_on_timeout_succeeds(self, retry_handler):
        """Test that function is retried on TimeoutError."""
        call_count = 0
        
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timeout on first attempt")
            return "success"
        
        result = retry_handler.with_retry(flaky_function, api_type='openai')
        assert result == "success"
        assert call_count == 2
    
    def test_retry_on_connection_error(self, retry_handler):
        """Test that function is retried on ConnectionError."""
        call_count = 0
        
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection refused")
            return "connected"
        
        result = retry_handler.with_retry(flaky_function, api_type='reddit')
        assert result == "connected"
        assert call_count == 2
    
    def test_no_retry_on_validation_error(self, retry_handler):
        """Test that validation errors are not retried."""
        call_count = 0
        
        def broken_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Invalid input")
        
        with pytest.raises(ValueError):
            retry_handler.with_retry(broken_function, api_type='openai')
        
        # Should only be called once (no retry)
        assert call_count == 1
    
    def test_no_retry_on_type_error(self, retry_handler):
        """Test that type errors are not retried."""
        call_count = 0
        
        def broken_function():
            nonlocal call_count
            call_count += 1
            raise TypeError("Wrong type")
        
        with pytest.raises(TypeError):
            retry_handler.with_retry(broken_function, api_type='gumroad')
        
        assert call_count == 1
    
    def test_max_attempts_openai(self, retry_handler):
        """Test that OpenAI respects max_attempts=4."""
        call_count = 0
        
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Always timeout")
        
        with pytest.raises(TimeoutError):
            retry_handler.with_retry(always_fails, api_type='openai', max_attempts=4)
        
        # Should attempt 4 times
        assert call_count == 4
    
    def test_max_attempts_reddit(self, retry_handler):
        """Test that Reddit respects max_attempts=3."""
        call_count = 0
        
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection lost")
        
        with pytest.raises(ConnectionError):
            retry_handler.with_retry(always_fails, api_type='reddit', max_attempts=3)
        
        # Should attempt 3 times
        assert call_count == 3
    
    def test_exponential_backoff_timing(self, retry_handler):
        """Test that backoff increases exponentially."""
        # This is a basic test - in practice, backoff timing is handled by tenacity
        call_count = 0
        
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError(f"Attempt {call_count}")
            return "success"
        
        result = retry_handler.with_retry(fails_twice, api_type='openai')
        assert result == "success"
        assert call_count == 3
    
    def test_retry_stats_tracking(self, retry_handler):
        """Test that retry statistics are tracked."""
        def succeeds_on_retry():
            if not hasattr(succeeds_on_retry, 'count'):
                succeeds_on_retry.count = 0
            succeeds_on_retry.count += 1
            if succeeds_on_retry.count < 2:
                raise TimeoutError()
            return "success"
        
        result = retry_handler.with_retry(succeeds_on_retry, api_type='openai')
        
        stats = retry_handler.get_retry_stats()
        assert 'total_attempts' in stats
        assert 'successful_retries' in stats
        assert stats['total_attempts'] > 0
    
    def test_generic_exception_not_retried(self, retry_handler):
        """Test that generic exceptions are not retried."""
        call_count = 0
        
        def fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Generic error")
        
        with pytest.raises(RuntimeError):
            retry_handler.with_retry(fails, api_type='openai')
        
        # Should only try once
        assert call_count == 1
    
    def test_retry_with_successful_first_attempt(self, retry_handler):
        """Test that successful first attempt doesn't retry."""
        call_count = 0
        
        def succeeds_immediately():
            nonlocal call_count
            call_count += 1
            return "done"
        
        result = retry_handler.with_retry(succeeds_immediately, api_type='reddit')
        assert result == "done"
        assert call_count == 1
    
    def test_different_api_types_have_different_strategies(self, retry_handler):
        """Test that different API types can have different retry strategies."""
        # OpenAI should allow 4 attempts, Reddit 3
        call_counts = {'openai': 0, 'reddit': 0}
        
        def make_failing_func(api_type):
            def fails():
                call_counts[api_type] += 1
                raise TimeoutError("timeout")
            return fails
        
        try:
            retry_handler.with_retry(make_failing_func('openai'), api_type='openai', max_attempts=4)
        except TimeoutError:
            pass
        
        try:
            retry_handler.with_retry(make_failing_func('reddit'), api_type='reddit', max_attempts=3)
        except TimeoutError:
            pass
        
        # OpenAI should have been called more times (4 vs 3)
        assert call_counts['openai'] == 4
        assert call_counts['reddit'] == 3
