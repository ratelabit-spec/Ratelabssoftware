import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import plotly.graph_objects as go
import datetime
import math
from datetime import date
from supabase import create_client, Client
import urllib.parse
import re
from apify_client import ApifyClient
from adapter_krossbooking import load_and_clean_krossbooking
from adapter_generic import apply_mapping, validate_mapping, FIELD_LABELS, REQUIRED_FIELDS
from etl_costs import update_or_insert_cost
from etl_metrics import calculate_property_margins

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Rate Labs RMS", page_icon="📊", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── GLOBAL ── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* ── SFONDO PRINCIPALE ── */
.main { background: #F1F5F9 !important; }
.block-container { padding-top: 1.8rem !important; }

/* ── SIDEBAR NAVY SCURO ── */
[data-testid="stSidebar"] {
    background: #1C2438 !important;
    border-right: 1px solid #2A3450;
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] small { color: #CBD5E1 !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #FFFFFF !important; }
[data-testid="stSidebar"] hr { border-color: #2D3A52 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: #2D3A52 !important;
    color: #E2E8F0 !important;
    border: 1px solid #3D4F6E !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stDateInput input,
[data-testid="stSidebar"] .stMultiSelect > div > div {
    background: #243049 !important;
    border-color: #3D4F6E !important;
    color: #E2E8F0 !important;
    border-radius: 8px !important;
}

/* ── METRIC CARDS ── */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border-radius: 14px !important;
    padding: 1.1rem 1.25rem !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 2px 8px rgba(15,23,42,0.06), 0 0 0 1px rgba(15,23,42,0.03) !important;
}
[data-testid="stMetricLabel"] > div {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    color: #64748B !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}
[data-testid="stMetricValue"] > div {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    line-height: 1.15 !important;
}
[data-testid="stMetricDelta"] svg { display: none !important; }
[data-testid="stMetricDelta"] > div {
    font-size: 0.82rem !important;
    font-weight: 700 !important;
}

/* ── TAB — pill style ── */
.stTabs [data-baseweb="tab-list"] {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 5px;
    gap: 3px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 8px 18px !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
    color: #64748B !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover { background: #F1F5F9 !important; color: #1E293B !important; }
.stTabs [aria-selected="true"][data-baseweb="tab"] {
    background: #1E6FD9 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(30,111,217,0.3);
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ── BUTTONS ── */
.stButton > button {
    border-radius: 9px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    transition: all 0.18s ease !important;
}
.stButton > button[kind="primary"] {
    background: #1E6FD9 !important;
    border: none !important;
    box-shadow: 0 2px 8px rgba(30,111,217,0.35) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1558B0 !important;
    box-shadow: 0 4px 14px rgba(30,111,217,0.45) !important;
    transform: translateY(-1px);
}
.stButton > button:not([kind="primary"]) { border: 1px solid #E2E8F0 !important; }

/* ── ALERTS ── */
[data-testid="stAlert"] { border-radius: 10px !important; border-left-width: 4px !important; }

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }

/* ── EXPANDER ── */
details summary {
    background: #FFFFFF !important;
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    font-weight: 500 !important;
    padding: 0.7rem 1rem !important;
}

/* ── FORM / INPUT ── */
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox > div > div {
    border-radius: 8px !important;
    border-color: #E2E8F0 !important;
}
.stForm { background: #FFFFFF; border-radius: 14px; padding: 1.2rem; border: 1px solid #E2E8F0; }

/* ── TYPOGRAPHY ── */
h1 { font-weight: 700 !important; color: #0F172A !important; letter-spacing: -0.02em !important; }
h2 { font-weight: 600 !important; color: #1E293B !important; letter-spacing: -0.01em !important; }
h3 { font-weight: 600 !important; color: #334155 !important; }
hr { border-color: #E2E8F0 !important; margin: 1.5rem 0 !important; }
[data-testid="stCaptionContainer"] p { color: #64748B !important; font-size: 0.78rem !important; }

/* ── RL-TABLE (tabelle HTML custom) ── */
.rl-table-wrap {
    background: #FFFFFF;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 8px rgba(15,23,42,0.06);
    overflow: hidden;
    margin: 0.5rem 0 1rem 0;
}
.rl-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Inter', sans-serif;
    font-size: 0.84rem;
    color: #1E293B;
}
.rl-table thead tr { background: #1C2438; }
.rl-table thead th {
    padding: 10px 16px;
    font-weight: 600;
    font-size: 0.69rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94A3B8;
    text-align: left;
    white-space: nowrap;
}
.rl-table thead th.rnum { text-align: right; }
.rl-table tbody tr:nth-child(even) { background: #F8FAFC; }
.rl-table tbody tr:hover { background: #EFF6FF; transition: background 0.12s; }
.rl-table tbody td {
    padding: 9px 16px;
    border-bottom: 1px solid #F1F5F9;
    font-size: 0.84rem;
}
.rl-table tbody tr:last-child td { border-bottom: none; }
.rl-table td.rnum { text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }
.rl-table td.pos { color: #16A34A !important; font-weight: 700; }
.rl-table td.neg { color: #DC2626 !important; font-weight: 700; }
.rl-table td.neu { color: #94A3B8 !important; font-weight: 600; }
.rl-table td.warn { color: #D97706 !important; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# --- CONNESSIONE SUPABASE & API KEY ---
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    API_KEY = None

if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')

@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("⚠️ Configura i segreti di Supabase in .streamlit/secrets.toml")
    st.stop()

# --- COSTANTI ---
MESI_IT = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
           'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']

# --- PALETTE & TEMA GRAFICI ---
C_CY   = "#1E6FD9"          # Blu — Anno Corrente
C_STLY = "#94A3B8"          # Grigio ardesia — STLY
C_POS  = "#10B981"          # Verde — valori positivi
C_NEG  = "#EF4444"          # Rosso — alert / negativi
C_WARN = "#F59E0B"          # Ambra — warning
C_TEAL = "#0EA5E9"          # Azzurro — accento
_BG    = "rgba(0,0,0,0)"    # Sfondo trasparente
_GRID  = "#E2E8F0"          # Grigio griglia

def _fig_layout(**kw):
    base = dict(
        plot_bgcolor=_BG, paper_bgcolor=_BG,
        font=dict(family="sans-serif", size=13, color="#1A202C"),
        margin=dict(t=50, b=20, l=10, r=10),
        hoverlabel=dict(bgcolor="white", font_size=13, bordercolor="#E2E8F0"),
    )
    base.update(kw)
    return base

# =====================================================
# FUNZIONI DI CARICAMENTO DAL CLOUD
# =====================================================

@st.cache_data
def load_data_from_supabase(user_id):
    try:
        response = supabase.table("reservations").select("*, properties(kross_unit_id)").eq("user_id", user_id).execute()
    except Exception as e:
        st.error(f"❌ Impossibile connettersi a Supabase: {e}\n\nControlla che l'URL e la chiave in `.streamlit/secrets.toml` siano corretti e che il progetto Supabase esista.")
        st.stop()

    if not response.data:
        return pd.DataFrame()

    df = pd.DataFrame(response.data)

    df['unit_id'] = df['properties'].apply(
        lambda x: x['kross_unit_id'] if isinstance(x, dict) and 'kross_unit_id' in x else 'Sconosciuto'
    )

    for col in ['check_in_date', 'check_out_date', 'booking_date']:
        df[col] = pd.to_datetime(df[col], errors='coerce')

    numeric_cols = ['gross_revenue', 'commission_amount', 'net_revenue', 'pm_net', 'owner_net', 'nights', 'lead_time']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df

@st.cache_data(ttl=3600) # Guarda en caché por 1 hora para no saturar Supabase
def load_comp_set_data(user_id):
    # 1. Traer los competidores
    res_comp = supabase.table("competitors").select("id, name").eq("user_id", user_id).execute()
    if not res_comp.data:
        return pd.DataFrame()
    df_comp = pd.DataFrame(res_comp.data)
    
    # 2. Traer los precios de esos competidores
    comp_ids = df_comp['id'].tolist()
    res_prices = supabase.table("comp_set_prices").select("*").in_("competitor_id", comp_ids).execute()
    if not res_prices.data:
        return pd.DataFrame()
    df_prices = pd.DataFrame(res_prices.data)
    
    # 3. Unir las tablas para tener el nombre del hotel junto al precio
    df_final = pd.merge(df_prices, df_comp, left_on="competitor_id", right_on="id")
    df_final['stay_date'] = pd.to_datetime(df_final['stay_date'])
    df_final.sort_values('stay_date', inplace=True)
    
    return df_final

def calcola_kpi(df_otb, df_otb_ly, df_final_ly):
    k = {}
    k['rev'] = df_otb['gross_revenue'].sum()
    k['rev_ly'] = df_otb_ly['gross_revenue'].sum()
    k['var_rev'] = (k['rev'] / k['rev_ly'] - 1) * 100 if k['rev_ly'] > 0 else 0

    k['notti'] = df_otb['nights'].sum()
    k['notti_ly'] = df_otb_ly['nights'].sum()
    k['var_notti'] = (k['notti'] / k['notti_ly'] - 1) * 100 if k['notti_ly'] > 0 else 0

    k['adr'] = k['rev'] / k['notti'] if k['notti'] > 0 else 0
    k['adr_ly'] = k['rev_ly'] / k['notti_ly'] if k['notti_ly'] > 0 else 0
    k['var_adr'] = (k['adr'] / k['adr_ly'] - 1) * 100 if k['adr_ly'] > 0 else 0

    k['los'] = df_otb['nights'].mean() if not df_otb.empty else 0
    k['los_ly'] = df_otb_ly['nights'].mean() if not df_otb_ly.empty else 0
    k['var_los'] = (k['los'] / k['los_ly'] - 1) * 100 if k['los_ly'] > 0 else 0

    k['lt'] = df_otb['lead_time'].mean() if not df_otb.empty else 0
    k['lt_ly_final'] = df_final_ly['lead_time'].mean() if not df_final_ly.empty else 0

    k['netto']          = df_otb['pm_net'].sum()
    k['commissioni']    = df_otb['commission_amount'].sum() if 'commission_amount' in df_otb.columns else 0
    k['commissioni_ly'] = df_otb_ly['commission_amount'].sum() if 'commission_amount' in df_otb_ly.columns else 0

    return k


@st.cache_data(ttl=3600)
def load_budget(user_id, year, month):
    res = supabase.table('monthly_budget').select('*') \
        .eq('user_id', user_id).eq('year', year).eq('month', month).execute()
    return res.data[0] if res.data else None

@st.cache_data(ttl=3600)
def load_budget_year(user_id, year):
    res = supabase.table('monthly_budget').select('*') \
        .eq('user_id', user_id).eq('year', year).order('month').execute()
    return res.data if res.data else []

@st.cache_data(ttl=3600)
def load_total_units(user_id):
    """Conta le proprietà registrate — denominatore reale per RevPAR e Bottom Rate."""
    res = supabase.table('properties').select('id').eq('user_id', user_id).execute()
    return len(res.data) if res.data else 0

@st.cache_data(ttl=3600)
def load_portfolio_costs(user_id):
    """Carica costi fissi, variabili e bollette utenze per il Cervello Matematico."""
    res_fix  = supabase.table('fixed_costs').select('*').eq('user_id', user_id).is_('valid_to', 'null').execute()
    res_var  = supabase.table('variable_costs').select('*').eq('user_id', user_id).is_('valid_to', 'null').execute()
    cutoff   = (pd.Timestamp.now() - pd.DateOffset(months=12)).strftime('%Y-%m-%d')
    res_util = supabase.table('utility_bills').select('*').eq('user_id', user_id).gte('period_to', cutoff).execute()
    df_fix  = pd.DataFrame(res_fix.data)  if res_fix.data  else pd.DataFrame(columns=['amount', 'frequency', 'valid_to'])
    df_var  = pd.DataFrame(res_var.data)  if res_var.data  else pd.DataFrame(columns=['value', 'basis', 'valid_to'])
    df_util = pd.DataFrame(res_util.data) if res_util.data else pd.DataFrame(columns=['amount', 'period_from', 'period_to'])
    return df_fix, df_var, df_util


def _run_scraper(user_id, target_date):
    """Esegue lo scraper Apify per tutti i competitor per una data specifica."""
    apify_token = st.secrets.get("APIFY_API_TOKEN")
    if not apify_token:
        st.error("⚠️ APIFY_API_TOKEN non configurato in .streamlit/secrets.toml")
        return

    res = supabase.table("competitors").select("id, name, booking_url").eq("user_id", user_id).execute()
    if not res.data:
        st.warning("Nessun competitor registrato. Aggiungine uno nella sezione 'Gestione Competitor'.")
        return

    checkin_str  = target_date.strftime('%Y-%m-%d')
    checkout_str = (target_date + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    hotel_urls, url_map = [], {}
    for comp in res.data:
        base_url   = comp['booking_url'].split('?')[0]
        hotel_path = urllib.parse.urlparse(base_url).path
        final_url  = (f"{base_url}?checkin={checkin_str}&checkout={checkout_str}"
                      f"&group_adults=2&no_rooms=1&selected_currency=EUR")
        hotel_urls.append({"url": final_url, "method": "GET"})
        url_map[f"{hotel_path}_{checkin_str}"] = {"competitor_id": comp['id'], "stay_date": checkin_str}

    try:
        apify  = ApifyClient(apify_token)
        run    = apify.actor("noraview/booking-price-scraper").call(
            run_input={"hotelUrls": hotel_urls, "includeSoldOut": True, "useApifyProxy": True}
        )
        records = []
        for item in apify.dataset(run["defaultDatasetId"]).iterate_items():
            parsed      = urllib.parse.urlparse(item.get("url", ""))
            params      = urllib.parse.parse_qs(parsed.query)
            checkin_ret = params.get("checkin", [None])[0]
            meta        = url_map.get(f"{parsed.path}_{checkin_ret}")
            if not meta:
                continue
            raw   = item.get("priceAmount") or item.get("price")
            price = 0.0
            if raw:
                try:
                    nums  = re.findall(r"[-+]?\d*\.\d+|\d+", str(raw).replace(",", "."))
                    price = float(nums[0]) if nums else 0.0
                except Exception:
                    pass
            records.append({
                "competitor_id": meta["competitor_id"],
                "stay_date":     meta["stay_date"],
                "price":         price,
                "is_available":  price > 0,
            })

        if records:
            supabase.table("comp_set_prices").upsert(records, on_conflict="competitor_id, stay_date").execute()
            st.cache_data.clear()
            st.success(f"✅ {len(records)} prezzi aggiornati per il {checkin_str}.")
        else:
            st.warning("⚠️ Nessun prezzo trovato — Booking potrebbe aver cambiato struttura.")
    except Exception as e:
        st.error(f"Errore scraper: {e}")


def show_login_page():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("# 📊 Rate Labs RMS")
        st.markdown("### Accesso")
        email = st.text_input("Email", placeholder="nome@email.com")
        password = st.text_input("Password", type="password")
        if st.button("Accedi", use_container_width=True, type="primary"):
            if not email or not password:
                st.warning("Inserisci email e password.")
                return
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user_id = res.user.id
                st.session_state.user_email = res.user.email
                st.rerun()
            except Exception:
                st.error("❌ Credenziali non valide. Controlla email e password.")


def calcola_pace(df_cy_attive, df_ly_attive, mes, anio_cy, fecha_hoy_pd, fecha_stly, max_days=120):
    """Curva di riempimento cumulativa (Revenue) per il mese selezionato, CY vs STLY."""
    mes_start_cy = pd.Timestamp(anio_cy, mes, 1)
    mes_start_ly = pd.Timestamp(anio_cy - 1, mes, 1)

    def _prep(df, mes_start, cutoff=None):
        sub = df[df['check_in_date'].dt.month == mes].copy()
        sub = sub[sub['booking_date'].notna()]
        if cutoff is not None:
            sub = sub[sub['booking_date'] <= cutoff]
        sub['days_out'] = (mes_start - pd.to_datetime(sub['booking_date'])).dt.days
        return sub

    def _curve(df_sub):
        if df_sub.empty:
            return pd.DataFrame(columns=['days_out', 'cum_rev', 'cum_pren'])
        agg = df_sub.groupby('days_out').agg(
            rev=('gross_revenue', 'sum'),
            pren=('gross_revenue', 'count')
        ).reset_index()
        rng = pd.DataFrame({'days_out': range(max_days, -61, -1)})
        agg = rng.merge(agg, on='days_out', how='left').fillna(0)
        agg = agg.sort_values('days_out', ascending=False)
        agg['cum_rev']  = agg['rev'].cumsum()
        agg['cum_pren'] = agg['pren'].cumsum()
        return agg[['days_out', 'cum_rev', 'cum_pren']].sort_values('days_out', ascending=True)

    days_out_oggi = int((mes_start_cy - fecha_hoy_pd).days)
    return (
        _curve(_prep(df_cy_attive, mes_start_cy, fecha_hoy_pd)),
        _curve(_prep(df_ly_attive, mes_start_ly, fecha_stly)),
        _curve(_prep(df_ly_attive, mes_start_ly)),
        days_out_oggi,
    )


def _html_table(df: pd.DataFrame, num_cols=None, delta_cols=None,
                fmt=None, color_fn=None) -> str:
    """Renders a DataFrame as a styled HTML table (Rate Labs RMS style)."""
    num_cols   = set(num_cols or [])
    delta_cols = set(delta_cols or [])
    fmt        = fmt or {}
    color_fn   = color_fn or {}

    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            num_cols.add(col)

    headers = "".join(
        f'<th class="rnum">{col}</th>' if col in num_cols else f'<th>{col}</th>'
        for col in df.columns
    )

    rows = ""
    for _, row in df.iterrows():
        cells = ""
        for col in df.columns:
            val = row[col]
            if col in fmt:
                try:
                    display = fmt[col].format(val)
                except Exception:
                    display = str(val)
            else:
                display = "—" if (isinstance(val, float) and pd.isna(val)) else str(val)

            parts = ["rnum"] if col in num_cols else []
            if col in delta_cols and isinstance(val, (int, float)):
                parts.append("pos" if val > 0 else ("neg" if val < 0 else "neu"))
            elif col in color_fn:
                parts.append(color_fn[col](val))

            cells += f'<td class="{" ".join(parts)}">{display}</td>'
        rows += f"<tr>{cells}</tr>"

    return (
        '<div class="rl-table-wrap">'
        '<table class="rl-table">'
        f'<thead><tr>{headers}</tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table></div>'
    )


def calcola_pickup(df_cy, df_ly, mes, data_oggi, data_stly, finestre=(7, 14, 30)):
    """Calcola le prenotazioni e i ricavi acquisiti nelle ultime N giorni per il mese selezionato."""
    righe = []
    for giorni in finestre:
        inizio_cy = data_oggi - pd.Timedelta(days=giorni)
        p_cy = df_cy[
            (df_cy['check_in_date'].dt.month == mes) &
            (df_cy['booking_date'] >= inizio_cy) &
            (df_cy['booking_date'] <= data_oggi)
        ]
        inizio_ly = data_stly - pd.Timedelta(days=giorni)
        p_ly = df_ly[
            (df_ly['check_in_date'].dt.month == mes) &
            (df_ly['booking_date'] >= inizio_ly) &
            (df_ly['booking_date'] <= data_stly)
        ]
        righe.append({
            'Finestra': f'Ultimi {giorni}gg',
            'Pren. CY': len(p_cy),
            'Pren. STLY': len(p_ly),
            'Δ Pren.': len(p_cy) - len(p_ly),
            'Rev. CY (€)': p_cy['gross_revenue'].sum(),
            'Rev. STLY (€)': p_ly['gross_revenue'].sum(),
            'Δ Rev. (€)': p_cy['gross_revenue'].sum() - p_ly['gross_revenue'].sum(),
        })
    return pd.DataFrame(righe)

# =====================================================
# AUTENTICAZIONE
# =====================================================
if not st.session_state.get("user_id"):
    show_login_page()
    st.stop()

USER_ID = st.session_state.user_id

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("⚙️ Impostazioni")

tipo_struttura = st.sidebar.selectbox(
    "🏨 Tipo struttura:",
    ["Property Manager (Appartamenti)", "Hotel Diretto"]
)
is_hotel = tipo_struttura == "Hotel Diretto"
lbl_unita   = "Camere"       if is_hotel else "Appartamenti"
lbl_netto   = "Netto Oper."  if is_hotel else "Netto PM"
lbl_portf   = "Hotel"        if is_hotel else "Portafoglio"

st.sidebar.markdown("---")

mes_interes = st.sidebar.selectbox(
    "📅 Mese da analizzare:",
    range(1, 13), index=4,
    format_func=lambda x: MESI_IT[x - 1]
)
fecha_hoy = st.sidebar.date_input("🗓️ Data OTB (oggi):", value=date.today())
fecha_hoy_pd = pd.to_datetime(fecha_hoy)

st.sidebar.markdown("---")
st.sidebar.success("🟢 Connesso al Cloud (Supabase)")
st.sidebar.caption(f"👤 {st.session_state.get('user_email', '')}")
if st.sidebar.button("🚪 Esci", use_container_width=True):
    supabase.auth.sign_out()
    st.session_state.pop("user_id", None)
    st.session_state.pop("user_email", None)
    st.rerun()

# =====================================================
# MAIN
# =====================================================

st.title("📊 Rate Labs RMS")

with st.spinner('Sincronizzazione con il database in corso...'):
    df_cloud = load_data_from_supabase(USER_ID)

if not df_cloud.empty:
    anio_actual = fecha_hoy_pd.year
    
    df_cy_raw = df_cloud[df_cloud['check_in_date'].dt.year == anio_actual].copy()
    df_ly_raw = df_cloud[df_cloud['check_in_date'].dt.year == (anio_actual - 1)].copy()
    
    # --- FILTRO APPARTAMENTO ---
    st.sidebar.markdown("---")
    tutti_apt = sorted(df_cy_raw['unit_id'].dropna().unique())
    apt_sel = st.sidebar.multiselect("🏨 Filtra Appartamenti (vuoto = tutti):", tutti_apt)

    if apt_sel:
        df_ly = df_ly_raw[df_ly_raw['unit_id'].isin(apt_sel)].copy()
        df_cy = df_cy_raw[df_cy_raw['unit_id'].isin(apt_sel)].copy()
        txt_filtro = f"Appartamenti: {', '.join(apt_sel)}"
    else:
        df_ly = df_ly_raw.copy()
        df_cy = df_cy_raw.copy()
        txt_filtro = "Intero Portafoglio"

    # --- GESTIONE STATUS & CANCELLAZIONI ---
    # Convertimos a string, quitamos espacios ocultos, pasamos a minúsculas y buscamos "cancel"
    mask_canc_cy = df_cy['status'].astype(str).str.strip().str.lower().str.contains('cancel', na=False)
    mask_canc_ly = df_ly['status'].astype(str).str.strip().str.lower().str.contains('cancel', na=False)
    # Separamos reservas activas de las canceladas
    df_cy_attive = df_cy[~mask_canc_cy]
    df_cy_canc   = df_cy[mask_canc_cy]
    df_ly_attive = df_ly[~mask_canc_ly]

    # --- SLICE TEMPORALI (Solo Prenotazioni Attive per i KPI finanziari) ---
    mes_nombre = MESI_IT[mes_interes - 1]
    fecha_stly = fecha_hoy_pd - pd.DateOffset(years=1)

    df_cy_otb   = df_cy_attive[(df_cy_attive['check_in_date'].dt.month == mes_interes) & (df_cy_attive['booking_date'] <= fecha_hoy_pd)]
    df_ly_otb   = df_ly_attive[(df_ly_attive['check_in_date'].dt.month == mes_interes) & (df_ly_attive['booking_date'] <= fecha_stly)]
    df_ly_final = df_ly_attive[df_ly_attive['check_in_date'].dt.month == mes_interes]

    # Calculamos cuántas se han cancelado para el OTB actual
    df_cy_canc_mes = df_cy_canc[(df_cy_canc['check_in_date'].dt.month == mes_interes) & (df_cy_canc['booking_date'] <= fecha_hoy_pd)]

    # --- KPI ---
    k = calcola_kpi(df_cy_otb, df_ly_otb, df_ly_final)

    giorni_mese = fecha_hoy_pd.replace(day=1).replace(month=mes_interes)
    giorni_nel_mese = (giorni_mese + pd.offsets.MonthEnd(0)).day

    # Denominatore reale: se filtro attivo usa solo le unità selezionate, altrimenti tutto il portfolio
    total_units_portfolio = load_total_units(USER_ID)
    if apt_sel:
        unita_cy = len(apt_sel)
    else:
        unita_cy = total_units_portfolio if total_units_portfolio > 0 else max(df_cy['unit_id'].nunique(), 1)
    unita_ly = unita_cy  # stesso sottoinsieme per confronto STLY

    capacita_totale_cy = unita_cy * giorni_nel_mese
    capacita_totale_ly = unita_ly * giorni_nel_mese

    revpar    = k['rev']    / capacita_totale_cy if capacita_totale_cy > 0 else 0
    revpar_ly = k['rev_ly'] / capacita_totale_ly if capacita_totale_ly > 0 else 0
    var_revpar = (revpar / revpar_ly - 1) * 100 if revpar_ly > 0 else 0

    # Occupancy %
    occupancy_cy  = (k['notti'] / capacita_totale_cy * 100) if capacita_totale_cy > 0 else 0
    occupancy_ly  = (k['notti_ly'] / capacita_totale_ly * 100) if capacita_totale_ly > 0 else 0
    var_occ       = occupancy_cy - occupancy_ly  # delta in punti percentuale

    # Net ADR (dopo commissioni OTA)
    net_adr       = (k['rev'] - k['commissioni']) / k['notti'] if k['notti'] > 0 else 0
    net_adr_ly    = (k['rev_ly'] - k['commissioni_ly']) / k['notti_ly'] if k['notti_ly'] > 0 else 0
    var_net_adr   = (net_adr / net_adr_ly - 1) * 100 if net_adr_ly > 0 else 0

    # Cancellazioni: % + ricavi a rischio
    tot_res_cy = len(df_cy_otb) + len(df_cy_canc_mes)
    pct_canc   = (len(df_cy_canc_mes) / tot_res_cy * 100) if tot_res_cy > 0 else 0
    rev_at_risk = df_cy_canc_mes['gross_revenue'].sum() if not df_cy_canc_mes.empty else 0.0

    # =====================================================
    # CERVELLO MATEMATICO — BOTTOM RATE
    # =====================================================
    df_fix_portfolio, df_var_portfolio, df_util_portfolio = load_portfolio_costs(USER_ID)
    costos_configurados = not df_fix_portfolio.empty or not df_var_portfolio.empty or not df_util_portfolio.empty

    bottom_rate = 0.0
    fixed_per_night = 0.0
    var_per_night   = 0.0
    if costos_configurados:
        fixed_annual = (
            df_fix_portfolio[df_fix_portfolio['frequency'] == 'yearly']['amount'].sum() +
            df_fix_portfolio[df_fix_portfolio['frequency'] == 'monthly']['amount'].sum() * 12
        ) if not df_fix_portfolio.empty else 0.0

        # Utenze: somma delle bollette degli ultimi 12 mesi come stima annua
        util_annual = float(df_util_portfolio['amount'].sum()) if not df_util_portfolio.empty else 0.0
        fixed_annual += util_annual

        los_est = max(k['los'], 1.0)
        var_per_night = 0.0
        if not df_var_portfolio.empty:
            var_per_night = (
                df_var_portfolio[df_var_portfolio['basis'] == 'per_night']['value'].sum() +
                df_var_portfolio[df_var_portfolio['basis'] == 'per_booking']['value'].sum() / los_est +
                df_var_portfolio[df_var_portfolio['basis'] == 'per_guest']['value'].sum() * 2 / los_est
            )

        capacita_annua = unita_cy * 365
        fixed_per_night = fixed_annual / capacita_annua if capacita_annua > 0 else 0.0
        costo_base_notte = fixed_per_night + var_per_night
        commissione_pct = (k['commissioni'] / k['rev'] * 100) if k['rev'] > 0 else 15.0
        bottom_rate = costo_base_notte / (1 - commissione_pct / 100) if commissione_pct < 100 else 0.0

    # =====================================================
    # PICKUP REPORT
    # =====================================================
    df_pickup = calcola_pickup(df_cy_attive, df_ly_attive, mes_interes, fecha_hoy_pd, fecha_stly)
    pickup_7_cy  = int(df_pickup.loc[0, 'Pren. CY'])  if not df_pickup.empty else 0
    pickup_7_ly  = int(df_pickup.loc[0, 'Pren. STLY']) if not df_pickup.empty else 0
    pickup_7_rev = float(df_pickup.loc[0, 'Rev. CY (€)']) if not df_pickup.empty else 0.0

    # =====================================================
    # COMP SET — caricato qui per renderlo disponibile all'IA
    # =====================================================
    df_market = load_comp_set_data(USER_ID)

    # =====================================================
    # PANORAMICA ANNUALE — sempre visibile all'apertura
    # =====================================================
    st.subheader(f"📊 Panoramica Anno {anio_actual} — YTD al {fecha_hoy.strftime('%d/%m/%Y')}")
    st.caption(f"📍 {txt_filtro} | {total_units_portfolio} {lbl_unita}")

    # --- Dati aggregati YTD (tutte le mensilità, stessa logica OTB) ---
    dias_ytd   = (fecha_hoy_pd - pd.Timestamp(anio_actual, 1, 1)).days + 1
    df_cy_ytd  = df_cy_attive[df_cy_attive['booking_date'] <= fecha_hoy_pd]
    df_ly_ytd  = df_ly_attive[df_ly_attive['booking_date'] <= fecha_stly]

    rev_ytd      = df_cy_ytd['gross_revenue'].sum()
    rev_ly_ytd   = df_ly_ytd['gross_revenue'].sum()
    notti_ytd    = df_cy_ytd['nights'].sum()
    notti_ly_ytd = df_ly_ytd['nights'].sum()
    comm_ytd     = df_cy_ytd['commission_amount'].sum() if 'commission_amount' in df_cy_ytd.columns else 0
    comm_ly_ytd  = df_ly_ytd['commission_amount'].sum() if 'commission_amount' in df_ly_ytd.columns else 0

    adr_ytd        = rev_ytd / notti_ytd              if notti_ytd > 0 else 0
    adr_ly_ytd     = rev_ly_ytd / notti_ly_ytd        if notti_ly_ytd > 0 else 0
    net_adr_ytd    = (rev_ytd - comm_ytd) / notti_ytd     if notti_ytd > 0 else 0
    net_adr_ly_ytd = (rev_ly_ytd - comm_ly_ytd) / notti_ly_ytd if notti_ly_ytd > 0 else 0

    cap_ytd        = unita_cy * dias_ytd
    revpar_ytd     = rev_ytd    / cap_ytd if cap_ytd > 0 else 0
    revpar_ly_ytd  = rev_ly_ytd / cap_ytd if cap_ytd > 0 else 0
    occ_ytd        = notti_ytd    / cap_ytd * 100 if cap_ytd > 0 else 0
    occ_ly_ytd     = notti_ly_ytd / cap_ytd * 100 if cap_ytd > 0 else 0

    var_rev_ytd     = (rev_ytd / rev_ly_ytd - 1) * 100         if rev_ly_ytd > 0 else 0
    var_revpar_ytd  = (revpar_ytd / revpar_ly_ytd - 1) * 100   if revpar_ly_ytd > 0 else 0
    var_occ_ytd     = occ_ytd - occ_ly_ytd
    var_adr_ytd     = (adr_ytd / adr_ly_ytd - 1) * 100         if adr_ly_ytd > 0 else 0
    var_net_adr_ytd = (net_adr_ytd / net_adr_ly_ytd - 1) * 100 if net_adr_ly_ytd > 0 else 0

    # KPI row
    ya1, ya2, ya3, ya4, ya5 = st.columns(5)
    ya1.metric("💰 Revenue YTD",   f"€{rev_ytd:,.0f}",      f"{var_rev_ytd:+.1f}% vs STLY"     if rev_ly_ytd > 0 else "—")
    ya2.metric("🏠 RevPAR YTD",    f"€{revpar_ytd:,.2f}",   f"{var_revpar_ytd:+.1f}% vs STLY"  if revpar_ly_ytd > 0 else "—")
    ya3.metric("📊 Occupancy YTD", f"{occ_ytd:.1f}%",        f"{var_occ_ytd:+.1f}pp vs STLY"    if occ_ly_ytd > 0 else "—")
    ya4.metric("🏷️ ADR YTD",       f"€{adr_ytd:,.2f}",       f"{var_adr_ytd:+.1f}% vs STLY"    if adr_ly_ytd > 0 else "—")
    ya5.metric("🏷️ Net ADR YTD",   f"€{net_adr_ytd:,.2f}",   f"{var_net_adr_ytd:+.1f}% vs STLY" if net_adr_ly_ytd > 0 else "—")

    # --- Aggregazione mensile per grafici ---
    _MESI_BREVI  = ['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic']
    _scaffold    = pd.DataFrame({'MeseNum': range(1, 13), 'Mese': _MESI_BREVI})
    _label_ly    = f"{anio_actual - 1} (STLY)"
    _color_map   = {str(anio_actual): C_CY, _label_ly: C_STLY}
    _cat_order   = {'Mese': _MESI_BREVI, 'Anno': [str(anio_actual), _label_ly]}

    def _agg_men(df, anno):
        if df.empty:
            base = _scaffold.copy()
            for col in ['Revenue', 'Notti', 'ADR', 'Occ%']:
                base[col] = 0.0
            return base
        g = df.groupby(df['check_in_date'].dt.month).agg(
            Revenue=('gross_revenue', 'sum'),
            Notti=('nights', 'sum'),
        ).reset_index()
        g.columns = ['MeseNum', 'Revenue', 'Notti']
        g['ADR']    = g.apply(lambda r: r['Revenue'] / r['Notti'] if r['Notti'] > 0 else 0, axis=1)
        g['Giorni'] = g['MeseNum'].apply(lambda m: (pd.Timestamp(anno, m, 1) + pd.offsets.MonthEnd(0)).day)
        g['Occ%']   = g.apply(lambda r: r['Notti'] / (r['Giorni'] * unita_cy) * 100 if unita_cy > 0 else 0, axis=1)
        return _scaffold.merge(g[['MeseNum', 'Revenue', 'Notti', 'ADR', 'Occ%']], on='MeseNum', how='left').fillna(0)

    _men_cy        = _agg_men(df_cy_ytd, anio_actual);      _men_cy['Anno'] = str(anio_actual)
    _men_ly        = _agg_men(df_ly_ytd, anio_actual - 1);  _men_ly['Anno'] = _label_ly
    _men_all       = pd.concat([_men_cy, _men_ly], ignore_index=True)

    # --- Semaforo mensile (Rev CY vs STLY per mese) ---
    _sema_html = '<div style="display:flex;gap:5px;flex-wrap:wrap;margin:0.75rem 0 0.5rem;">'
    for _si in range(12):
        _m = _si + 1
        _cv = float(_men_cy[_men_cy['MeseNum'] == _m]['Revenue'].values[0]) if len(_men_cy[_men_cy['MeseNum'] == _m]) > 0 else 0
        _lv = float(_men_ly[_men_ly['MeseNum'] == _m]['Revenue'].values[0]) if len(_men_ly[_men_ly['MeseNum'] == _m]) > 0 else 0
        if _cv == 0 and _m > fecha_hoy_pd.month:
            _bg, _col, _ico = '#F1F5F9', '#94A3B8', '○'
        elif _lv == 0:
            _bg, _col, _ico = '#EFF6FF', '#3B82F6', '·'
        else:
            _pct_s = (_cv / _lv - 1) * 100
            if _pct_s >= 5:   _bg, _col, _ico = '#DCFCE7', '#16A34A', '↑'
            elif _pct_s >= -5: _bg, _col, _ico = '#FEF3C7', '#D97706', '→'
            else:              _bg, _col, _ico = '#FEE2E2', '#DC2626', '↓'
        _brd = 'border:2px solid #1E6FD9;' if _m == mes_interes else 'border:1px solid transparent;'
        _sema_html += (
            f'<div style="background:{_bg};color:{_col};border-radius:8px;padding:4px 10px;'
            f'font-size:0.73rem;font-weight:600;{_brd}display:inline-flex;align-items:center;gap:3px;">'
            f'<span>{_ico}</span><span>{_MESI_BREVI[_si]}</span></div>'
        )
    _sema_html += '</div>'
    st.markdown(_sema_html, unsafe_allow_html=True)

    gc1, gc2, gc3 = st.columns(3)

    with gc1:
        _f1 = px.bar(_men_all, x='Mese', y='Revenue', color='Anno', barmode='group',
                     title="Revenue per Mese (€)",
                     color_discrete_map=_color_map, category_orders=_cat_order)
        _f1.update_traces(marker=dict(line=dict(width=0), cornerradius=4),
                          hovertemplate="<b>%{x}</b><br>€%{y:,.0f}<extra>%{fullData.name}</extra>")
        _f1.update_layout(**_fig_layout(height=300, showlegend=True,
                                        legend=dict(orientation='h', y=-0.28, x=0.5, xanchor='center', title_text='')))
        _f1.update_xaxes(showgrid=False)
        _f1.update_yaxes(showgrid=True, gridcolor=_GRID)
        _f1.add_shape(type='rect', xref='x', yref='paper',
                      x0=mes_interes-1-0.46, x1=mes_interes-1+0.46, y0=0, y1=1,
                      fillcolor='rgba(30,111,217,0.07)', line_width=0, layer='below')
        st.plotly_chart(_f1, use_container_width=True)

    with gc2:
        _f2 = px.bar(_men_all, x='Mese', y='Occ%', color='Anno', barmode='group',
                     title="Occupancy % per Mese",
                     color_discrete_map=_color_map, category_orders=_cat_order)
        _f2.update_traces(marker=dict(line=dict(width=0), cornerradius=4),
                          hovertemplate="<b>%{x}</b><br>%{y:.1f}%<extra>%{fullData.name}</extra>")
        _f2.update_layout(**_fig_layout(height=300, showlegend=True,
                                        legend=dict(orientation='h', y=-0.28, x=0.5, xanchor='center', title_text='')))
        _f2.update_xaxes(showgrid=False)
        _f2.update_yaxes(showgrid=True, gridcolor=_GRID, ticksuffix='%')
        _f2.add_shape(type='rect', xref='x', yref='paper',
                      x0=mes_interes-1-0.46, x1=mes_interes-1+0.46, y0=0, y1=1,
                      fillcolor='rgba(30,111,217,0.07)', line_width=0, layer='below')
        st.plotly_chart(_f2, use_container_width=True)

    with gc3:
        _f3 = px.bar(_men_all, x='Mese', y='ADR', color='Anno', barmode='group',
                     title="ADR per Mese (€)",
                     color_discrete_map=_color_map, category_orders=_cat_order)
        _f3.update_traces(marker=dict(line=dict(width=0), cornerradius=4),
                          hovertemplate="<b>%{x}</b><br>€%{y:,.2f}<extra>%{fullData.name}</extra>")
        _f3.update_layout(**_fig_layout(height=300, showlegend=True,
                                        legend=dict(orientation='h', y=-0.28, x=0.5, xanchor='center', title_text='')))
        _f3.update_xaxes(showgrid=False)
        _f3.update_yaxes(showgrid=True, gridcolor=_GRID)
        _f3.add_shape(type='rect', xref='x', yref='paper',
                      x0=mes_interes-1-0.46, x1=mes_interes-1+0.46, y0=0, y1=1,
                      fillcolor='rgba(30,111,217,0.07)', line_width=0, layer='below')
        st.plotly_chart(_f3, use_container_width=True)

    st.divider()
    st.caption(f"🔍 Analisi mensile — **{mes_nombre}** | OTB al **{fecha_hoy.strftime('%d/%m/%Y')}** | {lbl_portf}: **{unita_cy} {lbl_unita}**")

    tab_revenue, tab_costi, tab_mercato, tab_strategia, tab_dati = st.tabs([
        "📊 Revenue", "💰 Costi & Margini", "🕵️ Mercato", "💡 Strategia", "⚙️ Dati"
    ])

    with tab_revenue:
        st.subheader("Riepilogo Performance")

        # ── Status header ──
        if k['rev_ly'] > 0:
            _drev = k['var_rev']
            if _drev >= 5:
                _sh_bg, _sh_col, _sh_ico = '#DCFCE7', '#15803D', '📈'
                _sh_txt = f"+{_drev:.1f}% vs STLY — Sopra ritmo"
            elif _drev <= -5:
                _sh_bg, _sh_col, _sh_ico = '#FEE2E2', '#DC2626', '📉'
                _sh_txt = f"{_drev:.1f}% vs STLY — Sotto ritmo"
            else:
                _sh_bg, _sh_col, _sh_ico = '#FEF3C7', '#D97706', '↔️'
                _sh_txt = f"{_drev:+.1f}% vs STLY — In linea"
            if occupancy_cy >= 80:
                _sh_txt += f"  ·  Occ. {occupancy_cy:.0f}% — Alto riempimento"
            st.markdown(
                f'<div style="background:{_sh_bg};color:{_sh_col};border-radius:10px;'
                f'padding:0.55rem 1.1rem;font-weight:600;font-size:0.88rem;margin-bottom:0.6rem;'
                f'border:1px solid {_sh_col}33;">'
                f'{_sh_ico}&nbsp;&nbsp;<b>{mes_nombre}</b> — {_sh_txt}</div>',
                unsafe_allow_html=True
            )

        # ── Riga 1: KPI strategici ──
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Ricavi OTB",   f"€{k['rev']:,.0f}",      f"{k['var_rev']:+.1f}% vs STLY"    if k['rev_ly'] > 0 else "")
        c2.metric("🏠 RevPAR",       f"€{revpar:,.2f}",         f"{var_revpar:+.1f}% vs STLY"      if revpar_ly > 0 else "")
        c3.metric("📊 Occupancy",    f"{occupancy_cy:.1f}%",    f"{var_occ:+.1f}pp vs STLY"        if occupancy_ly > 0 else "")
        c4.metric("🏷️ ADR Lordo",    f"€{k['adr']:,.2f}",       f"{k['var_adr']:+.1f}% vs STLY"   if k['adr_ly'] > 0 else "")
        c5.metric("🏷️ Net ADR",      f"€{net_adr:,.2f}",        f"{var_net_adr:+.1f}% vs STLY"    if net_adr_ly > 0 else "")

        # ── Riga 2: KPI operativi ──
        d1, d2, d3, d4, d5 = st.columns(5)
        d1.metric(f"🛏️ {lbl_unita} analizzate", f"{unita_cy}", f"{total_units_portfolio} totali" if total_units_portfolio != unita_cy else "")
        d2.metric("🌙 Notti vendute",  f"{k['notti']:,.0f}",    f"{k['notti'] - k['notti_ly']:+.0f} vs STLY")
        d3.metric("🛌 LOS medio",      f"{k['los']:.1f} notti", f"STLY: {k['los_ly']:.1f}")
        d4.metric("⏱️ Lead Time",      f"{k['lt']:.0f} gg",     f"Chiusura STLY: {k['lt_ly_final']:.0f}gg")
        d5.metric("❌ Cancellazioni",  f"{pct_canc:.1f}%",      f"€{rev_at_risk:,.0f} a rischio" if rev_at_risk > 0 else f"{len(df_cy_canc_mes)} pren.")

        # ── Insight rapido ──
        st.markdown("")
        col_diag, col_info = st.columns([2, 1])
        with col_diag:
            st.subheader("🧠 Insight Rapido")
            if occupancy_cy >= 85 and var_net_adr < 0:
                st.warning("⚠️ **Occupancy alta, Net ADR in calo** — sei quasi pieno ma stai scontando. Alza i prezzi.")
            elif occupancy_cy < 50 and k['var_rev'] < -10:
                st.error("📉 **Calo ricavi e occupancy bassa** — ritardo significativo vs STLY.")
            elif k['los'] > (k['los_ly'] + 1):
                st.success(f"🌟 **Mix Ottimo:** Soggiorni più lunghi (+{k['los'] - k['los_ly']:.1f} notti) — meno cambi, meno costi.")
            elif k['var_rev'] > 0 and var_net_adr >= 0:
                st.success("🏆 **Crescita Sana:** Ricavi e Net ADR in aumento.")
            elif k['var_notti'] > 0 and k['var_adr'] < -5:
                st.warning("⚠️ **Diluizione ADR:** Vendi di più ma a prezzo inferiore — controlla il mix canale.")
            else:
                st.info("📊 **Ritmo Stabile:** Indicatori in linea con lo storico.")
        with col_info:
            st.subheader("📐 Struttura")
            st.caption(f"**Tipo:** {tipo_struttura}")
            st.caption(f"**{lbl_unita} totali:** {total_units_portfolio}")
            st.caption(f"**Capacità mese:** {capacita_totale_cy:,.0f} notti disponibili")

        st.divider()

        # =====================================================
        # PICKUP REPORT
        # =====================================================
        st.subheader("📥 Pickup Report")
        if not df_pickup.empty:
            col_pu_left, col_pu_right = st.columns([3, 2])
            with col_pu_left:
                st.markdown(_html_table(
                    df_pickup,
                    num_cols=['Pren. CY', 'Pren. STLY', 'Δ Pren.', 'Rev. CY (€)', 'Rev. STLY (€)', 'Δ Rev. (€)'],
                    delta_cols=['Δ Pren.', 'Δ Rev. (€)'],
                    fmt={
                        'Rev. CY (€)':   '€ {:,.0f}',
                        'Rev. STLY (€)': '€ {:,.0f}',
                        'Δ Rev. (€)':    '€ {:+,.0f}',
                        'Δ Pren.':       '{:+d}',
                    }
                ), unsafe_allow_html=True)

            with col_pu_right:
                pickup_7_delta  = pickup_7_cy - pickup_7_ly
                pickup_7_rev_ly = float(df_pickup.loc[0, 'Rev. STLY (€)']) if not df_pickup.empty else 0.0
                st.metric(
                    "🔥 Pickup 7gg (Pren.)",
                    f"{pickup_7_cy}",
                    f"{pickup_7_delta:+d} vs STLY"
                )
                st.metric(
                    "💶 Pickup 7gg (Ricavi)",
                    f"€ {pickup_7_rev:,.0f}",
                    f"€ {pickup_7_rev - pickup_7_rev_ly:+,.0f} vs STLY"
                )
        else:
            st.info("Nessun dato disponibile per il Pickup Report.")

        # =====================================================
        # BOOKING PACE CURVE
        # =====================================================
        st.divider()
        st.subheader("📈 Booking Pace — Curva di Riempimento")
        st.caption(f"Revenue cumulativo prenotato per {mes_nombre} — giorni prima dell'inizio del mese")

        _pace_cy, _pace_ly, _pace_ly_fin, _days_oggi = calcola_pace(
            df_cy_attive, df_ly_attive, mes_interes, anio_actual, fecha_hoy_pd, fecha_stly
        )

        if not _pace_cy.empty or not _pace_ly.empty:
            _pcol1, _pcol2 = st.columns([4, 1])
            with _pcol1:
                _fig_p = go.Figure()

                if not _pace_ly_fin.empty:
                    _fig_p.add_trace(go.Scatter(
                        x=_pace_ly_fin['days_out'], y=_pace_ly_fin['cum_rev'],
                        mode='lines', name=f"{anio_actual - 1} (finale)",
                        line=dict(color=C_STLY, width=1.5, dash='dot'),
                        opacity=0.5,
                        hovertemplate=f"<b>{anio_actual-1} Finale</b><br>%{{x}} gg | €%{{y:,.0f}}<extra></extra>",
                    ))
                if not _pace_ly.empty:
                    _fig_p.add_trace(go.Scatter(
                        x=_pace_ly['days_out'], y=_pace_ly['cum_rev'],
                        mode='lines', name=f"{anio_actual - 1} (stesso OTB)",
                        line=dict(color=C_STLY, width=2),
                        hovertemplate=f"<b>{anio_actual-1} OTB</b><br>%{{x}} gg | €%{{y:,.0f}}<extra></extra>",
                    ))
                if not _pace_cy.empty:
                    _fig_p.add_trace(go.Scatter(
                        x=_pace_cy['days_out'], y=_pace_cy['cum_rev'],
                        mode='lines', name=f"{anio_actual} (OTB)",
                        line=dict(color=C_CY, width=2.5),
                        hovertemplate=f"<b>{anio_actual} OTB</b><br>%{{x}} gg | €%{{y:,.0f}}<extra></extra>",
                    ))

                _fig_p.add_vline(
                    x=_days_oggi,
                    line_dash='dash', line_color='rgba(30,111,217,0.55)', line_width=1.5,
                    annotation_text="Oggi", annotation_position="top right",
                    annotation_font=dict(color=C_CY, size=11),
                )
                _fig_p.update_layout(**_fig_layout(
                    height=340, showlegend=True,
                    legend=dict(orientation='h', y=-0.22, x=0.5, xanchor='center', title_text=''),
                ))
                _fig_p.update_xaxes(
                    title_text="Giorni prima dell'inizio del mese",
                    autorange='reversed',
                    showgrid=True, gridcolor=_GRID,
                )
                _fig_p.update_yaxes(
                    title_text="Revenue Cumulativo (€)",
                    showgrid=True, gridcolor=_GRID,
                    tickprefix='€',
                )
                st.plotly_chart(_fig_p, use_container_width=True)

            with _pcol2:
                if not _pace_cy.empty and not _pace_ly.empty:
                    _cy_now_df = _pace_cy[_pace_cy['days_out'] >= _days_oggi]
                    _ly_now_df = _pace_ly[_pace_ly['days_out'] >= _days_oggi]
                    _cy_rev_now = float(_cy_now_df['cum_rev'].max()) if not _cy_now_df.empty else float(_pace_cy['cum_rev'].max())
                    _ly_rev_now = float(_ly_now_df['cum_rev'].max()) if not _ly_now_df.empty else float(_pace_ly['cum_rev'].max())
                    st.metric(f"📦 OTB {mes_nombre}", f"€{_cy_rev_now:,.0f}",
                              f"€{_cy_rev_now - _ly_rev_now:+,.0f} vs STLY")
                    if not _pace_ly_fin.empty:
                        _ly_fin_max = float(_pace_ly_fin['cum_rev'].max())
                        if _ly_fin_max > 0:
                            st.metric("🎯 % su STLY Finale", f"{_cy_rev_now / _ly_fin_max * 100:.0f}%")
                    _d_lbl = f"{abs(_days_oggi)} gg {'prima' if _days_oggi >= 0 else 'dopo inizio mese'}"
                    st.caption(f"📍 {_d_lbl}")
        else:
            st.info("Dati insufficienti per la curva di pace.")


    # ── AI section variables (rendered in tab_strategia below) ──
    _sezione_br = ""
    _sezione_comp = ""
    if bottom_rate > 0:
        _sezione_br = (
            f"⚠️ VINCOLO ASSOLUTO — BOTTOM RATE: €{bottom_rate:.2f}/notte "
            f"(soglia matematica di pareggio calcolata dai costi operativi reali + commissioni OTA medie del portafoglio). "
            f"REGOLA FERREA: non suggerire mai strategie che portino l'ADR al di sotto di €{bottom_rate:.2f}. "
            f"È il pavimento matematico, non si negozia."
        )
    else:
        _sezione_br = "ℹ️ Bottom Rate non disponibile (nessun costo operativo configurato). Analizza in base ai dati di mercato."
    if not df_market.empty:
        comp_mes = df_market[df_market['stay_date'].dt.month == mes_interes]
        if not comp_mes.empty:
            avg_comp = comp_mes[comp_mes['is_available'] == True]['price'].mean()
            n_soldout = comp_mes[comp_mes['is_available'] == False]['name'].nunique()
            _sezione_comp = (
                f"\n📊 MERCATO: prezzo medio competitor €{avg_comp:.0f}/notte per {mes_nombre}. "
                f"{n_soldout} competitor già sold out."
            )
    _prompt_ia = f"""Sei il Cervello Strategico di un sistema professionale di Revenue Management.
Oggi: {fecha_hoy.strftime('%d/%m/%Y')} | Portfolio: {txt_filtro} | Mese analizzato: {mes_nombre}

{_sezione_br}

📈 DATI OTB:
• Ricavi: €{k['rev']:,.0f} ({k['var_rev']:+.1f}% vs STLY) | RevPAR: €{revpar:,.2f} ({var_revpar:+.1f}%)
• Notti: {k['notti']:,.0f} ({k['var_notti']:+.1f}%) | ADR: €{k['adr']:,.2f} ({k['var_adr']:+.1f}%)
• LOS: {k['los']:.1f} notti | Lead Time: {k['lt']:.0f}gg (chiusura STLY: {k['lt_ly_final']:.0f}gg)
• Cancellazioni: {pct_canc:.1f}% | Pickup 7gg: {pickup_7_cy} pren. ({pickup_7_cy - pickup_7_ly:+d} vs STLY){_sezione_comp}

Genera un report STRUTTURATO con esattamente questo formato (max 300 parole totali):

🟢 SCENARIO CONSERVATIVO
Azione: [cosa fare concretamente sul channel manager]
Obiettivo: [risultato atteso in termini di RevPAR, ADR o occupazione]

🟡 SCENARIO MODERATO
Azione: [cosa fare concretamente]
Obiettivo: [risultato atteso]

🔴 SCENARIO AGGRESSIVO
Azione: [cosa fare concretamente]
Obiettivo: [risultato atteso]

💡 DIAGNOSI (2 righe max): Motivazione principale della strategia basata sui dati OTB e di mercato.
"""

    with tab_revenue:
        st.divider()
        st.subheader("📡 Analisi per Canale di Prenotazione")
        if not df_cy_otb.empty and df_cy_otb['gross_revenue'].sum() > 0:
            df_ch = df_cy_otb.groupby('channel_group').agg(
                Ricavi=('gross_revenue', 'sum'),
                Notti=('nights', 'sum'),
                Prenotazioni=('id', 'count'),
                Commissioni=('commission_amount', 'sum')
            ).reset_index()
            
            df_ch['ADR'] = df_ch.apply(lambda r: (r['Ricavi'] / r['Notti']) if r['Notti'] > 0 else 0, axis=1)
            tot_ricavi = df_ch['Ricavi'].sum()
            df_ch['% Ricavi'] = df_ch['Ricavi'].apply(lambda x: (x / tot_ricavi * 100) if tot_ricavi > 0 else 0)
            
            df_ch['% Commissione Media'] = df_ch.apply(
                lambda row: (row['Commissioni'] / row['Ricavi'] * 100) if row['Ricavi'] > 0 else 0, axis=1
            )

            st.markdown("##### 🧮 Dettaglio Performance per OTA")
            df_ch_display = df_ch[['channel_group', 'Ricavi', '% Ricavi', 'Commissioni', '% Commissione Media', 'Prenotazioni']].copy()
            df_ch_display = df_ch_display.sort_values('Ricavi', ascending=False)
            
            st.markdown(_html_table(
                df_ch_display,
                fmt={
                    'Ricavi':               '€ {:,.0f}',
                    '% Ricavi':             '{:.1f}%',
                    'Commissioni':          '€ {:,.0f}',
                    '% Commissione Media':  '{:.1f}%',
                }
            ), unsafe_allow_html=True)

            st.markdown("---")
            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                tot_ricavi_pie = df_ch['Ricavi'].sum()
                fig_pie = px.pie(df_ch, values='Ricavi', names='channel_group',
                                 title="Quota Ricavi per Canale",
                                 hole=0.52,
                                 color_discrete_sequence=[C_CY, C_TEAL, C_POS, C_WARN, C_STLY])
                fig_pie.update_traces(
                    textposition='outside',
                    textinfo='percent+label',
                    textfont_size=12,
                    hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>",
                    pull=[0.04]*len(df_ch),
                    marker=dict(line=dict(color='white', width=2)),
                )
                fig_pie.add_annotation(
                    text=f"<b>€{tot_ricavi_pie:,.0f}</b><br><span style='font-size:11px;color:#718096'>Totale</span>",
                    x=0.5, y=0.5, font_size=16, showarrow=False, align='center'
                )
                fig_pie.update_layout(**_fig_layout(
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05)
                ))
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_ch2:
                df_adr_sorted = df_ch.sort_values('ADR', ascending=True)
                fig_adr = px.bar(df_adr_sorted, x='ADR', y='channel_group', orientation='h',
                                 title="ADR per Canale (€)",
                                 text=df_adr_sorted['ADR'].apply(lambda x: f"€{x:,.0f}"))
                fig_adr.update_traces(
                    marker_color=C_CY, textposition='outside',
                    hovertemplate="<b>%{y}</b><br>ADR: €%{x:,.2f}<extra></extra>",
                    marker=dict(line=dict(width=0), cornerradius=6),
                )
                fig_adr.update_layout(**_fig_layout(showlegend=False, uniformtext_minsize=10, uniformtext_mode='hide'))
                fig_adr.update_xaxes(showgrid=True, gridcolor=_GRID)
                fig_adr.update_yaxes(showgrid=False)
                st.plotly_chart(fig_adr, use_container_width=True)
        else:
            st.info("⚠️ Nessun ricavo registrato per questo periodo, i grafici dei canali non sono disponibili.")

    with tab_costi:
        st.subheader(f"💼 {lbl_netto} per {lbl_unita}")
        if not df_cy_otb.empty and k['netto'] > 0:
            df_netto_apt = df_cy_otb.groupby('unit_id').agg(
                Lordo=('gross_revenue', 'sum'),
                Netto=('pm_net', 'sum'),
                Commissioni=('commission_amount', 'sum')
            ).reset_index()
            fig_netto = px.bar(df_netto_apt.sort_values('Netto', ascending=True),
                               x=['Netto', 'Commissioni'], y='unit_id', orientation='h',
                               barmode='stack', title=f"{lbl_netto} vs Commissioni per {lbl_unita} (€)",
                               color_discrete_map={'Netto': C_POS, 'Commissioni': C_NEG})
            fig_netto.update_traces(
                hovertemplate="<b>%{y}</b><br>%{fullData.name}: €%{x:,.0f}<extra></extra>",
                marker=dict(line=dict(width=0), cornerradius=6),
            )
            fig_netto.update_layout(**_fig_layout(uniformtext_minsize=9, uniformtext_mode='hide'))
            fig_netto.update_xaxes(showgrid=True, gridcolor=_GRID)
            fig_netto.update_yaxes(showgrid=False)
            st.plotly_chart(fig_netto, use_container_width=True)
        else:
            st.info("⚠️ Dati insufficienti per calcolare il Netto Property Manager in questo periodo.")

    with tab_revenue:
        st.divider()
        st.subheader("📈 Performance per Appartamento")
        if not df_cy_otb.empty:
            df_apt = df_cy_otb.groupby('unit_id').agg(
                Ricavi_Lordi=('gross_revenue', 'sum'),
                Notti=('nights', 'sum'),
                Netto_Real=('net_revenue', 'sum')
            ).reset_index()
            
            df_apt['Occupazione'] = (df_apt['Notti'] / giorni_nel_mese) * 100
            df_apt['Net_RevPAR_Real'] = df_apt['Netto_Real'] / giorni_nel_mese

            df_apt = df_apt.sort_values('Ricavi_Lordi', ascending=True)
            df_apt_occ = df_apt.sort_values('Occupazione', ascending=True)
            df_apt_revpar = df_apt.sort_values('Net_RevPAR_Real', ascending=True)

            col_g1, col_g2, col_g3 = st.columns(3)
            
            with col_g1:
                fig_r = px.bar(df_apt, x='Ricavi_Lordi', y='unit_id', orientation='h',
                               title="💰 Ricavi Lordi (€)",
                               text=df_apt['Ricavi_Lordi'].apply(lambda x: f"€{x:,.0f}"))
                fig_r.update_traces(
                    marker_color=C_CY, textposition='outside',
                    marker=dict(line=dict(width=0), cornerradius=6),
                    hovertemplate="<b>%{y}</b><br>Ricavi: €%{x:,.0f}<extra></extra>",
                )
                fig_r.update_layout(**_fig_layout(showlegend=False, uniformtext_minsize=9, uniformtext_mode='hide'))
                fig_r.update_xaxes(showgrid=True, gridcolor=_GRID)
                fig_r.update_yaxes(showgrid=False)
                st.plotly_chart(fig_r, use_container_width=True)

            with col_g2:
                fig_o = px.bar(df_apt_occ, x='Occupazione', y='unit_id', orientation='h',
                               title="🛏️ Occupazione (%)",
                               text=df_apt_occ['Occupazione'].apply(lambda x: f"{x:.1f}%"))
                fig_o.update_traces(
                    marker_color=C_TEAL, textposition='outside',
                    marker=dict(line=dict(width=0), cornerradius=6),
                    hovertemplate="<b>%{y}</b><br>Occupazione: %{x:.1f}%<extra></extra>",
                )
                fig_o.update_layout(**_fig_layout(showlegend=False, uniformtext_minsize=9, uniformtext_mode='hide'))
                fig_o.update_xaxes(showgrid=True, gridcolor=_GRID)
                fig_o.update_yaxes(showgrid=False)
                st.plotly_chart(fig_o, use_container_width=True)

            with col_g3:
                fig_revpar = px.bar(df_apt_revpar, x='Net_RevPAR_Real', y='unit_id', orientation='h',
                                    title="🏠 Net RevPAR Real (€)",
                                    text=df_apt_revpar['Net_RevPAR_Real'].apply(lambda x: f"€{x:,.1f}"))
                fig_revpar.update_traces(
                    marker_color=C_POS, textposition='outside',
                    marker=dict(line=dict(width=0), cornerradius=6),
                    hovertemplate="<b>%{y}</b><br>RevPAR: €%{x:,.1f}<extra></extra>",
                )
                fig_revpar.update_layout(**_fig_layout(showlegend=False, uniformtext_minsize=9, uniformtext_mode='hide'))
                fig_revpar.update_xaxes(showgrid=True, gridcolor=_GRID)
                fig_revpar.update_yaxes(showgrid=False)
                st.plotly_chart(fig_revpar, use_container_width=True)
        else:
            st.info("⚠️ Nessuna performance registrata per gli appartamenti in questo periodo.")

    with tab_revenue:
        st.divider()
        st.subheader(f"🌊 Booking Curve — {mes_nombre}")
        metrica_curve = st.radio("Visualizza per:", ["Ricavi Cumulati (€)", "Prenotazioni Cumulative"], horizontal=True)
        col_metrica = 'gross_revenue' if metrica_curve == "Ricavi Cumulati (€)" else 'id'
        agg_func = 'sum' if metrica_curve == "Ricavi Cumulati (€)" else 'count'

        curve_data = []

        if not df_ly_final.empty:
            df_ly_c = df_ly_final.groupby('booking_date')[col_metrica].agg(agg_func).reset_index().sort_values('booking_date')
            df_ly_c['Cumulato'] = df_ly_c[col_metrica].cumsum()
            df_ly_c['Anno'] = 'STLY (Storico Finale)'
            df_ly_c['Data Allineata'] = df_ly_c['booking_date'] + pd.DateOffset(years=1)
            curve_data.append(df_ly_c)

        if not df_cy_otb.empty:
            df_cy_c = df_cy_otb.groupby('booking_date')[col_metrica].agg(agg_func).reset_index().sort_values('booking_date')
            df_cy_c['Cumulato'] = df_cy_c[col_metrica].cumsum()
            df_cy_c['Anno'] = 'Anno Corrente (OTB)'
            df_cy_c['Data Allineata'] = df_cy_c['booking_date']
            curve_data.append(df_cy_c)

        if curve_data:
            df_curve = pd.concat(curve_data)
            fig_curve = px.line(
                df_curve, x='Data Allineata', y='Cumulato', color='Anno',
                line_shape='spline',
                color_discrete_map={
                    'Anno Corrente (OTB)':   C_CY,
                    'STLY (Storico Finale)': C_STLY,
                },
                title=f"Booking Curve — {metrica_curve.split()[0]} Cumulati"
            )
            fig_curve.update_traces(line=dict(width=2.5))
            for trace in fig_curve.data:
                if 'Corrente' in trace.name:
                    trace.fill = 'tozeroy'
                    trace.fillcolor = 'rgba(30,111,217,0.07)'

            fecha_str = fecha_hoy_pd.strftime('%Y-%m-%d')
            fig_curve.add_vline(x=fecha_str, line_dash="dash", line_color=C_NEG, line_width=1.5)
            fig_curve.add_annotation(
                x=fecha_str, y=1.02, yref="paper", text="📍 Oggi",
                showarrow=False, font=dict(color=C_NEG, size=12)
            )
            fig_curve.update_layout(
                **_fig_layout(legend_title_text='', hovermode='x unified', height=420)
            )
            fig_curve.update_xaxes(showgrid=True, gridcolor=_GRID, zeroline=False)
            fig_curve.update_yaxes(showgrid=True, gridcolor=_GRID, zeroline=False)
            st.plotly_chart(fig_curve, use_container_width=True)
        else:
            st.info("⚠️ Nessuna prenotazione disponibile per tracciare la curva in questo periodo.")

    with tab_costi:
        st.divider()
        st.subheader("📊 Costo per OTA & Margine per Canale")

        if df_cy_otb.empty or df_cy_otb['gross_revenue'].sum() == 0:
            st.info("⚠️ Nessun dato OTB disponibile per questo periodo.")
        else:
            # Costruisce tabella canali con scomposizione costi
            df_ota = df_cy_otb.groupby('channel_group').agg(
                Ricavi=('gross_revenue', 'sum'),
                Notti=('nights', 'sum'),
                Commissioni=('commission_amount', 'sum'),
                Prenotazioni=('id', 'count')
            ).reset_index()
            df_ota['ADR']          = df_ota.apply(lambda r: r['Ricavi'] / r['Notti'] if r['Notti'] > 0 else 0, axis=1)
            df_ota['Comm%']        = df_ota.apply(lambda r: r['Commissioni'] / r['Ricavi'] * 100 if r['Ricavi'] > 0 else 0, axis=1)
            df_ota['Comm/notte']   = df_ota['ADR'] * df_ota['Comm%'] / 100
            df_ota['Var/notte']    = var_per_night
            df_ota['Fissi/notte']  = fixed_per_night
            df_ota['Costo totale'] = df_ota['Comm/notte'] + var_per_night + fixed_per_night
            df_ota['Netto/notte']  = df_ota['ADR'] - df_ota['Costo totale']
            df_ota['Margine%']     = df_ota.apply(lambda r: r['Netto/notte'] / r['ADR'] * 100 if r['ADR'] > 0 else 0, axis=1)

            if not costos_configurados:
                st.warning("⚠️ Configura i costi fissi e variabili in questa tab per vedere i margini reali. Ora vengono mostrate solo commissioni OTA.")

            # ── Tabella dettaglio ──
            st.markdown("##### 🧮 Scomposizione Costi per Canale (€/notte)")
            cols_show = ['channel_group', 'ADR', 'Comm%', 'Comm/notte', 'Var/notte', 'Fissi/notte', 'Costo totale', 'Netto/notte', 'Margine%']
            df_display = df_ota[cols_show].sort_values('Margine%', ascending=False).rename(columns={'channel_group': 'Canale'})

            fmt_cost = {
                'ADR': '€{:.2f}', 'Comm/notte': '€{:.2f}', 'Var/notte': '€{:.2f}',
                'Fissi/notte': '€{:.2f}', 'Costo totale': '€{:.2f}', 'Netto/notte': '€{:.2f}',
                'Comm%': '{:.1f}%', 'Margine%': '{:.1f}%'
            }
            st.markdown(_html_table(
                df_display,
                fmt=fmt_cost,
                color_fn={
                    'Margine%':   lambda v: 'pos' if v >= 30 else ('warn' if v >= 10 else 'neg'),
                    'Netto/notte': lambda v: 'pos' if v > 0 else 'neg',
                }
            ), unsafe_allow_html=True)

            st.markdown("##### 📈 Margine Netto per Canale (€/notte)")
            col_l, col_r = st.columns(2)

            with col_l:
                fig_m = px.bar(
                    df_ota.sort_values('Margine%', ascending=True),
                    x='Margine%', y='channel_group', orientation='h',
                    title="Margine % per Canale",
                    text=df_ota.sort_values('Margine%', ascending=True)['Margine%'].apply(lambda x: f"{x:.1f}%"),
                    color='Margine%',
                    color_continuous_scale=[[0, C_NEG], [0.3, C_WARN], [1, C_POS]],
                )
                fig_m.update_traces(
                    textposition='outside',
                    marker=dict(line=dict(width=0), cornerradius=6),
                    hovertemplate="<b>%{y}</b><br>Margine: %{x:.1f}%<extra></extra>",
                )
                fig_m.update_layout(**_fig_layout(showlegend=False, coloraxis_showscale=False,
                                                   uniformtext_minsize=9, uniformtext_mode='hide'))
                fig_m.update_xaxes(showgrid=True, gridcolor=_GRID)
                fig_m.update_yaxes(showgrid=False)
                st.plotly_chart(fig_m, use_container_width=True)

            with col_r:
                fig_n = px.bar(
                    df_ota.sort_values('Netto/notte', ascending=True),
                    x='Netto/notte', y='channel_group', orientation='h',
                    title="Netto €/notte per Canale",
                    text=df_ota.sort_values('Netto/notte', ascending=True)['Netto/notte'].apply(lambda x: f"€{x:.2f}"),
                    color='Netto/notte',
                    color_continuous_scale=[[0, C_NEG], [0.3, C_WARN], [1, C_POS]],
                )
                fig_n.update_traces(
                    textposition='outside',
                    marker=dict(line=dict(width=0), cornerradius=6),
                    hovertemplate="<b>%{y}</b><br>Netto: €%{x:.2f}/notte<extra></extra>",
                )
                fig_n.update_layout(**_fig_layout(showlegend=False, coloraxis_showscale=False,
                                                   uniformtext_minsize=9, uniformtext_mode='hide'))
                fig_n.update_xaxes(showgrid=True, gridcolor=_GRID)
                fig_n.update_yaxes(showgrid=False)
                st.plotly_chart(fig_n, use_container_width=True)

            # ── Insight automatico ──
            if costos_configurados and len(df_ota) > 1:
                best  = df_ota.loc[df_ota['Margine%'].idxmax(), 'channel_group']
                worst = df_ota.loc[df_ota['Margine%'].idxmin(), 'channel_group']
                best_m  = df_ota['Margine%'].max()
                worst_m = df_ota['Margine%'].min()
                gap = best_m - worst_m
                st.info(
                    f"💡 **{best}** è il canale più redditizio ({best_m:.1f}% margine). "
                    f"**{worst}** è il meno redditizio ({worst_m:.1f}%). "
                    f"Gap di {gap:.1f} punti percentuali — considera di spingere il canale più profittevole."
                )

    with tab_mercato:
        st.divider()
        st.markdown("""
        <div style="
            text-align:center;
            padding: 3rem 2rem;
            background: linear-gradient(135deg, #F1F5F9 0%, #E2E8F0 100%);
            border-radius: 16px;
            border: 1.5px dashed #94A3B8;
            margin: 2rem 0;
        ">
            <div style="font-size: 3rem; margin-bottom: 0.75rem;">🚧</div>
            <h2 style="color: #1E293B; font-size: 1.5rem; margin: 0 0 0.5rem 0;">Analisi di Mercato — In Arrivo</h2>
            <p style="color: #64748B; font-size: 0.95rem; max-width: 480px; margin: 0 auto 1.25rem auto;">
                Il monitoraggio dei prezzi dei competitor su Booking.com sarà disponibile nella prossima versione.
                Potrai confrontare le tue tariffe con il mercato in tempo reale.
            </p>
            <div style="
                display: inline-block;
                background: #1E6FD9;
                color: white;
                padding: 0.35rem 1rem;
                border-radius: 999px;
                font-size: 0.78rem;
                font-weight: 600;
                letter-spacing: 0.05em;
                text-transform: uppercase;
            ">Prossimamente</div>
        </div>
        """, unsafe_allow_html=True)

    with tab_mercato:
        pass  # coming soon

    with tab_revenue:
        st.divider()
        st.subheader("📅 Segmentazione Weekday / Weekend")
        if not df_cy_otb.empty:
            all_days_month = pd.date_range(
                start=pd.Timestamp(fecha_hoy_pd.year, mes_interes, 1),
                periods=giorni_nel_mese
            )
            weekday_days_n = sum(1 for d in all_days_month if d.dayofweek <= 3)
            weekend_days_n = giorni_nel_mese - weekday_days_n

            df_seg = df_cy_otb.copy()
            df_seg['dow'] = df_seg['check_in_date'].dt.dayofweek
            df_seg['Segmento'] = df_seg['dow'].apply(
                lambda d: '🏖️ Weekend (Ven-Dom)' if d >= 4 else '💼 Weekday (Lun-Gio)'
            )
            seg = df_seg.groupby('Segmento').agg(
                Revenue=('gross_revenue', 'sum'),
                Notti=('nights', 'sum'),
                Commissioni=('commission_amount', 'sum'),
                Prenotazioni=('id', 'count'),
            ).reset_index()
            cap_map = {
                '💼 Weekday (Lun-Gio)': unita_cy * weekday_days_n,
                '🏖️ Weekend (Ven-Dom)': unita_cy * weekend_days_n,
            }
            seg['Capacita']  = seg['Segmento'].map(cap_map)
            seg['ADR']       = seg.apply(lambda r: r['Revenue'] / r['Notti'] if r['Notti'] > 0 else 0, axis=1)
            seg['Net ADR']   = seg.apply(lambda r: (r['Revenue'] - r['Commissioni']) / r['Notti'] if r['Notti'] > 0 else 0, axis=1)
            seg['Occupancy'] = seg.apply(lambda r: r['Notti'] / r['Capacita'] * 100 if r['Capacita'] > 0 else 0, axis=1)
            seg['RevPAR']    = seg.apply(lambda r: r['Revenue'] / r['Capacita'] if r['Capacita'] > 0 else 0, axis=1)

            sg1, sg2, sg3, sg4 = st.columns(4)
            for col_w, label in zip([sg1, sg2, sg3, sg4], ['ADR', 'Net ADR', 'Occupancy', 'RevPAR']):
                wd_val = seg[seg['Segmento'].str.contains('Weekday')][label].values
                we_val = seg[seg['Segmento'].str.contains('Weekend')][label].values
                wd = float(wd_val[0]) if len(wd_val) > 0 else 0
                we = float(we_val[0]) if len(we_val) > 0 else 0
                fmt = f"{we:.1f}%" if label == 'Occupancy' else f"€{we:,.2f}"
                delta = f"WD: €{wd:,.2f}" if label != 'Occupancy' else f"WD: {wd:.1f}%"
                col_w.metric(f"🏖️ Weekend — {label}", fmt, delta, delta_color="off")

            fig_seg = px.bar(
                seg, x='Segmento', y=['ADR', 'Net ADR', 'RevPAR'],
                barmode='group', title="ADR / Net ADR / RevPAR per Segmento (€)",
                color_discrete_map={'ADR': C_CY, 'Net ADR': C_TEAL, 'RevPAR': C_POS}
            )
            fig_seg.update_traces(marker=dict(line=dict(width=0), cornerradius=6))
            fig_seg.update_layout(**_fig_layout(uniformtext_minsize=9))
            fig_seg.update_xaxes(showgrid=False)
            fig_seg.update_yaxes(showgrid=True, gridcolor=_GRID)
            st.plotly_chart(fig_seg, use_container_width=True)

            if len(seg) == 2:
                adr_gap = abs(seg[seg['Segmento'].str.contains('Weekend')]['ADR'].values[0] -
                              seg[seg['Segmento'].str.contains('Weekday')]['ADR'].values[0])
                occ_we = seg[seg['Segmento'].str.contains('Weekend')]['Occupancy'].values[0]
                occ_wd = seg[seg['Segmento'].str.contains('Weekday')]['Occupancy'].values[0]
                if adr_gap < 10 and occ_we > occ_wd + 15:
                    st.warning(f"⚠️ Il weekend ha {occ_we-occ_wd:.0f}pp più occupancy del weekday ma solo €{adr_gap:.0f} di gap ADR — margine di aumento prezzi weekend non sfruttato.")
                elif adr_gap > 30:
                    st.success(f"✅ Buona differenziazione weekend/weekday: gap ADR €{adr_gap:.0f}.")
        else:
            st.info("Nessun dato OTB per la segmentazione.")

    with tab_revenue:
        st.divider()
        st.subheader(f"🎯 Forecast & Budget — {mes_nombre}")

        rev_stly_final  = df_ly_final['gross_revenue'].sum() if not df_ly_final.empty else 0
        notti_stly_final = df_ly_final['nights'].sum() if not df_ly_final.empty else 0
        rev_cy_otb      = k['rev']
        notti_cy_otb    = k['notti']

        # ── Forecast booking-curve ──
        # % del totale STLY già a libro nello stesso punto dell'anno scorso
        curve_pct = (k['rev_ly'] / rev_stly_final) if rev_stly_final > 0 else 1.0
        curve_pct = max(min(curve_pct, 1.0), 0.05)   # clamp 5%-100%
        rev_forecast = rev_cy_otb / curve_pct
        occ_forecast = (notti_cy_otb / curve_pct) / capacita_totale_cy * 100 if capacita_totale_cy > 0 else 0

        # ── Budget ──
        anno_sel = fecha_hoy_pd.year
        budget   = load_budget(USER_ID, anno_sel, mes_interes)
        bud_rev  = float(budget['target_revenue'])   if budget else None
        bud_occ  = float(budget['target_occupancy']) if budget else None
        bud_adr  = float(budget['target_adr'])       if budget else None

        # ── Metriche confronto ──
        c1, c2, c3 = st.columns(3)
        c1.metric("📈 Forecast Ricavi",   f"€{rev_forecast:,.0f}",
                  f"vs Budget: €{bud_rev:,.0f} ({(rev_forecast/bud_rev-1)*100:+.1f}%)" if bud_rev else "Budget non impostato")
        c2.metric("📊 Forecast Occupancy", f"{occ_forecast:.1f}%",
                  f"vs Budget: {bud_occ:.1f}%" if bud_occ else "Budget non impostato")
        c3.metric("🏷️ ADR attuale",        f"€{k['adr']:,.2f}",
                  f"vs Budget ADR: €{bud_adr:,.2f}" if bud_adr else "Budget non impostato")

        st.caption(f"Forecast basato sulla booking curve STLY: a questo punto dell'anno, lo STLY aveva il **{curve_pct*100:.0f}%** del totale già prenotato.")

        # ── Progress bar vs STLY e Budget ──
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pct_stly = (rev_cy_otb / rev_stly_final * 100) if rev_stly_final > 0 else 0
            st.markdown(f"**OTB vs Chiusura STLY:** {pct_stly:.1f}%")
            st.progress(min(pct_stly / 100, 1.0))
        with col_p2:
            if bud_rev:
                pct_bud = rev_forecast / bud_rev * 100
                color_label = "🟢" if pct_bud >= 95 else ("🟡" if pct_bud >= 80 else "🔴")
                st.markdown(f"**Forecast vs Budget:** {color_label} {pct_bud:.1f}%")
                st.progress(min(pct_bud / 100, 1.0))
            else:
                st.info("Imposta il budget mensile in ⚙️ Dati → Budget per vedere il confronto.")

        # ── Insight ──
        if bud_rev and rev_forecast < bud_rev * 0.85:
            gap = bud_rev - rev_forecast
            st.error(f"⚠️ **Gap Budget:** Il forecast indica un potenziale shortfall di **€{gap:,.0f}**. Considera azioni di yield o promozioni mirate.")
        elif bud_rev and rev_forecast >= bud_rev:
            st.success(f"✅ **Budget on track:** Il forecast supera il target di €{rev_forecast - bud_rev:,.0f}. Valuta di alzare i prezzi per massimizzare il margine.")
    
    with tab_mercato:
        pass  # coming soon
    
    with tab_costi:
        st.divider()
        st.header("💰 Analisi Margine Netto (Netto PM)")

        # 1. Recuperar propiedades del usuario
        res_props = supabase.table('properties').select('id, kross_unit_id').eq('user_id', USER_ID).execute()
        props_dict = {p['kross_unit_id']: p['id'] for p in res_props.data} if res_props.data else {}

        p_id = None
        if not props_dict:
            st.warning("⚠️ Carica prima le prenotazioni nella tab 'Gestione Dati'.")
        else:
            # 2. Selectores
            c1, c2 = st.columns([3, 1])
            with c1:
                prop_name = st.selectbox("Seleziona Proprietà", list(props_dict.keys()), key="sel_netto")
                p_id = props_dict[prop_name]
            with c2:
                anno = st.selectbox("Anno", [2024, 2025, 2026], index=2)

        st.divider()

        # 3. Descarga de datos y cálculo
        if p_id is None:
            st.info("Seleziona una proprietà per visualizzare l'analisi del margine.")
        if p_id is not None:
            with st.spinner("Calcolando i margini..."):
                res_res  = supabase.table('reservations').select('*').eq('property_id', p_id).execute()
                res_fix  = supabase.table('fixed_costs').select('*').eq('property_id', p_id).execute()
                res_var  = supabase.table('variable_costs').select('*').eq('property_id', p_id).execute()
                res_util = supabase.table('utility_bills').select('*').eq('property_id', p_id).execute()
                res_prop = supabase.table('properties').select('cleaning_fee').eq('id', p_id).execute()

            df_res  = pd.DataFrame(res_res.data)  if res_res.data  else pd.DataFrame()
            df_fix  = pd.DataFrame(res_fix.data)  if res_fix.data  else pd.DataFrame(columns=['amount','frequency','valid_to'])
            df_var  = pd.DataFrame(res_var.data)  if res_var.data  else pd.DataFrame(columns=['value','basis','valid_to'])
            df_util = pd.DataFrame(res_util.data) if res_util.data else pd.DataFrame(columns=['amount','period_from','period_to','category'])
            cleaning_fee_prop = float(res_prop.data[0].get('cleaning_fee') or 0) if res_prop.data else 0.0

            if not df_res.empty:
                fatturato, ota, variabili, fissi, netto = calculate_property_margins(df_res, df_fix, df_var, anno, df_util, cleaning_fee_prop)

                if not df_var.empty and (df_var['basis'] == 'per_guest').any():
                    st.caption("ℹ️ I costi 'per ospite' sono calcolati stimando 2 ospiti per prenotazione (dato non disponibile dal PMS).")

                st.divider()
                st.subheader("🎯 Calcolatore: Tariffa Minima e di Partenza")
                st.write("Usa i costi operativi attuali per definire i tuoi prezzi base.")
                
                # Costi strutturali annui
                costi_fissi_annuali = (
                    (df_fix[df_fix['frequency'] == 'yearly']['amount'].sum() +
                     df_fix[df_fix['frequency'] == 'monthly']['amount'].sum() * 12)
                    if not df_fix.empty else 0.0
                )
                # Utenze: somma delle bollette disponibili (stima annua)
                if not df_util.empty:
                    df_util['period_to'] = pd.to_datetime(df_util['period_to'], errors='coerce')
                    _cutoff_12m = pd.Timestamp.now() - pd.DateOffset(months=12)
                    costi_fissi_annuali += float(df_util[df_util['period_to'] >= _cutoff_12m]['amount'].sum())
                costi_var_prenotazione = df_var[df_var['basis'] == 'per_booking']['value'].sum() if not df_var.empty else 0.0
                costi_var_notte = df_var[df_var['basis'] == 'per_night']['value'].sum() if not df_var.empty else 0.0

                col_calc1, col_calc2 = st.columns(2)
                
                with col_calc1:
                    giorni_apertura = st.number_input("Giorni di apertura all'anno", min_value=30, max_value=365, value=365)
                    los_medio = st.number_input("Estancia Media stimata (LOS)", min_value=1.0, value=3.0, step=0.5)
                    
                with col_calc2:
                    comm_ota = st.number_input("Commissione Media OTA (%)", min_value=0.0, max_value=30.0, value=15.0)
                    margine_obiettivo = st.number_input("Margine di Profitto Desiderato (%)", min_value=0.0, value=30.0)

                # La Matemática
                costo_fisso_notte = costi_fissi_annuali / giorni_apertura if giorni_apertura > 0 else 0
                costo_variabile_notte = (costi_var_prenotazione / los_medio) + costi_var_notte if los_medio > 0 else 0
                costo_base_notte = costo_fisso_notte + costo_variabile_notte
                
                # Bottom Rate (Evita divisione per zero se comm_ota è 100)
                tariffa_minima = costo_base_notte / (1 - (comm_ota / 100)) if comm_ota < 100 else 0
                
                # Starting Rate
                tariffa_partenza = tariffa_minima * (1 + (margine_obiettivo / 100))

                st.info(f"💡 **Il tuo Costo Base Reale è di €{costo_base_notte:.2f} a notte.** (Senza contare le commissioni OTA).")
                
                k_min, k_part = st.columns(2)
                k_min.metric("🚨 Tariffa Minima (Bottom Rate)", f"€{tariffa_minima:.2f}", "Punto di pareggio (Netto zero)", delta_color="off")
                k_part.metric("🚀 Tariffa di Partenza (BAR)", f"€{tariffa_partenza:.2f}", f"+{margine_obiettivo}% Margine", delta_color="normal")
                
                # 4. KPIs
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Fatturato Lordo", f"€{fatturato:,.0f}")
                m2.metric("Commissioni OTA", f"€{abs(ota):,.0f}") 
                m3.metric("Costi Operativi", f"€{abs(variabili + fissi):,.0f}")
                
                margin_pct = (netto / fatturato * 100) if fatturato > 0 else 0
                m4.metric("Netto PM", f"€{netto:,.0f}", f"{margin_pct:.1f}% Margine")

                # 5. Gráfico Waterfall
                fig = go.Figure(go.Waterfall(
                    orientation = "v",
                    measure = ["relative", "relative", "relative", "relative", "total"],
                    x = ["Fatturato Lordo", "Comm. OTA", "Costi Variabili", "Costi Fissi", "Netto PM"],
                    text = [f"€{fatturato:,.0f}", f"-€{abs(ota):,.0f}", f"-€{abs(variabili):,.0f}", f"-€{abs(fissi):,.0f}", f"€{netto:,.0f}"],
                    y = [fatturato, ota, variabili, fissi, netto],
                    textposition = "outside",
                    connector = {"line": {"color": _GRID, "width": 1}},
                    increasing  = {"marker": {"color": C_CY}},
                    decreasing  = {"marker": {"color": C_NEG}},
                    totals      = {"marker": {"color": C_POS if netto > 0 else C_NEG}}
                ))

                fig.update_layout(
                    **_fig_layout(
                        title=f"Cascata del Margine: {prop_name} ({anno})",
                        height=460,
                    )
                )
                fig.update_xaxes(showgrid=False)
                fig.update_yaxes(showgrid=True, gridcolor=_GRID)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Nessuna prenotazione trovata per {prop_name} nell'anno {anno}.")

    with tab_strategia:
        st.subheader(f"📅 Calendario Occupancy — {mes_nombre}")
        st.caption("Heatmap degli arrivi per giorno del mese. Aiuta a identificare date deboli dove intervenire con i prezzi.")

        first_of_month = pd.Timestamp(fecha_hoy_pd.year, mes_interes, 1)
        first_dow = first_of_month.dayofweek  # 0=Lun

        # Arrivi per giorno del mese (proxy veloce per domanda)
        if not df_cy_attive.empty:
            arr = (df_cy_attive[df_cy_attive['check_in_date'].dt.month == mes_interes]
                   .groupby(df_cy_attive['check_in_date'].dt.day)
                   .agg(n_arr=('id', 'count'), rev=('gross_revenue', 'sum'))
                   .reset_index())
            arr.columns = ['day', 'n_arr', 'rev']
        else:
            arr = pd.DataFrame(columns=['day', 'n_arr', 'rev'])

        # Price suggestions per il mese selezionato
        try:
            sug_res = supabase.table('price_suggestions').select('date_from, date_to, suggested_price, status, scenario') \
                .eq('user_id', USER_ID).in_('status', ['pending', 'approved']).execute()
            df_sug = pd.DataFrame(sug_res.data) if sug_res.data else pd.DataFrame()
        except Exception:
            df_sug = pd.DataFrame()

        # Costruisco griglia calendario 7×6
        DAYS_IT = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']
        n_weeks = math.ceil((giorni_nel_mese + first_dow) / 7)
        z    = [[None]*n_weeks for _ in range(7)]
        text = [['']*n_weeks for _ in range(7)]

        for day_num in range(1, giorni_nel_mese + 1):
            dow  = (first_dow + day_num - 1) % 7
            week = (first_dow + day_num - 1) // 7
            arr_row = arr[arr['day'] == day_num]
            n = int(arr_row['n_arr'].iloc[0]) if not arr_row.empty else 0
            occ = min(n / unita_cy * 100, 100) if unita_cy > 0 else 0
            z[dow][week] = occ

            d_ts = pd.Timestamp(fecha_hoy_pd.year, mes_interes, day_num)
            sug_price = None
            if not df_sug.empty:
                mask = (pd.to_datetime(df_sug['date_from']) <= d_ts) & (pd.to_datetime(df_sug['date_to']) >= d_ts)
                sug_match = df_sug[mask]
                if not sug_match.empty:
                    sug_price = sug_match.iloc[0]['suggested_price']
                    status_icon = "✅" if sug_match.iloc[0]['status'] == 'approved' else "⏳"

            cell = f"<b>{day_num}</b><br>{occ:.0f}% occ"
            if sug_price:
                cell += f"<br>{status_icon}€{sug_price:.0f}"
            text[dow][week] = cell

        colorscale = [[0.0, '#FEE2E2'], [0.4, '#FEF3C7'], [0.7, '#D1FAE5'], [1.0, '#059669']]
        fig_cal = go.Figure(go.Heatmap(
            z=z, x=[f"Sett {i+1}" for i in range(n_weeks)],
            y=DAYS_IT, colorscale=colorscale, showscale=True,
            zmin=0, zmax=100,
            colorbar=dict(title='Occ%', thickness=12, len=0.8),
            hovertemplate='%{text}<extra></extra>',
            text=text,
        ))
        for day_num in range(1, giorni_nel_mese + 1):
            dow  = (first_dow + day_num - 1) % 7
            week = (first_dow + day_num - 1) // 7
            arr_row = arr[arr['day'] == day_num]
            n = int(arr_row['n_arr'].iloc[0]) if not arr_row.empty else 0
            occ = min(n / unita_cy * 100, 100) if unita_cy > 0 else 0
            fig_cal.add_annotation(
                x=week, y=dow,
                text=f"<b>{day_num}</b><br>{occ:.0f}%",
                showarrow=False, font=dict(size=10, color='#1A202C'),
                xref='x', yref='y'
            )
        fig_cal.update_layout(
            **_fig_layout(height=340, yaxis=dict(autorange='reversed')),
        )
        fig_cal.update_xaxes(showgrid=False)
        fig_cal.update_yaxes(showgrid=False)
        st.plotly_chart(fig_cal, use_container_width=True)

        days_below_50 = sum(
            1 for d in range(1, giorni_nel_mese+1)
            if (arr[arr['day']==d]['n_arr'].values[0] if not arr[arr['day']==d].empty else 0) / max(unita_cy,1) < 0.5
        )
        if days_below_50 > 0:
            st.warning(f"⚠️ **{days_below_50} giorni** con occupancy stimata sotto il 50% — considera suggerimenti prezzi per quelle date.")

        st.divider()

    with tab_strategia:
        st.subheader("🤖 Cervello Strategico — Analisi IA")
        if bottom_rate > 0:
            st.success(f"🔒 **Bottom Rate attivo:** €{bottom_rate:.2f}/notte — l'IA non suggerirà mai strategie sotto questa soglia.")
        else:
            st.warning("⚠️ Bottom Rate non calcolato — configura i costi in 'Costi & Margini' per attivare il vincolo matematico.")
        if st.button("✨ Genera Analisi IA"):
            if not API_KEY:
                st.error("⚠️ Configura GEMINI_API_KEY in .streamlit/secrets.toml")
            else:
                with st.spinner("Analisi in corso..."):
                    try:
                        risposta = model.generate_content(_prompt_ia)
                        st.markdown(risposta.text)
                    except Exception as e:
                        st.error(f"Errore IA: {e}")

    with tab_strategia:
        st.divider()
        st.subheader("💡 Suggerimenti Prezzi — Human-in-the-Loop")
        st.caption("Genera suggerimenti basati sul Bottom Rate, approva o rifiuta con un clic. In Fase B il prezzo verrà inviato automaticamente al PMS.")

        MARGINI = {"Conservativo": 1.20, "Moderato": 1.35, "Aggressivo": 1.50}

        # --- SEZIONE 1: GENERA SUGGERIMENTO ---
        st.markdown("### 📝 Genera Nuovo Suggerimento")
        with st.form("form_suggerimento"):
            c1, c2, c3 = st.columns(3)
            with c1:
                apt_sug = st.selectbox("Appartamento", tutti_apt)
            with c2:
                data_da = st.date_input("Dal", value=date.today())
                data_a  = st.date_input("Al",  value=date.today() + datetime.timedelta(days=6))
            with c3:
                scenario_sug   = st.selectbox("Scenario", list(MARGINI.keys()))
                prezzo_attuale = st.number_input("Prezzo attuale (€/notte)", min_value=0.0, step=5.0,
                                                 value=round(float(k['adr']), 0) if k['adr'] > 0 else 80.0)

            margine = MARGINI[scenario_sug]
            if bottom_rate > 0:
                prezzo_suggerito = round(max(bottom_rate * margine, prezzo_attuale), 0)
                br_label = f"Bottom Rate €{bottom_rate:.0f} × {margine:.2f}"
            else:
                prezzo_suggerito = round(prezzo_attuale * margine, 0)
                br_label = "⚠️ Bottom Rate non configurato — moltiplicatore sul prezzo attuale"

            comp_ctx = ""
            if not df_market.empty:
                mask_d = (df_market['stay_date'] >= pd.Timestamp(data_da)) & (df_market['stay_date'] <= pd.Timestamp(data_a))
                comp_avg_sug = df_market[mask_d]['price'].mean() if not df_market[mask_d].empty else None
                if comp_avg_sug:
                    comp_ctx = f" | 🕵️ Mercato: €{comp_avg_sug:.0f}/notte"

            st.info(f"💰 **Prezzo suggerito: €{prezzo_suggerito:.0f}/notte** | {br_label}{comp_ctx}")
            motivo_sug = st.text_area("Note / Motivazione (opzionale)", placeholder="Es: Weekend lungo, alta domanda prevista...")
            submitted_sug = st.form_submit_button("💾 Salva Suggerimento", use_container_width=True, type="primary")

            if submitted_sug:
                if data_a <= data_da:
                    st.error("La data di fine deve essere successiva alla data di inizio.")
                else:
                    try:
                        supabase.table('price_suggestions').insert({
                            "user_id":              USER_ID,
                            "property_name":        apt_sug,
                            "date_from":            str(data_da),
                            "date_to":              str(data_a),
                            "current_price":        float(prezzo_attuale),
                            "suggested_price":      float(prezzo_suggerito),
                            "scenario":             scenario_sug,
                            "reason":               motivo_sug or f"Scenario {scenario_sug} — {int((margine-1)*100)}% margine su Bottom Rate",
                            "bottom_rate_snapshot": float(bottom_rate),
                            "status":               "pending"
                        }).execute()
                        st.success("✅ Suggerimento salvato!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore nel salvataggio: {e}")

        st.divider()

        # --- SEZIONE 2: IN ATTESA DI DECISIONE ---
        st.markdown("### ⏳ In Attesa di Decisione")
        try:
            res_pending = supabase.table('price_suggestions').select('*') \
                .eq('user_id', USER_ID).eq('status', 'pending') \
                .order('created_at', desc=True).execute()
        except Exception as e:
            st.error(f"Errore caricamento suggerimenti: {e}")
            res_pending = None

        if res_pending and res_pending.data:
            for sug in res_pending.data:
                with st.container(border=True):
                    ca, cb, cc, cd, ce, cf = st.columns([2.5, 2, 1, 1, 1, 1])
                    ca.markdown(f"**{sug['property_name']}**  \n📅 {sug['date_from']} → {sug['date_to']}")
                    reason_short = (sug['reason'][:45] + '…') if sug.get('reason') and len(sug['reason']) > 45 else sug.get('reason', '')
                    cb.markdown(f"*{sug['scenario']}*  \n{reason_short}")
                    cc.metric("Attuale", f"€{sug['current_price']:.0f}")
                    delta_pct = f"{((sug['suggested_price']/sug['current_price'])-1)*100:+.0f}%" if sug.get('current_price', 0) > 0 else ""
                    cd.metric("Suggerito", f"€{sug['suggested_price']:.0f}", delta_pct)
                    if ce.button("✅ Approva", key=f"app_{sug['id']}", use_container_width=True, type="primary"):
                        supabase.table('price_suggestions').update({
                            "status": "approved",
                            "decided_at": datetime.datetime.utcnow().isoformat()
                        }).eq('id', sug['id']).execute()
                        st.rerun()
                    if cf.button("❌ Rifiuta", key=f"rif_{sug['id']}", use_container_width=True):
                        supabase.table('price_suggestions').update({
                            "status": "rejected",
                            "decided_at": datetime.datetime.utcnow().isoformat()
                        }).eq('id', sug['id']).execute()
                        st.rerun()
        else:
            st.info("Nessun suggerimento in attesa. Generane uno nuovo dalla sezione sopra.")

        st.divider()

        # --- SEZIONE 3: STORICO DECISIONI ---
        with st.expander("📋 Storico Decisioni", expanded=False):
            try:
                res_hist = supabase.table('price_suggestions').select('*') \
                    .eq('user_id', USER_ID).neq('status', 'pending') \
                    .order('decided_at', desc=True).limit(50).execute()
            except Exception:
                res_hist = None
            if res_hist and res_hist.data:
                df_hist = pd.DataFrame(res_hist.data)[
                    ['property_name', 'date_from', 'date_to', 'scenario',
                     'current_price', 'suggested_price', 'status', 'decided_at']
                ]
                df_hist.columns = ['Proprietà', 'Dal', 'Al', 'Scenario', 'Att. (€)', 'Sug. (€)', 'Decisione', 'Deciso il']
                df_hist['Decisione'] = df_hist['Decisione'].map({'approved': '✅ Approvato', 'rejected': '❌ Rifiutato'})
                df_hist['Deciso il'] = pd.to_datetime(df_hist['Deciso il']).dt.strftime('%d/%m/%Y %H:%M')
                st.dataframe(df_hist, use_container_width=True, hide_index=True)
            else:
                st.info("Nessuna decisione ancora registrata.")

    with tab_dati:
        st.header("⚙️ Gestione Dati")
        
        # --- SEZIONE 1: SINCRONIZZAZIONE PRENOTAZIONI ---
        st.subheader("☁️ Aggiorna il Database")

        pms_mode = st.radio("Seleziona il tuo PMS:", ["KrossBooking", "Altro PMS"], horizontal=True)

        # ── Helper: upsert normalizzato (condiviso da entrambi i flussi) ──
        def _upsert_reservations(df_total):
            unique_props = df_total['unit_id'].dropna().unique()
            prop_map = {}
            for prop_name in unique_props:
                res = supabase.table('properties').upsert(
                    {"user_id": USER_ID, "kross_unit_id": prop_name},
                    on_conflict='user_id, kross_unit_id'
                ).execute()
                prop_map[prop_name] = res.data[0]['id']

            records = []
            for _, row in df_total.iterrows():
                records.append({
                    "user_id":             USER_ID,
                    "property_id":         prop_map.get(row['unit_id']),
                    "pms_reservation_id":  str(row['pms_reservation_id']),
                    "check_in_date":       row['check_in_date'].strftime('%Y-%m-%d') if pd.notnull(row['check_in_date']) else None,
                    "check_out_date":      row['check_out_date'].strftime('%Y-%m-%d') if pd.notnull(row.get('check_out_date')) else None,
                    "booking_date":        row['booking_date'].strftime('%Y-%m-%d') if pd.notnull(row.get('booking_date')) else None,
                    "gross_revenue":       float(row['gross_revenue']),
                    "commission_amount":   float(row['commission_amount']),
                    "net_revenue":         float(row['net_revenue']),
                    "pm_net":              float(row['pm_net']),
                    "owner_net":           float(row['owner_net']),
                    "nights":              int(row['nights']),
                    "lead_time":           int(row['lead_time']),
                    "status":              str(row['status']),
                    "channel":             str(row.get('channel', '') or ''),
                    "channel_group":       str(row['channel_group']) if pd.notnull(row.get('channel_group')) else 'Altro',
                })

            chunk_size = 500
            total_chunks = math.ceil(len(records) / chunk_size)
            bar = st.progress(0, text="Caricamento in corso...")
            for i in range(total_chunks):
                chunk = records[i * chunk_size:(i + 1) * chunk_size]
                supabase.table('reservations').upsert(chunk, on_conflict='user_id, pms_reservation_id').execute()
                bar.progress((i + 1) / total_chunks, text=f"Lotto {i+1}/{total_chunks} caricato...")
            return len(records)

        # ════════════════════════════════════
        # FLUSSO A — KrossBooking (invariato)
        # ════════════════════════════════════
        if pms_mode == "KrossBooking":
            st.info("Carica l'ultimo export di KrossBooking. Il sistema aggiungerà le nuove prenotazioni e aggiornerà quelle modificate.")
            file_upload = st.file_uploader("📂 Carica file Excel KrossBooking", type=['xlsx'])
            if file_upload:
                if st.button("🚀 Sincronizza nel Cloud"):
                    with st.spinner("Analisi e caricamento in corso..."):
                        df_limpio, df_cancellate = load_and_clean_krossbooking(file_upload)
                        dfs = [d for d in [df_limpio, df_cancellate] if d is not None and not d.empty]
                        if dfs:
                            df_total = pd.concat(dfs, ignore_index=True)
                            df_total['pms_reservation_id'] = df_total['id'].astype(str)
                            try:
                                n = _upsert_reservations(df_total)
                                st.cache_data.clear()
                                st.success(f"✅ Sincronizzazione completata! ({n} record analizzati, incluse cancellazioni).")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore durante l'aggiornamento: {e}")
                        else:
                            st.warning("Il file caricato non contiene dati validi.")

        # ════════════════════════════════════
        # FLUSSO B — Altro PMS (parser generico)
        # ════════════════════════════════════
        else:
            st.info("Carica un export Excel da qualsiasi PMS. La prima volta configurerai il mapping delle colonne — verrà salvato per i prossimi upload.")

            pms_name = st.text_input("Nome PMS (es. Mews, Opera, Beds24, ecc.)", placeholder="Il tuo PMS")
            file_upload_gen = st.file_uploader("📂 Carica file Excel", type=['xlsx', 'xls'], key="gen_upload")

            if file_upload_gen and pms_name:
                df_raw = pd.read_excel(file_upload_gen)
                raw_cols = list(df_raw.columns.astype(str))
                opts = ["(Non mappare)"] + raw_cols

                # Cerca mapping salvato per questo PMS
                saved_res = supabase.table('pms_mappings').select('mapping') \
                    .eq('user_id', USER_ID).eq('pms_name', pms_name).execute()
                saved_mapping = saved_res.data[0]['mapping'] if saved_res.data else {}

                if saved_mapping:
                    st.success(f"✅ Mapping '{pms_name}' trovato — precompilato. Verifica e conferma.")
                else:
                    st.warning("Nessun mapping salvato per questo PMS. Configura le colonne qui sotto.")

                with st.expander("🗺️ Configura Mapping Colonne", expanded=not bool(saved_mapping)):
                    new_mapping = {}
                    col_a, col_b = st.columns(2)
                    for idx, (field, label) in enumerate(FIELD_LABELS.items()):
                        container = col_a if idx % 2 == 0 else col_b
                        saved_val = saved_mapping.get(field, "(Non mappare)")
                        default_idx = opts.index(saved_val) if saved_val in opts else 0
                        chosen = container.selectbox(label, opts, index=default_idx, key=f"gmap_{field}")
                        new_mapping[field] = chosen if chosen != "(Non mappare)" else None

                # Validazione
                errors = validate_mapping(new_mapping)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    col_prev, col_load = st.columns(2)

                    if col_prev.button("👁️ Anteprima (prime 5 righe)"):
                        try:
                            df_norm = apply_mapping(df_raw, new_mapping)
                            st.dataframe(df_norm.head(5), use_container_width=True)
                            st.caption(f"{len(df_norm)} prenotazioni valide trovate nel file.")
                        except Exception as e:
                            st.error(f"Errore nell'anteprima: {e}")

                    if col_load.button("🚀 Carica & Salva Mapping", type="primary"):
                        with st.spinner("Normalizzazione e caricamento in corso..."):
                            try:
                                # Salva mapping per riuso futuro
                                supabase.table('pms_mappings').upsert(
                                    {"user_id": USER_ID, "pms_name": pms_name, "mapping": new_mapping},
                                    on_conflict="user_id,pms_name"
                                ).execute()

                                df_norm = apply_mapping(df_raw, new_mapping)
                                if df_norm.empty:
                                    st.warning("Nessuna prenotazione valida trovata dopo la normalizzazione. Verifica il mapping.")
                                else:
                                    n = _upsert_reservations(df_norm)
                                    st.cache_data.clear()
                                    st.success(f"✅ {n} prenotazioni caricate da '{pms_name}'. Mapping salvato per i prossimi upload.")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Errore: {e}")
            elif file_upload_gen and not pms_name:
                st.warning("Inserisci il nome del PMS per salvare il mapping.")
        
        st.divider()

        # --- SEZIONE 2: GESTIONE COMPETITOR ---
        st.subheader("🕵️ Gestione Competitor")
        st.caption("Aggiungi gli hotel concorrenti che vuoi monitorare. Usa l'URL della pagina su Booking.com.")

        res_comp_list = supabase.table("competitors").select("id, name, booking_url") \
            .eq("user_id", USER_ID).order("name").execute()

        if res_comp_list.data:
            for comp in res_comp_list.data:
                ca, cb, cc = st.columns([2, 5, 1])
                ca.markdown(f"**{comp['name']}**")
                cb.caption(comp['booking_url'][:70] + "…" if len(comp['booking_url']) > 70 else comp['booking_url'])
                if cc.button("🗑️", key=f"del_comp_{comp['id']}"):
                    supabase.table("competitors").delete().eq("id", comp['id']).execute()
                    st.rerun()
        else:
            st.info("Nessun competitor ancora registrato.")

        with st.form("form_add_competitor"):
            cn1, cn2 = st.columns(2)
            new_comp_name = cn1.text_input("Nome hotel competitor", placeholder="Hotel Bellavista")
            new_comp_url  = cn2.text_input("URL Booking.com", placeholder="https://www.booking.com/hotel/it/...")
            if st.form_submit_button("➕ Aggiungi Competitor"):
                if not new_comp_name or not new_comp_url:
                    st.error("Inserisci sia il nome che l'URL.")
                elif "booking.com" not in new_comp_url:
                    st.error("L'URL deve essere una pagina Booking.com.")
                else:
                    supabase.table("competitors").insert({
                        "user_id": USER_ID,
                        "name": new_comp_name,
                        "booking_url": new_comp_url
                    }).execute()
                    st.success(f"✅ '{new_comp_name}' aggiunto!")
                    st.rerun()

        st.divider()

        # --- SEZIONE 3: BUDGET ANNUALE ---
        st.subheader("🎯 Budget Annuale")
        st.caption("Imposta i target mensili di Revenue, Occupancy e ADR. Verranno usati nella sezione Forecast.")

        anno_budget = st.selectbox("Anno", [fecha_hoy_pd.year, fecha_hoy_pd.year + 1], key="anno_budget_sel")
        mese_budget = st.selectbox("Mese", range(1, 13), format_func=lambda x: MESI_IT[x-1], key="mese_budget_sel")

        existing_bud = load_budget(USER_ID, anno_budget, mese_budget)

        with st.form("form_budget"):
            bc1, bc2, bc3 = st.columns(3)
            bud_rev_in  = bc1.number_input("Target Revenue (€)", min_value=0.0, step=1000.0,
                                            value=float(existing_bud['target_revenue']) if existing_bud else 0.0)
            bud_occ_in  = bc2.number_input("Target Occupancy (%)", min_value=0.0, max_value=100.0, step=1.0,
                                            value=float(existing_bud['target_occupancy']) if existing_bud else 0.0)
            bud_adr_in  = bc3.number_input("Target ADR (€)", min_value=0.0, step=5.0,
                                            value=float(existing_bud['target_adr']) if existing_bud else 0.0)
            bud_note    = st.text_input("Note (opzionale)", value=existing_bud.get('notes', '') if existing_bud else "")

            if st.form_submit_button("💾 Salva Budget", type="primary"):
                try:
                    supabase.table('monthly_budget').upsert({
                        "user_id": USER_ID, "year": anno_budget, "month": mese_budget,
                        "target_revenue": bud_rev_in, "target_occupancy": bud_occ_in,
                        "target_adr": bud_adr_in, "notes": bud_note
                    }, on_conflict="user_id,year,month").execute()
                    st.cache_data.clear()
                    st.success(f"✅ Budget {MESI_IT[mese_budget-1]} {anno_budget} salvato!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")

        # Tabella riepilogo anno
        with st.expander(f"📋 Riepilogo Budget {anno_budget}", expanded=False):
            bud_year = load_budget_year(USER_ID, anno_budget)
            if bud_year:
                df_bud = pd.DataFrame(bud_year)[['month', 'target_revenue', 'target_occupancy', 'target_adr']]
                df_bud['month'] = df_bud['month'].apply(lambda m: MESI_IT[m-1])
                df_bud.columns = ['Mese', 'Revenue (€)', 'Occupancy (%)', 'ADR (€)']
                st.markdown(_html_table(
                    df_bud,
                    fmt={'Revenue (€)': '€{:,.0f}', 'Occupancy (%)': '{:.1f}%', 'ADR (€)': '€{:.0f}'}
                ), unsafe_allow_html=True)
                tot = sum(b['target_revenue'] for b in bud_year)
                st.metric("Totale Revenue Budget Annuo", f"€{tot:,.0f}")
            else:
                st.info("Nessun budget impostato per quest'anno.")

        st.divider()

        # --- SEZIONE 4: CONFIGURAZIONE COSTI PERMANENTI ---
        st.subheader("⚙️ Configurazione Costi")
        st.caption("Configura una sola volta i costi per ogni unità — vengono applicati automaticamente a tutte le prenotazioni future. Se aggiorni una categoria già esistente, il vecchio valore viene storicizzato.")

        _FISSI_CAT = [
            "IMU", "TARI", "Assicurazione", "Affitto",
            "Internet / WiFi", "Pulizie comuni", "Manutenzione", "Altra spesa fissa",
        ]
        _UTIL_CAT  = ["Luce", "Gas", "Acqua", "Condominio", "Altra utenza"]
        _VAR_CAT = {
            "cleaning":  "🧹 Pulizia appartamento",
            "laundry":   "👕 Lavanderia / Biancheria",
            "amenities": "🎁 Kit benvenuto / Dotazioni",
            "other":     "🔧 Altro costo operativo",
        }
        _VAR_LABELS = list(_VAR_CAT.values())
        _VAR_KEYS   = list(_VAR_CAT.keys())

        res_props_c = supabase.table('properties').select('id, kross_unit_id').eq('user_id', USER_ID).execute()
        props_c     = {p['kross_unit_id']: p['id'] for p in res_props_c.data} if res_props_c.data else {}

        if not props_c:
            st.info("Carica un file di prenotazioni per registrare le tue proprietà prima di configurare i costi.")
        else:
            prop_c_nome = st.selectbox("🏠 Unità:", list(props_c.keys()), key="prop_cost_sel")
            prop_c_id   = props_c[prop_c_nome]

            # Carica costi attivi e cleaning fee per questa proprietà
            _rfix  = supabase.table('fixed_costs').select('*').eq('property_id', prop_c_id).is_('valid_to', 'null').execute()
            _rvar  = supabase.table('variable_costs').select('*').eq('property_id', prop_c_id).is_('valid_to', 'null').execute()
            _rutil = supabase.table('utility_bills').select('*').eq('property_id', prop_c_id).order('period_to', desc=True).limit(8).execute()
            _rprop = supabase.table('properties').select('cleaning_fee').eq('id', prop_c_id).execute()
            df_fix_c  = pd.DataFrame(_rfix.data)  if _rfix.data  else pd.DataFrame()
            df_var_c  = pd.DataFrame(_rvar.data)  if _rvar.data  else pd.DataFrame()
            df_util_c = pd.DataFrame(_rutil.data) if _rutil.data else pd.DataFrame()
            current_cf = float(_rprop.data[0].get('cleaning_fee') or 0) if _rprop.data else 0.0

            # ── Cleaning fee (ricavo da guest, non incluso nel PMS) ──
            with st.expander(f"🧹 Quota Pulizie addebitata al Guest — attuale: €{current_cf:.2f}/soggiorno", expanded=(current_cf == 0)):
                st.caption("Questa quota viene aggiunta al ricavo lordo nel calcolo del margine (non è un costo, è un ricavo non tracciato dal PMS).")
                with st.form("form_cleaning_fee"):
                    new_cf = st.number_input("Importo per soggiorno (€):", min_value=0.0, value=current_cf, step=5.0, format="%.2f")
                    if st.form_submit_button("💾 Aggiorna", type="primary"):
                        try:
                            supabase.table('properties').update({"cleaning_fee": float(new_cf)}).eq('id', prop_c_id).execute()
                            st.success(f"✅ Quota pulizie aggiornata a €{new_cf:.2f}/soggiorno.")
                            st.cache_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Errore: {e}")

            cl_left, cl_right = st.columns([3, 2])

            # ── PANNELLO SINISTRA: riepilogo costi attivi ──
            with cl_left:
                st.markdown("##### 📋 Costi configurati per questa unità")

                # ── Spese strutturali ──
                st.caption("**🏛️ Spese Strutturali** — IMU, TARI, assicurazione, affitto…")
                if not df_fix_c.empty:
                    _freq_map = {'monthly': 'Mensile', 'yearly': 'Annuale'}
                    for _, _r in df_fix_c.iterrows():
                        _ca, _cb, _cc, _cd = st.columns([2.5, 1.3, 1.1, 0.5])
                        _ca.markdown(f"**{_r['category']}**")
                        _cb.caption(f"€ {float(_r['amount']):,.2f}")
                        _cc.caption(_freq_map.get(_r['frequency'], _r['frequency']))
                        if _cd.button("🗑️", key=f"del_fix_{_r['id']}", help="Elimina"):
                            try:
                                supabase.table('fixed_costs').delete().eq('id', _r['id']).execute()
                                st.cache_data.clear(); st.rerun()
                            except Exception as _e:
                                st.error(f"Errore: {_e}")
                else:
                    st.info("Nessuna spesa strutturale configurata.")

                st.divider()

                # ── Bollette utenze ──
                st.caption("**⚡ Bollette Utenze** — ultime 8 inserite (luce, gas, acqua…)")
                if not df_util_c.empty:
                    for _, _r in df_util_c.iterrows():
                        _ca, _cb, _cc, _cd = st.columns([1.4, 1.2, 2.2, 0.5])
                        _ca.markdown(f"**{_r['category']}**")
                        _cb.caption(f"€ {float(_r['amount']):,.2f}")
                        _pf = pd.to_datetime(_r['period_from']).strftime('%d/%m/%y')
                        _pt = pd.to_datetime(_r['period_to']).strftime('%d/%m/%y')
                        _cc.caption(f"{_pf} → {_pt}")
                        if _cd.button("🗑️", key=f"del_util_{_r['id']}", help="Elimina"):
                            try:
                                supabase.table('utility_bills').delete().eq('id', _r['id']).execute()
                                st.cache_data.clear(); st.rerun()
                            except Exception as _e:
                                st.error(f"Errore: {_e}")
                else:
                    st.info("Nessuna bolletta inserita ancora.")

                st.divider()

                # ── Costi operativi per prenotazione ──
                st.caption("**🔑 Costi per Prenotazione** — pulizie, lavanderia…")
                if not df_var_c.empty:
                    _basis_map = {'per_booking': '/prenotazione', 'per_night': '/notte', 'per_guest': '/ospite'}
                    for _, _r in df_var_c.iterrows():
                        _ca, _cb, _cc, _cd = st.columns([2.2, 1.2, 1.4, 0.5])
                        _label = _VAR_CAT.get(_r['cost_type'], _r['cost_type'])
                        _label = _label.split(' ', 1)[1] if ' ' in _label else _label
                        _ca.markdown(f"**{_label}**")
                        _cb.caption(f"€ {float(_r['value']):,.2f}")
                        _cc.caption(_basis_map.get(_r['basis'], _r['basis']))
                        if _cd.button("🗑️", key=f"del_var_{_r['id']}", help="Elimina"):
                            try:
                                supabase.table('variable_costs').delete().eq('id', _r['id']).execute()
                                st.cache_data.clear(); st.rerun()
                            except Exception as _e:
                                st.error(f"Errore: {_e}")
                else:
                    st.info("Nessun costo operativo configurato.")

            # ── PANNELLO DESTRA: form aggiunta ──
            with cl_right:
                st.markdown("##### ➕ Aggiungi costo")
                tipo_c = st.radio(
                    "Tipo:",
                    ["🏛️ Strutturale", "⚡ Bolletta Utenza", "🔑 Per Prenotazione"],
                    horizontal=False, key="tipo_costo_radio",
                )

                if tipo_c == "🏛️ Strutturale":
                    st.caption("IMU, TARI, assicurazione, affitto — importo fisso mensile o annuale.")
                    with st.form("form_costi_fix"):
                        motivo_c  = st.selectbox("Categoria:", _FISSI_CAT)
                        importo_c = st.number_input("Importo (€)", min_value=0.0, step=10.0, format="%.2f")
                        freq_lbl  = st.radio("Frequenza:", ["Mensile", "Annuale"], horizontal=True)
                        data_c    = st.date_input("Valido dal:", datetime.date.today())
                        if st.form_submit_button("💾 Salva", type="primary"):
                            if importo_c <= 0:
                                st.error("Importo deve essere > 0.")
                            else:
                                try:
                                    ok_c, msg_c = update_or_insert_cost(
                                        supabase, USER_ID, prop_c_id, "Fijo", motivo_c, importo_c, data_c,
                                        None, None, "monthly" if freq_lbl == "Mensile" else "yearly",
                                    )
                                    if ok_c:
                                        st.success(f"✅ {motivo_c} — €{importo_c:.2f}/{freq_lbl.lower()} salvato.")
                                        st.cache_data.clear(); st.rerun()
                                    else:
                                        st.error(msg_c)
                                except Exception as e:
                                    st.error(f"Errore: {e}")

                elif tipo_c == "⚡ Bolletta Utenza":
                    st.caption("Inserisci ogni bolletta con il suo periodo — il sistema prorata il costo sui giorni corretti.")
                    with st.form("form_costi_util"):
                        cat_u     = st.selectbox("Utenza:", _UTIL_CAT)
                        importo_c = st.number_input("Importo bolletta (€)", min_value=0.0, step=1.0, format="%.2f")
                        uc1, uc2  = st.columns(2)
                        data_from = uc1.date_input("Dal:", datetime.date.today().replace(day=1))
                        data_to   = uc2.date_input("Al:", datetime.date.today())
                        note_c    = st.text_input("Note (opzionale)", placeholder="es. Bimestre gen-feb 2025")
                        if st.form_submit_button("💾 Salva Bolletta", type="primary"):
                            if importo_c <= 0:
                                st.error("Importo deve essere > 0.")
                            elif data_to < data_from:
                                st.error("La data 'Al' deve essere successiva alla data 'Dal'.")
                            else:
                                try:
                                    supabase.table('utility_bills').insert({
                                        "user_id":     USER_ID,
                                        "property_id": prop_c_id,
                                        "category":    cat_u,
                                        "amount":      float(importo_c),
                                        "period_from": data_from.isoformat(),
                                        "period_to":   data_to.isoformat(),
                                        "notes":       note_c or None,
                                    }).execute()
                                    st.success(f"✅ Bolletta {cat_u} €{importo_c:.2f} salvata ({data_from.strftime('%d/%m')}–{data_to.strftime('%d/%m/%Y')}).")
                                    st.cache_data.clear(); st.rerun()
                                except Exception as e:
                                    st.error(f"Errore: {e}")

                else:  # Per Prenotazione
                    st.caption("Pulizie, lavanderia, kit — costo che si applica ad ogni arrivo.")
                    with st.form("form_costi_var"):
                        var_lbl   = st.selectbox("Categoria:", _VAR_LABELS)
                        motivo_c  = _VAR_KEYS[_VAR_LABELS.index(var_lbl)]
                        importo_c = st.number_input("Importo (€)", min_value=0.0, step=5.0, format="%.2f")
                        base_lbl  = st.radio("Si applica:", ["Per prenotazione", "Per notte", "Per ospite"], horizontal=True)
                        base_c    = {"Per prenotazione": "per_booking", "Per notte": "per_night", "Per ospite": "per_guest"}[base_lbl]
                        data_c    = st.date_input("Valido dal:", datetime.date.today())
                        if st.form_submit_button("💾 Salva", type="primary"):
                            if importo_c <= 0:
                                st.error("Importo deve essere > 0.")
                            else:
                                try:
                                    ok_c, msg_c = update_or_insert_cost(
                                        supabase, USER_ID, prop_c_id, "Variable", motivo_c, importo_c, data_c,
                                        base_c, None, None,
                                    )
                                    if ok_c:
                                        st.success(f"✅ {var_lbl.split(' ',1)[1]} — €{importo_c:.2f} {base_lbl.lower()} salvato.")
                                        st.cache_data.clear(); st.rerun()
                                    else:
                                        st.error(msg_c)
                                except Exception as e:
                                    st.error(f"Errore: {e}")

else:
    # =====================================================
    # STATO VUOTO — Schermata di Onboarding
    # =====================================================
    st.divider()
    _, col_ob, _ = st.columns([1, 2, 1])
    with col_ob:
        st.markdown("## 👋 Benvenuto in Rate Labs RMS!")
        st.info("Il database è vuoto. Carica il tuo primo file di prenotazioni per iniziare ad analizzare il portafoglio.")
        st.markdown("---")

        pms_mode_ob = st.radio(
            "Seleziona il tuo PMS:",
            ["KrossBooking", "Altro PMS"],
            horizontal=True,
            key="ob_pms_mode"
        )

        # ── Flusso KrossBooking ──
        if pms_mode_ob == "KrossBooking":
            file_ob = st.file_uploader(
                "📂 Carica il file Excel esportato da KrossBooking",
                type=['xlsx'],
                key="ob_file_kb"
            )
            if file_ob:
                if st.button("🚀 Carica e Sincronizza", type="primary", use_container_width=True):
                    with st.spinner("Analisi e caricamento in corso..."):
                        df_limpio, df_cancellate = load_and_clean_krossbooking(file_ob)
                        dfs = [d for d in [df_limpio, df_cancellate] if d is not None and not d.empty]
                        if not dfs:
                            st.warning("⚠️ Il file non contiene dati validi.")
                        else:
                            try:
                                df_total = pd.concat(dfs, ignore_index=True)
                                df_total['pms_reservation_id'] = df_total['id'].astype(str)

                                prop_map = {}
                                for prop_name in df_total['unit_id'].dropna().unique():
                                    res = supabase.table('properties').upsert(
                                        {"user_id": USER_ID, "kross_unit_id": prop_name},
                                        on_conflict='user_id, kross_unit_id'
                                    ).execute()
                                    prop_map[prop_name] = res.data[0]['id']

                                records = []
                                for _, row in df_total.iterrows():
                                    records.append({
                                        "user_id":            USER_ID,
                                        "property_id":        prop_map.get(row['unit_id']),
                                        "pms_reservation_id": str(row['pms_reservation_id']),
                                        "check_in_date":      row['check_in_date'].strftime('%Y-%m-%d') if pd.notnull(row['check_in_date']) else None,
                                        "check_out_date":     row['check_out_date'].strftime('%Y-%m-%d') if pd.notnull(row.get('check_out_date')) else None,
                                        "booking_date":       row['booking_date'].strftime('%Y-%m-%d') if pd.notnull(row.get('booking_date')) else None,
                                        "gross_revenue":      float(row['gross_revenue']),
                                        "commission_amount":  float(row['commission_amount']),
                                        "net_revenue":        float(row['net_revenue']),
                                        "pm_net":             float(row['pm_net']),
                                        "owner_net":          float(row['owner_net']),
                                        "nights":             int(row['nights']),
                                        "lead_time":          int(row['lead_time']),
                                        "status":             str(row['status']),
                                        "channel":            str(row.get('channel', '') or ''),
                                        "channel_group":      str(row['channel_group']) if pd.notnull(row.get('channel_group')) else 'Altro',
                                    })

                                bar = st.progress(0, text="Caricamento in corso...")
                                total_chunks = math.ceil(len(records) / 500)
                                for i in range(total_chunks):
                                    chunk = records[i * 500:(i + 1) * 500]
                                    supabase.table('reservations').upsert(chunk, on_conflict='user_id, pms_reservation_id').execute()
                                    bar.progress((i + 1) / total_chunks, text=f"Lotto {i+1}/{total_chunks}...")

                                st.cache_data.clear()
                                st.success(f"✅ {len(records)} prenotazioni caricate con successo! Ricaricamento...")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Errore durante il caricamento: {e}")

        # ── Flusso Altro PMS ──
        else:
            pms_name_ob = st.text_input("Nome PMS (es. Mews, Opera, Beds24...)", key="ob_pms_name")
            file_ob_gen = st.file_uploader("📂 Carica file Excel", type=['xlsx', 'xls'], key="ob_file_gen")

            if file_ob_gen and pms_name_ob:
                df_raw_ob = pd.read_excel(file_ob_gen)
                raw_cols_ob = list(df_raw_ob.columns.astype(str))
                opts_ob = ["(Non mappare)"] + raw_cols_ob

                saved_res_ob = supabase.table('pms_mappings').select('mapping') \
                    .eq('user_id', USER_ID).eq('pms_name', pms_name_ob).execute()
                saved_mapping_ob = saved_res_ob.data[0]['mapping'] if saved_res_ob.data else {}

                if saved_mapping_ob:
                    st.success(f"✅ Mapping '{pms_name_ob}' trovato — precompilato.")
                else:
                    st.warning("Nessun mapping salvato. Configura le colonne qui sotto.")

                with st.expander("🗺️ Configura Mapping Colonne", expanded=not bool(saved_mapping_ob)):
                    new_mapping_ob = {}
                    col_a_ob, col_b_ob = st.columns(2)
                    for idx, (field, label) in enumerate(FIELD_LABELS.items()):
                        container = col_a_ob if idx % 2 == 0 else col_b_ob
                        saved_val = saved_mapping_ob.get(field, "(Non mappare)")
                        default_idx = opts_ob.index(saved_val) if saved_val in opts_ob else 0
                        chosen = container.selectbox(label, opts_ob, index=default_idx, key=f"ob_gmap_{field}")
                        new_mapping_ob[field] = chosen if chosen != "(Non mappare)" else None

                errors_ob = validate_mapping(new_mapping_ob)
                for err in errors_ob:
                    st.error(err)

                if not errors_ob:
                    if st.button("🚀 Carica & Salva Mapping", type="primary", use_container_width=True, key="ob_load_gen"):
                        with st.spinner("Normalizzazione e caricamento..."):
                            try:
                                supabase.table('pms_mappings').upsert(
                                    {"user_id": USER_ID, "pms_name": pms_name_ob, "mapping": new_mapping_ob},
                                    on_conflict="user_id,pms_name"
                                ).execute()
                                df_norm_ob = apply_mapping(df_raw_ob, new_mapping_ob)
                                if df_norm_ob.empty:
                                    st.warning("Nessuna prenotazione valida trovata. Verifica il mapping.")
                                else:
                                    prop_map_ob = {}
                                    for prop_name in df_norm_ob['unit_id'].dropna().unique():
                                        res = supabase.table('properties').upsert(
                                            {"user_id": USER_ID, "kross_unit_id": prop_name},
                                            on_conflict='user_id, kross_unit_id'
                                        ).execute()
                                        prop_map_ob[prop_name] = res.data[0]['id']

                                    records_ob = []
                                    for _, row in df_norm_ob.iterrows():
                                        records_ob.append({
                                            "user_id":            USER_ID,
                                            "property_id":        prop_map_ob.get(row['unit_id']),
                                            "pms_reservation_id": str(row['pms_reservation_id']),
                                            "check_in_date":      row['check_in_date'].strftime('%Y-%m-%d') if pd.notnull(row['check_in_date']) else None,
                                            "check_out_date":     row['check_out_date'].strftime('%Y-%m-%d') if pd.notnull(row.get('check_out_date')) else None,
                                            "booking_date":       row['booking_date'].strftime('%Y-%m-%d') if pd.notnull(row.get('booking_date')) else None,
                                            "gross_revenue":      float(row['gross_revenue']),
                                            "commission_amount":  float(row['commission_amount']),
                                            "net_revenue":        float(row['net_revenue']),
                                            "pm_net":             float(row['pm_net']),
                                            "owner_net":          float(row['owner_net']),
                                            "nights":             int(row['nights']),
                                            "lead_time":          int(row['lead_time']),
                                            "status":             str(row['status']),
                                            "channel":            str(row.get('channel', '') or ''),
                                            "channel_group":      str(row.get('channel_group', 'Altro') or 'Altro'),
                                        })

                                    for i in range(math.ceil(len(records_ob) / 500)):
                                        chunk = records_ob[i * 500:(i + 1) * 500]
                                        supabase.table('reservations').upsert(chunk, on_conflict='user_id, pms_reservation_id').execute()

                                    st.cache_data.clear()
                                    st.success(f"✅ {len(records_ob)} prenotazioni caricate da '{pms_name_ob}'!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ Errore: {e}")
            elif file_ob_gen and not pms_name_ob:
                st.warning("Inserisci il nome del PMS per continuare.")