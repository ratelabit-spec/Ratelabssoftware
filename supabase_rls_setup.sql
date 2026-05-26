-- ============================================================
-- KrossBooking Pace Pro — Row Level Security Setup
-- Run this ONCE in Supabase SQL Editor after switching to anon key
-- ============================================================

-- 1. Enable RLS on all tables
ALTER TABLE reservations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties        ENABLE ROW LEVEL SECURITY;
ALTER TABLE fixed_costs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE variable_costs    ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitors       ENABLE ROW LEVEL SECURITY;
ALTER TABLE comp_set_prices   ENABLE ROW LEVEL SECURITY;

-- 2. Drop any existing policies (safe to run multiple times)
DROP POLICY IF EXISTS "User can access own reservations"    ON reservations;
DROP POLICY IF EXISTS "User can access own properties"      ON properties;
DROP POLICY IF EXISTS "User can access own fixed_costs"     ON fixed_costs;
DROP POLICY IF EXISTS "User can access own variable_costs"  ON variable_costs;
DROP POLICY IF EXISTS "User can access own competitors"     ON competitors;
DROP POLICY IF EXISTS "User can access own comp_set_prices" ON comp_set_prices;

-- 3. Create policies — each user sees only their own rows
-- auth.uid() returns the UUID of the currently logged-in user

CREATE POLICY "User can access own reservations"
  ON reservations FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY "User can access own properties"
  ON properties FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY "User can access own fixed_costs"
  ON fixed_costs FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY "User can access own variable_costs"
  ON variable_costs FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY "User can access own competitors"
  ON competitors FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);

-- comp_set_prices joins through competitors, so policy uses subquery
CREATE POLICY "User can access own comp_set_prices"
  ON comp_set_prices FOR ALL
  USING (
    competitor_id IN (
      SELECT id FROM competitors WHERE user_id::text = auth.uid()::text
    )
  );

-- ============================================================
-- AFTER running this SQL:
-- 1. Go to Supabase Dashboard > Settings > API
-- 2. Copy the "anon public" key
-- 3. Replace SUPABASE_KEY in .streamlit/secrets.toml with the anon key
-- 4. Delete the service_role key from secrets.toml
-- ============================================================
