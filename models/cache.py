from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any

@dataclass
class CacheEntry:
    """Represents a cached course data entry."""
    course: str
    student_id: str
    data: List[Dict[str, Any]]
    timestamp: datetime
    
    def is_valid(self, max_age_seconds: int) -> bool:
        """Check if the cache entry is still valid."""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age < max_age_seconds
