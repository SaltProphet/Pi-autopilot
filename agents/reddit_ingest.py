from services.reddit_client import RedditClient
from services.storage import Storage
from config import settings


def ingest_reddit_posts():
    reddit_client = RedditClient()
    storage = Storage()

    subreddits = [s.strip() for s in settings.reddit_subreddits.split(',')]
    total_saved = 0

    for subreddit_name in subreddits:
        posts = reddit_client.fetch_posts(
            subreddit_name,
            limit=settings.reddit_post_limit,
            min_score=settings.reddit_min_score
        )

        for post in posts:
            if storage.save_post(post):
                total_saved += 1

    return {"total_saved": total_saved}
