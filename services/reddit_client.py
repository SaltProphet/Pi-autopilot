import praw
from config import settings


class RedditClient:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent
        )
    
    def fetch_posts(self, subreddit_name: str, limit: int, min_score: int):
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
