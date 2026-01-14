"""Factory for creating and managing data ingestion agents."""
from typing import List
from agents.base_ingest import BaseIngestAgent


class IngestFactory:
    """Factory for dynamically loading enabled data ingestion agents."""
    
    def __init__(self, settings):
        """Initialize factory with configuration settings.
        
        Args:
            settings: Configuration settings object
        """
        self.settings = settings
    
    def get_enabled_agents(self) -> List[BaseIngestAgent]:
        """Load all enabled data ingestion agents based on config.
        
        Returns:
            List of enabled BaseIngestAgent instances
        """
        agents = []
        
        # Parse enabled sources from config
        sources = [s.strip().lower() for s in self.settings.data_sources.split(',')]
        
        for source in sources:
            agent = self._create_agent(source)
            if agent:
                agents.append(agent)
        
        return agents
    
    def _create_agent(self, source: str) -> BaseIngestAgent:
        """Create a specific ingest agent by source name.
        
        Args:
            source: Source identifier (reddit, hackernews, rss, file)
        
        Returns:
            Instantiated agent, or None if source invalid or not configured
        """
        if source == 'reddit':
            return self._create_reddit_agent()
        elif source == 'hackernews':
            return self._create_hackernews_agent()
        elif source == 'rss':
            return self._create_rss_agent()
        elif source == 'file':
            return self._create_file_agent()
        else:
            print(f"Warning: Unknown data source '{source}'")
            return None
    
    def _create_reddit_agent(self) -> BaseIngestAgent:
        """Create Reddit agent if credentials are configured.
        
        Returns:
            RedditIngestAgent or None
        """
        if not self.settings.reddit_client_id or not self.settings.reddit_client_secret:
            print("Warning: Reddit source enabled but credentials not configured. Skipping.")
            return None
        
        # Import here to avoid loading config at module level
        from agents.reddit_ingest import RedditIngestAgent
        return RedditIngestAgent(self.settings)
    
    def _create_hackernews_agent(self) -> BaseIngestAgent:
        """Create HackerNews agent (no credentials required).
        
        Returns:
            HackerNewsIngestAgent
        """
        from agents.hackernews_ingest import HackerNewsIngestAgent
        return HackerNewsIngestAgent(self.settings)
    
    def _create_rss_agent(self) -> BaseIngestAgent:
        """Create RSS agent if feed URLs are configured.
        
        Returns:
            RSSIngestAgent or None
        """
        if not self.settings.rss_feed_urls:
            print("Warning: RSS source enabled but no feed URLs configured. Skipping.")
            return None
        
        from agents.rss_ingest import RSSIngestAgent
        return RSSIngestAgent(self.settings)
    
    def _create_file_agent(self) -> BaseIngestAgent:
        """Create file agent if file paths are configured.
        
        Returns:
            FileIngestAgent or None
        """
        if not self.settings.file_ingest_paths:
            print("Warning: File source enabled but no file paths configured. Skipping.")
            return None
        
        from agents.file_ingest import FileIngestAgent
        return FileIngestAgent(self.settings)
