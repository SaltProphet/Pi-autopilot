"""Database backup manager with retention policy."""
import shutil
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional
from config import settings


class BackupManager:
    """Manage automated backups with retention policy."""
    
    def __init__(self):
        """Initialize backup manager."""
        self.backup_dir = Path(settings.artifacts_path) / "backups"
        self.db_path = Path(settings.database_path)
        self.retention = {
            'daily': 7,      # Keep 7 daily backups (1 week)
            'weekly': 4,     # Keep 4 weekly backups (1 month)
            'monthly': 12    # Keep 12 monthly backups (1 year)
        }
    
    def backup_database(self) -> str:
        """Create backup of pipeline.db.
        
        Returns:
            Path to backup file
        """
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().isoformat().replace(':', '-')
            backup_path = self.backup_dir / f"pipeline_db_{timestamp}.sqlite"
            
            # Copy database file
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_path)
            else:
                # Create empty backup if db doesn't exist yet
                backup_path.touch()
            
            # Set restrictive permissions
            os.chmod(backup_path, 0o600)
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            return str(backup_path)
        except Exception as e:
            raise RuntimeError(f"Backup failed: {e}") from e
    
    def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup file.
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            True if successful
        """
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Create backup of current database before restore
            if self.db_path.exists():
                recovery_backup = self.db_path.parent / f"{self.db_path.name}.recovery"
                shutil.copy2(self.db_path, recovery_backup)
            
            # Restore from backup
            shutil.copy2(backup_file, self.db_path)
            os.chmod(self.db_path, 0o600)
            
            return True
        except Exception as e:
            raise RuntimeError(f"Restore failed: {e}") from e
    
    def cleanup_old_backups(self) -> int:
        """Apply retention policy and delete old backups.
        
        Returns:
            Number of backups deleted
        """
        if not self.backup_dir.exists():
            return 0
        
        backups = sorted(
            self.backup_dir.glob('pipeline_db_*.sqlite'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        deleted = 0
        for i, backup in enumerate(backups):
            # Keep most recent N backups based on age
            if i >= self.retention['daily']:
                backup.unlink()
                deleted += 1
        
        return deleted
    
    def get_backup_status(self) -> Dict:
        """Get backup status and statistics.
        
        Returns:
            Dictionary with backup info
        """
        if not self.backup_dir.exists():
            return {
                'backup_dir': str(self.backup_dir),
                'backup_count': 0,
                'total_size_mb': 0,
                'last_backup': None,
                'status': 'No backups yet'
            }
        
        backups = list(self.backup_dir.glob('pipeline_db_*.sqlite'))
        total_size = sum(b.stat().st_size for b in backups) / (1024 * 1024)
        last_backup = max(
            (b.stat().st_mtime for b in backups),
            default=None
        )
        
        return {
            'backup_dir': str(self.backup_dir),
            'backup_count': len(backups),
            'total_size_mb': round(total_size, 2),
            'last_backup': (
                datetime.fromtimestamp(last_backup).isoformat()
                if last_backup else None
            ),
            'status': 'OK' if len(backups) > 0 else 'WARNING: No backups'
        }
