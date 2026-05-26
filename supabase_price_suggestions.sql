-- ============================================================
-- KrossBooking Pace Pro — Price Suggestions Table (Phase A)
-- Run in Supabase SQL Editor before using the "Prezzi" tab
-- ============================================================

CREATE TABLE IF NOT EXISTS price_suggestions (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id         TEXT NOT NULL,
  property_name   TEXT NOT NULL,
  date_from       DATE NOT NULL,
  date_to         DATE NOT NULL,
  current_price   NUMERIC,
  suggested_price NUMERIC NOT NULL,
  scenario        TEXT NOT NULL,          -- 'Conservativo', 'Moderato', 'Aggressivo'
  reason          TEXT,
  bottom_rate_snapshot NUMERIC,           -- snapshot del Bottom Rate al momento della creazione
  status          TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  decided_at      TIMESTAMPTZ
);

-- Index for fast per-user queries
CREATE INDEX IF NOT EXISTS idx_price_suggestions_user ON price_suggestions(user_id, status);

-- RLS (enable after switching to anon key)
ALTER TABLE price_suggestions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "User can access own price_suggestions" ON price_suggestions;
CREATE POLICY "User can access own price_suggestions"
  ON price_suggestions FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);
