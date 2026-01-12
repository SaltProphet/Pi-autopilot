"""
Metrics module for tracking system performance and statistics.
"""
import time
from datetime import datetime
from typing import Dict, Any
from agents.db import get_database_stats


class MetricsCollector:
    """Collects and reports system metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.scrape_count = 0
        self.generation_count = 0
        self.upload_count = 0
    
    def increment_requests(self):
        """Increment total request counter."""
        self.request_count += 1
    
    def increment_errors(self):
        """Increment error counter."""
        self.error_count += 1
    
    def increment_scrapes(self):
        """Increment scrape counter."""
        self.scrape_count += 1
    
    def increment_generations(self):
        """Increment generation counter."""
        self.generation_count += 1
    
    def increment_uploads(self):
        """Increment upload counter."""
        self.upload_count += 1
    
    def get_uptime(self) -> float:
        """
        Get system uptime in seconds.
        
        Returns:
            Uptime in seconds
        """
        return time.time() - self.start_time
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all current metrics.
        
        Returns:
            Dict with all metric values
        """
        uptime_seconds = self.get_uptime()
        uptime_hours = uptime_seconds / 3600
        
        # Get database statistics
        db_stats = get_database_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": {
                "seconds": round(uptime_seconds, 2),
                "hours": round(uptime_hours, 2),
                "days": round(uptime_hours / 24, 2)
            },
            "api": {
                "total_requests": self.request_count,
                "total_errors": self.error_count,
                "error_rate": round(self.error_count / max(self.request_count, 1), 4)
            },
            "operations": {
                "scrapes": self.scrape_count,
                "generations": self.generation_count,
                "uploads": self.upload_count
            },
            "database": db_stats
        }
    
    def reset_counters(self):
        """Reset all operational counters (keeps uptime)."""
        self.request_count = 0
        self.error_count = 0
        self.scrape_count = 0
        self.generation_count = 0
        self.upload_count = 0


# Global metrics instance
metrics = MetricsCollector()


def get_system_metrics() -> Dict[str, Any]:
    """
    Get current system metrics.
    
    Returns:
        Dict with all metrics
    """
    return metrics.get_metrics()
