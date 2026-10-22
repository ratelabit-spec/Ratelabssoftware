# etl_metrics.py
import pandas as pd


def _reservations_of_year(df_res, year):
    if df_res is None or df_res.empty:
        return pd.DataFrame()
    df_res = df_res.copy()
    df_res['check_in_date'] = pd.to_datetime(df_res['check_in_date'], errors='coerce')
    return df_res[df_res['check_in_date'].dt.year == year]


def _costs_for_year(df_res_year, df_fixed, df_vars, df_util, year):
    """Ritorna (costi_variabili, costi_fissi_e_utenze) dell'anno, entrambi positivi."""
    total_reservas = len(df_res_year)
    total_noches = df_res_year['nights'].sum() if total_reservas else 0

    # Costi variabili vigenti
    var_costs_total = 0.0
    if df_vars is not None and not df_vars.empty and 'valid_to' in df_vars.columns:
        for _, row in df_vars[df_vars['valid_to'].isnull()].iterrows():
            val = float(row['value'])
            if row['basis'] == 'per_booking':
                var_costs_total += val * total_reservas
            elif row['basis'] == 'per_night':
                var_costs_total += val * total_noches
            elif row['basis'] == 'per_guest':
                # Senza il dato ospiti dal PMS stimiamo 2 pax per prenotazione
                var_costs_total += val * total_reservas * 2

    # Costi fissi vigenti
    fixed_costs_total = 0.0
    if df_fixed is not None and not df_fixed.empty and 'valid_to' in df_fixed.columns:
        for _, row in df_fixed[df_fixed['valid_to'].isnull()].iterrows():
            val = float(row['amount'])
            fixed_costs_total += val * 12 if row['frequency'] == 'monthly' else val

    # Bollette utenze — proratate per l'anno analizzato
    util_costs_total = 0.0
    if df_util is not None and not df_util.empty:
        df_util = df_util.copy()
        df_util['period_from'] = pd.to_datetime(df_util['period_from'], errors='coerce')
        df_util['period_to']   = pd.to_datetime(df_util['period_to'],   errors='coerce')
        year_start, year_end = pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31)
        for _, bill in df_util.iterrows():
            p_from, p_to = bill['period_from'], bill['period_to']
            if pd.isna(p_from) or pd.isna(p_to):
                continue
            overlap_start, overlap_end = max(p_from, year_start), min(p_to, year_end)
            if overlap_end >= overlap_start:
                bill_days    = max((p_to - p_from).days + 1, 1)
                overlap_days = (overlap_end - overlap_start).days + 1
                util_costs_total += float(bill['amount']) * overlap_days / bill_days

    return var_costs_total, fixed_costs_total + util_costs_total


def calculate_property_margins(df_res, df_fixed, df_vars, year, df_util=None, cleaning_fee=0.0):
    """Cruza reservas con costes para obtener el desglose financiero de la estructura."""
    df_res_year = _reservations_of_year(df_res, year)
    if df_res_year.empty:
        return 0, 0, 0, 0, 0

    # cleaning_fee viene sommata perché il PMS non la include nel gross_revenue
    gross_revenue = float(df_res_year['gross_revenue'].sum()) + float(cleaning_fee) * len(df_res_year)
    ota_commissions = float(df_res_year['commission_amount'].sum())
    var_costs, fixed_costs = _costs_for_year(df_res_year, df_fixed, df_vars, df_util, year)

    netto = gross_revenue - ota_commissions - var_costs - fixed_costs
    return gross_revenue, -ota_commissions, -var_costs, -fixed_costs, netto


def calculate_pm_owner_split(df_res, df_fixed, df_vars, year, df_util=None):
    """
    Ripartizione PM / proprietario:
      quota (Quota PM / Quota Proprietario dal PMS) − costi a carico di ciascuno = netto.
    Ritorna {'pm': {...}, 'owner': {...}} con chiavi quota, var, fixed, netto (costi positivi).
    """
    df_res_year = _reservations_of_year(df_res, year)
    out = {}
    for payer, quota_col in (('pm', 'pm_net'), ('owner', 'owner_net')):
        quota = float(df_res_year[quota_col].sum()) if not df_res_year.empty else 0.0

        def _mine(df):
            if df is None or df.empty or 'borne_by' not in df.columns:
                return df if payer == 'pm' else None   # senza borne_by: tutto a carico del PM
            return df[df['borne_by'] == payer]

        var_costs, fixed_costs = _costs_for_year(df_res_year, _mine(df_fixed), _mine(df_vars), _mine(df_util), year)
        out[payer] = {"quota": quota, "var": var_costs, "fixed": fixed_costs,
                      "netto": quota - var_costs - fixed_costs}
    return out
