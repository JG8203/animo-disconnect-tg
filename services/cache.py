import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from models.cache import CacheEntry

class CacheService:
    """Service for caching course data to reduce scraper calls."""
    
    def __init__(self, max_age_seconds: int = 60):
        """
        Initialize cache service.
        
        Args:
            max_age_seconds: Maximum age of cache entries in seconds
        """
        self.cache: Dict[str, CacheEntry] = {}
        self.max_age_seconds = max_age_seconds
        self.hits = 0
        self.misses = 0
        
    def get_cache_key(self, course: str, student_id: str) -> str:
        """Generate a cache key for a course and student ID."""
        return f"{course}:{student_id}"
        
    def get(self, course: str, student_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached data for a course if available and valid.
        
        Returns:
            The cached course data or None if not found or expired
        """
        cache_key = self.get_cache_key(course, student_id)
        entry = self.cache.get(cache_key)
        
        if entry and entry.is_valid(self.max_age_seconds):
            self.hits += 1
            logging.debug(f"Cache hit for {cache_key}")
            return entry.data
            
        if entry:
            logging.debug(f"Cache expired for {cache_key}")
        else:
            logging.debug(f"Cache miss for {cache_key}")
            
        self.misses += 1
        return None
        
    def set(self, course: str, student_id: str, data: List[Dict[str, Any]]) -> None:
        """Store course data in the cache."""
        cache_key = self.get_cache_key(course, student_id)
        self.cache[cache_key] = CacheEntry(
            course=course,
            student_id=student_id,
            data=data,
            timestamp=datetime.now()
        )
        logging.debug(f"Cached data for {cache_key}")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        valid_entries = sum(1 for e in self.cache.values() 
                         if e.is_valid(self.max_age_seconds))
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "total_entries": len(self.cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self.cache) - valid_entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }
