"""Tests for sales feedback service."""
import pytest
import tempfile
import os
import time
from unittest.mock import Mock, patch
from services.sales_feedback import SalesFeedback
from services.storage import Storage
from services.gumroad_client import GumroadClient


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def storage(temp_db, monkeypatch):
    """Create a Storage instance with test database."""
    import config
    monkeypatch.setattr(config.settings, 'database_path', temp_db)
    return Storage()


@pytest.mark.unit
class TestSalesFeedback:
    """Test suite for SalesFeedback service."""
    
    def test_ingest_sales_data_success(self, storage, monkeypatch):
        """Test successful sales data ingestion."""
        # Mock Gumroad client
        mock_gumroad = Mock(spec=GumroadClient)
        mock_gumroad.fetch_sales_data.return_value = [
            {
                "product_id": "prod1",
                "product_name": "Test Product 1",
                "sales_count": 5,
                "revenue_cents": 5000,
                "views": 100,
                "refunds": 0
            },
            {
                "product_id": "prod2",
                "product_name": "Test Product 2",
                "sales_count": 0,
                "revenue_cents": 0,
                "views": 50,
                "refunds": 0
            }
        ]
        
        sales_feedback = SalesFeedback(storage, mock_gumroad)
        result = sales_feedback.ingest_sales_data()
        
        assert result["success"] is True
        assert result["products_ingested"] == 2
        assert result["timestamp"] > 0
    
    def test_ingest_sales_data_failure(self, storage, monkeypatch):
        """Test sales data ingestion when fetch fails."""
        mock_gumroad = Mock(spec=GumroadClient)
        mock_gumroad.fetch_sales_data.return_value = []
        
        sales_feedback = SalesFeedback(storage, mock_gumroad)
        result = sales_feedback.ingest_sales_data()
        
        assert result["success"] is False
        assert result["products_ingested"] == 0
    
    def test_generate_feedback_summary_with_data(self, storage, monkeypatch):
        """Test feedback summary generation with sales data."""
        import config
        monkeypatch.setattr(config.settings, 'sales_lookback_days', 30)
        
        # Add test sales data
        current_time = int(time.time())
        storage.save_sales_metrics("prod1", "Product 1", 10, 10000, 200, 1, current_time)
        storage.save_sales_metrics("prod2", "Product 2", 0, 0, 50, 0, current_time)
        storage.save_sales_metrics("prod3", "Product 3", 5, 5000, 100, 0, current_time)
        
        # Add uploaded products
        storage.save_post({
            "id": "post1",
            "title": "Test Post 1",
            "body": "Content",
            "timestamp": current_time,
            "subreddit": "test",
            "author": "user",
            "score": 50,
            "url": "http://test.com"
        })
        storage.log_pipeline_run("post1", "gumroad_upload", "completed", "/path/to/artifact")
        
        sales_feedback = SalesFeedback(storage)
        summary = sales_feedback.generate_feedback_summary(lookback_days=30)
        
        assert summary["products_sold"] == 2
        assert summary["zero_sale_products"] == 1
        assert summary["total_sales"] == 15
        assert summary["total_revenue_cents"] == 15000
        assert summary["refund_rate"] == pytest.approx(1/15, 0.01)
    
    def test_generate_feedback_summary_no_data(self, storage):
        """Test feedback summary with no sales data."""
        sales_feedback = SalesFeedback(storage)
        summary = sales_feedback.generate_feedback_summary(lookback_days=30)
        
        assert summary["products_sold"] == 0
        assert summary["zero_sale_products"] == 0
        assert summary["total_sales"] == 0
        assert summary["refund_rate"] == 0.0
    
    def test_get_top_performing_categories(self, storage):
        """Test retrieval of top-performing categories."""
        current_time = int(time.time())
        storage.save_sales_metrics("prod1", "AI Tools", 20, 20000, 500, 0, current_time)
        storage.save_sales_metrics("prod2", "Marketing Guide", 15, 15000, 300, 0, current_time)
        storage.save_sales_metrics("prod3", "Code Template", 10, 10000, 200, 0, current_time)
        storage.save_sales_metrics("prod4", "Zero Sales", 0, 0, 50, 0, current_time)
        
        sales_feedback = SalesFeedback(storage)
        top_categories = sales_feedback.get_top_performing_categories(lookback_days=30, limit=2)
        
        assert len(top_categories) == 2
        assert top_categories[0] == "AI Tools"
        assert top_categories[1] == "Marketing Guide"
    
    def test_get_zero_sale_categories(self, storage):
        """Test retrieval of zero-sale categories."""
        current_time = int(time.time())
        storage.save_sales_metrics("prod1", "Good Product", 10, 10000, 200, 0, current_time)
        storage.save_sales_metrics("prod2", "Zero Sale 1", 0, 0, 50, 0, current_time)
        storage.save_sales_metrics("prod3", "Zero Sale 2", 0, 0, 30, 0, current_time)
        
        sales_feedback = SalesFeedback(storage)
        zero_categories = sales_feedback.get_zero_sale_categories(lookback_days=30)
        
        assert len(zero_categories) == 2
        assert "Zero Sale 1" in zero_categories
        assert "Zero Sale 2" in zero_categories
    
    def test_should_suppress_publishing_zero_sales(self, storage, monkeypatch):
        """Test publishing suppression due to consecutive zero sales."""
        import config
        monkeypatch.setattr(config.settings, 'zero_sales_suppression_count', 3)
        monkeypatch.setattr(config.settings, 'sales_lookback_days', 30)
        
        current_time = int(time.time())
        
        # Create 3 recent uploaded products with zero sales
        for i in range(3):
            post_id = f"post{i}"
            storage.save_post({
                "id": post_id,
                "title": f"Test Post {i}",
                "body": "Content",
                "timestamp": current_time - (i * 1000),
                "subreddit": "test",
                "author": "user",
                "score": 50,
                "url": f"http://test{i}.com"
            })
            storage.log_pipeline_run(post_id, "gumroad_upload", "completed", "/path")
            storage.save_sales_metrics(f"prod{i}", f"Product {i}", 0, 0, 50, 0, current_time)
        
        sales_feedback = SalesFeedback(storage)
        result = sales_feedback.should_suppress_publishing()
        
        assert result["suppress"] is True
        assert "zero sales" in result["reason"].lower()
    
    def test_should_suppress_publishing_high_refund_rate(self, storage, monkeypatch):
        """Test publishing suppression due to high refund rate."""
        import config
        monkeypatch.setattr(config.settings, 'refund_rate_max', 0.3)
        monkeypatch.setattr(config.settings, 'sales_lookback_days', 30)
        monkeypatch.setattr(config.settings, 'zero_sales_suppression_count', 3)
        
        current_time = int(time.time())
        
        # Create an uploaded product
        storage.save_post({
            "id": "post1",
            "title": "Test Post",
            "body": "Content",
            "timestamp": current_time,
            "subreddit": "test",
            "author": "user",
            "score": 50,
            "url": "http://test.com"
        })
        storage.log_pipeline_run("post1", "gumroad_upload", "completed", "/path")
        
        # Create products with high refund rate (5 refunds out of 10 sales = 50%)
        storage.save_sales_metrics("prod1", "Product 1", 10, 10000, 200, 5, current_time)
        
        sales_feedback = SalesFeedback(storage)
        result = sales_feedback.should_suppress_publishing()
        
        assert result["suppress"] is True
        assert "refund" in result["reason"].lower()
    
    def test_should_not_suppress_publishing_normal_performance(self, storage, monkeypatch):
        """Test that publishing is not suppressed with normal performance."""
        import config
        monkeypatch.setattr(config.settings, 'zero_sales_suppression_count', 3)
        monkeypatch.setattr(config.settings, 'refund_rate_max', 0.3)
        monkeypatch.setattr(config.settings, 'sales_lookback_days', 30)
        
        current_time = int(time.time())
        
        # Create products with good performance
        storage.save_post({
            "id": "post1",
            "title": "Test Post",
            "body": "Content",
            "timestamp": current_time,
            "subreddit": "test",
            "author": "user",
            "score": 50,
            "url": "http://test.com"
        })
        storage.log_pipeline_run("post1", "gumroad_upload", "completed", "/path")
        storage.save_sales_metrics("prod1", "Product 1", 10, 10000, 200, 1, current_time)
        
        sales_feedback = SalesFeedback(storage)
        result = sales_feedback.should_suppress_publishing()
        
        assert result["suppress"] is False
        assert result["reason"] == ""
    
    def test_should_not_suppress_publishing_no_products(self, storage):
        """Test that publishing is not suppressed when no products exist."""
        sales_feedback = SalesFeedback(storage)
        result = sales_feedback.should_suppress_publishing()
        
        assert result["suppress"] is False
        assert result["reason"] == ""
