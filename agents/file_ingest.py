"""File-based data ingestion agent for manual curation."""
from typing import List, Dict, Any
import json
import csv
import os
from agents.base_ingest import BaseIngestAgent


class FileIngestAgent(BaseIngestAgent):
    """Ingest posts from local JSON or CSV files.
    
    Useful for testing or manual curation. No external API required.
    """
    
    @property
    def source_name(self) -> str:
        return "file"
    
    def fetch_posts(self) -> List[Dict[str, Any]]:
        """Fetch posts from configured file paths.
        
        Returns:
            List of posts in standardized format
        
        Raises:
            Exception: If file paths are invalid or files cannot be read
        """
        if not self.settings.file_ingest_paths:
            return []
        
        file_paths = [path.strip() for path in self.settings.file_ingest_paths.split(',')]
        all_posts = []
        
        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                print(f"Warning: File not found: {file_path}")
                continue
            
            try:
                if file_path.endswith('.json'):
                    posts = self._read_json_file(file_path)
                elif file_path.endswith('.csv'):
                    posts = self._read_csv_file(file_path)
                else:
                    print(f"Warning: Unsupported file format: {file_path}")
                    continue
                
                all_posts.extend(posts)
            except Exception as e:
                print(f"Warning: Failed to read file '{file_path}': {e}")
                continue
        
        return all_posts[:self.settings.file_post_limit]
    
    def _read_json_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Read posts from JSON file.
        
        Expected format: Array of objects with standardized fields
        
        Args:
            file_path: Path to JSON file
        
        Returns:
            List of standardized posts
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]
        
        posts = []
        for item in data:
            post = self._normalize_post(item)
            if post:
                posts.append(post)
        
        return posts
    
    def _read_csv_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Read posts from CSV file.
        
        Expected columns: id, title, body, score, url, author, created_utc
        
        Args:
            file_path: Path to CSV file
        
        Returns:
            List of standardized posts
        """
        posts = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                post = self._normalize_post(row)
                if post:
                    posts.append(post)
        
        return posts
    
    def _normalize_post(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize post data to standardized format.
        
        Args:
            data: Raw post data from file
        
        Returns:
            Standardized post dict, or None if required fields missing
        """
        # Check for required fields
        if not data.get('title'):
            return None
        
        # Generate ID if missing
        post_id = data.get('id') or data.get('title', '')[:50]
        if not post_id.startswith('file_'):
            post_id = f"file_{post_id}"
        
        return {
            'id': post_id,
            'title': str(data.get('title', '')),
            'body': str(data.get('body', data.get('content', ''))),
            'score': int(data.get('score', 0)),
            'url': str(data.get('url', '')),
            'source': 'file',
            'author': str(data.get('author', 'unknown')),
            'created_utc': float(data.get('created_utc', data.get('timestamp', 0))),
            'num_comments': int(data.get('num_comments', 0))
        }
