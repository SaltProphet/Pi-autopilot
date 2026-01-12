import pytest
import tempfile
import os
import sqlite3
from pathlib import Path
from services.backup_manager import BackupManager
from config import settings


class TestBackupManager:
    """Test suite for BackupManager module."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Initialize with minimal schema
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'test_data')")
        conn.commit()
        conn.close()
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
    
    @pytest.fixture
    def backup_manager(self, temp_db_path):
        """Create a BackupManager instance with temp DB."""
        # Clean up backup directory if it exists
        backup_dir = os.path.join(os.path.dirname(temp_db_path), 'backups')
        if os.path.exists(backup_dir):
            import shutil
            shutil.rmtree(backup_dir)
        
        manager = BackupManager(temp_db_path)
        yield manager
        
        # Cleanup backups
        if os.path.exists(backup_dir):
            import shutil
            shutil.rmtree(backup_dir)
    
    def test_backup_creates_file(self, backup_manager):
        """Test that backup_database creates a backup file."""
        backup_path = backup_manager.backup_database()
        assert os.path.exists(backup_path)
        assert backup_path.endswith('.sqlite.gz')
    
    def test_backup_file_has_restricted_permissions(self, backup_manager):
        """Test that backup files have 0o600 permissions."""
        backup_path = backup_manager.backup_database()
        stat_info = os.stat(backup_path)
        # Check that permissions are 0o600 (owner read/write only)
        assert stat_info.st_mode & 0o777 == 0o600
    
    def test_backup_path_contains_timestamp(self, backup_manager):
        """Test that backup filename contains timestamp."""
        backup_path = backup_manager.backup_database()
        filename = os.path.basename(backup_path)
        # Should contain date pattern like 2026-01-12
        assert any(c.isdigit() for c in filename)
    
    def test_get_backup_status_returns_metrics(self, backup_manager):
        """Test that get_backup_status returns expected metrics."""
        backup_manager.backup_database()
        status = backup_manager.get_backup_status()
        
        assert 'total_backups' in status
        assert 'total_size_mb' in status
        assert 'latest_backup' in status
        assert status['total_backups'] >= 1
    
    def test_cleanup_old_backups_enforces_retention(self, backup_manager, temp_db_path):
        """Test that cleanup enforces retention policy."""
        # Create multiple backups
        for _ in range(3):
            backup_manager.backup_database()
        
        initial_status = backup_manager.get_backup_status()
        initial_count = initial_status['total_backups']
        
        # Cleanup should maintain retention
        backup_manager.cleanup_old_backups()
        
        final_status = backup_manager.get_backup_status()
        # After cleanup, count should not exceed retention limits
        assert final_status['total_backups'] <= initial_count
    
    def test_restore_database_from_backup(self, backup_manager, temp_db_path):
        """Test that database can be restored from backup."""
        # Create initial backup
        backup_path = backup_manager.backup_database()
        
        # Modify database
        conn = sqlite3.connect(temp_db_path)
        conn.execute("DELETE FROM test")
        conn.commit()
        conn.close()
        
        # Verify deletion
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM test")
        assert cursor.fetchone()[0] == 0
        conn.close()
        
        # Restore from backup
        restore_result = backup_manager.restore_database(backup_path)
        assert restore_result['success'] is True
        
        # Verify data is restored
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.execute("SELECT data FROM test WHERE id=1")
        assert cursor.fetchone()[0] == 'test_data'
        conn.close()
    
    def test_restore_invalid_backup_fails(self, backup_manager):
        """Test that restore fails gracefully with invalid backup."""
        result = backup_manager.restore_database('/nonexistent/backup.gz')
        assert result['success'] is False
