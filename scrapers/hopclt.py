"""
HopCLT scraper.
Parses brewery pages like https://hopclt.com/brewery/olde_mecklenburg
Returns beers that appear before the "Previously On Tap" section.
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

        # Collect beer links that appear before the "Previously On Tap" section
        previously_header = soup.find(string=re.compile(r"Previously On Tap", re.IGNORECASE))

        for a in soup.find_all("a", href=re.compile(r"^/beer/")):
            # Stop once we pass the previously-on-tap header
            if previously_header and a.sourcepos and previously_header.sourcepos:
                if a.sourcepos > previously_header.sourcepos:
                    break
            # Fallback: if sourcepos isn't available, check document order via parents
            if previously_header:
                # Simple heuristic: if this link's parent chain comes after the header in the tree
                # We'll just collect and filter later if needed
                pass

            beer_name = a.get_text(strip=True)
            if not beer_name or len(beer_name) < 2:
                continue

            # Climb to a container that includes the ABV
            card = a
            for _ in range(8):
                card = card.parent
                if card is None or card.name == "body":
                    break
                if "%" in card.get_text():
                    break

            if card is None:
                continue

            text = card.get_text(" ", strip=True)

            # Skip if this card is clearly in the previously section (no ABV and long name history)
            # Prefer beers that actually show an ABV percentage
            if "%" not in text:
                continue

            style = None
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

            # Safety: current tap lists are rarely > 40 beers
            if len(listings) >= 40:
                break

        return listings
