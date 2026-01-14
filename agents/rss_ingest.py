"""RSS/Atom feed data ingestion agent."""
from typing import List, Dict, Any
import hashlib
from datetime import datetime
import xml.etree.ElementTree as ET
import requests
from agents.base_ingest import BaseIngestAgent


class RSSIngestAgent(BaseIngestAgent):
    """Ingest posts from RSS/Atom feeds.
    
    No authentication required! Parses RSS 2.0 and Atom feeds.
    """
    
    @property
    def source_name(self) -> str:
        return "rss"
    
    def fetch_posts(self) -> List[Dict[str, Any]]:
        """Fetch posts from configured RSS feeds.
        
        Returns:
            List of posts in standardized format
        
        Raises:
            Exception: If feed URLs are invalid or unreachable
        """
        if not self.settings.rss_feed_urls:
            return []
        
        feed_urls = [url.strip() for url in self.settings.rss_feed_urls.split(',')]
        all_posts = []
        
        for feed_url in feed_urls:
            if not feed_url:
                continue
            
            try:
                posts = self._fetch_from_feed(feed_url)
                all_posts.extend(posts)
            except Exception as e:
                print(f"Warning: Failed to fetch RSS feed '{feed_url}': {e}")
                # Continue with other feeds
                continue
        
        # Sort by date (newest first) and limit
        all_posts.sort(key=lambda x: x['created_utc'], reverse=True)
        return all_posts[:self.settings.rss_post_limit]
    
    def _fetch_from_feed(self, feed_url: str) -> List[Dict[str, Any]]:
        """Fetch and parse a single RSS/Atom feed.
        
        Args:
            feed_url: URL to RSS/Atom feed
        
        Returns:
            List of standardized posts
        """
        response = requests.get(feed_url, timeout=10)
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.content)
        
        # Detect feed type (RSS vs Atom)
        if root.tag == '{http://www.w3.org/2005/Atom}feed':
            return self._parse_atom_feed(root, feed_url)
        else:
            return self._parse_rss_feed(root, feed_url)
    
    def _parse_rss_feed(self, root: ET.Element, feed_url: str) -> List[Dict[str, Any]]:
        """Parse RSS 2.0 feed.
        
        Args:
            root: XML root element
            feed_url: Source feed URL
        
        Returns:
            List of standardized posts
        """
        posts = []
        
        for item in root.findall('.//item'):
            title = self._get_text(item, 'title')
            link = self._get_text(item, 'link')
            description = self._get_text(item, 'description')
            pub_date = self._get_text(item, 'pubDate')
            author = self._get_text(item, 'author') or self._get_text(item, 'dc:creator')
            
            if not title:
                continue
            
            post = {
                'id': self._generate_id(link or title),
                'title': title,
                'body': description,
                'score': 0,  # RSS feeds don't have scores
                'url': link or feed_url,
                'source': 'rss',
                'author': author or 'unknown',
                'created_utc': self._parse_date(pub_date),
                'num_comments': 0
            }
            posts.append(post)
        
        return posts
    
    def _parse_atom_feed(self, root: ET.Element, feed_url: str) -> List[Dict[str, Any]]:
        """Parse Atom feed.
        
        Args:
            root: XML root element
            feed_url: Source feed URL
        
        Returns:
            List of standardized posts
        """
        posts = []
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('atom:entry', ns):
            title = self._get_text(entry, 'atom:title', ns)
            link_elem = entry.find('atom:link', ns)
            link = link_elem.get('href') if link_elem is not None else None
            content = self._get_text(entry, 'atom:content', ns) or self._get_text(entry, 'atom:summary', ns)
            published = self._get_text(entry, 'atom:published', ns) or self._get_text(entry, 'atom:updated', ns)
            author_elem = entry.find('atom:author/atom:name', ns)
            author = author_elem.text if author_elem is not None else 'unknown'
            
            if not title:
                continue
            
            post = {
                'id': self._generate_id(link or title),
                'title': title,
                'body': content,
                'score': 0,
                'url': link or feed_url,
                'source': 'rss',
                'author': author,
                'created_utc': self._parse_date(published),
                'num_comments': 0
            }
            posts.append(post)
        
        return posts
    
    def _get_text(self, element: ET.Element, tag: str, namespaces: Dict[str, str] = None) -> str:
        """Safely extract text from XML element.
        
        Args:
            element: XML element
            tag: Tag name to find
            namespaces: Optional namespace dict
        
        Returns:
            Text content or empty string
        """
        child = element.find(tag, namespaces) if namespaces else element.find(tag)
        return child.text.strip() if child is not None and child.text else ""
    
    def _generate_id(self, text: str) -> str:
        """Generate unique ID from text using hash.
        
        Args:
            text: Input text (URL or title)
        
        Returns:
            Hash-based ID with 'rss_' prefix
        """
        hash_obj = hashlib.md5(text.encode())
        return f"rss_{hash_obj.hexdigest()[:16]}"
    
    def _parse_date(self, date_str: str) -> float:
        """Parse RSS/Atom date string to Unix timestamp.
        
        Args:
            date_str: Date string in various formats
        
        Returns:
            Unix timestamp (float), or current time if parsing fails
        """
        if not date_str:
            return datetime.now().timestamp()
        
        # Try common date formats
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 822
            '%Y-%m-%dT%H:%M:%S%z',       # ISO 8601
            '%Y-%m-%dT%H:%M:%SZ',        # ISO 8601 UTC
            '%Y-%m-%d %H:%M:%S',         # Simple format
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.timestamp()
            except ValueError:
                continue
        
        # Fallback to current time if parsing fails
        return datetime.now().timestamp()
