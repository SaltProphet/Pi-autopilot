"""Reddit data ingestion agent."""
from typing import List, Dict, Any
from agents.base_ingest import BaseIngestAgent


class RedditIngestAgent(BaseIngestAgent):
    """Ingest posts from Reddit using PRAW."""
    
    @property
    def source_name(self) -> str:
        return "reddit"
    
    def fetch_posts(self) -> List[Dict[str, Any]]:
        """Fetch posts from configured subreddits.
        
        Returns:
            List of posts in standardized format
        
        Raises:
            Exception: If Reddit API is unavailable or credentials are invalid
        """
        # Import here to avoid circular dependency and config loading at module level
        from services.reddit_client import RedditClient
        
        reddit_client = RedditClient()
        subreddits = [s.strip() for s in self.settings.reddit_subreddits.split(',')]
        
        all_posts = []
        
        for subreddit_name in subreddits:
            posts = reddit_client.fetch_posts(
                subreddit_name,
                limit=self.settings.reddit_post_limit,
                min_score=self.settings.reddit_min_score
            )
            
            # Convert to standardized format
            for post in posts:
                standardized_post = {
                    'id': post['id'],
                    'title': post['title'],
                    'body': post['body'],
                    'score': post['score'],
                    'url': post['url'],
                    'source': 'reddit',
                    'author': post['author'],
                    'created_utc': float(post['timestamp']),
                    'num_comments': post.get('num_comments', 0)
                }
                all_posts.append(standardized_post)
        
        return all_posts


# Backward compatibility: keep original function for existing code
def ingest_reddit_posts():
    """Legacy function for backward compatibility.
    
    Returns:
        Dict with 'total_saved' and 'post_ids' keys
    """
    from services.storage import Storage
    from config import settings
    
    agent = RedditIngestAgent(settings)
    storage = Storage()
    
    posts = agent.fetch_posts()
    
    total_saved = 0
    post_ids = []
    
    for post in posts:
        if storage.save_post(post):
            total_saved += 1
            post_ids.append(post['id'])
    
    return {"total_saved": total_saved, "post_ids": post_ids}
