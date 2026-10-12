"""
Accesso dati Rate Labs (schema: supabase/migrations/).
Tutte le query passano da qui. Ogni funzione riceve il client Supabase e filtra per tenant_id
(la RLS lo garantisce comunque; il filtro esplicito serve agli utenti con più tenant).
"""
import datetime
import pandas as pd

PAGE_SIZE = 1000  # limite righe per richiesta di PostgREST

FIXED_BASES    = ('monthly', 'yearly')
VARIABLE_BASES = ('per_booking', 'per_night', 'per_guest')
UTILITY_BASIS  = 'period_total'


def fetch_all(build_query):
    """Legge tutte le righe paginando. build_query() deve restituire una query nuova a ogni chiamata."""
    rows, start = [], 0
    while True:
        res = build_query().range(start, start + PAGE_SIZE - 1).execute()
        rows.extend(res.data or [])
        if not res.data or len(res.data) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


# ──────────────────────────────────────────
# TENANT
# ──────────────────────────────────────────
def load_user_tenants(client, user_id):
    """[{'tenant_id', 'name', 'role'}] dei tenant di cui l'utente è membro."""
    res = client.table('tenant_members').select('tenant_id, role, tenants(name)').eq('user_id', user_id).execute()
    return [
        {'tenant_id': r['tenant_id'], 'role': r['role'], 'name': (r.get('tenants') or {}).get('name', '—')}
        for r in (res.data or [])
    ]


# ──────────────────────────────────────────
# PROPERTIES
# ──────────────────────────────────────────
def load_properties(client, tenant_id, active_only=True):
    q = lambda: (client.table('properties').select('id, name, external_id, units, segment, is_active')
                 .eq('tenant_id', tenant_id).order('name'))
    df = pd.DataFrame(fetch_all(q))
    if df.empty:
        return pd.DataFrame(columns=['id', 'name', 'external_id', 'units', 'segment', 'is_active'])
    return df[df['is_active']].reset_index(drop=True) if active_only else df


def ensure_properties(client, tenant_id, external_ids):
    """Crea le proprietà mancanti (senza toccare quelle esistenti). Ritorna {external_id: property_id}."""
    external_ids = [str(x) for x in external_ids]
    if not external_ids:
        return {}
    client.table('properties').upsert(
        [{"tenant_id": tenant_id, "external_id": x, "name": x} for x in external_ids],
        on_conflict='tenant_id,external_id', ignore_duplicates=True
    ).execute()
    res = client.table('properties').select('id, external_id') \
        .eq('tenant_id', tenant_id).in_('external_id', external_ids).execute()
    return {r['external_id']: r['id'] for r in res.data}


# ──────────────────────────────────────────
# RESERVATIONS
# ──────────────────────────────────────────
def load_reservations(client, tenant_id, property_id=None):
    """Prenotazioni con unit_id = nome della proprietà (colonna usata dalla dashboard)."""
    def q():
        query = client.table('reservations').select('*').eq('tenant_id', tenant_id)
        return query.eq('property_id', property_id) if property_id else query
    df = pd.DataFrame(fetch_all(q))
    if df.empty:
        return df

    props = load_properties(client, tenant_id, active_only=False)
    df['unit_id'] = df['property_id'].map(dict(zip(props['id'], props['name']))).fillna('Sconosciuto')

    for col in ['check_in_date', 'check_out_date', 'booking_date', 'cancellation_date']:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    for col in ['gross_revenue', 'commission_amount', 'net_revenue', 'pm_net', 'owner_net', 'nights', 'lead_time']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


# ──────────────────────────────────────────
# SOURCE MAPPINGS
# ──────────────────────────────────────────
def load_source_mapping(client, tenant_id, source_name, source_type='pms'):
    res = client.table('source_mappings').select('id, mapping').eq('tenant_id', tenant_id) \
        .eq('source_type', source_type).eq('source_name', source_name).execute()
    return res.data[0] if res.data else None


def save_source_mapping(client, tenant_id, source_name, mapping, source_type='pms'):
    res = client.table('source_mappings').upsert(
        {"tenant_id": tenant_id, "source_type": source_type, "source_name": source_name, "mapping": mapping},
        on_conflict='tenant_id,source_type,source_name'
    ).execute()
    return res.data[0]['id']


# ──────────────────────────────────────────
# COSTI (property_costs con storico: valid_to NULL = vigente)
# ──────────────────────────────────────────
def load_costs(client, tenant_id, property_id=None):
    """
    Ritorna (df_fix, df_var, df_util) nei formati usati da Bottom Rate ed etl_metrics:
      df_fix : id, category, amount, frequency, valid_from, valid_to   (solo vigenti)
      df_var : id, cost_type, value, basis, channel_name, valid_from, valid_to (solo vigenti)
      df_util: id, category, amount, period_from, period_to, notes     (tutte le bollette)
    """
    def q():
        query = client.table('property_costs').select('*').eq('tenant_id', tenant_id)
        return query.eq('property_id', property_id) if property_id else query
    df = pd.DataFrame(fetch_all(q))
    if df.empty:
        df = pd.DataFrame(columns=['id', 'property_id', 'category', 'basis', 'amount', 'channel', 'valid_from', 'valid_to', 'notes'])
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    active = df['valid_to'].isna()

    df_fix = df[active & df['basis'].isin(FIXED_BASES)].rename(columns={'basis': 'frequency'})
    df_var = df[active & df['basis'].isin(VARIABLE_BASES)].rename(
        columns={'category': 'cost_type', 'amount': 'value', 'channel': 'channel_name'})
    df_util = df[df['basis'] == UTILITY_BASIS].rename(columns={'valid_from': 'period_from', 'valid_to': 'period_to'})
    return (df_fix.reset_index(drop=True), df_var.reset_index(drop=True),
            df_util.sort_values('period_to', ascending=False).reset_index(drop=True))


def save_recurring_cost(client, tenant_id, property_id, category, basis, amount, valid_from, channel=None):
    """
    Costo fisso (monthly/yearly) o variabile (per_booking/per_night/per_guest) con storico:
    il costo vigente della stessa categoria (e canale, per i variabili) viene chiuso al giorno prima.
    """
    group = FIXED_BASES if basis in FIXED_BASES else VARIABLE_BASES
    channel = str(channel).strip() if channel and str(channel).strip() else None

    query = client.table('property_costs').select('id, valid_from').eq('tenant_id', tenant_id) \
        .eq('property_id', property_id).eq('category', category).in_('basis', list(group)).is_('valid_to', 'null')
    query = query.eq('channel', channel) if channel else query.is_('channel', 'null')
    current = query.execute().data

    for row in current:
        if datetime.date.fromisoformat(row['valid_from']) >= valid_from:
            # stesso giorno (o retrodatato): correggi il record invece di storicizzarlo
            client.table('property_costs').update(
                {"basis": basis, "amount": float(amount), "valid_from": valid_from.isoformat()}
            ).eq('id', row['id']).execute()
            return
        client.table('property_costs').update(
            {"valid_to": (valid_from - datetime.timedelta(days=1)).isoformat()}
        ).eq('id', row['id']).execute()

    client.table('property_costs').insert({
        "tenant_id": tenant_id, "property_id": property_id, "category": category, "basis": basis,
        "amount": float(amount), "channel": channel, "valid_from": valid_from.isoformat(),
    }).execute()


def save_utility_bill(client, tenant_id, property_id, category, amount, period_from, period_to, notes=None):
    client.table('property_costs').insert({
        "tenant_id": tenant_id, "property_id": property_id, "category": category, "basis": UTILITY_BASIS,
        "amount": float(amount), "valid_from": period_from.isoformat(), "valid_to": period_to.isoformat(),
        "notes": notes or None,
    }).execute()


def delete_cost(client, cost_id):
    client.table('property_costs').delete().eq('id', cost_id).execute()


# ──────────────────────────────────────────
# PROPERTY SETTINGS (con storico)
# ──────────────────────────────────────────
def load_current_settings(client, tenant_id, property_id):
    res = client.table('property_settings').select('*').eq('tenant_id', tenant_id) \
        .eq('property_id', property_id).is_('valid_to', 'null').execute()
    return res.data[0] if res.data else None


def update_settings(client, tenant_id, property_id, changes, valid_from=None):
    """Applica `changes` creando una nuova versione (la vigente viene chiusa al giorno prima)."""
    valid_from = valid_from or datetime.date.today()
    current = load_current_settings(client, tenant_id, property_id)

    if current and datetime.date.fromisoformat(current['valid_from']) >= valid_from:
        client.table('property_settings').update(changes).eq('id', current['id']).execute()
        return

    new_row = {"tenant_id": tenant_id, "property_id": property_id, "valid_from": valid_from.isoformat()}
    if current:
        for key in ('min_stay', 'cancellation_policy', 'cleaning_fee', 'promos', 'notes'):
            new_row[key] = current.get(key)
        client.table('property_settings').update(
            {"valid_to": (valid_from - datetime.timedelta(days=1)).isoformat()}
        ).eq('id', current['id']).execute()
    new_row.update(changes)
    client.table('property_settings').insert(new_row).execute()


# ──────────────────────────────────────────
# COMP SET
# ──────────────────────────────────────────
def load_competitors(client, tenant_id):
    res = client.table('competitors').select('id, name, url, platform, property_id, is_active') \
        .eq('tenant_id', tenant_id).order('name').execute()
    return res.data or []


def add_competitor(client, tenant_id, property_id, name, url, platform='booking'):
    client.table('competitors').insert({
        "tenant_id": tenant_id, "property_id": property_id, "name": name, "url": url, "platform": platform,
    }).execute()


def delete_competitor(client, competitor_id):
    client.table('competitors').delete().eq('id', competitor_id).execute()


def load_market_snapshots(client, tenant_id):
    """Ultimo prezzo rilevato per competitor e data di soggiorno: stay_date, price, is_available, name."""
    comps = load_competitors(client, tenant_id)
    if not comps:
        return pd.DataFrame()
    q = lambda: (client.table('market_snapshots').select('competitor_id, stay_date, captured_on, price, is_available')
                 .eq('tenant_id', tenant_id).not_.is_('competitor_id', 'null'))
    df = pd.DataFrame(fetch_all(q))
    if df.empty:
        return df
    df = df.sort_values('captured_on').drop_duplicates(['competitor_id', 'stay_date'], keep='last')
    df['name'] = df['competitor_id'].map({c['id']: c['name'] for c in comps})
    df['stay_date'] = pd.to_datetime(df['stay_date'])
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    return df.sort_values('stay_date').reset_index(drop=True)
