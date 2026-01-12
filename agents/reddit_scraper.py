"""
Reddit scraper module using PRAW.
Scrapes posts from specified subreddits and saves to database.
"""
import os
import praw
from datetime import datetime
from typing import List, Dict, Any
from agents.db import save_reddit_post

# Load environment variables
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "Pi-Autopilot/1.0")


class RedditScraper:
    """Handles Reddit scraping operations using PRAW."""
    
    def __init__(self):
        """Initialize Reddit API client."""
        if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
            raise ValueError("Reddit API credentials not found in environment variables")
        
        self.reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        print(f"Reddit client initialized. Read-only: {self.reddit.read_only}")
    
    def scrape_subreddit(self, subreddit_name: str, limit: int = 10, 
                        time_filter: str = "week") -> Dict[str, Any]:
        """
        Scrape top posts from a subreddit.
        
        Args:
            subreddit_name: Name of the subreddit (without r/)
            limit: Number of posts to fetch (default 10)
            time_filter: Time filter for top posts (day, week, month, year, all)
        
        Returns:
            Dict with scraped count and saved count
        """
        try:
            print(f"Scraping r/{subreddit_name}...")
            subreddit = self.reddit.subreddit(subreddit_name)
            
            scraped = 0
            saved = 0
            skipped = 0
            
            # Fetch top posts from the time period
            for submission in subreddit.top(time_filter=time_filter, limit=limit):
                scraped += 1
                
                # Extract post data
                post_id = submission.id
                title = submission.title
                body = submission.selftext if submission.is_self else ""
                timestamp = int(submission.created_utc)
                author = str(submission.author) if submission.author else "[deleted]"
                score = submission.score
                url = submission.url
                
                # Save to database
                success = save_reddit_post(
                    post_id=post_id,
                    title=title,
                    body=body,
                    timestamp=timestamp,
                    subreddit=subreddit_name,
                    author=author,
                    score=score,
                    url=url
                )
                
                if success:
                    saved += 1
                    print(f"  Saved: {post_id} - {title[:60]}...")
                else:
                    skipped += 1
                    print(f"  Skipped (duplicate): {post_id}")
            
            result = {
                "subreddit": subreddit_name,
                "scraped": scraped,
                "saved": saved,
                "skipped": skipped,
                "time_filter": time_filter
            }
            print(f"Scrape complete: {saved} new posts saved, {skipped} skipped")
            return result
            
        except Exception as e:
            error_msg = f"Error scraping r/{subreddit_name}: {str(e)}"
            print(error_msg)
            return {
                "subreddit": subreddit_name,
                "scraped": 0,
                "saved": 0,
                "skipped": 0,
                "error": error_msg
            }
    
    def scrape_multiple_subreddits(self, subreddit_list: List[str], 
                                   limit: int = 10) -> Dict[str, Any]:
        """
        Scrape multiple subreddits.
        
        Args:
            subreddit_list: List of subreddit names
            limit: Number of posts per subreddit
        
        Returns:
            Dict with results for each subreddit
        """
        results = {
            "total_scraped": 0,
            "total_saved": 0,
            "subreddits": {}
        }
        
        for subreddit_name in subreddit_list:
            result = self.scrape_subreddit(subreddit_name, limit=limit)
            results["total_scraped"] += result["scraped"]
            results["total_saved"] += result["saved"]
            results["subreddits"][subreddit_name] = result
        
        return results


def scrape_subreddit(subreddit_name: str, limit: int = 10) -> Dict[str, Any]:
    """
    Convenience function to scrape a single subreddit.
    Creates scraper instance and returns results.
    """
    try:
        scraper = RedditScraper()
        return scraper.scrape_subreddit(subreddit_name, limit=limit)
    except Exception as e:
        return {
            "subreddit": subreddit_name,
            "scraped": 0,
            "saved": 0,
            "error": str(e)
        }
