"""
HopCLT scraper skeleton.
HopCLT aggregates Charlotte brewery menus. Adjust selectors once you inspect the live pages.
"""
import httpx
from typing import List
from .base import BaseScraper, TapListing


class HopCLTScraper(BaseScraper):
    source_name = "hopclt"

    async def fetch(self, venue_url: str, venue_name: str) -> str:
        # venue_url should be the HopCLT page for that brewery
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(venue_url)
            resp.raise_for_status()
            return resp.text

    def parse(self, content: str, venue_name: str) -> List[TapListing]:
        # TODO: inspect HopCLT HTML and replace this with real parsing
        # (BeautifulSoup or selectolax recommended)
        listings = []
        # Example placeholder — replace with actual selectors
        # soup = BeautifulSoup(content, "html.parser")
        # for item in soup.select(".tap-item"):
        #     listings.append(TapListing(
        #         beer_name=item.select_one(".beer-name").get_text(strip=True),
        #         brewery=item.select_one(".brewery").get_text(strip=True) or venue_name,
        #         style=item.select_one(".style").get_text(strip=True),
        #     ))
        return listings
