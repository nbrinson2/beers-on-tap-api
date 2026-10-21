"""
Simple seeder: pulls Charlotte-area venues from Open Brewery DB and inserts them.
Run after schema is applied.
"""
import asyncio
import os
import asyncpg
import httpx

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/beers")
OBDB_BASE = "https://api.openbrewerydb.org/v1/breweries"

async def seed():
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with httpx.AsyncClient(timeout=30) as client:
        # Charlotte + nearby
        resp = await client.get(OBDB_BASE, params={"by_city": "Charlotte", "by_state": "North_Carolina", "per_page": 50})
        resp.raise_for_status()
        breweries = resp.json()

        print(f"Found {len(breweries)} Charlotte venues from Open Brewery DB")

        async with pool.acquire() as conn:
            for b in breweries:
                lat = b.get("latitude")
                lon = b.get("longitude")
                if not lat or not lon:
                    continue
                await conn.execute("""
                    INSERT INTO venues (name, address, city, state, country, location, website, sources)
                    VALUES ($1, $2, $3, $4, $5, ST_MakePoint($6, $7)::geography, $8, $9)
                    ON CONFLICT DO NOTHING
                """,
                    b.get("name"),
                    b.get("address_1") or b.get("street"),
                    b.get("city"),
                    b.get("state"),
                    b.get("country"),
                    float(lon), float(lat),
                    b.get("website_url"),
                    ["openbrewerydb"]
                )
        print("Seeding complete.")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(seed())
