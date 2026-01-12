"""Tests for Reddit and Gumroad clients and config."""
import pytest
from unittest.mock import Mock, MagicMock, patch
import os
import tempfile


@pytest.mark.unit
class TestRedditClient:
    """Test suite for RedditClient class."""

    @patch('services.reddit_client.praw.Reddit')
    def test_reddit_client_initialization(self, mock_praw):
        """Test RedditClient initialization."""
        from services.reddit_client import RedditClient
        
        client = RedditClient()
        
        mock_praw.assert_called_once()
        assert client.reddit is not None

    @patch('services.reddit_client.praw.Reddit')
    def test_fetch_posts_filters_by_score(self, mock_praw):
        """Test that fetch_posts filters by minimum score."""
        from services.reddit_client import RedditClient
        
        # Create mock submissions
        mock_submission_high = Mock()
        mock_submission_high.id = "high1"
        mock_submission_high.title = "High Score Post"
        mock_submission_high.selftext = "Content"
        mock_submission_high.author = "user1"
        mock_submission_high.score = 50
        mock_submission_high.url = "https://reddit.com/high"
        mock_submission_high.created_utc = 1234567890
        mock_submission_high.num_comments = 10
        
        mock_submission_low = Mock()
        mock_submission_low.score = 5
        
        # Setup mock subreddit
        mock_subreddit = Mock()
        mock_subreddit.hot.return_value = [mock_submission_high, mock_submission_low]
        
        mock_reddit = Mock()
        mock_reddit.subreddit.return_value = mock_subreddit
        mock_praw.return_value = mock_reddit
        
        client = RedditClient()
        posts = client.fetch_posts("test", limit=10, min_score=10)
        
        # Should only include high score post
        assert len(posts) == 1
        assert posts[0]["score"] == 50

    @patch('services.reddit_client.praw.Reddit')
    def test_fetch_posts_structure(self, mock_praw):
        """Test that fetch_posts returns correct data structure."""
        from services.reddit_client import RedditClient
        
        mock_submission = Mock()
        mock_submission.id = "test123"
        mock_submission.title = "Test Title"
        mock_submission.selftext = "Test body"
        mock_submission.author = "testuser"
        mock_submission.score = 100
        mock_submission.url = "https://reddit.com/test"
        mock_submission.created_utc = 1234567890.5
        mock_submission.num_comments = 25
        
        mock_subreddit = Mock()
        mock_subreddit.hot.return_value = [mock_submission]
        
        mock_reddit = Mock()
        mock_reddit.subreddit.return_value = mock_subreddit
        mock_praw.return_value = mock_reddit
        
        client = RedditClient()
        posts = client.fetch_posts("testsubreddit", limit=5, min_score=10)
        
        assert len(posts) == 1
        post = posts[0]
        assert post["id"] == "test123"
        assert post["title"] == "Test Title"
        assert post["body"] == "Test body"
        assert post["author"] == "testuser"
        assert post["score"] == 100
        assert post["subreddit"] == "testsubreddit"
        assert post["timestamp"] == 1234567890
        assert post["num_comments"] == 25


@pytest.mark.unit
class TestGumroadClient:
    """Test suite for GumroadClient class."""

    @patch('services.gumroad_client.requests')
    def test_gumroad_client_initialization(self, mock_requests):
        """Test GumroadClient initialization."""
        from services.gumroad_client import GumroadClient
        
        client = GumroadClient()
        
        assert client.base_url == "https://api.gumroad.com/v2"
        assert client.access_token is not None

    @patch('services.gumroad_client.requests')
    def test_create_product_success(self, mock_requests):
        """Test successful product creation."""
        from services.gumroad_client import GumroadClient
        
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "product": {
                "id": "prod123",
                "name": "Test Product",
                "short_url": "https://gum.co/test"
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response
        
        client = GumroadClient()
        result = client.create_product(
            name="Test Product",
            description="Test description",
            price_cents=2999
        )
        
        assert result is not None
        assert result["id"] == "prod123"
        assert result["name"] == "Test Product"

    @patch('services.gumroad_client.requests')
    def test_create_product_with_permalink(self, mock_requests):
        """Test product creation with custom permalink."""
        from services.gumroad_client import GumroadClient
        
        mock_response = Mock()
        mock_response.json.return_value = {"success": True, "product": {"id": "prod123"}}
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response
        
        client = GumroadClient()
        client.create_product(
            name="Product",
            description="Desc",
            price_cents=1999,
            custom_permalink="custom-link"
        )
        
        # Verify custom_permalink was passed
        call_args = mock_requests.post.call_args
        assert "custom_permalink" in call_args[1]["data"]

    @patch('services.gumroad_client.requests')
    def test_create_product_invalid_price(self, mock_requests):
        """Test that invalid price raises ValueError."""
        from services.gumroad_client import GumroadClient
        
        client = GumroadClient()
        
        with pytest.raises(ValueError):
            client.create_product("Product", "Desc", price_cents=-100)
        
        with pytest.raises(ValueError):
            client.create_product("Product", "Desc", price_cents=0)

    @patch('services.gumroad_client.requests')
    def test_create_product_api_failure(self, mock_requests):
        """Test handling of API failures."""
        from services.gumroad_client import GumroadClient
        
        # Setup mock response with success=False
        mock_response = Mock()
        mock_response.json.return_value = {"success": False}
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response
        
        client = GumroadClient()
        result = client.create_product("Product", "Desc", price_cents=2999)
        
        assert result is None


@pytest.mark.unit
class TestConfig:
    """Test suite for configuration."""

    def test_settings_defaults(self):
        """Test that settings have correct default values."""
        from config import Settings
        
        # Create settings without env file
        with patch.dict(os.environ, {
            'REDDIT_CLIENT_ID': 'test_id',
            'REDDIT_CLIENT_SECRET': 'test_secret',
            'OPENAI_API_KEY': 'test_key',
            'GUMROAD_ACCESS_TOKEN': 'test_token'
        }, clear=True):
            settings = Settings()
            
            assert settings.reddit_user_agent == "Pi-Autopilot/2.0"
            assert settings.openai_model == "gpt-4"
            assert settings.database_path == "./data/pipeline.db"
            assert settings.artifacts_path == "./data/artifacts"
            assert settings.reddit_min_score == 10
            assert settings.reddit_post_limit == 20
            assert settings.max_regeneration_attempts == 1
            assert settings.max_tokens_per_run == 50000
            assert settings.max_usd_per_run == 5.0
            assert settings.max_usd_lifetime == 100.0
            assert settings.kill_switch is False

    def test_settings_from_env(self):
        """Test that settings can be loaded from environment."""
        from config import Settings
        
        with patch.dict(os.environ, {
            'REDDIT_CLIENT_ID': 'custom_id',
            'REDDIT_CLIENT_SECRET': 'custom_secret',
            'REDDIT_USER_AGENT': 'Custom/1.0',
            'OPENAI_API_KEY': 'custom_key',
            'OPENAI_MODEL': 'gpt-4-turbo',
            'GUMROAD_ACCESS_TOKEN': 'custom_token',
            'MAX_USD_PER_RUN': '10.0',
            'KILL_SWITCH': 'true'
        }, clear=True):
            settings = Settings()
            
            assert settings.reddit_client_id == 'custom_id'
            assert settings.reddit_user_agent == 'Custom/1.0'
            assert settings.openai_model == 'gpt-4-turbo'
            assert settings.max_usd_per_run == 10.0
            assert settings.kill_switch is True

    def test_settings_case_insensitive(self):
        """Test that settings are case insensitive."""
        from config import Settings
        
        with patch.dict(os.environ, {
            'reddit_client_id': 'lowercase_id',
            'REDDIT_CLIENT_SECRET': 'UPPERCASE_SECRET',
            'Reddit_User_Agent': 'MixedCase/1.0',
            'OPENAI_API_KEY': 'key',
            'GUMROAD_ACCESS_TOKEN': 'token'
        }, clear=True):
            settings = Settings()
            
            assert settings.reddit_client_id == 'lowercase_id'
            assert settings.reddit_client_secret == 'UPPERCASE_SECRET'
            assert settings.reddit_user_agent == 'MixedCase/1.0'
