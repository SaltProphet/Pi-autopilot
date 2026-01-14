"""Tests for dashboard configuration fields in Settings model."""

import pytest
from unittest.mock import patch, MagicMock
import os


class TestDashboardConfigFields:
    """Test suite for dashboard configuration fields in Settings model."""
    
    @pytest.mark.unit
    def test_dashboard_password_field_exists(self, monkeypatch):
        """Test that dashboard_password field exists in Settings."""
        # Set required env vars to allow Settings to load
        monkeypatch.setenv('SKIP_CONFIG_VALIDATION', 'true')
        monkeypatch.setenv('REDDIT_CLIENT_ID', 'test_id')
        monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'test_secret')
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
        monkeypatch.setenv('GUMROAD_ACCESS_TOKEN', 'test_token')
        
        import importlib
        import config
        importlib.reload(config)
        
        # Should have dashboard_password attribute
        assert hasattr(config.settings, 'dashboard_password')
        # Default should be empty string
        assert isinstance(config.settings.dashboard_password, str)
    
    @pytest.mark.unit
    def test_dashboard_allowed_ips_field_exists(self, monkeypatch):
        """Test that dashboard_allowed_ips field exists in Settings."""
        # Set required env vars to allow Settings to load
        monkeypatch.setenv('SKIP_CONFIG_VALIDATION', 'true')
        monkeypatch.setenv('REDDIT_CLIENT_ID', 'test_id')
        monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'test_secret')
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
        monkeypatch.setenv('GUMROAD_ACCESS_TOKEN', 'test_token')
        
        import importlib
        import config
        importlib.reload(config)
        
        # Should have dashboard_allowed_ips attribute
        assert hasattr(config.settings, 'dashboard_allowed_ips')
        # Default should be "127.0.0.1"
        assert isinstance(config.settings.dashboard_allowed_ips, str)
    
    @pytest.mark.unit
    def test_dashboard_fields_with_env_vars(self, monkeypatch):
        """Test that dashboard fields load from environment variables."""
        # Set environment variables
        monkeypatch.setenv('DASHBOARD_PASSWORD', 'test_password_123')
        monkeypatch.setenv('DASHBOARD_ALLOWED_IPS', '192.168.1.1,127.0.0.1')
        monkeypatch.setenv('SKIP_CONFIG_VALIDATION', 'true')
        
        # Required fields to prevent validation errors
        monkeypatch.setenv('REDDIT_CLIENT_ID', 'test_reddit_id')
        monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'test_reddit_secret')
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-abc123')
        monkeypatch.setenv('GUMROAD_ACCESS_TOKEN', 'test_gumroad_token')
        
        # Re-import settings to pick up new env vars
        import importlib
        import config
        importlib.reload(config)
        
        # Should load the environment variables
        assert config.settings.dashboard_password == 'test_password_123'
        assert config.settings.dashboard_allowed_ips == '192.168.1.1,127.0.0.1'
    
    @pytest.mark.unit
    def test_dashboard_fields_default_values(self, monkeypatch):
        """Test that dashboard fields have correct default values."""
        # Don't set DASHBOARD_PASSWORD or DASHBOARD_ALLOWED_IPS
        # but set required fields
        monkeypatch.setenv('SKIP_CONFIG_VALIDATION', 'true')
        monkeypatch.setenv('REDDIT_CLIENT_ID', 'test_reddit_id')
        monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'test_reddit_secret')
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-abc123')
        monkeypatch.setenv('GUMROAD_ACCESS_TOKEN', 'test_gumroad_token')
        
        # Re-import settings
        import importlib
        import config
        importlib.reload(config)
        
        # Should use default values from Settings class
        assert config.settings.dashboard_password == ""
        assert config.settings.dashboard_allowed_ips == "127.0.0.1"
    
    @pytest.mark.unit
    def test_no_pydantic_extra_forbidden_error(self, monkeypatch):
        """Test that Pydantic doesn't raise extra_forbidden error for dashboard fields."""
        # Set all required env vars plus dashboard fields
        monkeypatch.setenv('SKIP_CONFIG_VALIDATION', 'true')
        monkeypatch.setenv('REDDIT_CLIENT_ID', 'test_reddit_id')
        monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'test_reddit_secret')
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-key-abc123')
        monkeypatch.setenv('GUMROAD_ACCESS_TOKEN', 'test_gumroad_token')
        monkeypatch.setenv('DASHBOARD_PASSWORD', 'test_password')
        monkeypatch.setenv('DASHBOARD_ALLOWED_IPS', '0.0.0.0')
        
        # Should not raise any Pydantic validation error
        try:
            import importlib
            import config
            importlib.reload(config)
            # If we get here, no exception was raised
            assert True
        except Exception as e:
            # Should not get a validation error about extra inputs
            assert "extra_forbidden" not in str(e)
            assert "Extra inputs are not permitted" not in str(e)
            # Re-raise if it's a different error
            if "extra" in str(e).lower():
                raise
