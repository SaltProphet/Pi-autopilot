import sqlite3
import json
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
                    raw_json TEXT
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
            
            conn.commit()
    
    def save_post(self, post_data: dict):
        with self._get_conn() as conn:
            try:
                conn.execute("""
                    INSERT INTO reddit_posts (id, title, body, timestamp, subreddit, author, score, url, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    post_data["id"],
                    post_data["title"],
                    post_data["body"],
                    post_data["timestamp"],
                    post_data["subreddit"],
                    post_data["author"],
                    post_data["score"],
                    post_data["url"],
                    json.dumps(post_data)
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
            # Get posts that either:
            # 1. Have never been processed (pr.id IS NULL)
            # 2. Have only failed/discarded/cost_exceeded runs (no successful completion)
            rows = conn.execute("""
                SELECT rp.* FROM reddit_posts rp
                LEFT JOIN (
                    SELECT post_id, MAX(created_at) as last_run
                    FROM pipeline_runs
                    WHERE status IN ('completed', 'gumroad_uploaded')
                    GROUP BY post_id
                ) successful ON rp.id = successful.post_id
                WHERE successful.post_id IS NULL
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
