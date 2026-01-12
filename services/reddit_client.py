import praw
from config import settings
from services.retry_handler import RetryHandler


class RedditClient:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent
        )
        self.retry_handler = RetryHandler()
    
    def fetch_posts(self, subreddit_name: str, limit: int, min_score: int):
        def fetch_with_retry():
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for submission in subreddit.hot(limit=limit):
                if submission.score >= min_score:
                    posts.append({
                        "id": submission.id,
                        "title": submission.title,
                        "body": submission.selftext,
                        "author": str(submission.author),
                        "score": submission.score,
                        "url": submission.url,
                        "subreddit": subreddit_name,
                        "timestamp": int(submission.created_utc),
                        "num_comments": submission.num_comments
                    })
            
            return posts
        
        return self.retry_handler.with_retry(fetch_with_retry, api_type='reddit')
