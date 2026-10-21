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


_ADDRESS_WORDS = {
    "avenue": "ave",
    "street": "st",
    "road": "rd",
    "drive": "dr",
    "boulevard": "blvd",
    "lane": "ln",
    "court": "ct",
    "place": "pl",
    "parkway": "pkwy",
    "highway": "hwy",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
}


def normalize_address(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
    return " ".join(_ADDRESS_WORDS.get(part, part) for part in text.split())


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
    price = (listing.raw or {}).get("price")
    if not isinstance(price, (int, float)):
        price = None
    await conn.execute(
        """
        INSERT INTO tap_listings (venue_id, beer_id, status, price, source, confidence, last_seen, last_updated)
        VALUES ($1::uuid, $2::uuid, 'on_tap', $3, $4, 0.8, NOW(), NOW())
        ON CONFLICT (venue_id, beer_id) DO UPDATE
        SET status = 'on_tap',
            price = EXCLUDED.price,
            source = EXCLUDED.source,
            confidence = EXCLUDED.confidence,
            last_seen = NOW(),
            last_updated = NOW()
        """,
        venue_id,
        beer_id,
        price,
        listing.raw.get("source", "hopclt") if listing.raw else "hopclt",
    )


def source_tags(sources) -> list:
    if not sources:
        return []
    if isinstance(sources, str):
        sources = json.loads(sources)
    return sources if isinstance(sources, list) else []


def location_label(brewery_name: str, location) -> str:
    name = (location.name or "").strip()
    if not name or name.lower() == brewery_name.lower():
        if location.address:
            return f"{brewery_name} - {location.address}"
        return brewery_name
    return f"{brewery_name} - {name}"


def find_venue_for_location(candidates, location, only_location: bool):
    """Reuse a same-brewery venue already tied to this location or address."""
    tag = f"hopclt:{location.location_id}"
    for venue in candidates:
        if tag in source_tags(venue["sources"]):
            return venue

    address = normalize_address(location.address)
    if address:
        matches = [
            venue for venue in candidates
            if normalize_address(venue["address"]) == address
        ]
        if matches:
            return matches[0]

    if only_location and len(candidates) == 1:
        return candidates[0]
    return None


async def save_venue(conn, venues, venue, brewery_name, location):
    """Update a matched venue, or insert one, and return its id and name."""
    tag = json.dumps([f"hopclt:{location.location_id}"])
    lat = float(location.lat) if location.lat is not None else None
    lng = float(location.lng) if location.lng is not None else None
    if venue:
        row = await conn.fetchrow(
            """
            UPDATE venues
            SET address = COALESCE(NULLIF($2, ''), address),
                city = COALESCE(NULLIF($3, ''), city),
                neighborhood = COALESCE(NULLIF($4, ''), neighborhood),
                location = CASE
                    WHEN $5::float8 IS NOT NULL AND $6::float8 IS NOT NULL
                    THEN ST_SetSRID(ST_MakePoint($6, $5), 4326)::geography
                    ELSE location
                END,
                sources = CASE
                    WHEN sources @> $7::jsonb THEN sources
                    ELSE COALESCE(sources, '[]'::jsonb) || $7::jsonb
                END,
                updated_at = NOW()
            WHERE id = $1::uuid
            RETURNING id::text, name, address, city, sources
            """,
            venue["id"],
            location.address,
            location.city,
            location.neighborhood,
            lat,
            lng,
            tag,
        )
        return row

    name = location_label(brewery_name, location)
    row = await conn.fetchrow(
        """
        INSERT INTO venues (name, address, city, state, neighborhood, location, sources)
        VALUES (
            $1, NULLIF($2, ''), NULLIF($3, ''), 'North Carolina', NULLIF($4, ''),
            CASE
                WHEN $5::float8 IS NOT NULL AND $6::float8 IS NOT NULL
                THEN ST_SetSRID(ST_MakePoint($6, $5), 4326)::geography
                ELSE NULL
            END,
            $7::jsonb
        )
        RETURNING id::text, name, address, city, sources
        """,
        name,
        location.address,
        location.city,
        location.neighborhood,
        lat,
        lng,
        tag,
    )
    venues.append(row)
    return row


# Full HopCLT brewery list. Names are matched with ILIKE.
MAPPINGS = [
    ("Resident Culture", "https://hopclt.com/brewery/resident_culture"),
    ("HopFly", "https://hopclt.com/brewery/hopfly"),
    ("Birdsong", "https://hopclt.com/brewery/birdsong"),
    ("Petty Thieves", "https://hopclt.com/brewery/petty_thieves"),
    ("Fonta Flora", "https://hopclt.com/brewery/fonta_flora"),
    ("Wooden Robot", "https://hopclt.com/brewery/wooden_robot"),
    ("Lost Worlds", "https://hopclt.com/brewery/lost_worlds"),
    ("Town Brewing", "https://hopclt.com/brewery/town"),
    ("Free Range", "https://hopclt.com/brewery/free_range"),
    ("Heist", "https://hopclt.com/brewery/heist"),
    ("Pilot Brewing", "https://hopclt.com/brewery/pilot"),
    ("Club West", "https://hopclt.com/brewery/club_west_brewing"),
    ("Legion", "https://hopclt.com/brewery/legion"),
    ("Hi-Wire", "https://hopclt.com/brewery/hiwire"),
    ("Monday Night", "https://hopclt.com/brewery/monday_night"),
    ("Burial", "https://hopclt.com/brewery/burial"),
    ("Southern Strain", "https://hopclt.com/brewery/southern_strain"),
    ("NoDa Brewing", "https://hopclt.com/brewery/noda_brewing"),
    ("Triple C", "https://hopclt.com/brewery/triple_c"),
    ("Suffolk Punch", "https://hopclt.com/brewery/suffolk_punch"),
    ("Lenny Boy", "https://hopclt.com/brewery/lenny_boy"),
    ("Salud", "https://hopclt.com/brewery/salud"),
    ("Gilde", "https://hopclt.com/brewery/gilde"),
    ("Divine Barrel", "https://hopclt.com/brewery/divine_barrel"),
    ("Vaulted Oak", "https://hopclt.com/brewery/vaulted_oak"),
    ("Olde Mecklenburg", "https://hopclt.com/brewery/olde_mecklenburg"),
    ("Protagonist", "https://hopclt.com/brewery/protagonist_clubhouse"),
    ("Sugar Creek", "https://hopclt.com/brewery/sugar_creek"),
    ("Lower Left", "https://hopclt.com/brewery/lower_left"),
    ("Edge City", "https://hopclt.com/brewery/edge_city"),
    ("Armored Cow", "https://hopclt.com/brewery/armored_cow"),
    ("Middle James", "https://hopclt.com/brewery/middle_james"),
    ("Seaboard", "https://hopclt.com/brewery/seaboard"),
    ("Traust", "https://hopclt.com/brewery/traust"),
    ("Primal", "https://hopclt.com/brewery/primal"),
    ("Panzu", "https://hopclt.com/brewery/panzu"),
    ("Pour 64", "https://hopclt.com/brewery/pour_64"),
    ("Neoteric", "https://hopclt.com/brewery/neoteric"),
    ("760 Craft", "https://hopclt.com/brewery/760_craft_works"),
    ("Percent Tap", "https://hopclt.com/brewery/percent_tap_house"),
    ("Sweet Union", "https://hopclt.com/brewery/sweet_union"),
    ("Replay", "https://hopclt.com/brewery/replay"),
    ("Lore Brewing", "https://hopclt.com/brewery/lore"),
    ("Eleven Lakes", "https://hopclt.com/brewery/eleven_lakes"),
    ("Untamed Waters", "https://hopclt.com/brewery/untamed_waters"),
    ("Ass Clown", "https://hopclt.com/brewery/ass_clown"),
    ("Amor Artis", "https://hopclt.com/brewery/amor_artis"),
    ("Royal Bliss", "https://hopclt.com/brewery/royal_bliss"),
    ("Cabarrus", "https://hopclt.com/brewery/cabarrus"),
    ("High Branch", "https://hopclt.com/brewery/high_branch"),
    ("King Canary", "https://hopclt.com/brewery/king_canary"),
    ("Keepsake", "https://hopclt.com/brewery/keepsake"),
    ("Lake Norman", "https://hopclt.com/brewery/lake_norman"),
    ("Durty Bull", "https://hopclt.com/brewery/durty_bull"),
    ("Lake Wylie", "https://hopclt.com/brewery/lake_wylie"),
    ("Buzzed Viking", "https://hopclt.com/brewery/buzzed_viking_brewing_meadery"),
    ("Old Armor", "https://hopclt.com/brewery/old_armor"),
    ("Slow Play", "https://hopclt.com/brewery/slow_play"),
    ("Legal Remedy", "https://hopclt.com/brewery/legal_remedy"),
    ("Off The Tracks", "https://hopclt.com/brewery/off_the_tracks"),
    ("Rock Hill", "https://hopclt.com/brewery/rock_hill"),
    ("Brew Room", "https://hopclt.com/brewery/the_brew_room_locust"),
    ("Americana", "https://hopclt.com/brewery/americana"),
    ("Southern Range", "https://hopclt.com/brewery/southern_range"),
    ("Ghostface", "https://hopclt.com/brewery/ghostface"),
    ("Boondoggler", "https://hopclt.com/brewery/boondogglers"),
    ("Jolly Roger", "https://hopclt.com/brewery/jolly_roger"),
    ("Hoptown", "https://hopclt.com/brewery/hoptown"),
    ("Old Well", "https://hopclt.com/brewery/old_well"),
    ("Grove Cartel", "https://hopclt.com/brewery/grove_cartel"),
    ("Benford", "https://hopclt.com/brewery/benford"),
    ("New Sarum", "https://hopclt.com/brewery/new_sarum"),
    ("Uwharrie", "https://hopclt.com/brewery/uwharrie"),
    ("Red Buffalo", "https://hopclt.com/brewery/red_buffalo"),
]


async def run_scrapers():
    pool = await asyncpg.create_pool(DATABASE_URL)
    hopclt = HopCLTScraper()

    async with pool.acquire() as conn:
        venues = await conn.fetch(
            "SELECT id::text, name, address, city, sources FROM venues ORDER BY name"
        )
        venues = list(venues)

        for venue_name, hopclt_url in MAPPINGS:
            candidates = [
                venue for venue in venues
                if re.search(r"(?<![a-z])" + re.escape(venue_name.lower()), venue["name"].lower())
            ]
            print(f"Scraping {venue_name} ...")
            try:
                content = await hopclt.fetch(hopclt_url, venue_name)
                locations = hopclt.parse_locations(content, venue_name)
            except Exception as e:
                print(f"  Error: {e}")
                continue

            if not locations:
                print("  No locations found; left existing taps unchanged")
                continue

            brewery_name = venue_name
            for location in locations:
                if location.listings:
                    brewery_name = location.listings[0].brewery
                    break

            used_ids = set()
            only_location = len(locations) == 1
            print(f"  {len(locations)} locations")

            for location in locations:
                venue = find_venue_for_location(candidates, location, only_location)
                if venue and venue["id"] in used_ids:
                    venue = None
                saved = await save_venue(conn, venues, venue, brewery_name, location)
                for index, existing in enumerate(venues):
                    if existing["id"] == saved["id"]:
                        venues[index] = saved
                        break
                used_ids.add(saved["id"])

                beer_ids = []
                for listing in location.listings:
                    beer_id = await upsert_beer(conn, listing)
                    await upsert_tap(conn, saved["id"], beer_id, listing)
                    beer_ids.append(beer_id)
                if beer_ids:
                    await conn.execute(
                        """
                        DELETE FROM tap_listings
                        WHERE venue_id = $1::uuid
                          AND NOT (beer_id = ANY($2::uuid[]))
                        """,
                        saved["id"],
                        beer_ids,
                    )
                else:
                    await conn.execute(
                        """
                        DELETE FROM tap_listings
                        WHERE venue_id = $1::uuid AND source = 'hopclt'
                        """,
                        saved["id"],
                    )
                label = location.name or location.address or saved["name"]
                print(f"  {saved['name']}: {len(location.listings)} taps ({label})")

            for venue in candidates:
                if venue["id"] in used_ids:
                    continue
                await conn.execute(
                    """
                    DELETE FROM tap_listings
                    WHERE venue_id = $1::uuid AND source = 'hopclt'
                    """,
                    venue["id"],
                )

            await conn.execute(
                """
                DELETE FROM beers
                WHERE NOT EXISTS (
                    SELECT 1 FROM tap_listings tl WHERE tl.beer_id = beers.id
                )
                """
            )

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_scrapers())
