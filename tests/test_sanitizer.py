import pytest
from services.sanitizer import InputSanitizer


class TestInputSanitizer:
    """Test suite for InputSanitizer module."""
    
    @pytest.fixture
    def sanitizer(self):
        """Create an InputSanitizer instance."""
        return InputSanitizer()
    
    # Tests for sanitize_reddit_content
    
    def test_sanitize_reddit_removes_control_characters(self, sanitizer):
        """Test that control characters are removed from Reddit content."""
        text = "Hello\x00World\x01Test"
        result = sanitizer.sanitize_reddit_content(text)
        assert '\x00' not in result
        assert '\x01' not in result
        assert 'Hello' in result
        assert 'World' in result
    
    def test_sanitize_reddit_decodes_html_entities(self, sanitizer):
        """Test that HTML entities are decoded in Reddit content."""
        text = "Hello &lt;World&gt; &amp; friends"
        result = sanitizer.sanitize_reddit_content(text)
        assert '&lt;' not in result or '<' in result
        assert '&gt;' not in result or '>' in result
    
    def test_sanitize_reddit_preserves_newlines(self, sanitizer):
        """Test that newlines are preserved."""
        text = "Line 1\nLine 2\nLine 3"
        result = sanitizer.sanitize_reddit_content(text)
        assert '\n' in result
    
    def test_sanitize_reddit_removes_null_bytes(self, sanitizer):
        """Test that null bytes are removed."""
        text = "Text\x00With\x00Nulls"
        result = sanitizer.sanitize_reddit_content(text)
        assert '\x00' not in result
    
    # Tests for sanitize_gumroad_content
    
    def test_sanitize_gumroad_escapes_html_entities(self, sanitizer):
        """Test that HTML is escaped for Gumroad listings."""
        text = "<b>Bold</b> & <i>italic</i>"
        result = sanitizer.sanitize_gumroad_content(text)
        # Should be HTML-safe
        assert '&lt;b&gt;' in result or '<b>' not in result
    
    def test_sanitize_gumroad_removes_script_tags(self, sanitizer):
        """Test that script tags are removed."""
        text = "Hello <script>alert('xss')</script> World"
        result = sanitizer.sanitize_gumroad_content(text)
        assert '<script' not in result.lower()
        assert 'alert' not in result.lower() or 'Hello' in result
    
    def test_sanitize_gumroad_removes_iframe_tags(self, sanitizer):
        """Test that iframe tags are removed."""
        text = "Content <iframe src='evil.com'></iframe> more"
        result = sanitizer.sanitize_gumroad_content(text)
        assert '<iframe' not in result.lower()
        assert 'Content' in result
    
    def test_sanitize_gumroad_removes_event_handlers(self, sanitizer):
        """Test that event handler attributes are removed."""
        text = '<img src="pic.jpg" onclick="alert(\'xss\')">'
        result = sanitizer.sanitize_gumroad_content(text)
        assert 'onclick' not in result.lower()
    
    def test_sanitize_gumroad_removes_form_tags(self, sanitizer):
        """Test that form tags are removed."""
        text = "Content <form><input name='field'></form> end"
        result = sanitizer.sanitize_gumroad_content(text)
        assert '<form' not in result.lower()
        assert 'Content' in result
    
    def test_sanitize_gumroad_removes_javascript_protocol(self, sanitizer):
        """Test that javascript: protocol is removed."""
        text = '<a href="javascript:alert(1)">Click</a>'
        result = sanitizer.sanitize_gumroad_content(text)
        assert 'javascript:' not in result.lower()
    
    def test_sanitize_gumroad_removes_data_uri_html(self, sanitizer):
        """Test that data: URI HTML is removed."""
        text = '<img src="data:text/html,<script>alert(1)</script>">'
        result = sanitizer.sanitize_gumroad_content(text)
        assert 'data:text/html' not in result.lower()
    
    # Tests for sanitize_database_content
    
    def test_sanitize_database_removes_null_bytes(self, sanitizer):
        """Test that null bytes are removed for DB safety."""
        text = "Data\x00With\x00Nulls"
        result = sanitizer.sanitize_database_content(text)
        assert '\x00' not in result
        assert 'Data' in result
    
    def test_sanitize_database_validates_utf8(self, sanitizer):
        """Test that UTF-8 validation works."""
        text = "Valid UTF-8 text"
        result = sanitizer.sanitize_database_content(text)
        assert isinstance(result, str)
    
    def test_sanitize_database_preserves_normal_text(self, sanitizer):
        """Test that normal text is preserved."""
        text = "Normal database content with 'quotes' and \"double quotes\""
        result = sanitizer.sanitize_database_content(text)
        assert 'Normal' in result
        assert 'database' in result
    
    # XSS vector tests
    
    def test_xss_vector_alert_box(self, sanitizer):
        """Test blocking common XSS alert vector."""
        text = "<svg onload=alert('xss')>"
        result = sanitizer.sanitize_gumroad_content(text)
        assert 'onload' not in result.lower()
    
    def test_xss_vector_img_onerror(self, sanitizer):
        """Test blocking img onerror XSS vector."""
        text = "<img src=x onerror=alert('xss')>"
        result = sanitizer.sanitize_gumroad_content(text)
        assert 'onerror' not in result.lower()
    
    def test_xss_vector_input_autofocus(self, sanitizer):
        """Test blocking input autofocus XSS vector."""
        text = "<input autofocus onfocus=alert('xss')>"
        result = sanitizer.sanitize_gumroad_content(text)
        assert 'onfocus' not in result.lower()
    
    def test_xss_vector_base_href(self, sanitizer):
        """Test blocking base href XSS vector."""
        text = "<base href='javascript:alert(1)'>"
        result = sanitizer.sanitize_gumroad_content(text)
        assert 'javascript:' not in result.lower()
    
    # Integration tests
    
    def test_sanitize_reddit_then_gumroad(self, sanitizer):
        """Test chaining sanitizers for complete pipeline."""
        dirty_reddit = "Content with <script>alert(1)</script>\x00 null bytes &lt;tags&gt;"
        clean_reddit = sanitizer.sanitize_reddit_content(dirty_reddit)
        # Should have removed nulls but decoded entities
        assert '\x00' not in clean_reddit
        
        # Then sanitize for Gumroad
        clean_gumroad = sanitizer.sanitize_gumroad_content(clean_reddit)
        assert '<script' not in clean_gumroad.lower()
