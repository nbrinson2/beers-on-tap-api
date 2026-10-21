from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import os
import asyncpg
from contextlib import asynccontextmanager

# Simple in-memory connection for starter (replace with proper pool + env vars)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/beers")

app = FastAPI(title="Beers on Tap API", version="0.1.0", description="Charlotte-first beers on tap database API")

# Models
class Venue(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    location: Optional[dict] = None  # {"lat": ..., "lon": ...}
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
    beer: Optional[Beer] = None
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

# Database helpers (stub for starter — wire to real PostGIS queries)
async def get_db():
    # Placeholder: in real use, use asyncpg pool + GeoAlchemy2 or raw SQL with ST_DWithin
    return None

@app.get("/")
async def root():
    return {"message": "Beers on Tap API", "docs": "/docs", "city_focus": "Charlotte, NC"}

@app.get("/venues/near", response_model=List[Venue])
async def venues_near(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    radius_km: float = Query(10.0, description="Radius in km"),
    limit: int = Query(50, le=200)
):
    """
    Find venues within radius of a point.
    Uses PostGIS ST_DWithin in production.
    """
    # TODO: Replace with real query:
    # SELECT id, name, ..., ST_Y(location::geometry) as lat, ST_X(location::geometry) as lon
    # FROM venues
    # WHERE ST_DWithin(location, ST_MakePoint(lon, lat)::geography, radius_km * 1000)
    # ORDER BY location <-> ST_MakePoint(lon, lat)::geography
    # LIMIT limit
    return []

@app.get("/venues/{venue_id}/taps", response_model=List[TapListing])
async def venue_taps(venue_id: str):
    """Current tap list for a venue, ordered by last_seen desc."""
    # TODO: JOIN tap_listings + beers, filter last_seen recent
    return []

@app.get("/beers/search")
async def search_beers(q: str = Query(..., min_length=2), limit: int = 20):
    """Search beers by name (full-text)."""
    return []

@app.post("/reports", status_code=201)
async def create_report(report: ReportCreate):
    """Submit a user report of what's on tap (for later moderation/merge)."""
    # TODO: insert into reports table
    return {"status": "received", "message": "Thanks for the report"}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
