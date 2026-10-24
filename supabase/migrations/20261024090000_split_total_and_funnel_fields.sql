-- =====================================================================
-- 1) Ripartizione PM / proprietario: nuova base 'total' (soggiorno + quota pulizie)
-- 2) funnel_metrics: campi dei report di Booking (con benchmark competitor) e Airbnb
-- =====================================================================

-- 1. split_basis: 'total' | 'gross' | 'net_ota'
alter table public.property_settings drop constraint property_settings_split_basis_check;
alter table public.property_settings
    add constraint property_settings_split_basis_check check (split_basis in ('total', 'gross', 'net_ota'));


-- 2. funnel_metrics
--   Booking  "Prenotazioni effettuate tramite ricerca":
--     search_impressions = Presenza nelle ricerche, ctr_pct = % ha cliccato sulla pagina,
--     conversion_pct = % ha prenotato la struttura, comp_* = stessi valori dei Competitor diretti,
--     market_demand_change_pct = variazione della domanda per la destinazione (Dati sulla domanda)
--   Airbnb  "Conversione" / "Visualizzazioni":
--     search_impressions = Impressioni nella prima pagina di ricerca, listing_views = Visualizzazioni pagina,
--     first_page_pct = Tasso di impressioni nella prima pagina, ctr_pct = Conversione ricerca-alloggio,
--     conversion_pct = Conversione annuncio-prenotazione, overall_conversion_pct = Conversione globale
alter table public.funnel_metrics
    add column comp_search_impressions  integer,
    add column comp_ctr_pct             numeric(6,3),
    add column comp_conversion_pct      numeric(6,3),
    add column first_page_pct           numeric(6,3),
    add column overall_conversion_pct   numeric(6,3),
    add column market_demand_change_pct numeric(7,2),
    add column notes                    text;
