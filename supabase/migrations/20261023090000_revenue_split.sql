-- =====================================================================
-- Ripartizione dei ricavi PM / proprietario per proprietà (con storico in property_settings)
--   split_mode      'pms'     → usa Quota PM / Quota Proprietario importate dal PMS
--                   'percent' → calcola le quote con le percentuali qui sotto
--   pm_pct, owner_pct  percentuali indipendenti (la somma può essere < 100: il resto è "non ripartito")
--   split_basis     'net_ota' → (addebito soggiorno − commissioni OTA)
--                   'gross'   → addebito soggiorno
--   cleaning_fee_to 'pm' | 'owner' | 'split' (quota pulizie ripartita con le stesse percentuali)
-- =====================================================================
alter table public.property_settings
    add column split_mode      text not null default 'pms'     check (split_mode in ('pms', 'percent')),
    add column pm_pct          numeric(5,2)                    check (pm_pct between 0 and 100),
    add column owner_pct       numeric(5,2)                    check (owner_pct between 0 and 100),
    add column split_basis     text not null default 'net_ota' check (split_basis in ('net_ota', 'gross')),
    add column cleaning_fee_to text not null default 'pm'      check (cleaning_fee_to in ('pm', 'owner', 'split'));

alter table public.property_settings
    add constraint property_settings_split_pct_check
    check (split_mode = 'pms' or (pm_pct is not null and owner_pct is not null and pm_pct + owner_pct <= 100));
