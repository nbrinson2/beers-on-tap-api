"""
Runner that loads venues and runs scrapers against them.
"""
import asyncio
import os
import asyncpg
from dotenv import load_dotenv
from .hopclt import HopCLTScraper
from .brewery_website import BreweryWebsiteScraper

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


async def run_scrapers():
    pool = await asyncpg.create_pool(DATABASE_URL)
    hopclt = HopCLTScraper()
    website = BreweryWebsiteScraper()

    async with pool.acquire() as conn:
        venues = await conn.fetch("""
            SELECT id::text, name, website
            FROM venues
            WHERE website IS NOT NULL
            LIMIT 10
        """)

    print(f"Scraping {len(venues)} venues...")

    for v in venues:
        print(f"  {v['name']}")
        # Example: try HopCLT first if we have a known URL pattern, else website
        # For now just demonstrate the call
        try:
            listings = await website.scrape(v["website"], v["name"])
            print(f"    Found {len(listings)} taps")
            # TODO: upsert beers + tap_listings
        except Exception as e:
            print(f"    Error: {e}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_scrapers())
