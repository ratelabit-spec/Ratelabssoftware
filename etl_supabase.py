import math
import pandas as pd
from supabase import Client

from db import ensure_properties

CHUNK_SIZE = 500


def _date_str(value):
    return value.strftime('%Y-%m-%d') if pd.notnull(value) else None


def _int_or_none(value):
    return int(value) if pd.notnull(value) else None


def upsert_reservations(supabase_client: Client, df: pd.DataFrame, tenant_id: str, user_id: str,
                        file_name=None, source_mapping_id=None, rows_total=None, on_progress=None) -> int:
    """
    Sincronizza proprietà e prenotazioni normalizzate (Internal Standard Data Model) su Supabase
    e registra il caricamento in data_imports.
    df deve contenere 'pms_reservation_id' e le colonne di adapter_generic.INTERNAL_COLUMNS.
    on_progress(done_chunks, total_chunks) viene chiamato dopo ogni lotto caricato.
    Ritorna il numero di prenotazioni sincronizzate.
    """
    prop_map = ensure_properties(supabase_client, tenant_id, df['unit_id'].dropna().astype(str).unique())

    import_id = supabase_client.table('data_imports').insert({
        "tenant_id":         tenant_id,
        "source_mapping_id": source_mapping_id,
        "file_name":         file_name,
        "rows_total":        rows_total if rows_total is not None else len(df),
        "uploaded_by":       user_id,
    }).execute().data[0]['id']

    records = []
    for _, row in df.iterrows():
        status = str(row['status'])
        cancellation_date = row.get('cancellation_date')
        records.append({
            "tenant_id":          tenant_id,
            "property_id":        prop_map[str(row['unit_id'])],
            "import_id":          import_id,
            "pms_reservation_id": str(row['pms_reservation_id']),
            "check_in_date":      _date_str(row['check_in_date']),
            "check_out_date":     _date_str(row.get('check_out_date')),
            "booking_date":       _date_str(row.get('booking_date')),
            "cancellation_date":  _date_str(cancellation_date),
            "status":             status,
            "is_cancelled":       'cancel' in status.strip().lower() or pd.notnull(cancellation_date),
            "channel":            str(row.get('channel', '') or ''),
            "channel_group":      str(row['channel_group']) if pd.notnull(row.get('channel_group')) else 'Altro',
            "nights":             _int_or_none(row['nights']) or 0,
            "lead_time":          _int_or_none(row['lead_time']),
            "gross_revenue":      float(row['gross_revenue']),
            "commission_amount":  float(row['commission_amount']),
            "net_revenue":        float(row['net_revenue']),
            "pm_net":             float(row['pm_net']) if pd.notnull(row.get('pm_net')) else None,
            "owner_net":          float(row['owner_net']) if pd.notnull(row.get('owner_net')) else None,
        })

    total_chunks = math.ceil(len(records) / CHUNK_SIZE)
    for i in range(total_chunks):
        chunk = records[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
        supabase_client.table('reservations').upsert(chunk, on_conflict='tenant_id,pms_reservation_id').execute()
        if on_progress:
            on_progress(i + 1, total_chunks)

    supabase_client.table('data_imports').update({"rows_loaded": len(records)}).eq('id', import_id).execute()
    return len(records)
