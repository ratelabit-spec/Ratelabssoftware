-- =====================================================================
-- KrossBooking Pace Pro — Schema Supabase
-- Ricreato dal codice sorgente. Esegui nell'SQL Editor di Supabase.
-- NOTA: user_id è UUID NOT NULL senza FK diretta ad auth.users
--       (limitazione Supabase: non si può referenziare auth schema da public).
--       La sicurezza è gestita interamente da RLS + auth.uid().
-- =====================================================================

-- ──────────────────────────────────────────
-- STEP 0: DROP tabelle esistenti (le tabelle sono vuote, sicuro da eseguire)
-- CASCADE gestisce automaticamente le dipendenze FK
-- ──────────────────────────────────────────
DROP TABLE IF EXISTS fixed_costs        CASCADE;
DROP TABLE IF EXISTS variable_costs     CASCADE;
DROP TABLE IF EXISTS comp_set_prices    CASCADE;
DROP TABLE IF EXISTS reservations       CASCADE;
DROP TABLE IF EXISTS price_suggestions  CASCADE;
DROP TABLE IF EXISTS pms_mappings       CASCADE;
DROP TABLE IF EXISTS monthly_budget     CASCADE;
DROP TABLE IF EXISTS competitors        CASCADE;
DROP TABLE IF EXISTS properties         CASCADE;


-- ──────────────────────────────────────────
-- 1. PROPERTIES  (unità / appartamenti)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS properties (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    kross_unit_id   TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE properties ENABLE ROW LEVEL SECURITY;

CREATE UNIQUE INDEX IF NOT EXISTS properties_user_unit_idx
    ON properties (user_id, kross_unit_id);

CREATE POLICY "properties_own" ON properties
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────
-- 2. RESERVATIONS  (prenotazioni)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reservations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL,
    property_id          UUID REFERENCES properties(id) ON DELETE SET NULL,
    pms_reservation_id   TEXT NOT NULL,
    check_in_date        DATE,
    check_out_date       DATE,
    booking_date         DATE,
    gross_revenue        NUMERIC(12,2) DEFAULT 0,
    commission_amount    NUMERIC(12,2) DEFAULT 0,
    net_revenue          NUMERIC(12,2) DEFAULT 0,
    pm_net               NUMERIC(12,2) DEFAULT 0,
    owner_net            NUMERIC(12,2) DEFAULT 0,
    nights               INTEGER DEFAULT 0,
    lead_time            INTEGER DEFAULT 0,
    status               TEXT,
    channel              TEXT,
    channel_group        TEXT,
    created_at           TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;

CREATE UNIQUE INDEX IF NOT EXISTS reservations_user_pms_idx
    ON reservations (user_id, pms_reservation_id);

CREATE INDEX IF NOT EXISTS reservations_checkin_idx
    ON reservations (user_id, check_in_date);

CREATE POLICY "reservations_own" ON reservations
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────
-- 3. COMPETITORS  (hotel concorrenti)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS competitors (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL,
    name         TEXT NOT NULL,
    booking_url  TEXT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE competitors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "competitors_own" ON competitors
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────
-- 4. COMP_SET_PRICES  (prezzi dei competitor)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comp_set_prices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor_id   UUID NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    stay_date       DATE NOT NULL,
    price           NUMERIC(10,2) DEFAULT 0,
    is_available    BOOLEAN DEFAULT true,
    scraped_at      TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE comp_set_prices ENABLE ROW LEVEL SECURITY;

CREATE UNIQUE INDEX IF NOT EXISTS comp_prices_comp_date_idx
    ON comp_set_prices (competitor_id, stay_date);

-- RLS tramite join con competitors (owner check indiretto)
CREATE POLICY "comp_prices_own" ON comp_set_prices
    FOR ALL TO authenticated
    USING (
        competitor_id IN (
            SELECT id FROM competitors WHERE user_id = auth.uid()
        )
    )
    WITH CHECK (
        competitor_id IN (
            SELECT id FROM competitors WHERE user_id = auth.uid()
        )
    );


-- ──────────────────────────────────────────
-- 5. MONTHLY_BUDGET  (target mensili)
-- ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS monthly_budget (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            UUID NOT NULL,
    year               INTEGER NOT NULL,
    month              INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    target_revenue     NUMERIC(12,2) DEFAULT 0,
    target_occupancy   NUMERIC(5,2)  DEFAULT 0,
    target_adr         NUMERIC(10,2) DEFAULT 0,
    notes              TEXT,
    created_at         TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE monthly_budget ENABLE ROW LEVEL SECURITY;

CREATE UNIQUE INDEX IF NOT EXISTS budget_user_year_month_idx
    ON monthly_budget (user_id, year, month);

CREATE POLICY "budget_own" ON monthly_budget
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────
-- 6. FIXED_COSTS  (costi fissi per proprietà)
-- ──────────────────────────────────────────
-- Storicizzati: valid_to NULL = attivo, altrimenti è scaduto.
-- Categorie tipiche: Affitto, Internet, Assicurazione, ecc.
-- frequency: 'monthly' | 'yearly'
CREATE TABLE IF NOT EXISTS fixed_costs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL,
    property_id  UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    category     TEXT NOT NULL,
    amount       NUMERIC(10,2) NOT NULL,
    frequency    TEXT NOT NULL CHECK (frequency IN ('monthly', 'yearly')),
    valid_from   DATE NOT NULL,
    valid_to     DATE,
    created_at   TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE fixed_costs ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS fixed_costs_property_active_idx
    ON fixed_costs (property_id) WHERE valid_to IS NULL;

CREATE POLICY "fixed_costs_own" ON fixed_costs
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────
-- 7. VARIABLE_COSTS  (costi variabili per proprietà)
-- ──────────────────────────────────────────
-- Storicizzati: valid_to NULL = attivo.
-- cost_type: 'cleaning' | 'laundry' | 'amenities' | 'other'
-- basis:     'per_booking' | 'per_night' | 'per_guest'
-- channel_name: NULL = si applica a tutti i canali
CREATE TABLE IF NOT EXISTS variable_costs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL,
    property_id   UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    cost_type     TEXT NOT NULL CHECK (cost_type IN ('cleaning', 'laundry', 'amenities', 'other')),
    channel_name  TEXT,
    value         NUMERIC(10,2) NOT NULL,
    basis         TEXT NOT NULL CHECK (basis IN ('per_booking', 'per_night', 'per_guest')),
    valid_from    DATE NOT NULL,
    valid_to      DATE,
    created_at    TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE variable_costs ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS variable_costs_property_active_idx
    ON variable_costs (property_id) WHERE valid_to IS NULL;

CREATE POLICY "variable_costs_own" ON variable_costs
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────
-- 8. PRICE_SUGGESTIONS  (suggerimenti prezzi + workflow approvazione)
-- ──────────────────────────────────────────
-- status: 'pending' | 'approved' | 'rejected'
CREATE TABLE IF NOT EXISTS price_suggestions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID NOT NULL,
    property_name         TEXT NOT NULL,
    date_from             DATE NOT NULL,
    date_to               DATE NOT NULL,
    current_price         NUMERIC(10,2),
    suggested_price       NUMERIC(10,2),
    scenario              TEXT,
    reason                TEXT,
    bottom_rate_snapshot  NUMERIC(10,2) DEFAULT 0,
    status                TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    decided_at            TIMESTAMPTZ,
    created_at            TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE price_suggestions ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS price_sug_user_status_idx
    ON price_suggestions (user_id, status);

CREATE POLICY "price_suggestions_own" ON price_suggestions
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- ──────────────────────────────────────────
-- 9. PMS_MAPPINGS  (mapping colonne per PMS generici)
-- ──────────────────────────────────────────
-- mapping: JSONB con struttura {internal_col: raw_col_name}
CREATE TABLE IF NOT EXISTS pms_mappings (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL,
    pms_name    TEXT NOT NULL,
    mapping     JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE pms_mappings ENABLE ROW LEVEL SECURITY;

CREATE UNIQUE INDEX IF NOT EXISTS pms_mappings_user_pms_idx
    ON pms_mappings (user_id, pms_name);

CREATE POLICY "pms_mappings_own" ON pms_mappings
    FOR ALL TO authenticated
    USING  (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
