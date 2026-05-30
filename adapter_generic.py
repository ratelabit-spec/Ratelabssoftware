import pandas as pd
import hashlib

# Internal model columns required by the app and Supabase
INTERNAL_COLUMNS = [
    'pms_reservation_id', 'check_in_date', 'check_out_date', 'booking_date',
    'gross_revenue', 'commission_amount', 'net_revenue', 'pm_net', 'owner_net',
    'nights', 'lead_time', 'channel_group', 'status', 'unit_id'
]

# Required: upload will fail if these can't be resolved
REQUIRED_FIELDS = ['check_in_date', 'unit_id', 'gross_revenue', 'channel_group', 'status']

FIELD_LABELS = {
    'check_in_date':        'Data Check-in *',
    'unit_id':              'Nome Camera / Appartamento *',
    'gross_revenue':        'Revenue Lordo (€) *',
    'channel_group':        'Canale / OTA *',
    'status':               'Stato Prenotazione *',
    'pms_reservation_id':   'ID Prenotazione (generato se vuoto)',
    'check_out_date':       'Data Check-out',
    'booking_date':         'Data Prenotazione',
    'commission_amount':    'Commissione OTA (€)',
    'nights':               'Notti (se non c\'è Check-out)',
    'lead_time':            'Lead Time (giorni)',
    'net_revenue':          'Revenue Netto (€)',
    'pm_net':               'Netto PM (€)',
    'owner_net':            'Netto Proprietario (€)',
}


def _to_date(series):
    return pd.to_datetime(series, errors='coerce', dayfirst=True)


def apply_mapping(df_raw: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    mapping: {internal_col: raw_col_name_or_None}
    Returns a normalized DataFrame with INTERNAL_COLUMNS.
    Derives missing columns where possible.
    """
    df = pd.DataFrame(index=df_raw.index)

    # 1. Apply direct mapping
    for internal_col in INTERNAL_COLUMNS:
        raw_col = mapping.get(internal_col)
        if raw_col and raw_col in df_raw.columns:
            df[internal_col] = df_raw[raw_col]
        else:
            df[internal_col] = None

    # 2. Convert dates
    for col in ['check_in_date', 'check_out_date', 'booking_date']:
        df[col] = _to_date(df[col])

    # 3. Numeric coercion
    for col in ['gross_revenue', 'commission_amount', 'net_revenue', 'pm_net', 'owner_net', 'nights', 'lead_time']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 4. Derive nights from dates if not mapped
    if df['nights'].isna().all() and df['check_out_date'].notna().any():
        df['nights'] = (df['check_out_date'] - df['check_in_date']).dt.days

    # 5. Derive lead_time from booking_date if not mapped
    if df['lead_time'].isna().all() and df['booking_date'].notna().any():
        df['lead_time'] = (df['check_in_date'] - df['booking_date']).dt.days

    # 6. Fill commission default
    df['commission_amount'] = df['commission_amount'].fillna(0.0)

    # 7. Derive net_revenue
    if df['net_revenue'].isna().all():
        df['net_revenue'] = df['gross_revenue'].fillna(0) - df['commission_amount']

    # 8. Derive pm_net and owner_net
    if df['pm_net'].isna().all():
        df['pm_net'] = df['net_revenue']
    if df['owner_net'].isna().all():
        df['owner_net'] = df['pm_net']

    # 9. Fill remaining numeric defaults
    for col in ['gross_revenue', 'net_revenue', 'pm_net', 'owner_net', 'nights', 'lead_time']:
        df[col] = df[col].fillna(0)

    # 10. Generate pms_reservation_id if not mapped
    if df['pms_reservation_id'].isna().all():
        def _gen_id(row):
            raw = f"{row['unit_id']}_{row['check_in_date']}_{row['gross_revenue']:.2f}"
            return hashlib.md5(raw.encode()).hexdigest()[:16]
        df['pms_reservation_id'] = df.apply(_gen_id, axis=1)
    else:
        df['pms_reservation_id'] = df['pms_reservation_id'].astype(str)

    # 11. String columns defaults
    df['channel_group'] = df['channel_group'].fillna('Sconosciuto').astype(str)
    df['status']        = df['status'].fillna('confirmed').astype(str)
    df['unit_id']       = df['unit_id'].fillna('Sconosciuto').astype(str)

    # 12. Drop rows with no check_in_date or no revenue (unfixable)
    df = df[df['check_in_date'].notna() & (df['gross_revenue'] > 0)].reset_index(drop=True)

    return df[INTERNAL_COLUMNS]


def validate_mapping(mapping: dict) -> list[str]:
    """Returns list of error messages. Empty list = OK."""
    errors = []
    for field in REQUIRED_FIELDS:
        if not mapping.get(field):
            errors.append(f"Campo obbligatorio non mappato: **{FIELD_LABELS[field]}**")
    return errors
