"""Configuration validation module for Pi-Autopilot."""
import re
from typing import List, Tuple


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors or []


class ConfigValidator:
    """Validate all required configuration on startup."""
    
    REQUIRED_FIELDS = [
        'openai_api_key',
        'gumroad_access_token'
    ]
    
    # Reddit fields now optional - only required if reddit is enabled
    REDDIT_FIELDS = [
        'reddit_client_id',
        'reddit_client_secret'
    ]
    
    API_KEY_PATTERNS = {
        'openai_api_key': r'^sk-[A-Za-z0-9_-]{40,}$',
        'gumroad_access_token': r'^[a-zA-Z0-9_-]{20,}$',
        'reddit_client_id': r'^[a-zA-Z0-9_-]{20,}$',
        'reddit_client_secret': r'^[a-zA-Z0-9_-]{20,}$',
    }
    
    def __init__(self, config=None):
        """Initialize validator with optional config override."""
        if config is None:
            # Import here to avoid circular dependency
            from config import settings
            self.config = settings
        else:
            self.config = config
        self.errors: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str]]:
        """Run all validations and return (is_valid, errors)."""
        self.errors = []
        
        self._validate_required_fields()
        self._validate_data_sources()
        self._validate_api_key_formats()
        self._validate_numeric_ranges()
        self._validate_paths()
        
        if self.errors:
            return False, self.errors
        return True, []
    
    def validate_or_raise(self):
        """Validate and raise ConfigValidationError if invalid."""
        is_valid, errors = self.validate_all()
        if not is_valid:
            error_message = "Configuration validation failed:\n" + "\n".join(
                f"  ✗ {error}" for error in errors
            )
            raise ConfigValidationError(error_message, errors)
    
    def _validate_required_fields(self):
        """Check that all required env vars are present."""
        for field in self.REQUIRED_FIELDS:
            value = getattr(self.config, field, None)
            if not value or not str(value).strip():
                self.errors.append(f"Missing required field: {field}")
    
    def _validate_data_sources(self):
        """Validate data sources configuration."""
        # Check that at least one data source is configured
        if not self.config.data_sources or not str(self.config.data_sources).strip():
            self.errors.append("No data sources configured. Set DATA_SOURCES in .env")
            return
        
        sources = [s.strip().lower() for s in str(self.config.data_sources).split(',') if s.strip()]
        
        if not sources:
            self.errors.append("No valid data sources configured. Set DATA_SOURCES in .env")
            return
        
        valid_sources = ['reddit', 'hackernews', 'rss', 'file']
        
        # Check for invalid source names
        for source in sources:
            if source and source not in valid_sources:
                self.errors.append(
                    f"Invalid data source '{source}'. "
                    f"Valid options: {', '.join(valid_sources)}"
                )
        
        # Validate source-specific requirements
        if 'reddit' in sources:
            for field in self.REDDIT_FIELDS:
                value = getattr(self.config, field, None)
                if not value or not str(value).strip():
                    self.errors.append(
                        f"Reddit source enabled but {field} not configured"
                    )
            # Validate subreddit list
            self._validate_subreddit_list()
        
        if 'rss' in sources:
            if not self.config.rss_feed_urls or not str(self.config.rss_feed_urls).strip():
                self.errors.append(
                    "RSS source enabled but rss_feed_urls not configured"
                )
        
        if 'file' in sources:
            if not self.config.file_ingest_paths or not str(self.config.file_ingest_paths).strip():
                self.errors.append(
                    "File source enabled but file_ingest_paths not configured"
                )
    
    def _validate_api_key_formats(self):
        """Check API key formats match expected patterns."""
        for field, pattern in self.API_KEY_PATTERNS.items():
            value = getattr(self.config, field, None)
            
            # Skip Reddit credential validation if reddit not in data sources
            if field in self.REDDIT_FIELDS:
                sources = [s.strip().lower() for s in self.config.data_sources.split(',')]
                if 'reddit' not in sources:
                    continue
            
            if value and not re.match(pattern, str(value)):
                self.errors.append(
                    f"Invalid format for {field}. "
                    f"Expected pattern: {pattern}"
                )
    
    def _validate_numeric_ranges(self):
        """Check numeric config values are in valid ranges."""
        checks = [
            ('max_tokens_per_run', 1000, 1000000),
            ('max_usd_per_run', 0.01, 1000.0),
            ('max_usd_lifetime', 1.0, 10000.0),
            ('reddit_min_score', 0, 100000),
            ('reddit_post_limit', 1, 100),
            ('max_regeneration_attempts', 0, 5),
        ]
        
        for field, min_val, max_val in checks:
            value = getattr(self.config, field, None)
            if value is not None:
                if not (min_val <= value <= max_val):
                    self.errors.append(
                        f"{field} out of range. "
                        f"Expected {min_val}-{max_val}, got {value}"
                    )
    
    def _validate_paths(self):
        """Check database and artifact paths are accessible."""
        import os
        
        # Check database directory is writable
        db_dir = os.path.dirname(self.config.database_path)
        if db_dir and not os.access(db_dir or '.', os.W_OK):
            self.errors.append(
                f"Database directory not writable: {db_dir or './'}"
            )
        
        # Check artifacts directory is writable
        if not os.access(self.config.artifacts_path or '.', os.W_OK):
            self.errors.append(
                f"Artifacts directory not writable: {self.config.artifacts_path}"
            )
    
    def _validate_subreddit_list(self):
        """Check subreddit names are valid format (only when Reddit is enabled)."""
        if not self.config.reddit_subreddits or not self.config.reddit_subreddits.strip():
            self.errors.append("Reddit enabled but no subreddits configured")
            return
        
        subreddits = [
            s.strip() for s in self.config.reddit_subreddits.split(',')
        ]
        
        for sub in subreddits:
            if sub and not re.match(r'^[a-zA-Z0-9_-]{2,}$', sub):
                self.errors.append(f"Invalid subreddit name: {sub}")
        
        if not subreddits or all(not s for s in subreddits):
            self.errors.append("No valid subreddits configured")
