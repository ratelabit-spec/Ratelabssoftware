-- =====================================================================
-- Rate Labs — Schema iniziale (Documento Maestro, 30/09/2026)
-- Esegui UNA volta nell'SQL Editor del nuovo progetto Supabase.
--
-- Principi:
--   * Multi-tenant stretto: ogni tabella ha tenant_id + RLS via tenant_members.
--   * FK composte (id, tenant_id) per impedire incroci tra tenant.
--   * Registro decisioni append-only: decisions/outcomes non si cancellano dal client.
--   * Le regole diagnosticano (diagnoses), l'IA spiega (recommendations).
-- =====================================================================


-- ──────────────────────────────────────────
-- 0. UTILITY
-- ──────────────────────────────────────────
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;


-- ──────────────────────────────────────────
-- 1. AUTH: TENANTS, MEMBRI, PROFILI
-- ──────────────────────────────────────────
-- tenant = cliente Rate Labs (revenue manager, property manager o hotel)
create table public.tenants (
    id          uuid primary key default gen_random_uuid(),
    name        text not null,
    plan        text not null default 'pro' check (plan in ('pro', 'esencial', 'servicio')),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create table public.tenant_members (
    tenant_id   uuid not null references public.tenants(id) on delete cascade,
    user_id     uuid not null references auth.users(id) on delete cascade,
    role        text not null default 'member' check (role in ('owner', 'member')),
    created_at  timestamptz not null default now(),
    primary key (tenant_id, user_id)
);
create index tenant_members_user_idx on public.tenant_members (user_id);

create table public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    email       text,
    full_name   text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

-- Helper RLS (security definer: evita ricorsione sulle policy di tenant_members)
create or replace function public.is_tenant_member(t uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1 from public.tenant_members
        where tenant_id = t and user_id = (select auth.uid())
    );
$$;

create or replace function public.is_tenant_owner(t uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1 from public.tenant_members
        where tenant_id = t and user_id = (select auth.uid()) and role = 'owner'
    );
$$;

-- Alla registrazione: profilo + tenant personale + ruolo owner
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    new_tenant_id uuid;
begin
    insert into public.profiles (id, email, full_name)
    values (new.id, new.email, new.raw_user_meta_data ->> 'full_name');

    insert into public.tenants (name)
    values (coalesce(new.raw_user_meta_data ->> 'company', split_part(new.email, '@', 1)))
    returning id into new_tenant_id;

    insert into public.tenant_members (tenant_id, user_id, role)
    values (new_tenant_id, new.id, 'owner');

    return new;
end;
$$;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();


-- ──────────────────────────────────────────
-- 2. PROPERTIES
-- ──────────────────────────────────────────
create table public.properties (
    id           uuid primary key default gen_random_uuid(),
    tenant_id    uuid not null references public.tenants(id) on delete cascade,
    name         text not null,
    external_id  text not null,                 -- nome/ID unità nel PMS (es. "Mazzini 4 TO")
    segment      text check (segment in ('apartment', 'villa', 'trullo', 'bnb', 'hotel', 'masseria', 'agriturismo', 'other')),
    units        integer not null default 1 check (units > 0),  -- camere/unità vendibili (denominatore occupancy)
    city         text,
    is_active    boolean not null default true,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (tenant_id, external_id),
    unique (id, tenant_id)                      -- target delle FK composte
);


-- ──────────────────────────────────────────
-- 3. INGESTA: MAPPING E LOG DEI CARICAMENTI
-- ──────────────────────────────────────────
create table public.source_mappings (
    id           uuid primary key default gen_random_uuid(),
    tenant_id    uuid not null references public.tenants(id) on delete cascade,
    source_type  text not null check (source_type in ('pms', 'rms', 'booking', 'airbnb', 'other')),
    source_name  text not null,                 -- es. 'KrossBooking', 'Guesty', 'Beyond'
    mapping      jsonb not null,                -- {campo_interno: colonna_file}
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (tenant_id, source_type, source_name),
    unique (id, tenant_id)
);

-- Un record per ogni file caricato: tracciabilità + avvisi di validazione
create table public.data_imports (
    id                 uuid primary key default gen_random_uuid(),
    tenant_id          uuid not null references public.tenants(id) on delete cascade,
    source_mapping_id  uuid,
    file_name          text,
    rows_total         integer,
    rows_loaded        integer,
    warnings           jsonb not null default '[]'::jsonb,   -- colonne mancanti, date fuori range, totali che non quadrano
    uploaded_by        uuid references auth.users(id) on delete set null,
    created_at         timestamptz not null default now(),
    unique (id, tenant_id),
    foreign key (source_mapping_id, tenant_id) references public.source_mappings(id, tenant_id) on delete set null (source_mapping_id)
);


-- ──────────────────────────────────────────
-- 4. RESERVATIONS (fonte di verità: PMS)
-- ──────────────────────────────────────────
create table public.reservations (
    id                  uuid primary key default gen_random_uuid(),
    tenant_id           uuid not null references public.tenants(id) on delete cascade,
    property_id         uuid not null,
    import_id           uuid,
    pms_reservation_id  text not null,
    check_in_date       date not null,
    check_out_date      date,
    booking_date        date,
    cancellation_date   date,
    status              text,                   -- stato grezzo del PMS
    is_cancelled        boolean not null default false,
    channel             text,                   -- canale grezzo del PMS
    channel_group       text,                   -- Booking.com, Airbnb, Expedia Group, Diretto, Altro
    guests              integer,
    nights              integer not null default 0,
    lead_time           integer,
    gross_revenue       numeric(12,2) not null default 0,
    commission_amount   numeric(12,2) not null default 0,
    net_revenue         numeric(12,2) not null default 0,
    pm_net              numeric(12,2),          -- opzionale: quota PM
    owner_net           numeric(12,2),          -- opzionale: quota proprietario
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now(),
    unique (tenant_id, pms_reservation_id),
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete cascade,
    foreign key (import_id, tenant_id) references public.data_imports(id, tenant_id) on delete set null (import_id)
);
create index reservations_property_checkin_idx on public.reservations (property_id, check_in_date);
create index reservations_tenant_booking_idx   on public.reservations (tenant_id, booking_date);


-- ──────────────────────────────────────────
-- 5. FUNNEL OTA (fonte di verità: extranet Booking / pannello Airbnb)
-- ──────────────────────────────────────────
create table public.funnel_metrics (
    id                  uuid primary key default gen_random_uuid(),
    tenant_id           uuid not null references public.tenants(id) on delete cascade,
    property_id         uuid not null,
    import_id           uuid,
    channel             text not null check (channel in ('booking', 'airbnb', 'expedia', 'vrbo', 'google', 'other')),
    period_start        date not null,
    period_end          date not null,
    search_impressions  integer,                -- visualizzazioni nei risultati di ricerca
    listing_views       integer,                -- visite alla scheda
    bookings            integer,
    ctr_pct             numeric(6,3),           -- se il report lo dà già calcolato
    conversion_pct      numeric(6,3),
    search_position     numeric(6,2),           -- posizione media in ricerca
    review_score        numeric(4,2),
    review_count        integer,
    visibility_programs text[],                 -- es. {'Genius','Preferred'}
    entry_method        text not null default 'form' check (entry_method in ('form', 'import')),
    created_at          timestamptz not null default now(),
    check (period_end >= period_start),
    unique (property_id, channel, period_start, period_end),
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete cascade,
    foreign key (import_id, tenant_id) references public.data_imports(id, tenant_id) on delete set null (import_id)
);
create index funnel_metrics_tenant_period_idx on public.funnel_metrics (tenant_id, period_start);


-- ──────────────────────────────────────────
-- 6. COMP SET E MARKET SNAPSHOTS (scraping pubblico, Apify)
-- ──────────────────────────────────────────
create table public.competitors (
    id           uuid primary key default gen_random_uuid(),
    tenant_id    uuid not null references public.tenants(id) on delete cascade,
    property_id  uuid not null,                 -- proprietà a cui appartiene il comp set
    name         text not null,
    platform     text not null default 'booking' check (platform in ('booking', 'airbnb', 'other')),
    url          text not null,
    is_active    boolean not null default true,
    created_at   timestamptz not null default now(),
    unique (property_id, url),
    unique (id, tenant_id),
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete cascade
);

-- competitor_id NULL = snapshot della proprietà stessa (es. sua posizione in ricerca)
create table public.market_snapshots (
    id               uuid primary key default gen_random_uuid(),
    tenant_id        uuid not null references public.tenants(id) on delete cascade,
    property_id      uuid not null,
    competitor_id    uuid,
    stay_date        date not null,
    captured_on      date not null default current_date,
    price            numeric(10,2),
    is_available     boolean,
    review_score     numeric(4,2),
    search_position  integer,
    created_at       timestamptz not null default now(),
    foreign key (property_id, tenant_id)   references public.properties(id, tenant_id)  on delete cascade,
    foreign key (competitor_id, tenant_id) references public.competitors(id, tenant_id) on delete cascade
);
create unique index market_snapshots_unique_idx
    on public.market_snapshots (property_id, coalesce(competitor_id, '00000000-0000-0000-0000-000000000000'::uuid), stay_date, captured_on);
create index market_snapshots_stay_idx on public.market_snapshots (property_id, stay_date);


-- ──────────────────────────────────────────
-- 7. CONFIGURAZIONE CLIENTE (con storico: valid_to NULL = vigente)
-- ──────────────────────────────────────────
-- Condizioni commerciali della proprietà
create table public.property_settings (
    id                   uuid primary key default gen_random_uuid(),
    tenant_id            uuid not null references public.tenants(id) on delete cascade,
    property_id          uuid not null,
    min_stay             integer check (min_stay > 0),
    cancellation_policy  text,                  -- es. 'flessibile', 'moderata', 'non rimborsabile'
    cleaning_fee         numeric(10,2) not null default 0,   -- addebitata al guest, fuori dal gross_revenue del PMS
    promos               jsonb not null default '[]'::jsonb, -- [{"name":"Genius","discount_pct":10,"channel":"booking"}]
    notes                text,
    valid_from           date not null default current_date,
    valid_to             date,
    created_at           timestamptz not null default now(),
    check (valid_to is null or valid_to >= valid_from),
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete cascade
);
create unique index property_settings_current_idx on public.property_settings (property_id) where valid_to is null;

-- Costi: fissi, variabili e bollette in un'unica tabella
--   basis 'monthly' | 'yearly'                       → costo fisso ricorrente
--   basis 'per_booking' | 'per_night' | 'per_guest'  → costo variabile
--   basis 'period_total'                              → bolletta: amount copre valid_from..valid_to
create table public.property_costs (
    id           uuid primary key default gen_random_uuid(),
    tenant_id    uuid not null references public.tenants(id) on delete cascade,
    property_id  uuid not null,
    category     text not null,                 -- es. 'affitto', 'pulizie', 'lavanderia', 'luce', 'gas'
    basis        text not null check (basis in ('monthly', 'yearly', 'per_booking', 'per_night', 'per_guest', 'period_total')),
    amount       numeric(10,2) not null check (amount >= 0),
    channel      text,                          -- NULL = tutti i canali
    valid_from   date not null default current_date,
    valid_to     date,
    notes        text,
    created_at   timestamptz not null default now(),
    check (valid_to is null or valid_to >= valid_from),
    check (basis <> 'period_total' or valid_to is not null),
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete cascade
);
create index property_costs_property_idx on public.property_costs (property_id, valid_from);

-- Commissioni per canale (property_id NULL = default del tenant)
create table public.channel_commissions (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references public.tenants(id) on delete cascade,
    property_id     uuid,
    channel_group   text not null,
    commission_pct  numeric(5,2) not null check (commission_pct between 0 and 100),
    valid_from      date not null default current_date,
    valid_to        date,
    created_at      timestamptz not null default now(),
    check (valid_to is null or valid_to >= valid_from),
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete cascade
);
create unique index channel_commissions_current_idx
    on public.channel_commissions (tenant_id, coalesce(property_id, '00000000-0000-0000-0000-000000000000'::uuid), channel_group)
    where valid_to is null;


-- ──────────────────────────────────────────
-- 8. REGISTRO: DIAGNOSI → RACCOMANDAZIONE → DECISIONE → RISULTATO
-- ──────────────────────────────────────────
-- Output dell'albero di regole (cervello matematico). Una per proprietà e settimana.
create table public.diagnoses (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references public.tenants(id) on delete cascade,
    property_id     uuid not null,
    week_start      date not null check (extract(isodow from week_start) = 1),   -- lunedì
    failed_stage    text check (failed_stage in ('impressions', 'ctr', 'conversion', 'margin')),  -- NULL = tutto OK
    lever           text not null check (lever in ('positioning', 'storefront', 'listing_conditions', 'profitability', 'none')),
    kpis            jsonb not null default '{}'::jsonb,   -- KPI calcolati (ADR, occupancy, pace, CTR, conversione, bottom rate...)
    rule_trace      jsonb not null default '[]'::jsonb,   -- esito di ogni domanda dell'albero con soglie usate
    bottom_rate     numeric(10,2),
    engine_version  text not null,
    created_at      timestamptz not null default now(),
    unique (property_id, week_start),
    unique (id, tenant_id),
    -- no action: una proprietà con storico decisioni non si cancella (si disattiva con is_active = false)
    foreign key (property_id, tenant_id) references public.properties(id, tenant_id) on delete no action,
    check ((failed_stage is null) = (lever = 'none'))
);
create index diagnoses_tenant_week_idx on public.diagnoses (tenant_id, week_start);

-- Testo dell'IA: una sola leva per diagnosi (regola 3)
create table public.recommendations (
    id                        uuid primary key default gen_random_uuid(),
    tenant_id                 uuid not null references public.tenants(id) on delete cascade,
    diagnosis_id              uuid not null,
    lever                     text not null check (lever in ('positioning', 'storefront', 'listing_conditions', 'profitability', 'none')),
    action                    text not null,
    rationale                 text not null,
    target_metric             text not null,      -- es. 'search_impressions', 'ctr_pct', 'conversion_pct', 'net_adr'
    expected_direction        text not null default 'up' check (expected_direction in ('up', 'down')),
    measurement_window_days   integer not null default 14 check (measurement_window_days > 0),
    ai_model                  text,
    prompt_version            text,
    created_at                timestamptz not null default now(),
    unique (diagnosis_id),
    unique (id, tenant_id),
    foreign key (diagnosis_id, tenant_id) references public.diagnoses(id, tenant_id) on delete cascade
);

-- Decisione del revenue: ogni decisione è un'ipotesi da misurare
create table public.decisions (
    id                 uuid primary key default gen_random_uuid(),
    tenant_id          uuid not null references public.tenants(id) on delete cascade,
    recommendation_id  uuid not null,
    decision           text not null check (decision in ('accepted', 'modified', 'rejected')),
    action_taken       text,                    -- obbligatoria se 'modified'
    reason             text,                    -- motivo (soprattutto se rifiutata/modificata)
    effective_from     date not null default current_date,
    decided_by         uuid references auth.users(id) on delete set null,
    decided_at         timestamptz not null default now(),
    unique (recommendation_id),
    unique (id, tenant_id),
    foreign key (recommendation_id, tenant_id) references public.recommendations(id, tenant_id) on delete cascade,
    check (decision <> 'modified' or action_taken is not null)
);

-- Misura del risultato, confrontato con anno precedente e comp set
create table public.outcomes (
    id               uuid primary key default gen_random_uuid(),
    tenant_id        uuid not null references public.tenants(id) on delete cascade,
    decision_id      uuid not null,
    metric           text not null,
    window_start     date not null,
    window_end       date not null,
    value_before     numeric,
    value_after      numeric,
    value_ly         numeric,                   -- stesso periodo anno precedente
    value_comp_set   numeric,
    verdict          text check (verdict in ('improved', 'no_change', 'worsened', 'inconclusive')),
    notes            text,
    measured_at      timestamptz not null default now(),
    check (window_end >= window_start),
    unique (decision_id, metric, window_start, window_end),
    foreign key (decision_id, tenant_id) references public.decisions(id, tenant_id) on delete cascade
);


-- ──────────────────────────────────────────
-- 9. TRIGGER updated_at
-- ──────────────────────────────────────────
create trigger tenants_updated_at         before update on public.tenants         for each row execute function public.set_updated_at();
create trigger profiles_updated_at        before update on public.profiles        for each row execute function public.set_updated_at();
create trigger properties_updated_at      before update on public.properties      for each row execute function public.set_updated_at();
create trigger source_mappings_updated_at before update on public.source_mappings for each row execute function public.set_updated_at();
create trigger reservations_updated_at    before update on public.reservations    for each row execute function public.set_updated_at();


-- ──────────────────────────────────────────
-- 10. ROW LEVEL SECURITY
-- ──────────────────────────────────────────
alter table public.tenants             enable row level security;
alter table public.tenant_members      enable row level security;
alter table public.profiles            enable row level security;
alter table public.properties          enable row level security;
alter table public.source_mappings     enable row level security;
alter table public.data_imports        enable row level security;
alter table public.reservations        enable row level security;
alter table public.funnel_metrics      enable row level security;
alter table public.competitors         enable row level security;
alter table public.market_snapshots    enable row level security;
alter table public.property_settings   enable row level security;
alter table public.property_costs      enable row level security;
alter table public.channel_commissions enable row level security;
alter table public.diagnoses           enable row level security;
alter table public.recommendations     enable row level security;
alter table public.decisions           enable row level security;
alter table public.outcomes            enable row level security;

-- Tenants: i membri leggono, solo l'owner modifica. La creazione avviene via trigger.
create policy tenants_select on public.tenants for select to authenticated
    using (public.is_tenant_member(id));
create policy tenants_update on public.tenants for update to authenticated
    using (public.is_tenant_owner(id)) with check (public.is_tenant_owner(id));

-- Membri: i membri vedono il team, solo l'owner aggiunge/rimuove
create policy tenant_members_select on public.tenant_members for select to authenticated
    using (public.is_tenant_member(tenant_id));
create policy tenant_members_insert on public.tenant_members for insert to authenticated
    with check (public.is_tenant_owner(tenant_id));
create policy tenant_members_delete on public.tenant_members for delete to authenticated
    using (public.is_tenant_owner(tenant_id));

-- Profili: ognuno il proprio
create policy profiles_select on public.profiles for select to authenticated
    using (id = (select auth.uid()));
create policy profiles_update on public.profiles for update to authenticated
    using (id = (select auth.uid())) with check (id = (select auth.uid()));

-- Tabelle operative: accesso completo per i membri del tenant
do $$
declare
    t text;
begin
    foreach t in array array[
        'properties', 'source_mappings', 'data_imports', 'reservations', 'funnel_metrics',
        'competitors', 'market_snapshots', 'property_settings', 'property_costs',
        'channel_commissions', 'diagnoses', 'recommendations'
    ]
    loop
        execute format(
            'create policy %1$s_member_all on public.%1$I for all to authenticated
                 using (public.is_tenant_member(tenant_id))
                 with check (public.is_tenant_member(tenant_id))', t);
    end loop;
end;
$$;

-- Registro decisioni: append-only dal client (select/insert/update, niente delete)
create policy decisions_select on public.decisions for select to authenticated
    using (public.is_tenant_member(tenant_id));
create policy decisions_insert on public.decisions for insert to authenticated
    with check (public.is_tenant_member(tenant_id) and decided_by = (select auth.uid()));
create policy decisions_update on public.decisions for update to authenticated
    using (public.is_tenant_member(tenant_id)) with check (public.is_tenant_member(tenant_id));

create policy outcomes_select on public.outcomes for select to authenticated
    using (public.is_tenant_member(tenant_id));
create policy outcomes_insert on public.outcomes for insert to authenticated
    with check (public.is_tenant_member(tenant_id));
create policy outcomes_update on public.outcomes for update to authenticated
    using (public.is_tenant_member(tenant_id)) with check (public.is_tenant_member(tenant_id));


-- ──────────────────────────────────────────
-- 11. BACKFILL: utenti registrati prima di questo script
-- ──────────────────────────────────────────
do $$
declare
    u record;
    new_tenant_id uuid;
begin
    for u in
        select au.id, au.email, au.raw_user_meta_data
        from auth.users au
        where not exists (select 1 from public.tenant_members tm where tm.user_id = au.id)
    loop
        insert into public.profiles (id, email, full_name)
        values (u.id, u.email, u.raw_user_meta_data ->> 'full_name')
        on conflict (id) do nothing;

        insert into public.tenants (name)
        values (coalesce(u.raw_user_meta_data ->> 'company', split_part(u.email, '@', 1)))
        returning id into new_tenant_id;

        insert into public.tenant_members (tenant_id, user_id, role)
        values (new_tenant_id, u.id, 'owner');
    end loop;
end;
$$;
