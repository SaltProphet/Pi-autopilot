"""Immutable audit trail for all pipeline operations."""
import json
import sqlite3
import time
from typing import List, Dict, Optional
from datetime import datetime
from contextlib import contextmanager
from config import settings


class AuditLogger:
    """Log all pipeline operations to immutable audit trail."""
    
    # Standard action types
    ACTIONS = {
        'post_ingested': 'Reddit post fetched and stored',
        'problem_extracted': 'Problem analysis completed',
        'spec_generated': 'Product spec created',
        'content_generated': 'Product content generated',
        'content_verified': 'Content passed verification',
        'content_rejected': 'Content failed verification',
        'gumroad_listed': 'Gumroad listing created',
        'gumroad_uploaded': 'Product uploaded to Gumroad',
        'post_discarded': 'Post marked as discarded',
        'cost_limit_exceeded': 'Cost limit reached',
        'error_occurred': 'Error during processing',
        'publishing_suppressed': 'Publishing suppressed due to performance',
        'sales_data_ingested': 'Sales data fetched from Gumroad',
    }
    
    def __init__(self):
        """Initialize audit logger."""
        self.db_path = settings.database_path
        self._init_audit_table()
    
    @contextmanager
    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_audit_table(self):
        """Create audit_log table if it doesn't exist."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    post_id TEXT,
                    run_id INTEGER,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_post_id
                ON audit_log(post_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_action
                ON audit_log(action)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp DESC)
            """)
            
            conn.commit()
    
    def log(self, action: str, post_id: Optional[str] = None, 
            run_id: Optional[int] = None, details: Optional[Dict] = None) -> bool:
        """Log an operation to audit trail.
        
        Args:
            action: Action type (e.g., 'post_ingested')
            post_id: Associated Reddit post ID
            run_id: Associated run ID
            details: Additional context as dictionary
        
        Returns:
            True if logged successfully
        """
        if action not in self.ACTIONS:
            return False
        
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO audit_log (timestamp, action, post_id, run_id, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    int(time.time()),
                    action,
                    post_id,
                    run_id,
                    json.dumps(details) if details else None
                ))
                conn.commit()
            return True
        except Exception as e:
            print(f"Audit log error: {e}")
            return False
    
    def get_post_history(self, post_id: str) -> List[Dict]:
        """Get all operations for a post.
        
        Args:
            post_id: Reddit post ID
        
        Returns:
            List of audit entries
        """
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_log
                WHERE post_id = ?
                ORDER BY timestamp ASC
            """, (post_id,)).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def get_run_history(self, run_id: int) -> List[Dict]:
        """Get all operations in a run.
        
        Args:
            run_id: Run ID
        
        Returns:
            List of audit entries
        """
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_log
                WHERE run_id = ?
                ORDER BY timestamp ASC
            """, (run_id,)).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def get_action_history(self, action: str, limit: int = 100) -> List[Dict]:
        """Get recent occurrences of an action.
        
        Args:
            action: Action type
            limit: Maximum results
        
        Returns:
            List of audit entries
        """
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_log
                WHERE action = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (action, limit)).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def get_recent_errors(self, limit: int = 50) -> List[Dict]:
        """Get recent errors from audit trail.
        
        Args:
            limit: Maximum results
        
        Returns:
            List of error audit entries
        """
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM audit_log
                WHERE action IN ('error_occurred', 'cost_limit_exceeded')
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [self._row_to_dict(row) for row in rows]
    
    def get_timeline(self, post_id: str) -> str:
        """Get human-readable timeline for a post.
        
        Args:
            post_id: Reddit post ID
        
        Returns:
            Formatted timeline string
        """
        history = self.get_post_history(post_id)
        
        if not history:
            return "No audit history found."
        
        lines = [f"Timeline for post {post_id}:"]
        for entry in history:
            dt = datetime.fromtimestamp(entry['timestamp'])
            action_desc = self.ACTIONS.get(entry['action'], entry['action'])
            lines.append(f"  {dt.isoformat()} - {action_desc}")
        
        return "\n".join(lines)
    
    @staticmethod
    def _row_to_dict(row) -> Dict:
        """Convert sqlite3.Row to dictionary."""
        data = dict(row)
        # Parse details JSON if present
        if data.get('details'):
            try:
                data['details'] = json.loads(data['details'])
            except json.JSONDecodeError:
                pass
        return data
