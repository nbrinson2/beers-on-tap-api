# Beers on Tap API

Minimal API-first beers-on-tap database starting with Charlotte, NC.

## Quick start

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set DATABASE_URL (Postgres + PostGIS required)
export DATABASE_URL="postgresql://user:pass@localhost:5432/beers"

# Run schema
psql $DATABASE_URL -f schema.sql

# Start API
uvicorn main:app --reload
```

Docs at http://localhost:8000/docs

## Endpoints (starter)

- `GET /venues/near?lat=&lon=&radius_km=`
- `GET /venues/{id}/taps`
- `GET /beers/search?q=`
- `POST /reports`
- `GET /health`

## Next steps

1. Wire real asyncpg / SQLAlchemy + GeoAlchemy2 queries.
2. Seed Charlotte venues from Open Brewery DB.
3. Add scrapers for HopCLT / brewery sites.
4. Deploy (Railway, Fly, Render, or Supabase + Vercel).

## Schema

See `schema.sql` for venues, beers, tap_listings, and reports tables with PostGIS.
