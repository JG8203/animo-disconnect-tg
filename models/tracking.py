from dataclasses import dataclass, field
from typing import Dict, List, Any

@dataclass
class UserPreferences:
    """User preferences and subscription settings."""
    id_no: str = ""
    courses: List[str] = field(default_factory=list)
    sections: Dict[str, List[int]] = field(default_factory=dict)
    previous_data: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    
    @classmethod
    def default(cls) -> 'UserPreferences':
        return cls()

@dataclass
class TrackingInfo:
    """Information needed to fetch and process course data for a user."""
    chat_id: int
    student_id: str
    course: str
    track_all: bool = True
    class_numbers: List[int] = field(default_factory=list)

    def get_data_key(self) -> str:
        """Returns the key used for storing previous data."""
        return self.course if self.track_all else f"{self.course}:sections"
