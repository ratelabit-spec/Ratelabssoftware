-- market_snapshots: vincolo univoco utilizzabile da upsert (on_conflict) di PostgREST.
-- L'indice con coalesce() non è utilizzabile come target di ON CONFLICT dal client:
-- lo sostituiamo con un vincolo NULLS NOT DISTINCT (competitor_id NULL = la proprietà stessa).
drop index if exists public.market_snapshots_unique_idx;

alter table public.market_snapshots
    add constraint market_snapshots_unique
    unique nulls not distinct (property_id, competitor_id, stay_date, captured_on);
