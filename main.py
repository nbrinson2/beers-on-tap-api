from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/beers")

app = FastAPI(title="Beers on Tap API", version="0.2.0", description="Charlotte-first beers on tap database API")

pool: Optional[asyncpg.Pool] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    yield
    await pool.close()

app.router.lifespan_context = lifespan

# Models
class Venue(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    website: Optional[str] = None
    neighborhood: Optional[str] = None
    last_checked: Optional[datetime] = None

class Beer(BaseModel):
    id: str
    name: str
    brewery: Optional[str] = None
    style: Optional[str] = None
    abv: Optional[float] = None
    ibu: Optional[int] = None

class TapListing(BaseModel):
    id: str
    venue_id: str
    beer_id: str
    beer_name: Optional[str] = None
    brewery: Optional[str] = None
    style: Optional[str] = None
    abv: Optional[float] = None
    status: str = "on_tap"
    serving_type: Optional[str] = None
    price: Optional[float] = None
    size: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[float] = None
    last_seen: Optional[datetime] = None

class ReportCreate(BaseModel):
    venue_id: str
    beer_name: str
    brewery: Optional[str] = None
    style: Optional[str] = None
    status: str = "on_tap"
    notes: Optional[str] = None
    reporter: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Beers on Tap API", "docs": "/docs", "city_focus": "Charlotte, NC"}

@app.get("/venues/near", response_model=List[Venue])
async def venues_near(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(10.0),
    limit: int = Query(50, le=200)
):
    query = """
        SELECT id::text, name, address, city, website, neighborhood, last_checked,
               ST_Y(location::geometry) AS lat,
               ST_X(location::geometry) AS lon
        FROM venues
        WHERE ST_DWithin(location, ST_MakePoint($1, $2)::geography, $3)
        ORDER BY location <-> ST_MakePoint($1, $2)::geography
        LIMIT $4
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, lon, lat, radius_km * 1000, limit)
    return [Venue(**dict(r)) for r in rows]

@app.get("/venues/{venue_id}/taps", response_model=List[TapListing])
async def venue_taps(venue_id: str):
    query = """
        SELECT tl.id::text, tl.venue_id::text, tl.beer_id::text,
               b.name AS beer_name, b.brewery, b.style, b.abv,
               tl.status, tl.serving_type, tl.price, tl.size,
               tl.source, tl.confidence, tl.last_seen
        FROM tap_listings tl
        JOIN beers b ON b.id = tl.beer_id
        WHERE tl.venue_id = $1::uuid
          AND tl.status = 'on_tap'
          AND tl.last_seen > NOW() - INTERVAL '14 days'
        ORDER BY tl.last_seen DESC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, venue_id)
    return [TapListing(**dict(r)) for r in rows]

@app.get("/beers/search")
async def search_beers(q: str = Query(..., min_length=2), limit: int = 20):
    query = """
        SELECT id::text, name, brewery, style, abv, ibu
        FROM beers
        WHERE to_tsvector('english', name) @@ plainto_tsquery('english', $1)
           OR name ILIKE $2
        LIMIT $3
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, q, f"%{q}%", limit)
    return [dict(r) for r in rows]

@app.post("/reports", status_code=201)
async def create_report(report: ReportCreate):
    query = """
        INSERT INTO reports (venue_id, beer_name, brewery, style, status, notes, reporter)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
        RETURNING id::text
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, report.venue_id, report.beer_name, report.brewery,
                                   report.style, report.status, report.notes, report.reporter)
    return {"status": "received", "id": row["id"], "message": "Thanks for the report"}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
