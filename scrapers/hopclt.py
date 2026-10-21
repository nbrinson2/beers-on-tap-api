"""
HopCLT scraper.
Parses brewery pages like https://hopclt.com/brewery/olde_mecklenburg
"""
import re
import httpx
from typing import List
from bs4 import BeautifulSoup
from .base import BaseScraper, TapListing


class HopCLTScraper(BaseScraper):
    source_name = "hopclt"

    async def fetch(self, venue_url: str, venue_name: str) -> str:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(venue_url)
            resp.raise_for_status()
            return resp.text

    def parse(self, content: str, venue_name: str) -> List[TapListing]:
        soup = BeautifulSoup(content, "html.parser")
        listings: List[TapListing] = []

        # Beer rows live inside grid containers under "On Tap Now"
        # Each beer is in a div that contains an <h3><a> with the name
        for h3 in soup.find_all("h3"):
            a = h3.find("a", href=re.compile(r"^/beer/"))
            if not a:
                continue
            beer_name = a.get_text(strip=True)
            if not beer_name:
                continue

            # Walk up to the containing beer card
            card = h3.find_parent("div")
            if not card:
                continue

            style = None
            abv = None
            ibu = None

            # Style is usually the first span after the name in the same card
            for span in card.find_all("span"):
                text = span.get_text(strip=True)
                if text and not text.endswith("%") and "ABV" not in text and "IBU" not in text:
                    if not style:
                        style = text
                    break

            # ABV appears as e.g. "6.8%" near the word ABV
            text = card.get_text(" ", strip=True)
            abv_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
            if abv_match:
                try:
                    abv = float(abv_match.group(1))
                except ValueError:
                    pass

            ibu_match = re.search(r"(\d+)\s*IBU", text, re.IGNORECASE)
            if ibu_match:
                try:
                    ibu = int(ibu_match.group(1))
                except ValueError:
                    pass

            listings.append(
                TapListing(
                    beer_name=beer_name,
                    brewery=venue_name,
                    style=style,
                    abv=abv,
                    raw={"ibu": ibu, "source": "hopclt"},
                )
            )

        return listings
