"""
HopCLT scraper.
Parses brewery pages like https://hopclt.com/brewery/olde_mecklenburg.
Uses the page data for beers marked on tap, one list per location.
"""
import json
import httpx
from typing import List
from bs4 import BeautifulSoup
from .base import BaseScraper, TapListing


class LocationTaps:
    """One HopCLT taproom and the beers currently on tap there."""

    def __init__(self, location_id, name, address, city, neighborhood, lat, lng, listings):
        self.location_id = location_id
        self.name = name or ""
        self.address = address or ""
        self.city = city or ""
        self.neighborhood = neighborhood or ""
        self.lat = lat
        self.lng = lng
        self.listings = listings


class HopCLTScraper(BaseScraper):
    source_name = "hopclt"

    async def fetch(self, venue_url: str, venue_name: str) -> str:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(venue_url)
            resp.raise_for_status()
            return resp.text

    def _page_props(self, content: str):
        soup = BeautifulSoup(content, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if script is None or not script.string:
            return None
        return json.loads(script.string)["props"]["pageProps"]

    def parse_locations(self, content: str, venue_name: str) -> List[LocationTaps]:
        props = self._page_props(content)
        if not props:
            return []

        brewery_name = (props.get("brewery") or {}).get("name") or venue_name
        locations = list(props.get("breweryLocations") or [])
        by_id = {loc["id"]: loc for loc in locations}
        listings_by_location = {loc["id"]: [] for loc in locations}
        seen = set()

        for beer in props.get("breweryBeers") or []:
            if not beer.get("on_tap"):
                continue
            if beer.get("first_seen_status") == "rejected":
                continue
            name = (beer.get("name") or "").strip()
            if len(name) < 2:
                continue

            location_id = beer.get("location_id")
            key = (beer.get("id") or name, location_id)
            if key in seen:
                continue
            seen.add(key)

            style = beer.get("style_original") or beer.get("style")
            if style == "Unknown":
                style = None
            abv = beer.get("abv")
            ibu = beer.get("ibu")
            loc = by_id.get(location_id) or {}
            listing = TapListing(
                beer_name=name,
                brewery=brewery_name,
                style=style,
                abv=float(abv) if abv is not None else None,
                ibu=int(ibu) if isinstance(ibu, (int, float)) else None,
                raw={
                    "source": "hopclt",
                    "hopclt": beer.get("beerSlug") or beer.get("id"),
                    "location_id": location_id,
                    "location_name": loc.get("name") or "",
                    "address": loc.get("address") or "",
                    "city": loc.get("city") or "",
                    "price": beer.get("price"),
                },
            )
            listings_by_location.setdefault(location_id, []).append(listing)

        parsed = []
        for loc in locations:
            parsed.append(LocationTaps(
                location_id=loc.get("id"),
                name=loc.get("name") or "",
                address=loc.get("address") or "",
                city=loc.get("city") or "",
                neighborhood=loc.get("neighborhood") or "",
                lat=loc.get("lat"),
                lng=loc.get("lng"),
                listings=listings_by_location.get(loc.get("id"), []),
            ))
        for location_id, listings in listings_by_location.items():
            if location_id in by_id or not listings:
                continue
            sample = listings[0].raw
            parsed.append(LocationTaps(
                location_id=location_id,
                name=sample.get("location_name") or "",
                address=sample.get("address") or "",
                city=sample.get("city") or "",
                neighborhood="",
                lat=None,
                lng=None,
                listings=listings,
            ))
        return parsed

    def parse(self, content: str, venue_name: str) -> List[TapListing]:
        listings = []
        for location in self.parse_locations(content, venue_name):
            listings.extend(location.listings)
        return listings
