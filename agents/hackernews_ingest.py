"""HackerNews data ingestion agent using Algolia API."""
from typing import List, Dict, Any
import requests
from agents.base_ingest import BaseIngestAgent


class HackerNewsIngestAgent(BaseIngestAgent):
    """Ingest posts from HackerNews using public Algolia API.
    
    No authentication required! Fetches Ask HN and Show HN posts.
    """
    
    ALGOLIA_API_BASE = "https://hn.algolia.com/api/v1"
    
    @property
    def source_name(self) -> str:
        return "hackernews"
    
    def fetch_posts(self) -> List[Dict[str, Any]]:
        """Fetch posts from HackerNews.
        
        Returns:
            List of posts in standardized format
        
        Raises:
            Exception: If HackerNews API is unavailable
        """
        all_posts = []
        
        # Parse story types from config
        story_types = [s.strip().lower() for s in self.settings.hn_story_types.split(',')]
        
        for story_type in story_types:
            # Map story type to search tag
            tag = self._get_search_tag(story_type)
            if not tag:
                continue
            
            try:
                posts = self._fetch_by_tag(tag)
                all_posts.extend(posts)
            except Exception as e:
                print(f"Warning: Failed to fetch HN posts for tag '{tag}': {e}")
                # Continue with other tags
                continue
        
        # Sort by score and limit
        all_posts.sort(key=lambda x: x['score'], reverse=True)
        return all_posts[:self.settings.hn_post_limit]
    
    def _get_search_tag(self, story_type: str) -> str:
        """Map story type config to HN search tag."""
        mapping = {
            'ask_hn': 'ask_hn',
            'show_hn': 'show_hn',
            'story': 'story',
            'poll': 'poll'
        }
        return mapping.get(story_type, '')
    
    def _fetch_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Fetch posts from HN Algolia API by tag.
        
        Args:
            tag: HN tag (ask_hn, show_hn, story, poll)
        
        Returns:
            List of standardized posts
        """
        # Algolia search endpoint with filters
        url = f"{self.ALGOLIA_API_BASE}/search"
        params = {
            'tags': tag,
            'numericFilters': f'points>={self.settings.hn_min_score}',
            'hitsPerPage': self.settings.hn_post_limit
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        posts = []
        
        for hit in data.get('hits', []):
            # Extract post data from Algolia response
            post = {
                'id': f"hn_{hit.get('objectID', '')}",
                'title': hit.get('title', hit.get('story_title', '')),
                'body': hit.get('story_text', hit.get('comment_text', '')),
                'score': hit.get('points', 0),
                'url': self._get_post_url(hit),
                'source': 'hackernews',
                'author': hit.get('author', 'unknown'),
                'created_utc': float(hit.get('created_at_i', 0)),
                'num_comments': hit.get('num_comments', 0)
            }
            
            # Only include posts with titles (skip orphaned comments)
            if post['title']:
                posts.append(post)
        
        return posts
    
    def _get_post_url(self, hit: Dict[str, Any]) -> str:
        """Generate HackerNews URL for a post.
        
        Args:
            hit: Algolia API hit object
        
        Returns:
            URL to the HN post
        """
        object_id = hit.get('objectID', '')
        if object_id:
            return f"https://news.ycombinator.com/item?id={object_id}"
        return "https://news.ycombinator.com/"
