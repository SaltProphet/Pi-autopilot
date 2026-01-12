"""
Database module for SQLite operations.
Manages reddit_posts and product_specs tables.
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Get database path from environment or use default
DATABASE_PATH = os.getenv("DATABASE_PATH", "./pi_autopilot.db")


@contextmanager
def get_db_connection():
    """Context manager for database connections with automatic cleanup."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """
    Initialize the SQLite database with required tables.
    Creates reddit_posts and product_specs tables if they don't exist.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create reddit_posts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reddit_posts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT,
                timestamp INTEGER NOT NULL,
                subreddit TEXT,
                author TEXT,
                score INTEGER DEFAULT 0,
                url TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        # Create product_specs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_post_id TEXT NOT NULL,
                json_spec TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                gumroad_product_id TEXT,
                FOREIGN KEY (source_post_id) REFERENCES reddit_posts(id)
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reddit_posts_timestamp 
            ON reddit_posts(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_product_specs_status 
            ON product_specs(status)
        """)
        
        conn.commit()
        print(f"Database initialized at {DATABASE_PATH}")


def save_reddit_post(post_id: str, title: str, body: str, timestamp: int, 
                     subreddit: str = None, author: str = None, 
                     score: int = 0, url: str = None) -> bool:
    """
    Save a Reddit post to the database.
    Returns True if saved successfully, False if already exists or error.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reddit_posts 
                (id, title, body, timestamp, subreddit, author, score, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, title, body, timestamp, subreddit, author, score, url))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        # Post already exists
        return False
    except Exception as e:
        print(f"Error saving reddit post {post_id}: {e}")
        return False


def get_reddit_post(post_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a Reddit post by ID.
    Returns dict with post data or None if not found.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reddit_posts WHERE id = ?", (post_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"Error getting reddit post {post_id}: {e}")
        return None


def get_recent_reddit_posts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recent Reddit posts.
    Returns list of post dicts ordered by timestamp descending.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM reddit_posts 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting recent posts: {e}")
        return []


def save_product_spec(source_post_id: str, json_spec: Dict[str, Any], 
                      status: str = "pending") -> Optional[int]:
    """
    Save a product specification to the database.
    Returns the product_spec ID if saved successfully, None on error.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO product_specs (source_post_id, json_spec, status)
                VALUES (?, ?, ?)
            """, (source_post_id, json.dumps(json_spec), status))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Error saving product spec for post {source_post_id}: {e}")
        return None


def get_product_spec(spec_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve a product spec by ID.
    Returns dict with spec data (json_spec parsed) or None if not found.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM product_specs WHERE id = ?", (spec_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                # Parse JSON spec
                data['json_spec'] = json.loads(data['json_spec'])
                return data
            return None
    except Exception as e:
        print(f"Error getting product spec {spec_id}: {e}")
        return None


def update_product_spec_status(spec_id: int, status: str, 
                                gumroad_product_id: str = None) -> bool:
    """
    Update the status of a product spec.
    Optionally set the Gumroad product ID.
    Returns True if updated successfully.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if gumroad_product_id:
                cursor.execute("""
                    UPDATE product_specs 
                    SET status = ?, gumroad_product_id = ?
                    WHERE id = ?
                """, (status, gumroad_product_id, spec_id))
            else:
                cursor.execute("""
                    UPDATE product_specs 
                    SET status = ?
                    WHERE id = ?
                """, (status, spec_id))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating product spec {spec_id}: {e}")
        return False


def get_pending_product_specs(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get product specs with 'pending' status.
    Returns list of spec dicts with parsed json_spec.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM product_specs 
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data['json_spec'] = json.loads(data['json_spec'])
                results.append(data)
            return results
    except Exception as e:
        print(f"Error getting pending product specs: {e}")
        return []


def get_posts_without_specs() -> List[Dict[str, Any]]:
    """
    Get Reddit posts that don't have product specs yet.
    Returns list of post dicts.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT rp.* FROM reddit_posts rp
                LEFT JOIN product_specs ps ON rp.id = ps.source_post_id
                WHERE ps.id IS NULL
                ORDER BY rp.timestamp DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting posts without specs: {e}")
        return []


def get_database_stats() -> Dict[str, int]:
    """
    Get statistics about the database contents.
    Returns dict with counts of posts, specs, and specs by status.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Count posts
            cursor.execute("SELECT COUNT(*) FROM reddit_posts")
            total_posts = cursor.fetchone()[0]
            
            # Count specs
            cursor.execute("SELECT COUNT(*) FROM product_specs")
            total_specs = cursor.fetchone()[0]
            
            # Count specs by status
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM product_specs 
                GROUP BY status
            """)
            specs_by_status = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_posts": total_posts,
                "total_specs": total_specs,
                "pending_specs": specs_by_status.get("pending", 0),
                "completed_specs": specs_by_status.get("completed", 0),
                "failed_specs": specs_by_status.get("failed", 0),
            }
    except Exception as e:
        print(f"Error getting database stats: {e}")
        return {
            "total_posts": 0,
            "total_specs": 0,
            "pending_specs": 0,
            "completed_specs": 0,
            "failed_specs": 0,
        }


# Initialize database on module import
if __name__ != "__main__":
    init_database()
