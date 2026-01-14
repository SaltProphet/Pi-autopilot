"""Base abstraction layer for data ingestion agents."""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseIngestAgent(ABC):
    """Abstract base class for data ingestion agents.
    
    All ingest agents must implement this interface to ensure
    a standardized data format throughout the pipeline.
    """
    
    def __init__(self, settings):
        """Initialize the ingest agent with configuration settings.
        
        Args:
            settings: Configuration settings object containing source-specific configs
        """
        self.settings = settings
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the name of this data source (e.g., 'reddit', 'hackernews').
        
        Returns:
            String identifier for this data source
        """
        pass
    
    @abstractmethod
    def fetch_posts(self) -> List[Dict[str, Any]]:
        """Fetch posts from the data source.
        
        Returns:
            List of dicts with standardized format:
            {
                'id': str,              # Unique identifier for the post
                'title': str,           # Post title
                'body': str,            # Post body/content
                'score': int,           # Score/upvotes/points
                'url': str,             # URL to original post
                'source': str,          # Source name (reddit/hackernews/rss/etc)
                'author': str,          # Post author username
                'created_utc': float,   # Unix timestamp of post creation
                'num_comments': int     # Number of comments (optional, default 0)
            }
        """
        pass
