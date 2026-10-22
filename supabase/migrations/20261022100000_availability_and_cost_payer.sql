-- =====================================================================
-- 1) Chi sostiene il costo: Property Manager o proprietario dell'immobile
-- 2) Calendario di apertura per proprietà (occupancy su notti realmente vendibili)
-- =====================================================================

-- ──────────────────────────────────────────
-- 1. property_costs.borne_by
-- ──────────────────────────────────────────
-- I costi già inseriti restano a carico del PM: rivederli dalla tab Dati.
alter table public.property_costs
    add column borne_by text not null default 'pm' check (borne_by in ('pm', 'owner'));


-- ──────────────────────────────────────────
-- 2. property_availability
-- ──────────────────────────────────────────
-- Periodi in cui la proprietà è aperta alla vendita (estremi inclusi).
-- Regola di calcolo: in un anno senza periodi registrati la proprietà è considerata aperta tutto l'anno;
-- se nell'anno esiste almeno un periodo, sono vendibili solo le notti dentro i periodi.
create table public.property_availability (
    id           uuid primary key default gen_random_uuid(),
    tenant_id    uuid not null references public.tenants(id) on delete cascade,
    property_id  uuid not null,
    open_from    date not null,
    open_to      date not null,
    notes        text,
    created_at   timestamptz not null default now(),
    check (open_to >= open_from),
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete cascade
);
create index property_availability_property_idx on public.property_availability (property_id, open_from);

alter table public.property_availability enable row level security;

create policy property_availability_member_all on public.property_availability for all to authenticated
    using (public.is_tenant_member(tenant_id))
    with check (public.is_tenant_member(tenant_id));
