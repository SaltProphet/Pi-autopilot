"""Tests for storage module."""
import pytest
import sqlite3
import os
import tempfile
import json
from services.storage import Storage


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
class TestStorage:
    """Test suite for Storage class."""

    def test_database_initialization(self, storage):
        """Test that database tables are created."""
        conn = sqlite3.connect(storage.db_path)
        cursor = conn.cursor()
        
        # Check reddit_posts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reddit_posts'")
        assert cursor.fetchone() is not None
        
        # Check pipeline_runs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        assert cursor.fetchone() is not None
        
        conn.close()

    def test_save_post(self, storage):
        """Test saving a Reddit post."""
        post_data = {
            'id': 'test123',
            'title': 'Test Post',
            'body': 'Test content',
            'timestamp': 1234567890,
            'subreddit': 'test',
            'author': 'testuser',
            'score': 100,
            'url': 'https://reddit.com/test',
            'num_comments': 5
        }
        
        result = storage.save_post(post_data)
        assert result is True
        
        # Verify post was saved
        saved_post = storage.get_post('test123')
        assert saved_post is not None
        assert saved_post['title'] == 'Test Post'
        assert saved_post['score'] == 100

    def test_save_duplicate_post(self, storage):
        """Test that duplicate posts are rejected."""
        post_data = {
            'id': 'dup123',
            'title': 'Duplicate Post',
            'body': 'Content',
            'timestamp': 1234567890,
            'subreddit': 'test',
            'author': 'testuser',
            'score': 50,
            'url': 'https://reddit.com/dup',
            'num_comments': 2
        }
        
        # Save first time
        result1 = storage.save_post(post_data)
        assert result1 is True
        
        # Try to save again
        result2 = storage.save_post(post_data)
        assert result2 is False

    def test_get_post(self, storage):
        """Test retrieving a post by ID."""
        post_data = {
            'id': 'get123',
            'title': 'Get Test',
            'body': 'Test body',
            'timestamp': 1234567890,
            'subreddit': 'test',
            'author': 'testuser',
            'score': 75,
            'url': 'https://reddit.com/get',
            'num_comments': 3
        }
        
        storage.save_post(post_data)
        retrieved = storage.get_post('get123')
        
        assert retrieved is not None
        assert retrieved['id'] == 'get123'
        assert retrieved['title'] == 'Get Test'

    def test_get_nonexistent_post(self, storage):
        """Test retrieving a post that doesn't exist."""
        result = storage.get_post('nonexistent')
        assert result is None

    def test_get_unprocessed_posts(self, storage):
        """Test retrieving posts without pipeline runs."""
        # Save some posts
        for i in range(3):
            post_data = {
                'id': f'unproc{i}',
                'title': f'Unprocessed {i}',
                'body': 'Content',
                'timestamp': 1234567890 + i,
                'subreddit': 'test',
                'author': 'testuser',
                'score': 50,
                'url': f'https://reddit.com/{i}',
                'num_comments': 1
            }
            storage.save_post(post_data)
        
        # Mark one as processed
        storage.log_pipeline_run('unproc0', 'test_stage', 'completed')
        
        # Get unprocessed posts
        unprocessed = storage.get_unprocessed_posts()
        unprocessed_ids = [p['id'] for p in unprocessed]
        
        assert len(unprocessed) == 2
        assert 'unproc1' in unprocessed_ids
        assert 'unproc2' in unprocessed_ids
        assert 'unproc0' not in unprocessed_ids

    def test_log_pipeline_run(self, storage):
        """Test logging a pipeline run."""
        # Create a post first
        post_data = {
            'id': 'pipe123',
            'title': 'Pipeline Test',
            'body': 'Content',
            'timestamp': 1234567890,
            'subreddit': 'test',
            'author': 'testuser',
            'score': 60,
            'url': 'https://reddit.com/pipe',
            'num_comments': 2
        }
        storage.save_post(post_data)
        
        # Log pipeline run
        storage.log_pipeline_run(
            post_id='pipe123',
            stage='problem_extraction',
            status='completed',
            artifact_path='/tmp/artifact.json'
        )
        
        # Verify run was logged
        runs = storage.get_pipeline_runs('pipe123')
        assert len(runs) == 1
        assert runs[0]['stage'] == 'problem_extraction'
        assert runs[0]['status'] == 'completed'

    def test_log_pipeline_run_with_error(self, storage):
        """Test logging a failed pipeline run."""
        post_data = {
            'id': 'err123',
            'title': 'Error Test',
            'body': 'Content',
            'timestamp': 1234567890,
            'subreddit': 'test',
            'author': 'testuser',
            'score': 40,
            'url': 'https://reddit.com/err',
            'num_comments': 1
        }
        storage.save_post(post_data)
        
        storage.log_pipeline_run(
            post_id='err123',
            stage='spec_generation',
            status='failed',
            error_message='API error occurred'
        )
        
        runs = storage.get_pipeline_runs('err123')
        assert len(runs) == 1
        assert runs[0]['status'] == 'failed'
        assert runs[0]['error_message'] == 'API error occurred'

    def test_get_pipeline_runs(self, storage):
        """Test retrieving all pipeline runs for a post."""
        post_data = {
            'id': 'multi123',
            'title': 'Multi Stage Test',
            'body': 'Content',
            'timestamp': 1234567890,
            'subreddit': 'test',
            'author': 'testuser',
            'score': 80,
            'url': 'https://reddit.com/multi',
            'num_comments': 4
        }
        storage.save_post(post_data)
        
        # Log multiple runs
        storage.log_pipeline_run('multi123', 'problem_extraction', 'completed')
        storage.log_pipeline_run('multi123', 'spec_generation', 'completed')
        storage.log_pipeline_run('multi123', 'content_generation', 'failed')
        
        runs = storage.get_pipeline_runs('multi123')
        assert len(runs) == 3
        
        stages = [r['stage'] for r in runs]
        assert 'problem_extraction' in stages
        assert 'spec_generation' in stages
        assert 'content_generation' in stages

    def test_raw_json_storage(self, storage):
        """Test that raw JSON is stored correctly."""
        post_data = {
            'id': 'json123',
            'title': 'JSON Test',
            'body': 'Content',
            'timestamp': 1234567890,
            'subreddit': 'test',
            'author': 'testuser',
            'score': 90,
            'url': 'https://reddit.com/json',
            'num_comments': 6
        }
        
        storage.save_post(post_data)
        retrieved = storage.get_post('json123')
        
        # raw_json should contain serialized post data
        assert retrieved['raw_json'] is not None
        raw_data = json.loads(retrieved['raw_json'])
        assert raw_data['id'] == 'json123'
    
    def test_save_sales_metrics(self, storage):
        """Test saving sales metrics."""
        import time
        fetched_at = int(time.time())
        
        storage.save_sales_metrics(
            product_id="prod123",
            product_name="Test Product",
            sales_count=10,
            revenue_cents=10000,
            views=200,
            refunds=1,
            fetched_at=fetched_at
        )
        
        # Verify data was saved
        metrics = storage.get_sales_metrics_since(days=1)
        assert len(metrics) > 0
        assert metrics[0]["product_id"] == "prod123"
        assert metrics[0]["sales_count"] == 10
        assert metrics[0]["revenue_cents"] == 10000
    
    def test_get_sales_metrics_since(self, storage):
        """Test retrieving sales metrics from a time period."""
        import time
        current_time = int(time.time())
        old_time = current_time - (40 * 86400)  # 40 days ago
        
        # Add recent and old metrics
        storage.save_sales_metrics("prod1", "Recent", 5, 5000, 100, 0, current_time)
        storage.save_sales_metrics("prod2", "Old", 3, 3000, 50, 0, old_time)
        
        # Get last 30 days
        recent_metrics = storage.get_sales_metrics_since(days=30)
        assert len(recent_metrics) == 1
        assert recent_metrics[0]["product_name"] == "Recent"
    
    def test_get_recent_uploaded_products(self, storage):
        """Test retrieving recently uploaded products."""
        import time
        current_time = int(time.time())
        
        # Add posts and mark as uploaded
        for i in range(3):
            post_data = {
                'id': f'upload{i}',
                'title': f'Upload Test {i}',
                'body': 'Content',
                'timestamp': current_time - (i * 1000),
                'subreddit': 'test',
                'author': 'testuser',
                'score': 50,
                'url': f'https://reddit.com/upload{i}',
                'num_comments': 2
            }
            storage.save_post(post_data)
            storage.log_pipeline_run(f'upload{i}', 'gumroad_upload', 'completed', '/path/to/artifact')
        
        # Get recent uploads
        recent_uploads = storage.get_recent_uploaded_products(limit=10)
        assert len(recent_uploads) == 3
        assert recent_uploads[0]['post_id'] == 'upload0'  # Most recent first
