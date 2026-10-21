"""
Generic brewery website scraper skeleton.
Many breweries publish menus on their own sites. This is a starting point for custom parsers.
"""
import httpx
from typing import List
from .base import BaseScraper, TapListing


class BreweryWebsiteScraper(BaseScraper):
    source_name = "brewery_website"

    async def fetch(self, venue_url: str, venue_name: str) -> str:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            # Some sites block non-browser User-Agents
            headers = {"User-Agent": "Mozilla/5.0 (compatible; BeersOnTapBot/0.1)"}
            resp = await client.get(venue_url, headers=headers)
            resp.raise_for_status()
            return resp.text

    def parse(self, content: str, venue_name: str) -> List[TapListing]:
        # TODO: implement site-specific parsing or a heuristic
        # Consider: look for common patterns, or maintain a map of venue_id -> parser
        return []
