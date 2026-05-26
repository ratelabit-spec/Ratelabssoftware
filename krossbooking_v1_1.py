import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import plotly.graph_objects as go
import datetime
import math
from datetime import date
from supabase import create_client, Client
from adapter_krossbooking import load_and_clean_krossbooking
from etl_costs import update_or_insert_cost
from etl_metrics import calculate_property_margins

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="KrossBooking Pace Pro", page_icon="📈", layout="wide")

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

    k['netto'] = df_otb['pm_net'].sum()
    k['commissioni'] = df_otb['commission_amount'].sum() if 'commission_amount' in df_otb.columns else 0

    return k


@st.cache_data(ttl=3600)
def load_portfolio_costs(user_id):
    """Carica i costi fissi e variabili attivi per tutto il portafoglio (usato dal Cervello Matematico)."""
    res_fix = supabase.table('fixed_costs').select('*').eq('user_id', user_id).is_('valid_to', 'null').execute()
    res_var = supabase.table('variable_costs').select('*').eq('user_id', user_id).is_('valid_to', 'null').execute()
    df_fix = pd.DataFrame(res_fix.data) if res_fix.data else pd.DataFrame(columns=['amount', 'frequency', 'valid_to'])
    df_var = pd.DataFrame(res_var.data) if res_var.data else pd.DataFrame(columns=['value', 'basis', 'valid_to'])
    return df_fix, df_var


def show_login_page():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("# 📈 KrossBooking Pace Pro")
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

st.title("📊 KrossBooking Pace Pro — Cloud V3.0")

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
    
    unita_cy = df_cy['unit_id'].nunique() if not df_cy.empty else 1
    unita_ly = df_ly['unit_id'].nunique() if not df_ly.empty else 1
    
    capacita_totale_cy = unita_cy * giorni_nel_mese
    capacita_totale_ly = unita_ly * giorni_nel_mese
    
    revpar = k['rev'] / capacita_totale_cy if capacita_totale_cy > 0 else 0
    revpar_ly = k['rev_ly'] / capacita_totale_ly if capacita_totale_ly > 0 else 0
    var_revpar = (revpar / revpar_ly - 1) * 100 if revpar_ly > 0 else 0

    # Calcolo percentuale di cancellazione
    tot_res_cy = len(df_cy_otb) + len(df_cy_canc_mes)
    pct_canc = (len(df_cy_canc_mes) / tot_res_cy * 100) if tot_res_cy > 0 else 0

    # =====================================================
    # CERVELLO MATEMATICO — BOTTOM RATE
    # =====================================================
    df_fix_portfolio, df_var_portfolio = load_portfolio_costs(USER_ID)
    costos_configurados = not df_fix_portfolio.empty or not df_var_portfolio.empty

    bottom_rate = 0.0
    if costos_configurados:
        fixed_annual = (
            df_fix_portfolio[df_fix_portfolio['frequency'] == 'yearly']['amount'].sum() +
            df_fix_portfolio[df_fix_portfolio['frequency'] == 'monthly']['amount'].sum() * 12
        ) if not df_fix_portfolio.empty else 0.0

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

    st.caption(f"📍 **{txt_filtro}** | Mese: **{mes_nombre}** | OTB al: **{fecha_hoy.strftime('%d/%m/%Y')}**")

    tab_kpi, tab_canali, tab_netto, tab_netto_pm, tab_grafici, tab_curve, tab_radar, tab_obiettivi, tab_compset, tab_dati = st.tabs([
    "📊 KPI & Strategia", "📡 Canali", "💼 Netto PM", "💰 Analisi Costi", "📈 Grafici OTB", "🌊 Booking Curve", "🚨 Radar Rendimento", "🎯 Tracker Obiettivi", "🕵️‍♂️ Comp Set", "☁️ Gestione Dati"
])

    with tab_kpi:
        st.subheader("Riepilogo Performance")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Ricavi OTB", f"€ {k['rev']:,.0f}", f"{k['var_rev']:+.1f}% vs STLY" if k['rev_ly'] > 0 else "")
        c2.metric("🏠 RevPAR", f"€ {revpar:,.2f}", f"{var_revpar:+.1f}% vs STLY" if revpar_ly > 0 else "")
        c3.metric("🏷️ ADR", f"€ {k['adr']:,.2f}", f"{k['var_adr']:+.1f}% vs STLY" if k['adr_ly'] > 0 else "")
        c4.metric("🛏️ Notti", f"{k['notti']:,.0f}", f"{k['notti'] - k['notti_ly']:+.0f} vs STLY")
        
        # Métrica de cancelaciones restaurada y funcional
        c5.metric("❌ Cancellazioni", f"{pct_canc:.1f}%", f"{len(df_cy_canc_mes)} prenotazioni")

        col_lt, col_los, col_diag = st.columns([1, 1, 2])
        with col_lt:
            st.subheader("⏱️ Lead Time")
            st.info(f"**OTB attuale:** {k['lt']:.0f} giorni")
            st.warning(f"**Chiusura STLY:** {k['lt_ly_final']:.0f} giorni")
        with col_los:
            st.subheader("🛌 L.O.S.")
            st.info(f"**OTB attuale:** {k['los']:.1f} notti")
            st.warning(f"**STLY OTB:** {k['los_ly']:.1f} notti")

        with col_diag:
            st.subheader("🧠 Insight Rapido")
            if k['los'] > (k['los_ly'] + 1):
                st.success(f"🌟 **Mix Ottimo:** Soggiorni più lunghi (+{k['los'] - k['los_ly']:.1f} notti).")
            elif k['var_rev'] > 0 and k['var_adr'] >= 0:
                st.success("🏆 **Crescita Sana:** Ricavi e prezzi in aumento.")
            elif k['var_rev'] < -10:
                st.error("📉 **Calo Ricavi:** Sei in ritardo rispetto all'anno scorso.")
            elif k['var_notti'] > 0 and k['var_adr'] < -5:
                st.warning("⚠️ **Diluizione ADR:** Vendi di più ma a prezzo inferiore.")
            else:
                st.info("📊 **Ritmo Stabile:** Indicatori in linea con lo storico.")

        st.divider()

        # =====================================================
        # PICKUP REPORT
        # =====================================================
        st.subheader("📥 Pickup Report")
        if not df_pickup.empty:
            col_pu_left, col_pu_right = st.columns([3, 2])
            with col_pu_left:
                def stile_delta(val):
                    if isinstance(val, (int, float)):
                        color = "#38A169" if val > 0 else ("#E53E3E" if val < 0 else "#718096")
                        return f"color: {color}; font-weight: bold"
                    return ""

                styled = df_pickup.style\
                    .format({
                        'Rev. CY (€)':   '€ {:,.0f}',
                        'Rev. STLY (€)': '€ {:,.0f}',
                        'Δ Rev. (€)':    '€ {:+,.0f}',
                        'Δ Pren.':       '{:+d}',
                    })\
                    .map(stile_delta, subset=['Δ Pren.', 'Δ Rev. (€)'])
                st.dataframe(styled, use_container_width=True, hide_index=True)

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

        st.divider()

        # =====================================================
        # CERVELLO STRATEGICO — IA (Gemini)
        # =====================================================
        st.subheader("🤖 Cervello Strategico — Analisi IA (Gemini)")

        # Bottom Rate context
        if bottom_rate > 0:
            st.success(f"🔒 **Bottom Rate attivo:** €{bottom_rate:.2f}/notte — l'IA non suggerirà mai strategie sotto questa soglia.")
            sezione_br = (
                f"⚠️ VINCOLO ASSOLUTO — BOTTOM RATE: €{bottom_rate:.2f}/notte "
                f"(soglia matematica di pareggio calcolata dai costi operativi reali + commissioni OTA medie del portafoglio). "
                f"REGOLA FERREA: non suggerire mai strategie che portino l'ADR al di sotto di €{bottom_rate:.2f}. "
                f"È il pavimento matematico, non si negozia."
            )
        else:
            st.warning("⚠️ Bottom Rate non calcolato — configura i costi operativi nel tab 'Analisi Costi' per attivare il vincolo matematico sull'IA.")
            sezione_br = "ℹ️ Bottom Rate non disponibile (nessun costo operativo configurato). Analizza in base ai dati di mercato."

        # Comp Set context
        sezione_comp = ""
        if not df_market.empty:
            comp_mes = df_market[df_market['stay_date'].dt.month == mes_interes]
            if not comp_mes.empty:
                avg_comp = comp_mes[comp_mes['is_available'] == True]['price'].mean()
                n_soldout = comp_mes[comp_mes['is_available'] == False]['name'].nunique()
                sezione_comp = (
                    f"\n📊 MERCATO: prezzo medio competitor €{avg_comp:.0f}/notte per {mes_nombre}. "
                    f"{n_soldout} competitor già sold out."
                )

        prompt_ia = f"""Sei il Cervello Strategico di un sistema professionale di Revenue Management.
Oggi: {fecha_hoy.strftime('%d/%m/%Y')} | Portfolio: {txt_filtro} | Mese analizzato: {mes_nombre}

{sezione_br}

📈 DATI OTB:
• Ricavi: €{k['rev']:,.0f} ({k['var_rev']:+.1f}% vs STLY) | RevPAR: €{revpar:,.2f} ({var_revpar:+.1f}%)
• Notti: {k['notti']:,.0f} ({k['var_notti']:+.1f}%) | ADR: €{k['adr']:,.2f} ({k['var_adr']:+.1f}%)
• LOS: {k['los']:.1f} notti | Lead Time: {k['lt']:.0f}gg (chiusura STLY: {k['lt_ly_final']:.0f}gg)
• Cancellazioni: {pct_canc:.1f}% | Pickup 7gg: {pickup_7_cy} pren. ({pickup_7_cy - pickup_7_ly:+d} vs STLY){sezione_comp}

Genera un report STRUTTURATO con esattamente questo formato (max 300 parole totali):

🟢 SCENARIO CONSERVATIVO
Azione: [cosa fare concretamente sul channel manager / PriceLabs]
Obiettivo: [risultato atteso in termini di RevPAR, ADR o occupazione]

🟡 SCENARIO MODERATO
Azione: [cosa fare concretamente]
Obiettivo: [risultato atteso]

🔴 SCENARIO AGGRESSIVO
Azione: [cosa fare concretamente]
Obiettivo: [risultato atteso]

💡 DIAGNOSI (2 righe max): Motivazione principale della strategia basata sui dati OTB e di mercato.
"""
        if st.button("✨ Genera Analisi IA"):
            if not API_KEY:
                st.error("⚠️ Configura GEMINI_API_KEY in .streamlit/secrets.toml")
            else:
                with st.spinner("Analisi in corso..."):
                    try:
                        risposta = model.generate_content(prompt_ia)
                        st.markdown(risposta.text)
                    except Exception as e:
                        st.error(f"Errore IA: {e}")

    with tab_canali:
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
            
            st.dataframe(
                df_ch_display.style.format({
                    'Ricavi': '€ {:,.2f}',
                    '% Ricavi': '{:.1f} %',
                    'Commissioni': '€ {:,.2f}',
                    '% Commissione Media': '{:.1f} %'
                }),
                hide_index=True, use_container_width=True
            )

            st.markdown("---")
            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                fig_pie = px.pie(df_ch, values='Ricavi', names='channel_group', title="Quota Ricavi per Canale")
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_ch2:
                fig_adr = px.bar(df_ch.sort_values('ADR', ascending=True), x='ADR', y='channel_group', orientation='h', title="ADR per Canale (€)")
                st.plotly_chart(fig_adr, use_container_width=True)
        else:
            st.info("⚠️ Nessun ricavo registrato per questo periodo, i grafici dei canali non sono disponibili.")

    with tab_netto:
        st.subheader("💼 Netto Property Manager")
        if not df_cy_otb.empty and k['netto'] > 0:
            df_netto_apt = df_cy_otb.groupby('unit_id').agg(
                Lordo=('gross_revenue', 'sum'),
                Netto=('pm_net', 'sum'),
                Commissioni=('commission_amount', 'sum')
            ).reset_index()
            fig_netto = px.bar(df_netto_apt.sort_values('Netto', ascending=True), x=['Netto', 'Commissioni'], y='unit_id', orientation='h', barmode='stack', title="Netto vs Commissioni per Appartamento (€)")
            st.plotly_chart(fig_netto, use_container_width=True)
        else:
            st.info("⚠️ Dati insufficienti per calcolare il Netto Property Manager in questo periodo.")

    with tab_grafici:
        st.subheader("Performance per Appartamento (Netto Real)")
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
                fig_r = px.bar(df_apt, x='Ricavi_Lordi', y='unit_id', orientation='h', title="💰 Ricavi Lordi (€)", text=df_apt['Ricavi_Lordi'].apply(lambda x: f"€ {x:,.0f}"))
                fig_r.update_traces(textposition='outside')
                fig_r.update_layout(showlegend=False)
                st.plotly_chart(fig_r, use_container_width=True)
            
            with col_g2:
                fig_o = px.bar(df_apt_occ, x='Occupazione', y='unit_id', orientation='h', title="🛏️ Occupazione (%)", text=df_apt_occ['Occupazione'].apply(lambda x: f"{x:.1f}%"))
                fig_o.update_traces(textposition='outside')
                fig_o.update_layout(showlegend=False)
                st.plotly_chart(fig_o, use_container_width=True)
            
            with col_g3:
                fig_revpar = px.bar(df_apt_revpar, x='Net_RevPAR_Real', y='unit_id', orientation='h', title="🏠 Net RevPAR Real (€)", text=df_apt_revpar['Net_RevPAR_Real'].apply(lambda x: f"€ {x:,.1f}"))
                fig_revpar.update_traces(textposition='outside')
                fig_revpar.update_layout(showlegend=False)
                st.plotly_chart(fig_revpar, use_container_width=True)
        else:
            st.info("⚠️ Nessuna performance registrata per gli appartamenti in questo periodo.")

    with tab_curve:
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
            fig_curve = px.line(df_curve, x='Data Allineata', y='Cumulato', color='Anno', line_shape='hv', title=f"Evoluzione {metrica_curve.split()[0]}")
            
            fecha_str = fecha_hoy_pd.strftime('%Y-%m-%d')
            fig_curve.add_vline(x=fecha_str, line_dash="dash", line_color="red")
            fig_curve.add_annotation(x=fecha_str, y=1.02, yref="paper", text="Foto OTB (Oggi)", showarrow=False, font=dict(color="red", size=12))
            
            fig_curve.update_layout(legend_title_text='')
            st.plotly_chart(fig_curve, use_container_width=True)
        else:
            st.info("⚠️ Nessuna prenotazione disponibile per tracciare la curva in questo periodo.")

    with tab_radar:
        st.subheader("🚨 Radar di Sotto-Rendimento")
        st.markdown(f"Confronto ADR per appartamento vs media portafoglio: **{k['var_adr']:+.1f}%**")

        if not df_cy_otb.empty and not df_ly_otb.empty:
            apt_cy = df_cy_otb.groupby('unit_id').agg(Rev_cy=('gross_revenue', 'sum'), Notti_cy=('nights', 'sum')).reset_index()
            apt_cy['ADR_cy'] = apt_cy.apply(lambda r: r['Rev_cy'] / r['Notti_cy'] if r['Notti_cy'] > 0 else 0, axis=1)

            apt_ly = df_ly_otb.groupby('unit_id').agg(Rev_ly=('gross_revenue', 'sum'), Notti_ly=('nights', 'sum')).reset_index()
            apt_ly['ADR_ly'] = apt_ly.apply(lambda r: r['Rev_ly'] / r['Notti_ly'] if r['Notti_ly'] > 0 else 0, axis=1)

            apt_cmp = pd.merge(apt_cy, apt_ly, on='unit_id')
            apt_cmp['Var_ADR'] = apt_cmp.apply(
                lambda r: (r['ADR_cy'] / r['ADR_ly'] - 1) * 100 if r['ADR_ly'] > 0 else 0, axis=1
            )
            apt_cmp['Diff_vs_Media'] = apt_cmp['Var_ADR'] - k['var_adr']

            under = apt_cmp[apt_cmp['Diff_vs_Media'] < -2.0].sort_values('Diff_vs_Media')

            if not under.empty:
                st.error(f"⚠️ {len(under)} appartament{'o' if len(under) == 1 else 'i'} crescono più lentamente della media del portafoglio.")
                st.dataframe(
                    under[['unit_id', 'ADR_ly', 'ADR_cy', 'Var_ADR', 'Diff_vs_Media']].rename(columns={
                        'unit_id': 'Appartamento',
                        'ADR_ly': 'ADR STLY (€)',
                        'ADR_cy': 'ADR Attuale (€)',
                        'Var_ADR': 'Crescita (%)',
                        'Diff_vs_Media': 'Diff vs Media (%)'
                    }).style.format({
                        'ADR STLY (€)': '€ {:.2f}',
                        'ADR Attuale (€)': '€ {:.2f}',
                        'Crescita (%)': '{:+.1f}%',
                        'Diff vs Media (%)': '{:+.1f}%'
                    }),
                    use_container_width=True, hide_index=True
                )
            else:
                st.success("✅ Tutti gli appartamenti performano in linea o sopra la media del portafoglio.")

            with st.expander("Vedi confronto completo"):
                st.dataframe(
                    apt_cmp[['unit_id', 'ADR_ly', 'ADR_cy', 'Var_ADR', 'Diff_vs_Media']].rename(columns={
                        'unit_id': 'Appartamento',
                        'ADR_ly': 'ADR STLY (€)',
                        'ADR_cy': 'ADR Attuale (€)',
                        'Var_ADR': 'Crescita (%)',
                        'Diff_vs_Media': 'Diff vs Media (%)'
                    }).style.format({
                        'ADR STLY (€)': '€ {:.2f}',
                        'ADR Attuale (€)': '€ {:.2f}',
                        'Crescita (%)': '{:+.1f}%',
                        'Diff vs Media (%)': '{:+.1f}%'
                    }),
                    use_container_width=True, hide_index=True
                )
        else:
            st.info("⚠️ Impossibile generare il radar: dati storici o attuali insufficienti per il confronto.")

    with tab_obiettivi:
        st.subheader(f"🎯 Tracker Chiusura — {mes_nombre}")
        
        rev_ly_final = df_ly_final['gross_revenue'].sum() if not df_ly_final.empty else 0
        notti_ly_final = df_ly_final['nights'].sum() if not df_ly_final.empty else 0
        
        rev_cy_otb = k['rev']
        notti_cy_otb = k['notti']
        
        pct_rev = (rev_cy_otb / rev_ly_final * 100) if rev_ly_final > 0 else 0
        pct_notti = (notti_cy_otb / notti_ly_final * 100) if notti_ly_final > 0 else 0

        col_t1, col_t2 = st.columns(2)
        
        with col_t1:
            st.metric("💰 Ricavi Attuali vs Target", 
                      f"€ {rev_cy_otb:,.0f}", 
                      f"Target: € {rev_ly_final:,.0f} ({pct_rev:.1f}%)",
                      delta_color="off")
            st.progress(min(pct_rev / 100, 1.0))

        with col_t2:
            st.metric("🛏️ Notti Attuali vs Target", 
                      f"{notti_cy_otb:,.0f}", 
                      f"Target: {notti_ly_final:,.0f} notti ({pct_notti:.1f}%)",
                      delta_color="off")
            st.progress(min(pct_notti / 100, 1.0))

        if pct_rev >= 100:
            st.success("🎉 **Obiettivo Ricavi Raggiunto!** Stai superando i risultati finali dell'anno scorso.")
        elif pct_rev >= 85 and rev_cy_otb > 0:
            st.info("🔥 **Ultimo Sforzo!** Sei a un passo dal raggiungere il fatturato storico.")
    
    with tab_compset:
        st.subheader("🕵️‍♂️ Analisi Competitiva (Prezzi Pubblici)")
        st.markdown("Monitoraggio dei prezzi e disponibilità dei tuoi diretti concorrenti su Booking.com.")
        st.info("ℹ️ **Aggiornamento dati:** i prezzi vengono raccolti eseguendo manualmente `python etl_competitors.py` dal terminale. I dati vengono poi memorizzati nel cloud e mostrati qui (cache 1 ora).")

        if df_market.empty:
            st.warning("Nessun dato competitivo trovato. Assicurati di aver configurato i competitor nella tabella `competitors` e di aver eseguito lo scraper.")
        else:
            # --- 1. SLIDER DE FECHAS ---
            min_date = df_market['stay_date'].min().date()
            max_date = df_market['stay_date'].max().date()
            
            col1, col2 = st.columns([2, 1])
            with col1:
                date_range = st.slider(
                    "🗓️ Seleziona il periodo da analizzare:",
                    min_value=min_date,
                    max_value=max_date,
                    value=(min_date, max_date),
                    format="DD/MM/YYYY"
                )
            
            # Filtramos los datos según el slider
            mask = (df_market['stay_date'].dt.date >= date_range[0]) & (df_market['stay_date'].dt.date <= date_range[1])
            df_filtered = df_market.loc[mask].copy()
            
            # --- 2. LÓGICA DE GRÁFICO (DISPONIBLES VS SOLD OUT) ---
            df_available = df_filtered[df_filtered['is_available'] == True]
            df_soldout = df_filtered[df_filtered['is_available'] == False]
            
            # Dibujamos las líneas normales solo para los días disponibles
            fig = px.line(
                df_available, 
                x="stay_date", 
                y="price", 
                color="name", 
                markers=True,
                title=f"Andamento Prezzi dal {date_range[0].strftime('%d/%m')} al {date_range[1].strftime('%d/%m')}",
                labels={"stay_date": "Data Soggiorno", "price": "Prezzo (€)", "name": "Competitor"}
            )
            
            # Añadimos los marcadores de "Sold Out" (cruces rojas en la parte baja del gráfico)
            if not df_soldout.empty:
                fig.add_scatter(
                    x=df_soldout['stay_date'],
                    y=[0] * len(df_soldout), # Los ponemos en el eje Y=0 para que resalten abajo
                    mode='markers',
                    marker=dict(symbol='x', size=12, color='red'),
                    name='Sold Out',
                    text=df_soldout['name'], # Para ver quién está lleno al pasar el ratón
                    hovertemplate="<b>%{text}</b><br>❌ Sold Out"
                )
            
            # Mejoramos el diseño y forzamos al eje Y a empezar en 0 para ver bien los Sold Outs
            fig.update_layout(
                hovermode="x unified", 
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis_rangemode='tozero' 
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("Vedi dati grezzi"):
                st.dataframe(df_filtered[['stay_date', 'name', 'price', 'is_available']].sort_values(['stay_date', 'name']), hide_index=True)
    
    with tab_netto_pm:
        st.header("💰 Analisi Margine Netto (Netto PM)")

        # 1. Recuperar propiedades del usuario
        res_props = supabase.table('properties').select('id, kross_unit_id').eq('user_id', USER_ID).execute()
        props_dict = {p['kross_unit_id']: p['id'] for p in res_props.data} if res_props.data else {}

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
        with st.spinner("Calcolando i margini..."):
            res_res = supabase.table('reservations').select('*').eq('property_id', p_id).execute()
            res_fix = supabase.table('fixed_costs').select('*').eq('property_id', p_id).execute()
            res_var = supabase.table('variable_costs').select('*').eq('property_id', p_id).execute()

            df_res = pd.DataFrame(res_res.data) if res_res.data else pd.DataFrame()
            df_fix = pd.DataFrame(res_fix.data) if res_fix.data else pd.DataFrame(columns=['amount','frequency','valid_to'])
            df_var = pd.DataFrame(res_var.data) if res_var.data else pd.DataFrame(columns=['value','basis','valid_to'])

            if not df_res.empty:
                fatturato, ota, variabili, fissi, netto = calculate_property_margins(df_res, df_fix, df_var, anno)

                if not df_var.empty and (df_var['basis'] == 'per_guest').any():
                    st.caption("ℹ️ I costi 'per ospite' sono calcolati stimando 2 ospiti per prenotazione (dato non disponibile dal PMS).")

                st.divider()
                st.subheader("🎯 Calcolatore: Tariffa Minima e di Partenza")
                st.write("Usa i costi operativi attuali per definire i tuoi prezzi base.")
                
                # Agrupamos los costos actuales para el cálculo
                costi_fissi_annuali = df_fix[df_fix['frequency'] == 'yearly']['amount'].sum() + (df_fix[df_fix['frequency'] == 'monthly']['amount'].sum() * 12)
                costi_var_prenotazione = df_var[df_var['basis'] == 'per_booking']['value'].sum()
                costi_var_notte = df_var[df_var['basis'] == 'per_night']['value'].sum()

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
                    text = [f"€{fatturato:,.0f}", f"€{ota:,.0f}", f"€{variabili:,.0f}", f"€{fissi:,.0f}", f"€{netto:,.0f}"],
                    y = [fatturato, ota, variabili, fissi, netto],
                    connector = {"line":{"color":"#444"}},
                    decreasing = {"marker":{"color":"#e74c3c"}}, 
                    totals = {"marker":{"color":"#2ecc71" if netto > 0 else "#e74c3c"}}
                ))

                fig.update_layout(
                    title=f"Cascata del Margine: {prop_name} ({anno})", 
                    height=500, 
                    plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Nessuna prenotazione trovata per {prop_name} nell'anno {anno}.")

    with tab_dati:
        st.header("⚙️ Gestione Dati")
        
        # --- SEZIONE 1: SINCRONIZZAZIONE PRENOTAZIONI ---
        st.subheader("☁️ Aggiorna il Database (KrossBooking)")
        st.info("Carica l'ultimo export di KrossBooking. Il sistema aggiungerà le nuove prenotazioni (incluse le cancellazioni) e aggiornerà quelle modificate.")
        
        file_upload = st.file_uploader("📂 Carica file Excel", type=['xlsx'])
        
        if file_upload:
            if st.button("🚀 Sincronizza nel Cloud"):
                with st.spinner("Analisi e caricamento in corso..."):
                    # 1. Recuperamos AMBOS DataFrames (Activas y Canceladas)
                    df_limpio, df_cancellate = load_and_clean_krossbooking(file_upload)
                    
                    # 2. Las unimos en un solo DataFrame masivo
                    dfs_to_concat = []
                    if df_limpio is not None and not df_limpio.empty:
                        dfs_to_concat.append(df_limpio)
                    if df_cancellate is not None and not df_cancellate.empty:
                        dfs_to_concat.append(df_cancellate)
                    
                    if dfs_to_concat:
                        df_total = pd.concat(dfs_to_concat, ignore_index=True)
                        
                        try:
                            # Sincronizar apartamentos
                            unique_props = df_total['unit_id'].dropna().unique()
                            prop_mapping = {}
                            for prop_name in unique_props:
                                res = supabase.table('properties').upsert(
                                    {"user_id": USER_ID, "kross_unit_id": prop_name},
                                    on_conflict='user_id, kross_unit_id'
                                ).execute()
                                prop_mapping[prop_name] = res.data[0]['id']

                            # Preparar registros
                            records = []
                            for _, row in df_total.iterrows():
                                record = {
                                    "user_id": USER_ID,
                                    "property_id": prop_mapping[row['unit_id']],
                                    "pms_reservation_id": str(row['id']),
                                    "check_in_date": row['check_in_date'].strftime('%Y-%m-%d'),
                                    "check_out_date": row['check_out_date'].strftime('%Y-%m-%d') if pd.notnull(row['check_out_date']) else None,
                                    "booking_date": row['booking_date'].strftime('%Y-%m-%d'),
                                    "gross_revenue": float(row['gross_revenue']) if pd.notnull(row['gross_revenue']) else 0,
                                    "commission_amount": float(row['commission_amount']) if pd.notnull(row['commission_amount']) else 0,
                                    "net_revenue": float(row['net_revenue']) if pd.notnull(row['net_revenue']) else 0,
                                    "pm_net": float(row['pm_net']) if pd.notnull(row['pm_net']) else 0,
                                    "owner_net": float(row['owner_net']) if pd.notnull(row['owner_net']) else 0,
                                    "nights": int(row['nights']) if pd.notnull(row['nights']) else 0,
                                    "lead_time": int(row['lead_time']) if pd.notnull(row['lead_time']) else 0,
                                    "status": str(row['status']),
                                    "channel": str(row.get('channel', '')),
                                    "channel_group": str(row['channel_group'])
                                }
                                records.append(record)

                            # Upsert en chunks de 500 para evitar Payload Too Large
                            chunk_size = 500
                            total_chunks = math.ceil(len(records) / chunk_size)
                            progress_bar = st.progress(0, text="Caricamento in corso...")
                            for i in range(total_chunks):
                                chunk = records[i * chunk_size:(i + 1) * chunk_size]
                                supabase.table('reservations').upsert(chunk, on_conflict='user_id, pms_reservation_id').execute()
                                progress_bar.progress((i + 1) / total_chunks, text=f"Lotto {i+1}/{total_chunks} caricato...")

                            st.cache_data.clear()
                            st.success(f"✅ Sincronizzazione completata! ({len(records)} record analizzati, incluse cancellazioni).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore durante l'aggiornamento: {e}")
                    else:
                        st.warning("Il file caricato non contiene dati validi.")
        
        st.divider()
        
        # --- SEZIONE 2: INSERIMENTO COSTI (DATA ENTRY) ---
        st.subheader("📝 Inserimento e Aggiornamento Costi")
        st.write("Gestisci i costi fissi e variabili per calcolare il Netto PM.")
        
        # Obtenemos las propiedades del usuario para el selector
        res_props = supabase.table('properties').select('id, kross_unit_id').eq('user_id', USER_ID).execute()
        props_dict = {p['kross_unit_id']: p['id'] for p in res_props.data} if res_props.data else {}
        
        if not props_dict:
            st.info("Carica un file di prenotazioni per registrare le tue proprietà prima di inserire i costi.")
        else:
            with st.form("form_costi"):
                col_prop, col_tipo = st.columns(2)
                
                with col_prop:
                    prop_selezionata_nome = st.selectbox("Seleziona Proprietà", list(props_dict.keys()))
                    selected_property_id = props_dict[prop_selezionata_nome]
                
                with col_tipo:
                    tipo_coste = st.selectbox("Tipo di Costo", ["Fisso", "Variabile"])
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fecha_inicio = st.date_input("Data di inizio validità", datetime.date.today())
                    monto = st.number_input("Importo (€ o %)", min_value=0.0, step=1.0)
                    
                with col2:
                    if tipo_coste == "Fisso":
                        motivo = st.text_input("Motivo (Es: Affitto, Internet, Assicurazione)")
                        frecuencia = st.selectbox("Frequenza", ["monthly", "yearly"])
                        base_calculo = None
                        canal = None
                    else:
                        # Fuera comisiones, solo costos operativos
                        motivo = st.selectbox("Categoria", ["cleaning", "laundry", "amenities", "other"])
                        base_calculo = st.selectbox("Come si applica?", ["per_booking", "per_night", "per_guest"])
                        canal = None
                        frecuencia = None
                
                submitted_costo = st.form_submit_button("💾 Salva Costo")
                
                if submitted_costo:
                    if not motivo:
                        st.error("Devi inserire il motivo o la categoria.")
                    else:
                        try:
                            update_or_insert_cost(
                                supabase, 
                                USER_ID, 
                                selected_property_id, 
                                "Fijo" if tipo_coste == "Fisso" else "Variable", 
                                motivo, 
                                monto, 
                                fecha_inicio, 
                                base_calculo, # Reemplazamos 'es_porcentaje' por 'base_calculo'
                                canal, 
                                frecuencia
                            )
                            st.success(f"✅ Costo di '{motivo}' salvato con successo a partire dal {fecha_inicio}.")
                        except Exception as e:
                            st.error(f"Errore durante il salvataggio: {e}")