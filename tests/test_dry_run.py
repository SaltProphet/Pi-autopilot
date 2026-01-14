"""Tests for dry run mode functionality."""

import pytest
from unittest.mock import patch, MagicMock


class TestDryRunMode:
    """Test dry run mode configuration and behavior."""
    
    @pytest.mark.unit
    def test_dry_run_enabled_skips_api_call(self):
        """Test that dry run mode returns mock data without making API calls."""
        # Import here to avoid config loading at module level
        from services.gumroad_client import GumroadClient
        
        # Mock settings with dry_run enabled
        mock_settings = MagicMock()
        mock_settings.dry_run = True
        mock_settings.gumroad_access_token = "test_token"
        
        with patch('services.gumroad_client.settings', mock_settings):
            client = GumroadClient()
            assert client.dry_run is True
            
            # Make product creation call
            result = client.create_product(
                name="Test Product",
                description="Test Description",
                price_cents=1000
            )
            
            # Should return mock product data
            assert result is not None
            assert "id" in result
            assert "short_url" in result
            assert result["id"].startswith("dry_run_product_")
            assert "dry-run" in result["short_url"]
            assert result["price"] == 1000
    
    @pytest.mark.unit
    def test_dry_run_disabled_allows_api_call(self):
        """Test that with dry_run=False, API calls are attempted."""
        # Import here to avoid config loading at module level
        from services.gumroad_client import GumroadClient
        
        # Mock settings with dry_run disabled
        mock_settings = MagicMock()
        mock_settings.dry_run = False
        mock_settings.gumroad_access_token = "test_token"
        
        with patch('services.gumroad_client.settings', mock_settings):
            client = GumroadClient()
            assert client.dry_run is False
            
            # Mock the actual API call
            with patch('services.gumroad_client.requests.post') as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "success": True,
                    "product": {
                        "id": "real_product_id",
                        "short_url": "https://gumroad.com/l/test"
                    }
                }
                mock_post.return_value = mock_response
                
                result = client.create_product(
                    name="Test Product",
                    description="Test Description",
                    price_cents=1000
                )
                
                # Should have called the API
                assert mock_post.called
                assert result is not None
                assert result["id"] == "real_product_id"
    
    @pytest.mark.unit
    def test_dry_run_sales_fetch_returns_empty(self):
        """Test that dry run mode returns empty sales data."""
        # Import here to avoid config loading at module level
        from services.gumroad_client import GumroadClient
        
        # Mock settings with dry_run enabled
        mock_settings = MagicMock()
        mock_settings.dry_run = True
        mock_settings.gumroad_access_token = "test_token"
        
        with patch('services.gumroad_client.settings', mock_settings):
            client = GumroadClient()
            
            # Fetch sales data in dry run mode
            sales_data = client.fetch_sales_data()
            
            # Should return empty list without making API call
            assert sales_data == []

