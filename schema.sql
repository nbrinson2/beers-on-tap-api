-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Venues
CREATE TABLE venues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    country TEXT DEFAULT 'United States',
    location GEOGRAPHY(POINT, 4326),
    website TEXT,
    neighborhood TEXT,
    hours JSONB,
    sources JSONB DEFAULT '[]',
    last_checked TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_venues_location ON venues USING GIST (location);
CREATE INDEX idx_venues_city ON venues (city);

-- Beers
CREATE TABLE beers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    brewery TEXT,
    style TEXT,
    abv NUMERIC(4,2),
    ibu INTEGER,
    normalized_name TEXT,
    external_ids JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_beers_normalized ON beers (normalized_name);
CREATE INDEX idx_beers_name ON beers USING gin (to_tsvector('english', name));

-- Tap listings
CREATE TABLE tap_listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id UUID REFERENCES venues(id) ON DELETE CASCADE,
    beer_id UUID REFERENCES beers(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'on_tap', -- on_tap, on_deck, off
    serving_type TEXT, -- draft, cask, keg, etc.
    price NUMERIC(6,2),
    size TEXT,
    source TEXT,
    confidence NUMERIC(3,2) DEFAULT 0.5,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(venue_id, beer_id)
);

CREATE INDEX idx_tap_listings_venue ON tap_listings (venue_id);
CREATE INDEX idx_tap_listings_beer ON tap_listings (beer_id);
CREATE INDEX idx_tap_listings_last_seen ON tap_listings (last_seen);

-- Simple user reports table for contributions
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id UUID REFERENCES venues(id),
    beer_name TEXT,
    brewery TEXT,
    style TEXT,
    status TEXT DEFAULT 'on_tap',
    notes TEXT,
    reporter TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
