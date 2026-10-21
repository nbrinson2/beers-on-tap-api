-- Required for the runner's ON CONFLICT upsert on beers.
-- Run this once if it doesn't already exist:

ALTER TABLE beers ADD CONSTRAINT beers_name_brewery_key UNIQUE (name, brewery);

-- (Optional) If you prefer a generated normalized_name column later, you can drop this
-- and switch the upsert to use that instead.
