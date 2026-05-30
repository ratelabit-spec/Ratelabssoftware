-- ============================================================
-- KrossBooking Pace Pro — PMS Column Mappings Table
-- Run in Supabase SQL Editor before using "Altro PMS" upload
-- ============================================================

CREATE TABLE IF NOT EXISTS pms_mappings (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     TEXT NOT NULL,
  pms_name    TEXT NOT NULL,
  mapping     JSONB NOT NULL,  -- {"check_in_date": "Arrival", "gross_revenue": "Total", ...}
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, pms_name)
);

CREATE INDEX IF NOT EXISTS idx_pms_mappings_user ON pms_mappings(user_id);

-- RLS
ALTER TABLE pms_mappings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "User can access own pms_mappings" ON pms_mappings;
CREATE POLICY "User can access own pms_mappings"
  ON pms_mappings FOR ALL
  USING (user_id::text = auth.uid()::text)
  WITH CHECK (user_id::text = auth.uid()::text);
