import logging
import asyncio
from typing import List, Dict, Any, Optional

import aiohttp

import config
from services.cache import CacheService

class CloudflareBlockedError(Exception):
    """Raised when the scraper replies 503 / cloudflare_blocked."""

class ScraperService:
    """Service to fetch course data from the scraper API."""
    
    def __init__(self, cache: CacheService):
        """
        Initialize the scraper service.
        
        Args:
            cache: Cache service for storing and retrieving course data
        """
        self.cache = cache
    
    async def fetch_course_data(self, course: str, id_no: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch course data from the scraper service.
        
        Args:
            course: Course code to fetch.
            id_no: Student ID number.
            use_cache: Whether to use cached data if available.
            
        Returns:
            List of course sections data.
            
        Raises:
            CloudflareBlockedError: If the scraper replies with HTTP 503.
            aiohttp.ClientError: For other HTTP errors or network failures.
        """
        # Try to get from cache first if enabled
        if use_cache and config.CACHE_ENABLED:
            cached_data = self.cache.get(course, id_no)
            if cached_data is not None:
                logging.debug(f"Using cached data for {course} (student ID: {id_no})")
                return cached_data
        
        # Cache miss or cache disabled, fetch from scraper
        url = f"{config.SCRAPER_URL}?course={course}&id_no={id_no}"
        logging.debug(f"Fetching from scraper: {url}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=60) as resp:
                    if resp.status == 503:
                        logging.warning(
                            "Scraper returned 503 (Cloudflare Blocked?) for %s", url
                        )
                        raise CloudflareBlockedError(f"Scraper returned 503 for {course}")
                    if resp.status != 200:
                        logging.error("Scraper returned HTTP %d for %s", resp.status, url)
                        raise aiohttp.ClientError(f"Scraper HTTP {resp.status}")
                    
                    data = await resp.json(encoding="utf-8")
                    
                    # Cache the result if caching is enabled
                    if config.CACHE_ENABLED:
                        self.cache.set(course, id_no, data)
                    
                    return data
            except asyncio.TimeoutError as e:
                logging.error("Timeout fetching data from scraper for %s", url)
                raise aiohttp.ClientError("Scraper request timed out") from e
            except aiohttp.ClientConnectorError as e:
                logging.error("Connection error contacting scraper for %s: %s", url, e)
                raise aiohttp.ClientError(f"Cannot connect to scraper: {e}") from e
                
    async def fetch_and_filter_data(
        self, course: str, id_no: str, class_numbers: Optional[List[int]] = None, 
        use_cache: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch course data and optionally filter by class numbers.
        """
        try:
            sections = await self.fetch_course_data(course, id_no, use_cache)
            if class_numbers:
                sections = [s for s in sections if s.get("classNbr") in class_numbers]
            return sections
        except CloudflareBlockedError:
            raise
        except aiohttp.ClientError as exc:
            logging.error("Client error fetching data for %s: %s", course, exc)
            return None
        except Exception as exc:
            logging.error(
                "Unexpected error fetching/filtering data for %s: %s",
                course, exc, exc_info=True
            )
            return None
