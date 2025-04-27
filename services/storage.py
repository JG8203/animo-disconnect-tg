import json
import logging
from typing import Dict
from pathlib import Path

import config
from models.tracking import UserPreferences

class StorageService:
    """Handles data persistence for user subscriptions."""
    
    def __init__(self, file_path: Path = config.SUBSCRIPTIONS_FILE):
        self.file_path = file_path
        self.subscriptions: Dict[int, UserPreferences] = {}
        
    def load(self) -> Dict[int, UserPreferences]:
        """Load subscriptions from file."""
        if not self.file_path.exists():
            return self.subscriptions
            
        try:
            data = json.loads(self.file_path.read_text("utf-8"))
            self.subscriptions = {
                int(k): UserPreferences(**v) for k, v in data.items()
            }
            logging.info(
                "Loaded %d subscriptions from %s", len(self.subscriptions), self.file_path
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logging.error("Error loading subscriptions from %s: %s", self.file_path, e)
            
        return self.subscriptions
        
    def save(self) -> None:
        """Save subscriptions to file."""
        try:
            self.file_path.write_text(
                json.dumps(
                    {k: v.__dict__ for k, v in self.subscriptions.items()},
                    indent=2, 
                    ensure_ascii=False
                ), 
                encoding="utf-8"
            )
            logging.debug("Saved %d subscriptions to %s", 
                         len(self.subscriptions), self.file_path)
        except Exception as e:
            logging.error(
                "Error saving subscriptions to %s: %s", 
                self.file_path, e, exc_info=True
            )
    
    def get(self, chat_id: int) -> UserPreferences:
        """Get a user's preferences, creating default if not found."""
        if chat_id not in self.subscriptions:
            self.subscriptions[chat_id] = UserPreferences.default()
        return self.subscriptions[chat_id]
        
    def update(self, chat_id: int, preferences: UserPreferences) -> None:
        """Update a user's preferences and save to disk."""
        self.subscriptions[chat_id] = preferences
        self.save()
        
    def delete(self, chat_id: int) -> bool:
        """Delete a user's subscription and save to disk."""
        if chat_id in self.subscriptions:
            del self.subscriptions[chat_id]
            self.save()
            return True
        return False
