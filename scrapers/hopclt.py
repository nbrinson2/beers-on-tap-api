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

        # Each beer name is an <a href="/beer/..."> inside an <h3>
        for a in soup.find_all("a", href=re.compile(r"^/beer/")):
            beer_name = a.get_text(strip=True)
            if not beer_name or len(beer_name) < 2:
                continue

            # Climb to a reasonably large container that holds the beer row
            card = a
            for _ in range(6):
                card = card.parent
                if card is None or card.name == "body":
                    break
                # Stop once we have a container with both the name and a % sign
                if "%" in card.get_text():
                    break

            if card is None:
                continue

            text = card.get_text(" ", strip=True)

            style = None
            # Style tends to appear as a short token after the name and before ABV
            # Look for common style words or the first non-numeric span-like text
            style_match = re.search(
                r"(?:IPA|Pilsner|Altbier|Lager|Porter|Stout|Hefeweizen|Pale Ale|Sour|Saison|Bock|Wit|Weisse|Kellerbier|Helles|Dunkel|Schwarzbier|Red|Wheat|Seltzer|Cider)",
                text,
                re.IGNORECASE,
            )
            if style_match:
                style = style_match.group(0)

            abv = None
            abv_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
            if abv_match:
                try:
                    abv = float(abv_match.group(1))
                except ValueError:
                    pass

            ibu = None
            ibu_match = re.search(r"(\d+)\s*IBU", text, re.IGNORECASE)
            if ibu_match:
                try:
                    ibu = int(ibu_match.group(1))
                except ValueError:
                    pass

            # Deduplicate by name within this page (multi-location pages repeat beers)
            if any(l.beer_name == beer_name for l in listings):
                continue

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
