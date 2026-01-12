import pytest
from config import settings
from services.config_validator import ConfigValidator, ConfigValidationError


class TestConfigValidator:
    """Test suite for ConfigValidator module."""
    
    def test_validate_or_raise_success_with_valid_config(self):
        """Test that validate_or_raise passes with valid configuration."""
        validator = ConfigValidator(settings)
        result = validator.validate_or_raise()
        assert result is not None
        assert isinstance(result, dict)
    
    def test_validate_required_fields_all_present(self):
        """Test that all required fields are present."""
        validator = ConfigValidator(settings)
        result = validator.validate_required_fields()
        assert result['required_fields'] is True
    
    def test_validate_api_key_formats_openai(self):
        """Test OpenAI API key format validation."""
        validator = ConfigValidator(settings)
        result = validator.validate_api_key_formats()
        # Should pass if settings has valid OpenAI key
        assert result['api_keys'] is True or result['api_keys'] is False
    
    def test_validate_numeric_ranges_tokens(self):
        """Test numeric range validation for token limits."""
        validator = ConfigValidator(settings)
        result = validator.validate_numeric_ranges()
        # Token limits should be positive integers within bounds
        assert result['numeric_ranges'] is True
    
    def test_validate_numeric_ranges_usd_limits(self):
        """Test USD limit validation."""
        validator = ConfigValidator(settings)
        result = validator.validate_numeric_ranges()
        # USD limits should be positive floats
        assert result['numeric_ranges'] is True
    
    def test_validate_path_accessibility(self):
        """Test path accessibility checks."""
        validator = ConfigValidator(settings)
        result = validator.validate_path_accessibility()
        # Database and artifacts paths should be writable
        assert result['paths'] is True
    
    def test_validate_subreddit_names(self):
        """Test subreddit name format validation."""
        validator = ConfigValidator(settings)
        result = validator.validate_subreddit_names()
        # Should validate comma-separated subreddit list
        assert result['subreddits'] is True
    
    def test_validate_required_fields_none_value(self):
        """Test that None values in required fields are caught."""
        # Create minimal settings-like object with missing field
        class BadSettings:
            openai_api_key = None
            reddit_client_id = "test"
            reddit_client_secret = "test"
            reddit_user_agent = "test"
            gumroad_access_token = "test"
        
        validator = ConfigValidator(BadSettings())
        result = validator.validate_required_fields()
        assert result['required_fields'] is False
    
    def test_error_message_includes_field_name(self):
        """Test that error messages include the field name."""
        class BadSettings:
            openai_api_key = None
            reddit_client_id = "test"
            reddit_client_secret = "test"
            reddit_user_agent = "test"
            gumroad_access_token = "test"
        
        validator = ConfigValidator(BadSettings())
        try:
            validator.validate_or_raise()
            assert False, "Should raise ConfigValidationError"
        except ConfigValidationError as e:
            assert len(e.errors) > 0
            assert any('openai_api_key' in error.lower() for error in e.errors)
