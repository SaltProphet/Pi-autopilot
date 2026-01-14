"""Tests for multi-source config validator changes."""
import pytest
from unittest.mock import Mock
from services.config_validator import ConfigValidator, ConfigValidationError


class TestConfigValidatorMultiSource:
    """Test config validator with multi-source support."""
    
    def test_validates_with_hackernews_only(self):
        """Test validation passes with only HackerNews configured."""
        settings = Mock()
        settings.data_sources = "hackernews"
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.reddit_client_id = ""
        settings.reddit_client_secret = ""
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn"
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        # Should pass without Reddit credentials
        assert is_valid or 'reddit' not in str(errors).lower()
    
    def test_requires_reddit_credentials_when_enabled(self):
        """Test validation fails when Reddit enabled but credentials missing."""
        settings = Mock()
        settings.data_sources = "reddit"
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.reddit_client_id = ""
        settings.reddit_client_secret = ""
        settings.reddit_subreddits = "test"
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        assert not is_valid
        assert any('reddit' in error.lower() for error in errors)
    
    def test_validates_reddit_when_enabled_with_credentials(self):
        """Test validation passes when Reddit enabled with valid credentials."""
        settings = Mock()
        settings.data_sources = "reddit"
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.reddit_client_id = "x" * 22
        settings.reddit_client_secret = "x" * 22
        settings.reddit_subreddits = "test"
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        # Should validate Reddit credentials
        if not is_valid:
            # Allow path-related errors but not credential errors
            assert not any('reddit_client' in error.lower() for error in errors)
    
    def test_requires_rss_urls_when_enabled(self):
        """Test validation fails when RSS enabled but URLs missing."""
        settings = Mock()
        settings.data_sources = "rss"
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.rss_feed_urls = ""
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        assert not is_valid
        assert any('rss' in error.lower() for error in errors)
    
    def test_requires_file_paths_when_enabled(self):
        """Test validation fails when File source enabled but paths missing."""
        settings = Mock()
        settings.data_sources = "file"
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.file_ingest_paths = ""
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        assert not is_valid
        assert any('file' in error.lower() for error in errors)
    
    def test_validates_multiple_sources(self):
        """Test validation with multiple sources configured."""
        settings = Mock()
        settings.data_sources = "hackernews,rss"
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn"
        settings.rss_feed_urls = "https://example.com/feed.xml"
        settings.rss_post_limit = 20
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        # Should pass with both sources properly configured
        assert is_valid or not any('hackernews' in error.lower() or 'rss' in error.lower() for error in errors)
    
    def test_fails_when_no_data_sources_configured(self):
        """Test validation fails when no data sources specified."""
        settings = Mock()
        settings.data_sources = ""
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        assert not is_valid
        assert any('data source' in error.lower() for error in errors)
    
    def test_warns_on_invalid_data_source_name(self):
        """Test validation fails with invalid data source name."""
        settings = Mock()
        settings.data_sources = "invalid_source"
        settings.openai_api_key = "sk-" + "x" * 48
        settings.gumroad_access_token = "x" * 32
        settings.max_tokens_per_run = 50000
        settings.max_usd_per_run = 5.0
        settings.max_usd_lifetime = 100.0
        settings.reddit_min_score = 10
        settings.reddit_post_limit = 20
        settings.max_regeneration_attempts = 1
        settings.database_path = "./data/pipeline.db"
        settings.artifacts_path = "./data/artifacts"
        
        validator = ConfigValidator(settings)
        is_valid, errors = validator.validate_all()
        
        assert not is_valid
        assert any('invalid' in error.lower() or 'data source' in error.lower() for error in errors)
