"""
Basic tests for Pi-Autopilot
"""
import pytest
from agents.db import init_database, get_database_stats
from agents.metrics import MetricsCollector


def test_database_initialization():
    """Test that database initializes without errors."""
    try:
        init_database()
        assert True
    except Exception as e:
        pytest.fail(f"Database initialization failed: {e}")


def test_database_stats():
    """Test that database stats can be retrieved."""
    stats = get_database_stats()
    assert isinstance(stats, dict)
    assert "total_posts" in stats
    assert "total_specs" in stats


def test_metrics_collector():
    """Test metrics collector functionality."""
    metrics = MetricsCollector()
    
    # Test incrementing
    metrics.increment_requests()
    metrics.increment_scrapes()
    
    # Get metrics
    data = metrics.get_metrics()
    
    assert isinstance(data, dict)
    assert "uptime" in data
    assert "api" in data
    assert "operations" in data
    assert data["api"]["total_requests"] >= 1
    assert data["operations"]["scrapes"] >= 1


def test_metrics_uptime():
    """Test uptime calculation."""
    metrics = MetricsCollector()
    uptime = metrics.get_uptime()
    
    assert isinstance(uptime, float)
    assert uptime >= 0
