"""
Base scraper interface for tap list sources.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class TapListing:
    """Normalized tap listing from any source."""
    def __init__(
        self,
        beer_name: str,
        brewery: Optional[str] = None,
        style: Optional[str] = None,
        abv: Optional[float] = None,
        serving_type: Optional[str] = None,
        price: Optional[float] = None,
        size: Optional[str] = None,
        raw: Optional[Dict[str, Any]] = None,
    ):
        self.beer_name = beer_name
        self.brewery = brewery
        self.style = style
        self.abv = abv
        self.serving_type = serving_type
        self.price = price
        self.size = size
        self.raw = raw or {}
        self.scraped_at = datetime.utcnow()


class BaseScraper(ABC):
    """Override fetch() and parse() for each source."""

    source_name: str = "unknown"

    @abstractmethod
    async def fetch(self, venue_url: str, venue_name: str) -> str:
        """Fetch raw content (HTML, JSON, etc.) for a venue."""
        ...

    @abstractmethod
    def parse(self, content: str, venue_name: str) -> List[TapListing]:
        """Turn raw content into a list of TapListing objects."""
        ...

    async def scrape(self, venue_url: str, venue_name: str) -> List[TapListing]:
        content = await self.fetch(venue_url, venue_name)
        return self.parse(content, venue_name)
