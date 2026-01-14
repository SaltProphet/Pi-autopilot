"""Tests for dashboard configuration fields in Settings model."""

import pytest
from unittest.mock import patch, MagicMock
import os
import importlib


@pytest.fixture
def mock_env_with_required_fields(monkeypatch):
    """Fixture to set up minimal required environment variables for Settings."""
    monkeypatch.setenv('SKIP_CONFIG_VALIDATION', 'true')
    monkeypatch.setenv('REDDIT_CLIENT_ID', 'test_reddit_id')
    monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'test_reddit_secret')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-abc123')
    monkeypatch.setenv('GUMROAD_ACCESS_TOKEN', 'test_gumroad_token')
    return monkeypatch


def reload_config():
    """Helper to reload config module to pick up environment changes."""
    import config
    importlib.reload(config)
    return config


class TestDashboardConfigFields:
    """Test suite for dashboard configuration fields in Settings model."""
    
    @pytest.mark.unit
    def test_dashboard_password_field_exists(self, mock_env_with_required_fields):
        """Test that dashboard_password field exists in Settings."""
        config = reload_config()
        
        # Should have dashboard_password attribute
        assert hasattr(config.settings, 'dashboard_password')
        # Default should be empty string
        assert isinstance(config.settings.dashboard_password, str)
    
    @pytest.mark.unit
    def test_dashboard_allowed_ips_field_exists(self, mock_env_with_required_fields):
        """Test that dashboard_allowed_ips field exists in Settings."""
        config = reload_config()
        
        # Should have dashboard_allowed_ips attribute
        assert hasattr(config.settings, 'dashboard_allowed_ips')
        # Default should be "127.0.0.1"
        assert isinstance(config.settings.dashboard_allowed_ips, str)
    
    @pytest.mark.unit
    def test_dashboard_fields_with_env_vars(self, mock_env_with_required_fields):
        """Test that dashboard fields load from environment variables."""
        # Set dashboard-specific environment variables
        mock_env_with_required_fields.setenv('DASHBOARD_PASSWORD', 'test_password_123')
        mock_env_with_required_fields.setenv('DASHBOARD_ALLOWED_IPS', '192.168.1.1,127.0.0.1')
        
        config = reload_config()
        
        # Should load the environment variables
        assert config.settings.dashboard_password == 'test_password_123'
        assert config.settings.dashboard_allowed_ips == '192.168.1.1,127.0.0.1'
    
    @pytest.mark.unit
    def test_dashboard_fields_default_values(self, mock_env_with_required_fields):
        """Test that dashboard fields have correct default values."""
        # Don't set DASHBOARD_PASSWORD or DASHBOARD_ALLOWED_IPS
        config = reload_config()
        
        # Should use default values from Settings class
        assert config.settings.dashboard_password == ""
        assert config.settings.dashboard_allowed_ips == "127.0.0.1"
    
    @pytest.mark.unit
    def test_no_pydantic_extra_forbidden_error(self, mock_env_with_required_fields):
        """Test that Pydantic doesn't raise extra_forbidden error for dashboard fields."""
        # Set dashboard fields in addition to required fields
        mock_env_with_required_fields.setenv('DASHBOARD_PASSWORD', 'test_password')
        mock_env_with_required_fields.setenv('DASHBOARD_ALLOWED_IPS', '0.0.0.0')
        
        # Should not raise any Pydantic validation error
        try:
            config = reload_config()
            # If we get here, no exception was raised
            assert True
        except Exception as e:
            # Should not get a validation error about extra inputs
            assert "extra_forbidden" not in str(e)
            assert "Extra inputs are not permitted" not in str(e)
            # Re-raise if it's a different error
            if "extra" in str(e).lower():
                raise
