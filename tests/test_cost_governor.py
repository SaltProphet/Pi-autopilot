"""Tests for cost_governor module."""
import pytest
import sqlite3
import os
import tempfile
from unittest.mock import patch, MagicMock
from services.cost_governor import CostGovernor, CostLimitExceeded


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def cost_governor(temp_db, monkeypatch):
    """Create a CostGovernor instance with test configuration."""
    import config
    
    monkeypatch.setattr(config.settings, 'database_path', temp_db)
    monkeypatch.setattr(config.settings, 'openai_model', 'gpt-4')
    monkeypatch.setattr(config.settings, 'openai_input_token_price', 0.00003)
    monkeypatch.setattr(config.settings, 'openai_output_token_price', 0.00006)
    monkeypatch.setattr(config.settings, 'max_tokens_per_run', 10000)
    monkeypatch.setattr(config.settings, 'max_usd_per_run', 1.0)
    monkeypatch.setattr(config.settings, 'max_usd_lifetime', 5.0)
    monkeypatch.setattr(config.settings, 'artifacts_path', tempfile.gettempdir())
    
    governor = CostGovernor()
    yield governor


@pytest.mark.unit
class TestCostGovernor:
    """Test suite for CostGovernor class."""

    def test_token_estimation(self, cost_governor):
        """Test token estimation accuracy."""
        text = "This is a test string for token estimation."
        tokens = cost_governor.estimate_tokens(text)
        # Should return a positive integer
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_cost_estimation(self, cost_governor):
        """Test cost calculation."""
        input_tokens = 1000
        output_tokens = 500
        cost = cost_governor.estimate_cost(input_tokens, output_tokens)
        
        # Expected: 1000 * 0.00003 + 500 * 0.00006 = 0.03 + 0.03 = 0.06
        expected_cost = 0.06
        assert abs(cost - expected_cost) < 0.0001

    def test_record_usage(self, cost_governor):
        """Test that usage recording updates run totals and database."""
        cost_governor.record_usage(1000, 500)
        
        assert cost_governor.run_tokens_sent == 1000
        assert cost_governor.run_tokens_received == 500
        assert cost_governor.run_cost > 0
        
        # Verify database record
        lifetime_cost = cost_governor.get_lifetime_cost()
        assert lifetime_cost > 0

    def test_per_run_token_limit(self, cost_governor):
        """Test that per-run token limit is enforced."""
        # Try to exceed max_tokens_per_run (10000)
        with pytest.raises(CostLimitExceeded) as exc_info:
            cost_governor.check_limits_before_call(12000, 1000)
        
        assert "MAX_TOKENS_PER_RUN exceeded" in str(exc_info.value)
        assert cost_governor.aborted is True

    def test_per_run_usd_limit(self, cost_governor):
        """Test that per-run USD limit is enforced."""
        # Set cost to near limit
        cost_governor.run_cost = 0.95
        
        # Try to add cost that exceeds max_usd_per_run (1.0)
        with pytest.raises(CostLimitExceeded) as exc_info:
            # This would add ~0.09 USD, exceeding the 1.0 limit
            cost_governor.check_limits_before_call(1000, 1000)
        
        assert "MAX_USD_PER_RUN exceeded" in str(exc_info.value)
        assert cost_governor.aborted is True

    def test_lifetime_usd_limit(self, cost_governor):
        """Test that lifetime USD limit is enforced."""
        # Add historical cost to database
        cost_governor.record_usage(50000, 25000)  # ~4.5 USD
        
        # Try to add cost that would exceed max_usd_lifetime (5.0)
        with pytest.raises(CostLimitExceeded) as exc_info:
            cost_governor.check_limits_before_call(10000, 10000)  # Would add ~0.9 USD
        
        assert "MAX_USD_LIFETIME exceeded" in str(exc_info.value)

    def test_abort_persists_across_calls(self, cost_governor):
        """Test that abort state persists."""
        # Trigger abort
        try:
            cost_governor.check_limits_before_call(12000, 1000)
        except CostLimitExceeded:
            pass
        
        # Subsequent call should also raise
        with pytest.raises(CostLimitExceeded):
            cost_governor.check_limits_before_call(100, 100)

    def test_get_run_stats(self, cost_governor):
        """Test run statistics retrieval."""
        cost_governor.record_usage(1000, 500)
        
        stats = cost_governor.get_run_stats()
        assert stats['run_id'] == cost_governor.run_id
        assert stats['tokens_sent'] == 1000
        assert stats['tokens_received'] == 500
        assert stats['cost_usd'] > 0
        assert stats['aborted'] is False

    def test_abort_creates_file(self, cost_governor):
        """Test that abort creates artifact file."""
        try:
            cost_governor.check_limits_before_call(12000, 1000)
        except CostLimitExceeded:
            pass
        
        # Check that abort file was created
        abort_file = f"{tempfile.gettempdir()}/abort_{cost_governor.run_id}.json"
        assert os.path.exists(abort_file)
        os.unlink(abort_file)

    def test_multiple_recordings(self, cost_governor):
        """Test multiple usage recordings accumulate correctly."""
        cost_governor.record_usage(1000, 500)
        cost_governor.record_usage(500, 250)
        cost_governor.record_usage(750, 375)
        
        assert cost_governor.run_tokens_sent == 2250
        assert cost_governor.run_tokens_received == 1125
        
        # Verify all records in database
        lifetime_cost = cost_governor.get_lifetime_cost()
        expected_cost = cost_governor.estimate_cost(2250, 1125)
        assert abs(lifetime_cost - expected_cost) < 0.0001

    def test_successful_call_within_limits(self, cost_governor):
        """Test that calls within limits succeed."""
        # Should not raise
        cost_governor.check_limits_before_call(100, 100)
        cost_governor.record_usage(100, 100)
        
        # Should still be operational
        assert cost_governor.aborted is False
        cost_governor.check_limits_before_call(100, 100)
