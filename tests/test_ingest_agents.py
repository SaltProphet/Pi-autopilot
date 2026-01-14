"""Tests for data ingestion agents and factory."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os


@pytest.mark.unit
class TestBaseIngestAgent:
    """Test base abstract ingest agent."""
    
    def test_cannot_instantiate_base_class(self):
        """Test that BaseIngestAgent cannot be instantiated directly."""
        from agents.base_ingest import BaseIngestAgent
        
        with pytest.raises(TypeError):
            BaseIngestAgent(Mock())
    
    def test_subclass_must_implement_source_name(self):
        """Test that subclasses must implement source_name property."""
        from agents.base_ingest import BaseIngestAgent
        
        class IncompleteAgent(BaseIngestAgent):
            def fetch_posts(self):
                return []
        
        with pytest.raises(TypeError):
            IncompleteAgent(Mock())
    
    def test_subclass_must_implement_fetch_posts(self):
        """Test that subclasses must implement fetch_posts method."""
        from agents.base_ingest import BaseIngestAgent
        
        class IncompleteAgent(BaseIngestAgent):
            @property
            def source_name(self):
                return "test"
        
        with pytest.raises(TypeError):
            IncompleteAgent(Mock())


@pytest.mark.unit
class TestRedditIngestAgent:
    """Test Reddit ingest agent."""
    
    @patch('services.reddit_client.praw.Reddit')
    def test_reddit_agent_fetch_posts(self, mock_praw):
        """Test Reddit agent fetches and transforms posts correctly."""
        from agents.reddit_ingest import RedditIngestAgent
        
        # Setup mock
        settings = Mock()
        settings.reddit_subreddits = "test1,test2"
        settings.reddit_post_limit = 10
        settings.reddit_min_score = 5
        
        # Mock Reddit client behavior
        mock_submission = Mock()
        mock_submission.id = "abc123"
        mock_submission.title = "Test Post"
        mock_submission.selftext = "Test body"
        mock_submission.score = 10
        mock_submission.url = "https://reddit.com/test"
        mock_submission.author = "testuser"
        mock_submission.created_utc = 1234567890
        mock_submission.num_comments = 5
        
        mock_subreddit = Mock()
        mock_subreddit.hot.return_value = [mock_submission]
        
        mock_reddit_instance = Mock()
        mock_reddit_instance.subreddit.return_value = mock_subreddit
        mock_praw.return_value = mock_reddit_instance
        
        agent = RedditIngestAgent(settings)
        posts = agent.fetch_posts()
        
        assert len(posts) == 2  # Called for 2 subreddits
        assert posts[0]['source'] == 'reddit'
        assert posts[0]['id'] == 'abc123'
        assert posts[0]['created_utc'] == 1234567890.0
    
    def test_reddit_agent_source_name(self):
        """Test Reddit agent returns correct source name."""
        from agents.reddit_ingest import RedditIngestAgent
        
        agent = RedditIngestAgent(Mock())
        assert agent.source_name == "reddit"


@pytest.mark.unit
class TestHackerNewsIngestAgent:
    """Test HackerNews ingest agent."""
    
    @patch('agents.hackernews_ingest.requests.get')
    def test_hackernews_agent_fetch_posts(self, mock_get):
        """Test HackerNews agent fetches posts from Algolia API."""
        from agents.hackernews_ingest import HackerNewsIngestAgent
        
        settings = Mock()
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn,show_hn"
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'hits': [
                {
                    'objectID': '12345',
                    'title': 'Ask HN: Test Question?',
                    'story_text': 'Test content',
                    'points': 100,
                    'author': 'hnuser',
                    'created_at_i': 1234567890,
                    'num_comments': 50
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        agent = HackerNewsIngestAgent(settings)
        posts = agent.fetch_posts()
        
        assert len(posts) > 0
        assert posts[0]['source'] == 'hackernews'
        assert posts[0]['id'] == 'hn_12345'
        assert 'news.ycombinator.com' in posts[0]['url']
    
    def test_hackernews_agent_source_name(self):
        """Test HackerNews agent returns correct source name."""
        from agents.hackernews_ingest import HackerNewsIngestAgent
        
        agent = HackerNewsIngestAgent(Mock())
        assert agent.source_name == "hackernews"
    
    @patch('agents.hackernews_ingest.requests.get')
    def test_hackernews_agent_handles_api_failure(self, mock_get):
        """Test HackerNews agent handles API failures gracefully."""
        from agents.hackernews_ingest import HackerNewsIngestAgent
        
        settings = Mock()
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn"
        
        mock_get.side_effect = Exception("API error")
        
        agent = HackerNewsIngestAgent(settings)
        posts = agent.fetch_posts()
        
        # Should return empty list on failure
        assert posts == []


@pytest.mark.unit
class TestRSSIngestAgent:
    """Test RSS ingest agent."""
    
    @patch('agents.rss_ingest.requests.get')
    def test_rss_agent_parses_rss_feed(self, mock_get):
        """Test RSS agent parses RSS 2.0 feeds correctly."""
        from agents.rss_ingest import RSSIngestAgent
        
        settings = Mock()
        settings.rss_feed_urls = "https://example.com/feed.xml"
        settings.rss_post_limit = 20
        
        # Mock RSS feed response
        rss_xml = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article</link>
                    <description>Test description</description>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
                    <author>testauthor</author>
                </item>
            </channel>
        </rss>
        """
        
        mock_response = Mock()
        mock_response.content = rss_xml.encode('utf-8')
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        agent = RSSIngestAgent(settings)
        posts = agent.fetch_posts()
        
        assert len(posts) == 1
        assert posts[0]['source'] == 'rss'
        assert posts[0]['title'] == 'Test Article'
        assert posts[0]['id'].startswith('rss_')
    
    def test_rss_agent_source_name(self):
        """Test RSS agent returns correct source name."""
        from agents.rss_ingest import RSSIngestAgent
        
        agent = RSSIngestAgent(Mock())
        assert agent.source_name == "rss"
    
    def test_rss_agent_handles_empty_feed_urls(self):
        """Test RSS agent handles empty feed URLs."""
        from agents.rss_ingest import RSSIngestAgent
        
        settings = Mock()
        settings.rss_feed_urls = ""
        settings.rss_post_limit = 20
        
        agent = RSSIngestAgent(settings)
        posts = agent.fetch_posts()
        
        assert posts == []


@pytest.mark.unit
class TestFileIngestAgent:
    """Test file-based ingest agent."""
    
    def test_file_agent_source_name(self):
        """Test File agent returns correct source name."""
        from agents.file_ingest import FileIngestAgent
        
        agent = FileIngestAgent(Mock())
        assert agent.source_name == "file"
    
    def test_file_agent_handles_empty_paths(self):
        """Test File agent handles empty file paths."""
        from agents.file_ingest import FileIngestAgent
        
        settings = Mock()
        settings.file_ingest_paths = ""
        settings.file_post_limit = 20
        
        agent = FileIngestAgent(settings)
        posts = agent.fetch_posts()
        
        assert posts == []
    
    @patch('agents.file_ingest.os.path.exists')
    @patch('builtins.open', create=True)
    def test_file_agent_reads_json_file(self, mock_open, mock_exists):
        """Test File agent reads JSON files correctly."""
        from agents.file_ingest import FileIngestAgent
        import json
        
        settings = Mock()
        settings.file_ingest_paths = "/tmp/test.json"
        settings.file_post_limit = 20
        
        mock_exists.return_value = True
        
        test_data = [{
            "id": "test123",
            "title": "Test Post",
            "body": "Test content",
            "score": 10,
            "url": "https://example.com",
            "author": "testuser",
            "created_utc": 1234567890
        }]
        
        mock_file = MagicMock()
        mock_file.__enter__.return_value = mock_file
        mock_file.read.return_value = json.dumps(test_data)
        mock_open.return_value = mock_file
        
        agent = FileIngestAgent(settings)
        posts = agent.fetch_posts()
        
        assert len(posts) == 1
        assert posts[0]['source'] == 'file'
        assert posts[0]['title'] == 'Test Post'


@pytest.mark.unit
class TestIngestFactory:
    """Test ingest factory."""
    
    def test_factory_creates_hackernews_agent(self):
        """Test factory creates HackerNews agent."""
        from agents.ingest_factory import IngestFactory
        from agents.hackernews_ingest import HackerNewsIngestAgent
        
        settings = Mock()
        settings.data_sources = "hackernews"
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn"
        
        factory = IngestFactory(settings)
        agents = factory.get_enabled_agents()
        
        assert len(agents) == 1
        assert isinstance(agents[0], HackerNewsIngestAgent)
    
    @patch('agents.reddit_ingest.RedditClient')
    def test_factory_creates_reddit_agent_with_credentials(self, mock_reddit_client):
        """Test factory creates Reddit agent when credentials provided."""
        from agents.ingest_factory import IngestFactory
        from agents.reddit_ingest import RedditIngestAgent
        
        settings = Mock()
        settings.data_sources = "reddit"
        settings.reddit_client_id = "test_id"
        settings.reddit_client_secret = "test_secret"
        settings.reddit_subreddits = "test"
        settings.reddit_post_limit = 20
        settings.reddit_min_score = 10
        
        factory = IngestFactory(settings)
        agents = factory.get_enabled_agents()
        
        assert len(agents) == 1
        assert isinstance(agents[0], RedditIngestAgent)
    
    def test_factory_skips_reddit_without_credentials(self):
        """Test factory skips Reddit agent when credentials missing."""
        from agents.ingest_factory import IngestFactory
        from agents.hackernews_ingest import HackerNewsIngestAgent
        
        settings = Mock()
        settings.data_sources = "reddit,hackernews"
        settings.reddit_client_id = ""
        settings.reddit_client_secret = ""
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn"
        
        factory = IngestFactory(settings)
        agents = factory.get_enabled_agents()
        
        # Should only have HackerNews agent
        assert len(agents) == 1
        assert isinstance(agents[0], HackerNewsIngestAgent)
    
    def test_factory_creates_multiple_agents(self):
        """Test factory creates multiple agents when configured."""
        from agents.ingest_factory import IngestFactory
        from agents.hackernews_ingest import HackerNewsIngestAgent
        from agents.rss_ingest import RSSIngestAgent
        
        settings = Mock()
        settings.data_sources = "hackernews,rss"
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn"
        settings.rss_feed_urls = "https://example.com/feed.xml"
        settings.rss_post_limit = 20
        
        factory = IngestFactory(settings)
        agents = factory.get_enabled_agents()
        
        assert len(agents) == 2
        assert any(isinstance(a, HackerNewsIngestAgent) for a in agents)
        assert any(isinstance(a, RSSIngestAgent) for a in agents)
    
    def test_factory_handles_invalid_source_name(self):
        """Test factory handles invalid source names gracefully."""
        from agents.ingest_factory import IngestFactory
        from agents.hackernews_ingest import HackerNewsIngestAgent
        
        settings = Mock()
        settings.data_sources = "invalid_source,hackernews"
        settings.hn_min_score = 50
        settings.hn_post_limit = 20
        settings.hn_story_types = "ask_hn"
        
        factory = IngestFactory(settings)
        agents = factory.get_enabled_agents()
        
        # Should only create valid agents
        assert len(agents) == 1
        assert isinstance(agents[0], HackerNewsIngestAgent)
    
    def test_factory_returns_empty_list_when_no_valid_sources(self):
        """Test factory returns empty list when no valid sources configured."""
        from agents.ingest_factory import IngestFactory
        
        settings = Mock()
        settings.data_sources = "reddit"
        settings.reddit_client_id = ""
        settings.reddit_client_secret = ""
        
        factory = IngestFactory(settings)
        agents = factory.get_enabled_agents()
        
        assert agents == []
