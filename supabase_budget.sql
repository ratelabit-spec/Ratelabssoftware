-- ============================================================
-- KrossBooking Pace Pro — Monthly Budget Table
-- Run in Supabase SQL Editor
-- ============================================================

CREATE TABLE IF NOT EXISTS monthly_budget (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id          TEXT NOT NULL,
  year             INT  NOT NULL,
  month            INT  NOT NULL,
  target_revenue   NUMERIC DEFAULT 0,
  target_occupancy NUMERIC DEFAULT 0,   -- percentuale 0-100
  target_adr       NUMERIC DEFAULT 0,
  notes            TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_budget_user_year ON monthly_budget(user_id, year);

ALTER TABLE monthly_budget ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "User can access own monthly_budget" ON monthly_budget;
CREATE POLICY "User can access own monthly_budget"
  ON monthly_budget FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);
