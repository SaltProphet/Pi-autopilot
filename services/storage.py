import sqlite3
import json
import time
from contextlib import contextmanager
from config import settings


class Storage:
    def __init__(self):
        self.db_path = settings.database_path
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_db(self):
        with self._get_conn() as conn:
            # Check if source column exists, if not, add migration
            cursor = conn.execute("PRAGMA table_info(reddit_posts)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'source' not in columns:
                # Migrate existing table by adding source column
                conn.execute("""
                    ALTER TABLE reddit_posts ADD COLUMN source TEXT DEFAULT 'reddit'
                """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reddit_posts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    body TEXT,
                    timestamp INTEGER NOT NULL,
                    subreddit TEXT,
                    author TEXT,
                    score INTEGER,
                    url TEXT,
                    raw_json TEXT,
                    source TEXT DEFAULT 'reddit'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    artifact_path TEXT,
                    error_message TEXT,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (post_id) REFERENCES reddit_posts(id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    tokens_sent INTEGER NOT NULL,
                    tokens_received INTEGER NOT NULL,
                    usd_cost REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    model TEXT,
                    abort_reason TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    post_id TEXT,
                    run_id TEXT,
                    details TEXT,
                    error_occurred INTEGER DEFAULT 0,
                    cost_limit_exceeded INTEGER DEFAULT 0
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_post_id ON audit_log(post_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp_desc ON audit_log(timestamp DESC)")
            
            # Add performance indexes for frequently queried columns
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_post_id ON pipeline_runs(post_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cost_tracking_timestamp ON cost_tracking(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reddit_posts_timestamp ON reddit_posts(timestamp)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sales_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    product_name TEXT,
                    sales_count INTEGER DEFAULT 0,
                    revenue_cents INTEGER DEFAULT 0,
                    views INTEGER DEFAULT 0,
                    refunds INTEGER DEFAULT 0,
                    fetched_at INTEGER NOT NULL,
                    created_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_product_id ON sales_metrics(product_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_fetched_at ON sales_metrics(fetched_at DESC)")
            
            conn.commit()
    
    def save_post(self, post_data: dict):
        with self._get_conn() as conn:
            try:
                # Convert created_utc to timestamp for backward compatibility
                timestamp = int(post_data.get("created_utc", post_data.get("timestamp", time.time())))
                
                # Extract subreddit from source or set default
                subreddit = post_data.get("subreddit", post_data.get("source", "unknown"))
                
                conn.execute("""
                    INSERT INTO reddit_posts (id, title, body, timestamp, subreddit, author, score, url, raw_json, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post_data["id"],
                    post_data["title"],
                    post_data.get("body", ""),
                    timestamp,
                    subreddit,
                    post_data.get("author", "unknown"),
                    post_data.get("score", 0),
                    post_data.get("url", ""),
                    json.dumps(post_data),
                    post_data.get("source", "unknown")
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_post(self, post_id: str):
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM reddit_posts WHERE id = ?", (post_id,)).fetchone()
            if row:
                return dict(row)
            return None
    
    def get_unprocessed_posts(self):
        with self._get_conn() as conn:
            # Optimized query: Get posts that don't have successful completion
            # Uses index on post_id and status for better performance
            rows = conn.execute("""
                SELECT rp.* FROM reddit_posts rp
                WHERE NOT EXISTS (
                    SELECT 1 FROM pipeline_runs pr
                    WHERE pr.post_id = rp.id
                    AND pr.status IN ('completed', 'gumroad_uploaded')
                )
                ORDER BY rp.timestamp DESC
            """).fetchall()
            return [dict(row) for row in rows]
    
    def log_pipeline_run(self, post_id: str, stage: str, status: str, artifact_path: str = None, error_message: str = None):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO pipeline_runs (post_id, stage, status, artifact_path, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (post_id, stage, status, artifact_path, error_message))
            conn.commit()
    
    def get_pipeline_runs(self, post_id: str):
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM pipeline_runs
                WHERE post_id = ?
                ORDER BY created_at ASC
            """, (post_id,)).fetchall()
            return [dict(row) for row in rows]
    
    def save_sales_metrics(self, product_id: str, product_name: str, sales_count: int, 
                          revenue_cents: int, views: int, refunds: int, fetched_at: int):
        """Save sales metrics for a product."""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO sales_metrics (product_id, product_name, sales_count, revenue_cents, views, refunds, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_id, product_name, sales_count, revenue_cents, views, refunds, fetched_at))
            conn.commit()
    
    def get_sales_metrics_since(self, days: int):
        """Get sales metrics from the last N days."""
        with self._get_conn() as conn:
            cutoff_timestamp = int(time.time() - (days * 86400))
            rows = conn.execute("""
                SELECT * FROM sales_metrics
                WHERE fetched_at >= ?
                ORDER BY fetched_at DESC
            """, (cutoff_timestamp,)).fetchall()
            return [dict(row) for row in rows]
    
    def get_recent_uploaded_products(self, limit: int = 100):
        """Get recently uploaded products from pipeline runs."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT pr.post_id, pr.artifact_path, pr.created_at, rp.title
                FROM pipeline_runs pr
                JOIN reddit_posts rp ON pr.post_id = rp.id
                WHERE pr.stage = 'gumroad_upload' AND pr.status = 'completed'
                ORDER BY pr.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
