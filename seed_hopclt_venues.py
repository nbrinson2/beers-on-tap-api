"""
Seed missing HopCLT breweries into the venues table.
Run after the Open Brewery DB seeder.
"""
import asyncio
import os
import json
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# (name, hopclt_url) — coordinates can be added later
HOPCLT_BREWERIES = [
    ("Resident Culture Brewing", "https://hopclt.com/brewery/resident_culture"),
    ("HopFly Brewing Company", "https://hopclt.com/brewery/hopfly"),
    ("Birdsong Brewing Company", "https://hopclt.com/brewery/birdsong"),
    ("Petty Thieves Brewing", "https://hopclt.com/brewery/petty_thieves"),
    ("Fonta Flora Brewery", "https://hopclt.com/brewery/fonta_flora"),
    ("Wooden Robot Brewery", "https://hopclt.com/brewery/wooden_robot"),
    ("Lost Worlds Brewing", "https://hopclt.com/brewery/lost_worlds"),
    ("Town Brewing", "https://hopclt.com/brewery/town"),
    ("Free Range Brewing", "https://hopclt.com/brewery/free_range"),
    ("Heist Brewery", "https://hopclt.com/brewery/heist"),
    ("Pilot Brewing", "https://hopclt.com/brewery/pilot"),
    ("Club West Brewing", "https://hopclt.com/brewery/club_west_brewing"),
    ("Legion Brewing", "https://hopclt.com/brewery/legion"),
    ("Hi-Wire Brewing", "https://hopclt.com/brewery/hiwire"),
    ("Monday Night Brewing", "https://hopclt.com/brewery/monday_night"),
    ("Burial Beer Co.", "https://hopclt.com/brewery/burial"),
    ("Southern Strain Brewing", "https://hopclt.com/brewery/southern_strain"),
    ("NoDa Brewing Company", "https://hopclt.com/brewery/noda_brewing"),
    ("Triple C Brewing", "https://hopclt.com/brewery/triple_c"),
    ("Suffolk Punch Brewing", "https://hopclt.com/brewery/suffolk_punch"),
    ("Lenny Boy Brewing", "https://hopclt.com/brewery/lenny_boy"),
    ("Salud Cerveceria", "https://hopclt.com/brewery/salud"),
    ("Gilde Brewery", "https://hopclt.com/brewery/gilde"),
    ("Divine Barrel Brewing", "https://hopclt.com/brewery/divine_barrel"),
    ("Vaulted Oak Brewing", "https://hopclt.com/brewery/vaulted_oak"),
    ("The Olde Mecklenburg Brewery", "https://hopclt.com/brewery/olde_mecklenburg"),
    ("Protagonist", "https://hopclt.com/brewery/protagonist_clubhouse"),
    ("Sugar Creek Brewing Company", "https://hopclt.com/brewery/sugar_creek"),
    ("Lower Left Brewing", "https://hopclt.com/brewery/lower_left"),
    ("Edge City Brewery", "https://hopclt.com/brewery/edge_city"),
    ("Armored Cow Brewing", "https://hopclt.com/brewery/armored_cow"),
    ("Middle James Brewing", "https://hopclt.com/brewery/middle_james"),
    ("Seaboard Brewing", "https://hopclt.com/brewery/seaboard"),
    ("Traust Brewing", "https://hopclt.com/brewery/traust"),
    ("Primal Brewery", "https://hopclt.com/brewery/primal"),
    ("Panzu Brewery", "https://hopclt.com/brewery/panzu"),
    ("Pour 64", "https://hopclt.com/brewery/pour_64"),
    ("Neoteric Brewing", "https://hopclt.com/brewery/neoteric"),
    ("760 Craft Works", "https://hopclt.com/brewery/760_craft_works"),
    ("Percent Tap House", "https://hopclt.com/brewery/percent_tap_house"),
    ("Sweet Union", "https://hopclt.com/brewery/sweet_union"),
    ("Replay Brewing", "https://hopclt.com/brewery/replay"),
    ("Lore Brewing", "https://hopclt.com/brewery/lore"),
    ("Eleven Lakes Brewing", "https://hopclt.com/brewery/eleven_lakes"),
    ("Untamed Waters Brewing", "https://hopclt.com/brewery/untamed_waters"),
    ("Ass Clown Brewing Company", "https://hopclt.com/brewery/ass_clown"),
    ("Amor Artis Brewing", "https://hopclt.com/brewery/amor_artis"),
    ("Royal Bliss Brewing", "https://hopclt.com/brewery/royal_bliss"),
    ("Cabarrus Brewing Company", "https://hopclt.com/brewery/cabarrus"),
    ("High Branch Brewing", "https://hopclt.com/brewery/high_branch"),
    ("King Canary Brewing", "https://hopclt.com/brewery/king_canary"),
    ("Keepsake Brewery", "https://hopclt.com/brewery/keepsake"),
    ("Lake Norman Brewery", "https://hopclt.com/brewery/lake_norman"),
    ("Durty Bull Brewing Co.", "https://hopclt.com/brewery/durty_bull"),
    ("Lake Wylie Brewing", "https://hopclt.com/brewery/lake_wylie"),
    ("Buzzed Viking Brewing & Meadery", "https://hopclt.com/brewery/buzzed_viking_brewing_meadery"),
    ("Old Armor Beer", "https://hopclt.com/brewery/old_armor"),
    ("Slow Play Brewing", "https://hopclt.com/brewery/slow_play"),
    ("Legal Remedy Brewing", "https://hopclt.com/brewery/legal_remedy"),
    ("Off The Tracks Brewing", "https://hopclt.com/brewery/off_the_tracks"),
    ("Rock Hill Brewing Company", "https://hopclt.com/brewery/rock_hill"),
    ("The Brew Room Locust", "https://hopclt.com/brewery/the_brew_room_locust"),
    ("Americana Beer Co", "https://hopclt.com/brewery/americana"),
    ("Southern Range Brewing", "https://hopclt.com/brewery/southern_range"),
    ("Ghostface Brewing", "https://hopclt.com/brewery/ghostface"),
    ("Boondoggler's Brewing Company", "https://hopclt.com/brewery/boondogglers"),
    ("Jolly Roger Brewery", "https://hopclt.com/brewery/jolly_roger"),
    ("Hoptown Brewing", "https://hopclt.com/brewery/hoptown"),
    ("Old Well Brewery", "https://hopclt.com/brewery/old_well"),
    ("Grove Cartel Brewing Co", "https://hopclt.com/brewery/grove_cartel"),
    ("Benford Brewing Company", "https://hopclt.com/brewery/benford"),
    ("New Sarum Brewing", "https://hopclt.com/brewery/new_sarum"),
    ("Uwharrie Brewing", "https://hopclt.com/brewery/uwharrie"),
    ("Red Buffalo Brewing Company", "https://hopclt.com/brewery/red_buffalo"),
]


async def seed_missing():
    pool = await asyncpg.create_pool(DATABASE_URL)
    inserted = 0
    async with pool.acquire() as conn:
        for name, url in HOPCLT_BREWERIES:
            exists = await conn.fetchval(
                "SELECT 1 FROM venues WHERE name ILIKE $1 LIMIT 1",
                f"%{name}%",
            )
            if exists:
                continue
            await conn.execute(
                """
                INSERT INTO venues (name, city, state, country, website, sources)
                VALUES ($1, 'Charlotte', 'North Carolina', 'United States', $2, $3::jsonb)
                """,
                name,
                url,
                json.dumps(["hopclt"]),
            )
            inserted += 1
            print(f"Inserted: {name}")
    print(f"Done. Inserted {inserted} new venues.")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(seed_missing())
