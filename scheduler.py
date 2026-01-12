#!/usr/bin/env python3
"""
Scheduler script for automated scraping and product generation.
Runs scheduled jobs at configured intervals.
"""
import os
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from agents.reddit_scraper import RedditScraper
from agents.product_generator import ProductGenerator
from agents.db import get_posts_without_specs, get_pending_product_specs

# Load environment variables
load_dotenv()

# Get configuration
SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", 24))
GENERATION_INTERVAL_HOURS = int(os.getenv("GENERATION_INTERVAL_HOURS", 6))

# Default subreddits to scrape
DEFAULT_SUBREDDITS = [
    "SideProject",
    "Entrepreneur",
    "startups",
    "indiehackers",
    "programming"
]


def scrape_job():
    """
    Scheduled job to scrape Reddit posts.
    Scrapes multiple subreddits and saves posts to database.
    """
    print(f"\n{'='*60}")
    print(f"SCRAPE JOB STARTED: {datetime.now().isoformat()}")
    print(f"{'='*60}")
    
    try:
        scraper = RedditScraper()
        
        # Scrape each default subreddit
        total_saved = 0
        for subreddit in DEFAULT_SUBREDDITS:
            result = scraper.scrape_subreddit(subreddit, limit=10)
            total_saved += result.get("saved", 0)
            time.sleep(2)  # Be nice to Reddit API
        
        print(f"\nScrape job complete: {total_saved} new posts saved")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"Error in scrape job: {e}")
        print(f"{'='*60}\n")


def generation_job():
    """
    Scheduled job to generate product specs.
    Finds posts without specs and generates product specifications.
    """
    print(f"\n{'='*60}")
    print(f"GENERATION JOB STARTED: {datetime.now().isoformat()}")
    print(f"{'='*60}")
    
    try:
        generator = ProductGenerator()
        
        # Get posts without specs
        posts = get_posts_without_specs()
        
        if not posts:
            print("No posts without specs found")
            print(f"{'='*60}\n")
            return
        
        # Generate specs for up to 5 posts
        generated = 0
        for post in posts[:5]:
            spec = generator.generate_product_spec(post["id"])
            if spec:
                generated += 1
            time.sleep(5)  # Rate limiting for OpenAI API
        
        print(f"\nGeneration job complete: {generated} specs generated")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"Error in generation job: {e}")
        print(f"{'='*60}\n")


def main():
    """
    Main scheduler function.
    Sets up and runs scheduled jobs.
    """
    print(f"\n{'*'*60}")
    print(f"Pi-Autopilot Scheduler Starting")
    print(f"{'*'*60}")
    print(f"Scrape interval: {SCRAPE_INTERVAL_HOURS} hours")
    print(f"Generation interval: {GENERATION_INTERVAL_HOURS} hours")
    print(f"Default subreddits: {', '.join(DEFAULT_SUBREDDITS)}")
    print(f"{'*'*60}\n")
    
    # Create scheduler
    scheduler = BlockingScheduler()
    
    # Add scrape job
    scheduler.add_job(
        scrape_job,
        'interval',
        hours=SCRAPE_INTERVAL_HOURS,
        id='scrape_job',
        name='Reddit Scraping Job',
        next_run_time=datetime.now()  # Run immediately on start
    )
    
    # Add generation job
    scheduler.add_job(
        generation_job,
        'interval',
        hours=GENERATION_INTERVAL_HOURS,
        id='generation_job',
        name='Product Generation Job',
        next_run_time=datetime.now()  # Run immediately on start
    )
    
    print("Scheduler initialized. Jobs will run at scheduled intervals.")
    print("Press Ctrl+C to stop.\n")
    
    try:
        # Start scheduler (blocks until stopped)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped by user")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
