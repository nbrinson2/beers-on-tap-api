"""
HopCLT scraper.
Parses brewery pages like https://hopclt.com/brewery/olde_mecklenburg
Reads style, ABV, and IBU from the On Tap Now section only.
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

    def _on_tap_soup(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Keep only the On Tap Now section, before the next page heading."""
        heading = next(
            (h2 for h2 in soup.find_all("h2") if "On Tap Now" in h2.get_text()),
            None,
        )
        if heading is None:
            return BeautifulSoup("", "html.parser")

        parts = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) == "h2":
                break
            parts.append(str(sibling))
        return BeautifulSoup("".join(parts), "html.parser")

    def parse(self, content: str, venue_name: str) -> List[TapListing]:
        soup = self._on_tap_soup(BeautifulSoup(content, "html.parser"))
        listings: List[TapListing] = []
        seen_hrefs = set()

        for card in soup.find_all("div"):
            style_attr = (card.get("style") or "").replace(" ", "")
            if "grid-template-columns:60px" not in style_attr:
                continue

            link = card.find("a", href=re.compile(r"^/beer/"))
            if link is None:
                continue
            href = link["href"]
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            beer_name = link.get_text(strip=True)
            if not beer_name or len(beer_name) < 2:
                continue

            style_span = card.find("span")
            style = style_span.get_text(strip=True) if style_span else None
            if style == "Unknown":
                style = None

            text = card.get_text(" ", strip=True)
            abv = None
            abv_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
            if abv_match:
                abv = float(abv_match.group(1))

            ibu = None
            ibu_match = re.search(r"(\d+)\s*IBU", text, re.IGNORECASE)
            if ibu_match:
                ibu = int(ibu_match.group(1))

            listings.append(
                TapListing(
                    beer_name=beer_name,
                    brewery=venue_name,
                    style=style,
                    abv=abv,
                    ibu=ibu,
                    raw={"source": "hopclt", "hopclt": href},
                )
            )

        return listings
