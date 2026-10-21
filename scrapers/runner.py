"""
Runner that loads venues and runs scrapers against them.
Upserts beers and tap_listings.
"""
import asyncio
import os
import json
import asyncpg
from dotenv import load_dotenv
from .hopclt import HopCLTScraper

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


async def upsert_beer(conn, listing) -> str:
    """Find or create a beer. Returns beer_id."""
    row = await conn.fetchrow(
        """
        INSERT INTO beers (name, brewery, style, abv)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (name, brewery) DO UPDATE
        SET style = COALESCE(EXCLUDED.style, beers.style),
            abv = COALESCE(EXCLUDED.abv, beers.abv),
            updated_at = NOW()
        RETURNING id::text
        """,
        listing.beer_name,
        listing.brewery,
        listing.style,
        listing.abv,
    )
    # Note: ON CONFLICT requires a unique constraint on (name, brewery).
    # If you don't have one yet, add it:
    # ALTER TABLE beers ADD CONSTRAINT beers_name_brewery_key UNIQUE (name, brewery);
    return row["id"]


async def upsert_tap(conn, venue_id: str, beer_id: str, listing):
    await conn.execute(
        """
        INSERT INTO tap_listings (venue_id, beer_id, status, source, confidence, last_seen, last_updated)
        VALUES ($1::uuid, $2::uuid, 'on_tap', $3, 0.8, NOW(), NOW())
        ON CONFLICT (venue_id, beer_id) DO UPDATE
        SET status = 'on_tap',
            source = EXCLUDED.source,
            confidence = EXCLUDED.confidence,
            last_seen = NOW(),
            last_updated = NOW()
        """,
        venue_id,
        beer_id,
        listing.raw.get("source", "hopclt") if listing.raw else "hopclt",
    )


async def run_scrapers():
    pool = await asyncpg.create_pool(DATABASE_URL)
    hopclt = HopCLTScraper()

    # For now we hard-code one mapping. Expand this into a table or config later.
    # Format: (venue_name_in_db, hopclt_url)
    mappings = [
        ("The Olde Mecklenburg Brewery", "https://hopclt.com/brewery/olde_mecklenburg"),
        # Add more as you map them
    ]

    async with pool.acquire() as conn:
        for venue_name, hopclt_url in mappings:
            venue = await conn.fetchrow(
                "SELECT id::text FROM venues WHERE name ILIKE $1 LIMIT 1",
                f"%{venue_name}%",
            )
            if not venue:
                print(f"Venue not found: {venue_name}")
                continue

            venue_id = venue["id"]
            print(f"Scraping {venue_name} ...")

            try:
                listings = await hopclt.scrape(hopclt_url, venue_name)
                print(f"  Found {len(listings)} current taps")

                for listing in listings:
                    beer_id = await upsert_beer(conn, listing)
                    await upsert_tap(conn, venue_id, beer_id, listing)

                print(f"  Upserted {len(listings)} taps")
            except Exception as e:
                print(f"  Error: {e}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_scrapers())
