import pytest
import tempfile
import json
import os
from services.error_handler import ErrorHandler


class TestErrorHandler:
    """Test suite for ErrorHandler module."""
    
    @pytest.fixture
    def error_handler(self):
        """Create an ErrorHandler instance."""
        return ErrorHandler()
    
    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create a temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_categorize_error_timeout_is_transient(self, error_handler):
        """Test that TimeoutError is categorized as transient."""
        error = TimeoutError("Connection timed out")
        categorization = error_handler.categorize_error(error)
        assert categorization['is_transient'] is True
    
    def test_categorize_error_connection_error_is_transient(self, error_handler):
        """Test that ConnectionError is categorized as transient."""
        error = ConnectionError("Connection refused")
        categorization = error_handler.categorize_error(error)
        assert categorization['is_transient'] is True
    
    def test_categorize_error_os_error_is_transient(self, error_handler):
        """Test that OSError is categorized as transient."""
        error = OSError("Network unreachable")
        categorization = error_handler.categorize_error(error)
        assert categorization['is_transient'] is True
    
    def test_categorize_error_type_error_is_fatal(self, error_handler):
        """Test that TypeError is categorized as fatal."""
        error = TypeError("Expected str, got int")
        categorization = error_handler.categorize_error(error)
        assert categorization['is_transient'] is False
    
    def test_categorize_error_value_error_is_fatal(self, error_handler):
        """Test that ValueError is categorized as fatal."""
        error = ValueError("Invalid value")
        categorization = error_handler.categorize_error(error)
        assert categorization['is_transient'] is False
    
    def test_categorize_error_key_error_is_fatal(self, error_handler):
        """Test that KeyError is categorized as fatal."""
        error = KeyError("Missing key")
        categorization = error_handler.categorize_error(error)
        assert categorization['is_transient'] is False
    
    def test_log_error_saves_artifact(self, error_handler, temp_artifacts_dir, monkeypatch):
        """Test that log_error saves artifact to filesystem."""
        # Mock artifact path
        monkeypatch.setenv('ARTIFACTS_PATH', temp_artifacts_dir)
        
        error = TimeoutError("Request timed out")
        artifact_path = error_handler.log_error(
            post_id='test_post_123',
            stage='content_generation',
            exception=error,
            context={'attempt': 1}
        )
        
        # Verify artifact file was created
        assert os.path.exists(artifact_path)
        
        # Verify artifact contents
        with open(artifact_path, 'r') as f:
            artifact_data = json.load(f)
        
        assert artifact_data['error_type'] == 'TimeoutError'
        assert artifact_data['categorization']['is_transient'] is True
        assert 'traceback' in artifact_data
    
    def test_artifact_includes_traceback(self, error_handler, temp_artifacts_dir, monkeypatch):
        """Test that error artifacts include full traceback."""
        monkeypatch.setenv('ARTIFACTS_PATH', temp_artifacts_dir)
        
        try:
            raise ValueError("Test error with context")
        except ValueError as e:
            artifact_path = error_handler.log_error(
                post_id='test_post_456',
                stage='verification',
                exception=e,
                context={}
            )
        
        with open(artifact_path, 'r') as f:
            artifact_data = json.load(f)
        
        assert 'ValueError' in artifact_data['traceback']
        assert 'Test error with context' in artifact_data['traceback']
    
    def test_artifact_has_context_metadata(self, error_handler, temp_artifacts_dir, monkeypatch):
        """Test that artifact includes context metadata."""
        monkeypatch.setenv('ARTIFACTS_PATH', temp_artifacts_dir)
        
        error = RuntimeError("Processing failed")
        context = {'post_title': 'My Test Post', 'retry_attempt': 3}
        artifact_path = error_handler.log_error(
            post_id='test_post_789',
            stage='problem_extraction',
            exception=error,
            context=context
        )
        
        with open(artifact_path, 'r') as f:
            artifact_data = json.load(f)
        
        assert artifact_data['context']['post_title'] == 'My Test Post'
        assert artifact_data['context']['retry_attempt'] == 3
    
    def test_artifact_includes_python_version(self, error_handler, temp_artifacts_dir, monkeypatch):
        """Test that artifact includes Python version."""
        monkeypatch.setenv('ARTIFACTS_PATH', temp_artifacts_dir)
        
        error = RuntimeError("Test")
        artifact_path = error_handler.log_error(
            post_id='test_post_xyz',
            stage='gumroad_upload',
            exception=error,
            context={}
        )
        
        with open(artifact_path, 'r') as f:
            artifact_data = json.load(f)
        
        assert 'python_version' in artifact_data
        assert artifact_data['python_version'] is not None
    
    def test_get_error_artifacts_returns_list(self, error_handler, temp_artifacts_dir, monkeypatch):
        """Test that get_error_artifacts returns list of error logs."""
        monkeypatch.setenv('ARTIFACTS_PATH', temp_artifacts_dir)
        
        # Log multiple errors for same post
        error_handler.log_error('post_multi', 'stage1', TimeoutError("e1"), {})
        error_handler.log_error('post_multi', 'stage2', ValueError("e2"), {})
        
        artifacts = error_handler.get_error_artifacts('post_multi')
        assert isinstance(artifacts, list)
        assert len(artifacts) >= 2
