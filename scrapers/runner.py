"""
Runner that loads venues and runs scrapers against them.
Upserts beers and tap_listings.
"""
import asyncio
import os
import json
import re
import asyncpg
from dotenv import load_dotenv
from .hopclt import HopCLTScraper

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


async def upsert_beer(conn, listing) -> str:
    """Find or create a beer. Returns beer_id."""
    external_ids = {}
    if listing.raw and listing.raw.get("hopclt"):
        external_ids["hopclt"] = listing.raw["hopclt"]
    row = await conn.fetchrow(
        """
        INSERT INTO beers (name, brewery, style, abv, ibu, normalized_name, external_ids)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
        ON CONFLICT (name, brewery) DO UPDATE
        SET style = EXCLUDED.style,
            abv = COALESCE(EXCLUDED.abv, beers.abv),
            ibu = COALESCE(EXCLUDED.ibu, beers.ibu),
            normalized_name = COALESCE(EXCLUDED.normalized_name, beers.normalized_name),
            external_ids = beers.external_ids || EXCLUDED.external_ids,
            updated_at = NOW()
        RETURNING id::text
        """,
        listing.beer_name,
        listing.brewery,
        listing.style,
        listing.abv,
        listing.ibu,
        normalize_name(listing.beer_name),
        json.dumps(external_ids),
    )
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


# Venue name (substring match) -> HopCLT brewery page
# Names are matched with ILIKE so they don't have to be exact.
MAPPINGS = [
    ("Olde Mecklenburg", "https://hopclt.com/brewery/olde_mecklenburg"),
    ("Resident Culture", "https://hopclt.com/brewery/resident_culture"),
    ("HopFly", "https://hopclt.com/brewery/hopfly"),
    ("Birdsong", "https://hopclt.com/brewery/birdsong"),
    ("Petty Thieves", "https://hopclt.com/brewery/petty_thieves"),
    ("Fonta Flora", "https://hopclt.com/brewery/fonta_flora"),
    ("Wooden Robot", "https://hopclt.com/brewery/wooden_robot"),
    ("Town Brewing", "https://hopclt.com/brewery/town"),
    ("Free Range", "https://hopclt.com/brewery/free_range"),
    ("Heist", "https://hopclt.com/brewery/heist"),
    ("Pilot Brewing", "https://hopclt.com/brewery/pilot"),
    ("Club West", "https://hopclt.com/brewery/club_west_brewing"),
    ("Legion", "https://hopclt.com/brewery/legion"),
    ("Hi-Wire", "https://hopclt.com/brewery/hiwire"),
    ("Monday Night", "https://hopclt.com/brewery/monday_night"),
    ("Burial", "https://hopclt.com/brewery/burial"),
    ("NoDa Brewing", "https://hopclt.com/brewery/noda_brewing"),
    ("Triple C", "https://hopclt.com/brewery/triple_c"),
    ("Suffolk Punch", "https://hopclt.com/brewery/suffolk_punch"),
    ("Lenny Boy", "https://hopclt.com/brewery/lenny_boy"),
    ("Salud", "https://hopclt.com/brewery/salud"),
    ("Divine Barrel", "https://hopclt.com/brewery/divine_barrel"),
    ("Sugar Creek", "https://hopclt.com/brewery/sugar_creek"),
    ("Edge City", "https://hopclt.com/brewery/edge_city"),
    ("Armored Cow", "https://hopclt.com/brewery/armored_cow"),
    ("Seaboard", "https://hopclt.com/brewery/seaboard"),
    ("Traust", "https://hopclt.com/brewery/traust"),
    ("Primal", "https://hopclt.com/brewery/primal"),
]


async def run_scrapers():
    pool = await asyncpg.create_pool(DATABASE_URL)
    hopclt = HopCLTScraper()

    async with pool.acquire() as conn:
        for venue_name, hopclt_url in MAPPINGS:
            venue = await conn.fetchrow(
                "SELECT id::text, name FROM venues WHERE name ILIKE $1 LIMIT 1",
                f"%{venue_name}%",
            )
            if not venue:
                print(f"Venue not found: {venue_name}")
                continue

            venue_id = venue["id"]
            print(f"Scraping {venue['name']} ...")

            try:
                listings = await hopclt.scrape(hopclt_url, venue["name"])
                print(f"  Found {len(listings)} current taps")
                if not listings:
                    print("  No on-tap beers found; left existing taps unchanged")
                    continue

                beer_ids = []
                for listing in listings:
                    beer_id = await upsert_beer(conn, listing)
                    await upsert_tap(conn, venue_id, beer_id, listing)
                    beer_ids.append(beer_id)

                await conn.execute(
                    """
                    DELETE FROM tap_listings
                    WHERE venue_id = $1::uuid
                      AND NOT (beer_id = ANY($2::uuid[]))
                    """,
                    venue_id,
                    beer_ids,
                )
                await conn.execute(
                    """
                    DELETE FROM beers
                    WHERE NOT EXISTS (
                        SELECT 1 FROM tap_listings tl WHERE tl.beer_id = beers.id
                    )
                    """
                )

                print(f"  Upserted {len(listings)} taps")
            except Exception as e:
                print(f"  Error: {e}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_scrapers())
