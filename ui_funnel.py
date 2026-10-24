"""
Tab Visibilità: inserimento settimanale del funnel OTA (Booking, Airbnb) e storico per proprietà.
I campi ricalcano i report delle extranet, così si copiano i numeri così come appaiono.
"""
import datetime
import pandas as pd
import streamlit as st

import db

_CHANNELS = {"booking": "Booking.com", "airbnb": "Airbnb"}
_BOOKING_PERIODS = {"Ultimi 7 giorni": 7, "Ultimi 14 giorni": 14, "Ultimi 30 giorni": 30}


def _num(value):
    """None se il campo è lasciato a 0 (non compilato)."""
    return None if value in (None, 0, 0.0) else value


def _booking_form(key):
    st.caption("Extranet → Analytics → **Prenotazioni effettuate tramite ricerca** (confronto con: Competitor diretti).")
    c0, c1 = st.columns(2)
    period = c0.selectbox("Periodo prenotazioni:", list(_BOOKING_PERIODS.keys()), key=f"{key}_period")
    end = c1.date_input("Data del report:", datetime.date.today(), key=f"{key}_end",
                        help="Il giorno in cui hai letto il report: il periodo termina qui.")
    start = end - datetime.timedelta(days=_BOOKING_PERIODS[period] - 1)

    st.markdown("**La tua struttura**")
    a1, a2, a3 = st.columns(3)
    impressions = a1.number_input("Presenza nelle ricerche", min_value=0, step=1, key=f"{key}_imp")
    ctr = a2.number_input("% ha cliccato sulla pagina", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=f"{key}_ctr")
    conv = a3.number_input("% ha prenotato la struttura", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=f"{key}_conv")

    st.markdown("**Competitor diretti**")
    b1, b2, b3 = st.columns(3)
    c_impressions = b1.number_input("Presenza nelle ricerche ", min_value=0, step=1, key=f"{key}_cimp")
    c_ctr = b2.number_input("% ha cliccato sulla pagina ", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=f"{key}_cctr")
    c_conv = b3.number_input("% ha prenotato la struttura ", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=f"{key}_cconv")

    with st.expander("Facoltativo: domanda della destinazione e recensioni"):
        d1, d2 = st.columns(2)
        demand = d1.number_input("Variazione domanda destinazione (%)", min_value=-100.0, max_value=1000.0, value=0.0,
                                 step=1.0, key=f"{key}_dem",
                                 help="Dati sulla domanda: «La domanda … è aumentata del X%». Lascia 0 se non disponibile.")
        review = d2.number_input("Punteggio recensioni (0–10)", min_value=0.0, max_value=10.0, step=0.1, key=f"{key}_rev")

    values = {
        "search_impressions": _num(impressions), "ctr_pct": _num(ctr), "conversion_pct": _num(conv),
        "comp_search_impressions": _num(c_impressions), "comp_ctr_pct": _num(c_ctr), "comp_conversion_pct": _num(c_conv),
        "market_demand_change_pct": demand if demand != 0 else None, "review_score": _num(review),
    }
    return start, end, values


def _airbnb_form(key):
    st.caption("Airbnb → Prestazioni → **Conversione** e **Visualizzazioni** (filtra l'annuncio e il periodo).")
    today = datetime.date.today()
    c0, c1 = st.columns(2)
    start = c0.date_input("Dal:", today.replace(day=1), key=f"{key}_start")
    end = c1.date_input("Al:", today, key=f"{key}_end")

    a1, a2, a3 = st.columns(3)
    views = a1.number_input("Visualizzazioni della pagina", min_value=0, step=1, key=f"{key}_views")
    impressions = a2.number_input("Impressioni nella prima pagina di ricerca", min_value=0, step=1, key=f"{key}_imp")
    first_page = a3.number_input("% impressioni nella prima pagina", min_value=0.0, max_value=100.0, step=0.1, format="%.2f", key=f"{key}_fp")
    b1, b2, b3 = st.columns(3)
    ctr = b1.number_input("% conversione ricerca-alloggio", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=f"{key}_ctr")
    conv = b2.number_input("% conversione annuncio-prenotazione", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=f"{key}_conv")
    overall = b3.number_input("% conversione globale", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", key=f"{key}_glob")
    review = st.number_input("Punteggio recensioni (0–5), facoltativo", min_value=0.0, max_value=5.0, step=0.01, key=f"{key}_rev")

    values = {
        "listing_views": _num(views), "search_impressions": _num(impressions), "first_page_pct": _num(first_page),
        "ctr_pct": _num(ctr), "conversion_pct": _num(conv), "overall_conversion_pct": _num(overall),
        "review_score": _num(review),
    }
    return start, end, values


def _history_table(df):
    """Storico leggibile: valori della struttura con il benchmark competitor accanto (Booking)."""
    def pct(v):
        return f"{v:.2f}%" if pd.notna(v) else "—"

    def vs(mine, comp):
        if pd.isna(mine) or pd.isna(comp) or comp == 0:
            return pct(mine)
        return f"{mine:.2f}% ({(mine / comp - 1) * 100:+.0f}% vs comp.)"

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "Periodo": f"{pd.to_datetime(r['period_start']):%d/%m} → {pd.to_datetime(r['period_end']):%d/%m/%y}",
            "Canale": _CHANNELS.get(r['channel'], r['channel']),
            "Impressioni": f"{int(r['search_impressions']):,}" if pd.notna(r.get('search_impressions')) else "—",
            "CTR": vs(r.get('ctr_pct'), r.get('comp_ctr_pct')),
            "Conversione": vs(r.get('conversion_pct'), r.get('comp_conversion_pct')),
            "Visualizzazioni": f"{int(r['listing_views']):,}" if pd.notna(r.get('listing_views')) else "—",
            "Domanda dest.": f"{r['market_demand_change_pct']:+.0f}%" if pd.notna(r.get('market_demand_change_pct')) else "—",
        })
    return pd.DataFrame(rows)


def render_funnel_tab(supabase, tenant_id):
    st.subheader("🔎 Visibilità OTA — inserimento settimanale")
    st.caption("Copia i numeri dai report di Booking e Airbnb: servono al diagnostico per capire se il problema è "
               "di posizionamento (impressioni), di vetrina (CTR) o di scheda e condizioni (conversione). "
               "I campi lasciati a 0 non vengono salvati; risalvando lo stesso periodo si aggiornano solo i campi compilati.")

    props = db.load_properties(supabase, tenant_id)
    if props.empty:
        st.info("Carica prima le prenotazioni per registrare le tue proprietà.")
        return
    names = dict(zip(props['id'], props['name']))

    c1, c2 = st.columns([2, 1])
    pid = c1.selectbox("🏠 Struttura:", list(names.keys()), format_func=lambda p: names[p], key="funnel_prop")
    channel = c2.radio("Canale:", list(_CHANNELS.keys()), format_func=_CHANNELS.get, horizontal=True, key="funnel_channel")

    with st.container(border=True):
        start, end, values = (_booking_form if channel == "booking" else _airbnb_form)(f"funnel_{channel}")
        if st.button("💾 Salva dati funnel", type="primary", key="funnel_save"):
            if end < start:
                st.error("La data di fine deve essere successiva a quella di inizio.")
            elif all(v is None for v in values.values()):
                st.error("Compila almeno un valore.")
            else:
                # solo i campi compilati: un nuovo salvataggio dello stesso periodo non cancella i valori già inseriti
                filled = {k: v for k, v in values.items() if v is not None}
                db.save_funnel_metrics(supabase, tenant_id, pid, channel, start, end, filled)
                st.success(f"✅ Dati {_CHANNELS[channel]} salvati per {names[pid]} ({start:%d/%m} → {end:%d/%m/%Y}).")

    st.markdown(f"##### 📋 Storico — {names[pid]}")
    hist = db.load_funnel_metrics(supabase, tenant_id, property_id=pid)
    if hist.empty:
        st.info("Nessun dato inserito per questa struttura.")
        return
    st.dataframe(_history_table(hist), hide_index=True, use_container_width=True)

    with st.expander("🗑️ Elimina un inserimento"):
        labels = {r['id']: f"{_CHANNELS.get(r['channel'], r['channel'])} · "
                           f"{pd.to_datetime(r['period_start']):%d/%m} → {pd.to_datetime(r['period_end']):%d/%m/%y}"
                  for _, r in hist.iterrows()}
        to_delete = st.selectbox("Inserimento:", list(labels.keys()), format_func=labels.get, key="funnel_del_sel")
        if st.button("Elimina", key="funnel_del_btn"):
            db.delete_funnel_metrics(supabase, to_delete)
            st.rerun()
