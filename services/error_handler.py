"""Structured error logging to artifacts."""
import json
import os
import time
import traceback
from typing import Tuple
from datetime import datetime
from config import settings


class ErrorHandler:
    """Log errors with full context to artifacts."""
    
    # Error categories
    TRANSIENT_ERRORS = (
        'Timeout',
        'ConnectionError',
        'RateLimitError',
        'APIError',
        'RequestException',
    )
    
    FATAL_ERRORS = (
        'ConfigValidationError',
        'SchemaValidationError',
        'ValueError',
        'TypeError',
        'FileNotFoundError',
    )
    
    def __init__(self):
        """Initialize error handler."""
        self.error_dir = os.path.join(settings.artifacts_path, 'errors')
        os.makedirs(self.error_dir, exist_ok=True)
    
    def log_error(self, post_id: str, stage: str, error: Exception) -> str:
        """Log exception with full context to artifact.
        
        Args:
            post_id: Reddit post ID
            stage: Pipeline stage where error occurred
            error: Exception object
        
        Returns:
            Path to error artifact
        """
        is_transient, category = self.categorize_error(error)
        
        error_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'unix_timestamp': int(time.time()),
            'post_id': post_id,
            'stage': stage,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'category': category,
            'is_transient': is_transient,
            'traceback': traceback.format_exc(),
            'context': {
                'python_version': self._get_python_version(),
            }
        }
        
        artifact_path = self._save_error_artifact(post_id, error_data)
        return artifact_path
    
    def categorize_error(self, error: Exception) -> Tuple[bool, str]:
        """Categorize error as transient or fatal.
        
        Args:
            error: Exception object
        
        Returns:
            (is_transient, category) tuple
        """
        error_type = type(error).__name__
        
        # Check transient errors
        for transient in self.TRANSIENT_ERRORS:
            if transient in error_type or transient in str(error):
                return True, 'transient'
        
        # Check fatal errors
        for fatal in self.FATAL_ERRORS:
            if fatal in error_type:
                return False, 'fatal'
        
        # Default to fatal
        return False, 'unknown'
    
    def _save_error_artifact(self, post_id: str, error_data: dict) -> str:
        """Save error to artifact file.
        
        Args:
            post_id: Reddit post ID
            error_data: Error information dict
        
        Returns:
            Path to saved artifact
        """
        post_dir = os.path.join(settings.artifacts_path, post_id)
        os.makedirs(post_dir, exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"error_{timestamp}.json"
        filepath = os.path.join(post_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(error_data, f, indent=2, default=str)
        
        # Restrict permissions
        os.chmod(filepath, 0o600)
        
        return filepath
    
    @staticmethod
    def _get_python_version() -> str:
        """Get Python version string."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
