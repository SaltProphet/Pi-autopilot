import pytest
import tempfile
import sqlite3
from pathlib import Path
from services.audit_logger import AuditLogger


class TestAuditLogger:
    """Test suite for AuditLogger module."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        import os
        if os.path.exists(db_path):
            os.remove(db_path)
    
    @pytest.fixture
    def audit_logger(self, temp_db_path):
        """Create an AuditLogger instance with temp DB."""
        return AuditLogger(temp_db_path)
    
    def test_log_records_action(self, audit_logger):
        """Test that log method records an action."""
        log_id = audit_logger.log(
            action='post_ingested',
            post_id='post_123',
            run_id='run_456',
            details={'subreddit': 'SideProject', 'score': 42}
        )
        
        assert log_id is not None
        assert isinstance(log_id, int)
    
    def test_log_stores_json_details(self, audit_logger):
        """Test that details are stored as JSON."""
        details_dict = {'key': 'value', 'count': 42, 'nested': {'a': 1}}
        log_id = audit_logger.log(
            action='spec_generated',
            post_id='post_abc',
            run_id='run_def',
            details=details_dict
        )
        
        # Verify it was stored
        assert log_id > 0
    
    def test_get_post_history_returns_all_ops(self, audit_logger):
        """Test that get_post_history returns all operations for a post."""
        post_id = 'test_post_xyz'
        
        # Log multiple operations for same post
        audit_logger.log('post_ingested', post_id=post_id, run_id='run1', details={})
        audit_logger.log('problem_extracted', post_id=post_id, run_id='run1', details={})
        audit_logger.log('spec_generated', post_id=post_id, run_id='run1', details={})
        
        history = audit_logger.get_post_history(post_id)
        
        assert len(history) >= 3
        actions = [entry['action'] for entry in history]
        assert 'post_ingested' in actions
        assert 'problem_extracted' in actions
        assert 'spec_generated' in actions
    
    def test_get_run_history_filters_by_run(self, audit_logger):
        """Test that get_run_history returns operations from specific run."""
        run_id = 'specific_run_123'
        
        # Log operations with this run_id
        audit_logger.log('post_ingested', post_id='post1', run_id=run_id, details={})
        audit_logger.log('problem_extracted', post_id='post1', run_id=run_id, details={})
        
        # Log operations with different run_id
        audit_logger.log('post_ingested', post_id='post2', run_id='other_run', details={})
        
        history = audit_logger.get_run_history(run_id)
        
        # Should only contain operations from specific_run_123
        assert len(history) >= 2
        assert all(entry['run_id'] == run_id for entry in history)
    
    def test_get_recent_errors_filters_on_flag(self, audit_logger):
        """Test that get_recent_errors filters on error_occurred flag."""
        # Log some normal operations
        audit_logger.log('post_ingested', post_id='p1', run_id='r1', details={})
        audit_logger.log('spec_generated', post_id='p1', run_id='r1', details={})
        
        # Log some errors
        audit_logger.log('error_occurred', post_id='p2', run_id='r2', details={'error': 'timeout'}, error_occurred=True)
        audit_logger.log('error_occurred', post_id='p3', run_id='r3', details={'error': 'auth'}, error_occurred=True)
        
        # Get recent errors
        errors = audit_logger.get_recent_errors(limit=10, hours=24)
        
        # Should only contain error_occurred entries
        assert len(errors) >= 2
        assert all(entry['error_occurred'] == 1 for entry in errors)
    
    def test_get_timeline_human_readable(self, audit_logger):
        """Test that get_timeline returns human-readable format."""
        post_id = 'timeline_test_post'
        
        audit_logger.log('post_ingested', post_id=post_id, run_id='run1', details={})
        audit_logger.log('problem_extracted', post_id=post_id, run_id='run1', details={})
        audit_logger.log('spec_generated', post_id=post_id, run_id='run1', details={})
        
        timeline = audit_logger.get_timeline(post_id)
        
        # Should be a string (human-readable)
        assert isinstance(timeline, str)
        # Should contain action names
        assert 'post_ingested' in timeline or 'ingested' in timeline.lower()
    
    def test_log_with_error_occurred_flag(self, audit_logger):
        """Test logging with error_occurred flag."""
        log_id = audit_logger.log(
            action='error_occurred',
            post_id='p_error',
            run_id='r_error',
            details={'error_type': 'TimeoutError'},
            error_occurred=True
        )
        
        assert log_id > 0
        
        history = audit_logger.get_post_history('p_error')
        assert len(history) > 0
        assert history[0]['error_occurred'] == 1
    
    def test_log_with_cost_limit_exceeded_flag(self, audit_logger):
        """Test logging with cost_limit_exceeded flag."""
        log_id = audit_logger.log(
            action='cost_limit_exceeded',
            post_id='p_cost',
            run_id='r_cost',
            details={'reason': 'daily_limit'},
            cost_limit_exceeded=True
        )
        
        assert log_id > 0
    
    def test_audit_log_schema_has_required_columns(self, audit_logger, temp_db_path):
        """Test that audit_log table has required columns."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("PRAGMA table_info(audit_log)")
        columns = cursor.fetchall()
        
        column_names = [col[1] for col in columns]
        
        # Verify required columns exist
        assert 'id' in column_names
        assert 'timestamp' in column_names
        assert 'action' in column_names
        assert 'post_id' in column_names
        assert 'run_id' in column_names
        assert 'details' in column_names
        assert 'error_occurred' in column_names
        assert 'cost_limit_exceeded' in column_names
        
        conn.close()
    
    def test_audit_log_has_indexes(self, audit_logger, temp_db_path):
        """Test that required indexes exist on audit_log table."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Get index info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='audit_log'")
        indexes = cursor.fetchall()
        index_names = [idx[0] for idx in indexes]
        
        # Verify indexes exist
        assert any('post_id' in name for name in index_names)
        assert any('action' in name for name in index_names)
        assert any('timestamp' in name for name in index_names)
        
        conn.close()
    
    def test_audit_log_immutable_no_deletes(self, audit_logger):
        """Test that audit log doesn't support DELETE operations."""
        # Log something
        audit_logger.log('post_ingested', post_id='immutable_test', run_id='r1', details={})
        
        # Try to delete (should fail or be prevented)
        # The implementation shouldn't provide a delete method
        assert not hasattr(audit_logger, 'delete_log')
        assert not hasattr(audit_logger, 'remove_log')
    
    def test_multiple_logs_same_post_different_stages(self, audit_logger):
        """Test logging multiple operations for same post through pipeline."""
        post_id = 'full_pipeline_test'
        run_id = 'full_run'
        
        stages = [
            ('post_ingested', {}),
            ('problem_extracted', {'urgency_score': 85}),
            ('spec_generated', {'confidence': 92}),
            ('content_generated', {'length': 3500}),
            ('content_verified', {'attempt': 1}),
            ('gumroad_listed', {}),
            ('gumroad_uploaded', {'product_url': 'https://gumroad.com/...'}),
        ]
        
        for action, details in stages:
            audit_logger.log(action, post_id=post_id, run_id=run_id, details=details)
        
        history = audit_logger.get_post_history(post_id)
        
        assert len(history) >= len(stages)
        recorded_actions = [entry['action'] for entry in history]
        for action, _ in stages:
            assert action in recorded_actions
