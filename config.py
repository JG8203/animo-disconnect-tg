import os
from pathlib import Path
from typing import Final
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: Final[str] = os.environ["BOT_TOKEN"]
POLLING_INTERVAL: Final[int] = int(os.environ.get("POLLING_INTERVAL", "300"))
DATA_DIR: Final[Path] = Path("data")
SUBSCRIPTIONS_FILE: Final[Path] = DATA_DIR / "subscriptions.json"
SCRAPER_URL: Final[str] = os.environ.get("SCRAPER_URL", "http://localhost:8000/scrape")
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_ENABLED: Final[bool] = os.environ.get("CACHE_ENABLED", "True").lower() == "true"
CACHE_TTL_SECONDS: Final[int] = int(os.environ.get("CACHE_TTL_SECONDS", "60"))
