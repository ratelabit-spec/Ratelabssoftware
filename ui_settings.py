"""
Sezioni di configurazione della tab Dati: calendario di apertura e costi.
Tutte le azioni possono essere applicate a più unità in un colpo solo.
"""
import datetime
import pandas as pd
import streamlit as st

import db
from capacity import capacity_by_property

PAYER_LABELS = {"pm": "PM", "owner": "Proprietario"}

_FISSI_CAT = [
    "IMU", "TARI", "Assicurazione", "Affitto",
    "Internet / WiFi", "Pulizie comuni", "Manutenzione", "Altra spesa fissa",
]
_UTIL_CAT = ["Luce", "Gas", "Acqua", "Condominio", "Altra utenza"]
_VAR_CAT = {
    "cleaning":  "🧹 Pulizia appartamento",
    "laundry":   "👕 Lavanderia / Biancheria",
    "amenities": "🎁 Kit benvenuto / Dotazioni",
    "other":     "🔧 Altro costo operativo",
}


def _units_picker(props, label, key, default_ids):
    """Multiselect di unità + opzione 'tutte'. Ritorna la lista di property_id scelti."""
    names = dict(zip(props['id'], props['name']))
    all_units = st.checkbox("Applica a tutte le unità", key=f"{key}_all")
    chosen = st.multiselect(label, list(names.keys()), default=default_ids,
                            format_func=lambda pid: names[pid], key=f"{key}_sel", disabled=all_units)
    return list(names.keys()) if all_units else chosen


def _done(msg):
    st.cache_data.clear()
    st.success(msg)
    st.rerun()


# ──────────────────────────────────────────
# CALENDARIO DI APERTURA
# ──────────────────────────────────────────
def render_availability_section(supabase, tenant_id):
    st.subheader("📅 Calendario di Apertura")
    st.caption(
        "Indica quando ogni unità è aperta alla vendita: l'occupancy e il Bottom Rate vengono calcolati solo sulle "
        "notti realmente vendibili. In un anno senza periodi registrati l'unità è considerata aperta tutto l'anno."
    )

    props = db.load_properties(supabase, tenant_id)
    if props.empty:
        st.info("Carica un file di prenotazioni per registrare le tue proprietà.")
        return
    periods = db.load_availability(supabase, tenant_id)
    names = dict(zip(props['id'], props['name']))

    # Riepilogo dell'anno in corso
    year = datetime.date.today().year
    open_nights = capacity_by_property(props, periods, f"{year}-01-01", f"{year}-12-31")
    summary = pd.DataFrame({
        'Unità': props['name'],
        'Camere/unità vendibili': props['units'].astype(int),
        'Periodi registrati': props['id'].map(lambda pid: int((periods['property_id'] == pid).sum())),
        f'Notti vendibili {year}': props['name'].map(open_nights),
    })
    with st.expander(f"📋 Riepilogo aperture {year}", expanded=False):
        st.dataframe(summary, hide_index=True, use_container_width=True)

    col_l, col_r = st.columns([3, 2])
    with col_l:
        sel = st.selectbox("🏠 Unità:", list(names.keys()), format_func=lambda pid: names[pid], key="avail_view")
        units_now = int(props.loc[props['id'] == sel, 'units'].iloc[0])
        with st.form("form_units"):
            new_units = st.number_input("Camere/unità vendibili (per hotel o strutture con più camere)",
                                        min_value=1, value=units_now, step=1)
            if st.form_submit_button("💾 Aggiorna unità") and new_units != units_now:
                db.update_property_units(supabase, sel, new_units)
                _done(f"✅ {names[sel]}: {new_units} unità vendibili.")

        own = periods[periods['property_id'] == sel]
        if own.empty:
            st.info("Nessun periodo registrato: unità considerata aperta tutto l'anno.")
        for _, per in own.iterrows():
            ca, cb, cc = st.columns([3, 3, 0.6])
            ca.markdown(f"**{pd.to_datetime(per['open_from']):%d/%m/%Y} → {pd.to_datetime(per['open_to']):%d/%m/%Y}**")
            cb.caption(per['notes'] or "")
            if cc.button("🗑️", key=f"del_av_{per['id']}", help="Elimina periodo"):
                db.delete_availability(supabase, per['id'])
                _done("✅ Periodo eliminato.")

    with col_r:
        st.markdown("##### ➕ Aggiungi periodo di apertura")
        target = _units_picker(props, "Unità:", "avail_add", [sel])
        with st.form("form_availability"):
            c1, c2 = st.columns(2)
            d_from = c1.date_input("Aperta dal:", datetime.date(year, 4, 1))
            d_to   = c2.date_input("Al:", datetime.date(year, 10, 31))
            notes  = st.text_input("Note (opzionale)", placeholder="es. Stagione estiva")
            if st.form_submit_button("💾 Salva periodo", type="primary"):
                if not target:
                    st.error("Seleziona almeno un'unità.")
                elif d_to < d_from:
                    st.error("La data di fine deve essere successiva a quella di inizio.")
                else:
                    db.add_availability(supabase, tenant_id, target, d_from, d_to, notes)
                    _done(f"✅ Periodo salvato per {len(target)} unità.")


# ──────────────────────────────────────────
# COSTI
# ──────────────────────────────────────────
def _cost_row(supabase, row, label, amount, detail, key):
    ca, cb, cc, cd, ce = st.columns([2.3, 1.1, 1.4, 1.3, 0.5])
    ca.markdown(f"**{label}**")
    cb.caption(f"€ {float(amount):,.2f}")
    cc.caption(detail)
    payer = row.get('borne_by', 'pm') or 'pm'
    other = 'owner' if payer == 'pm' else 'pm'
    if cd.button(f"👤 {PAYER_LABELS[payer]}", key=f"payer_{key}", help=f"A carico di: {PAYER_LABELS[payer]}. Clicca per passare a {PAYER_LABELS[other]}."):
        db.set_cost_payer(supabase, row['id'], other)
        _done(f"✅ {label}: ora a carico di {PAYER_LABELS[other]}.")
    if ce.button("🗑️", key=f"del_{key}", help="Elimina"):
        db.delete_cost(supabase, row['id'])
        _done("✅ Costo eliminato.")


def render_costs_section(supabase, tenant_id):
    st.subheader("⚙️ Configurazione Costi")
    st.caption(
        "Ogni costo si può applicare a più unità insieme. Se reinserisci una categoria già esistente con un nuovo "
        "importo, il valore precedente viene storicizzato: è anche il modo per modificare un costo su più unità. "
        "Il pulsante 👤 indica chi sostiene il costo (PM o proprietario): cliccalo per cambiarlo."
    )

    props = db.load_properties(supabase, tenant_id)
    if props.empty:
        st.info("Carica un file di prenotazioni per registrare le tue proprietà prima di configurare i costi.")
        return
    names = dict(zip(props['id'], props['name']))

    sel = st.selectbox("🏠 Unità:", list(names.keys()), format_func=lambda pid: names[pid], key="prop_cost_sel")
    df_fix, df_var, df_util = db.load_costs(supabase, tenant_id, property_id=sel)
    settings = db.load_current_settings(supabase, tenant_id, sel)
    current_cf = float(settings.get('cleaning_fee') or 0) if settings else 0.0

    # ── Quota pulizie addebitata al guest ──
    with st.expander(f"🧹 Quota Pulizie addebitata al Guest — {names[sel]}: €{current_cf:.2f}/soggiorno", expanded=(current_cf == 0)):
        st.caption("Viene aggiunta al ricavo lordo nel calcolo del margine (è un ricavo, non un costo).")
        target_cf = _units_picker(props, "Applica a:", "cf", [sel])
        with st.form("form_cleaning_fee"):
            new_cf = st.number_input("Importo per soggiorno (€):", min_value=0.0, value=current_cf, step=5.0, format="%.2f")
            if st.form_submit_button("💾 Aggiorna", type="primary"):
                if not target_cf:
                    st.error("Seleziona almeno un'unità.")
                else:
                    for pid in target_cf:
                        db.update_settings(supabase, tenant_id, pid, {"cleaning_fee": float(new_cf)})
                    _done(f"✅ Quota pulizie €{new_cf:.2f}/soggiorno salvata per {len(target_cf)} unità.")

    cl_left, cl_right = st.columns([3, 2])

    # ── Costi configurati per l'unità selezionata ──
    with cl_left:
        st.markdown(f"##### 📋 Costi configurati — {names[sel]}")

        st.caption("**🏛️ Spese Strutturali** — IMU, TARI, assicurazione, affitto…")
        freq_map = {'monthly': 'Mensile', 'yearly': 'Annuale'}
        for _, r in df_fix.iterrows():
            _cost_row(supabase, r, r['category'], r['amount'], freq_map.get(r['frequency'], r['frequency']), f"fix_{r['id']}")
        if df_fix.empty:
            st.info("Nessuna spesa strutturale configurata.")
        st.divider()

        st.caption("**⚡ Bollette Utenze** — ultime 8 inserite")
        for _, r in df_util.head(8).iterrows():
            period = f"{pd.to_datetime(r['period_from']):%d/%m/%y} → {pd.to_datetime(r['period_to']):%d/%m/%y}"
            _cost_row(supabase, r, r['category'], r['amount'], period, f"util_{r['id']}")
        if df_util.empty:
            st.info("Nessuna bolletta inserita.")
        st.divider()

        st.caption("**🔑 Costi per Prenotazione** — pulizie, lavanderia…")
        basis_map = {'per_booking': '/prenotazione', 'per_night': '/notte', 'per_guest': '/ospite'}
        for _, r in df_var.iterrows():
            label = _VAR_CAT.get(r['cost_type'], r['cost_type']).split(' ', 1)[-1]
            _cost_row(supabase, r, label, r['value'], basis_map.get(r['basis'], r['basis']), f"var_{r['id']}")
        if df_var.empty:
            st.info("Nessun costo operativo configurato.")

    # ── Aggiunta costi (anche su più unità) ──
    with cl_right:
        st.markdown("##### ➕ Aggiungi costo")
        tipo = st.radio("Tipo:", ["🏛️ Strutturale", "⚡ Bolletta Utenza", "🔑 Per Prenotazione"], key="tipo_costo_radio")
        target = _units_picker(props, "Applica a:", "cost_add", [sel])

        if tipo == "🏛️ Strutturale":
            with st.form("form_costi_fix"):
                cat    = st.selectbox("Categoria:", _FISSI_CAT)
                amount = st.number_input("Importo (€)", min_value=0.0, step=10.0, format="%.2f")
                freq   = st.radio("Frequenza:", ["Mensile", "Annuale"], horizontal=True)
                split  = st.checkbox("Ripartisci l'importo tra le unità selezionate",
                                     help="Es. un contratto internet unico per tutto l'edificio.")
                payer  = st.radio("A carico di:", ["Proprietario", "PM"], horizontal=True)
                d_from = st.date_input("Valido dal:", datetime.date.today())
                if st.form_submit_button("💾 Salva", type="primary"):
                    if amount <= 0 or not target:
                        st.error("Inserisci un importo > 0 e almeno un'unità.")
                    else:
                        each = amount / len(target) if split else amount
                        for pid in target:
                            db.save_recurring_cost(supabase, tenant_id, pid, cat,
                                                   "monthly" if freq == "Mensile" else "yearly", each, d_from,
                                                   borne_by="owner" if payer == "Proprietario" else "pm")
                        _done(f"✅ {cat} — €{each:.2f}/{freq.lower()} salvato per {len(target)} unità.")

        elif tipo == "⚡ Bolletta Utenza":
            st.caption("Inserisci ogni bolletta con il suo periodo: il costo viene proratato sui giorni corretti.")
            with st.form("form_costi_util"):
                cat    = st.selectbox("Utenza:", _UTIL_CAT)
                amount = st.number_input("Importo bolletta (€)", min_value=0.0, step=1.0, format="%.2f")
                c1, c2 = st.columns(2)
                d_from = c1.date_input("Dal:", datetime.date.today().replace(day=1))
                d_to   = c2.date_input("Al:", datetime.date.today())
                split  = st.checkbox("Ripartisci l'importo tra le unità selezionate", value=True,
                                     help="Es. una bolletta condominiale unica per più appartamenti.")
                payer  = st.radio("A carico di:", ["Proprietario", "PM"], horizontal=True)
                notes  = st.text_input("Note (opzionale)", placeholder="es. Bimestre gen-feb")
                if st.form_submit_button("💾 Salva Bolletta", type="primary"):
                    if amount <= 0 or not target:
                        st.error("Inserisci un importo > 0 e almeno un'unità.")
                    elif d_to < d_from:
                        st.error("La data 'Al' deve essere successiva alla data 'Dal'.")
                    else:
                        each = amount / len(target) if split else amount
                        for pid in target:
                            db.save_utility_bill(supabase, tenant_id, pid, cat, each, d_from, d_to, notes,
                                                 borne_by="owner" if payer == "Proprietario" else "pm")
                        _done(f"✅ Bolletta {cat} salvata per {len(target)} unità (€{each:.2f} ciascuna).")

        else:
            st.caption("Pulizie, lavanderia, kit — costo che si applica a ogni arrivo, per ogni unità.")
            with st.form("form_costi_var"):
                var_lbl = st.selectbox("Categoria:", list(_VAR_CAT.values()))
                cat     = list(_VAR_CAT.keys())[list(_VAR_CAT.values()).index(var_lbl)]
                amount  = st.number_input("Importo (€)", min_value=0.0, step=5.0, format="%.2f")
                base    = st.radio("Si applica:", ["Per prenotazione", "Per notte", "Per ospite"], horizontal=True)
                payer   = st.radio("A carico di:", ["PM", "Proprietario"], horizontal=True)
                d_from  = st.date_input("Valido dal:", datetime.date.today())
                if st.form_submit_button("💾 Salva", type="primary"):
                    if amount <= 0 or not target:
                        st.error("Inserisci un importo > 0 e almeno un'unità.")
                    else:
                        basis = {"Per prenotazione": "per_booking", "Per notte": "per_night", "Per ospite": "per_guest"}[base]
                        for pid in target:
                            db.save_recurring_cost(supabase, tenant_id, pid, cat, basis, amount, d_from,
                                                   borne_by="owner" if payer == "Proprietario" else "pm")
                        _done(f"✅ {var_lbl.split(' ', 1)[1]} — €{amount:.2f} {base.lower()} salvato per {len(target)} unità.")

        with st.expander("🗑️ Elimina un costo da più unità"):
            fix_all, var_all, _ = db.load_costs(supabase, tenant_id)
            options = sorted({("fixed", c) for c in fix_all['category']} | {("var", c) for c in var_all['cost_type']})
            if not options:
                st.caption("Nessun costo ricorrente configurato.")
            else:
                choice = st.selectbox("Costo:", options,
                                      format_func=lambda o: o[1] if o[0] == "fixed" else _VAR_CAT.get(o[1], o[1]),
                                      key="bulk_del_cat")
                source = fix_all[fix_all['category'] == choice[1]] if choice[0] == "fixed" else var_all[var_all['cost_type'] == choice[1]]
                having = [pid for pid in props['id'] if pid in set(source['property_id'])]
                del_target = st.multiselect("Da queste unità:", having, default=having,
                                            format_func=lambda pid: names[pid], key="bulk_del_units")
                if st.button("Elimina", key="bulk_del_btn") and del_target:
                    for cost_id in source[source['property_id'].isin(del_target)]['id']:
                        db.delete_cost(supabase, cost_id)
                    _done(f"✅ Costo eliminato da {len(del_target)} unità.")
