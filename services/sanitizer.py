"""Input sanitization for user-generated content."""
import re
from html import escape, unescape
from typing import Optional


class InputSanitizer:
    """Sanitize text for different contexts."""
    
    def __init__(self):
        """Initialize sanitizer."""
        # Dangerous characters and patterns
        self.control_char_pattern = re.compile(r'[\x00-\x1f\x7f-\x9f]')
        self.script_pattern = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
        self.dangerous_tags = ['script', 'iframe', 'object', 'embed', 'applet']
    
    def sanitize_reddit_content(self, text: str, max_length: int = 5000) -> str:
        """Sanitize content from Reddit posts (safe for LLM).
        
        Args:
            text: Raw Reddit post body
            max_length: Maximum length to preserve
        
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Remove control characters
        text = self._remove_control_chars(text)
        
        # HTML decode (Reddit often has encoded entities)
        text = unescape(text)
        
        # Remove script blocks
        text = self.script_pattern.sub('', text)
        
        # Truncate if too long
        text = text[:max_length]
        
        return text.strip()
    
    def sanitize_gumroad_content(self, text: str, max_length: int = 10000) -> str:
        """Sanitize content for Gumroad listing.
        
        Args:
            text: Product content or listing text
            max_length: Maximum length
        
        Returns:
            Sanitized text safe for Gumroad
        """
        if not text:
            return ""
        
        # Remove control characters
        text = self._remove_control_chars(text)
        
        # Remove script blocks
        text = self.script_pattern.sub('', text)
        
        # Escape HTML entities
        text = escape(text)
        
        # Remove any remaining dangerous patterns
        text = self._remove_dangerous_patterns(text)
        
        # Truncate if too long
        text = text[:max_length]
        
        return text.strip()
    
    def sanitize_database_content(self, text: str, max_length: int = 50000) -> str:
        """Sanitize content for SQLite storage.
        
        Args:
            text: Content to store
            max_length: Maximum length
        
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Remove null bytes (dangerous in SQLite)
        text = text.replace('\x00', '')
        
        # Remove other control characters
        text = self._remove_control_chars(text)
        
        # Truncate if too long
        text = text[:max_length]
        
        return text
    
    def _remove_control_chars(self, text: str) -> str:
        """Remove control characters from text.
        
        Args:
            text: Input text
        
        Returns:
            Text with control chars removed
        """
        return self.control_char_pattern.sub('', text)
    
    def _remove_dangerous_patterns(self, text: str) -> str:
        """Remove dangerous HTML patterns.
        
        Args:
            text: Input text
        
        Returns:
            Sanitized text
        """
        for tag in self.dangerous_tags:
            # Remove opening tags
            text = re.sub(f'<{tag}[^>]*>', '', text, flags=re.IGNORECASE)
            # Remove closing tags
            text = re.sub(f'</{tag}>', '', text, flags=re.IGNORECASE)
        
        # Remove onclick, onload, etc. event handlers
        text = re.sub(r'\s*on\w+\s*=\s*["\']?[^"\']*["\']?', '', text, flags=re.IGNORECASE)
        
        return text
    
    @staticmethod
    def is_safe_url(url: str) -> bool:
        """Check if URL is safe (not javascript: or data:).
        
        Args:
            url: URL to check
        
        Returns:
            True if safe
        """
        if not url:
            return True
        
        dangerous_protocols = ['javascript:', 'data:', 'vbscript:', 'file:']
        url_lower = url.lower().strip()
        
        return not any(url_lower.startswith(proto) for proto in dangerous_protocols)
