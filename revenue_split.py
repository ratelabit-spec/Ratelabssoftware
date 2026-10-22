"""
Ripartizione dei ricavi PM / proprietario per prenotazione.

Per ogni prenotazione si usa la versione di property_settings valida alla data di check-in
(se il check-in è precedente alla prima versione, vale la prima). Con split_mode 'pms' restano
le quote importate dal PMS; con 'percent' vengono ricalcolate:

    base   = addebito soggiorno − commissioni OTA   (split_basis 'net_ota')
           = addebito soggiorno                      (split_basis 'gross')
    PM     = base × pm_pct    + quota pulizie se va al PM   (o × pm_pct se 'split')
    Prop.  = base × owner_pct + quota pulizie se va al prop. (o × owner_pct se 'split')
"""
import pandas as pd

SPLIT_FIELDS = ('split_mode', 'pm_pct', 'owner_pct', 'split_basis', 'cleaning_fee_to')


def settings_for_reservations(df_res: pd.DataFrame, settings: pd.DataFrame) -> pd.DataFrame:
    """Per ogni prenotazione (stesso indice di df_res) la riga di settings valida al check-in, o NaN."""
    cols = ['cleaning_fee', *SPLIT_FIELDS]
    out = pd.DataFrame(index=df_res.index, columns=cols, dtype=object)
    if settings is None or settings.empty or df_res.empty:
        return out
    settings = settings.assign(valid_from=pd.to_datetime(settings['valid_from']),
                               valid_to=pd.to_datetime(settings['valid_to'])).sort_values('valid_from')
    check_in = pd.to_datetime(df_res['check_in_date'])
    for pid, versions in settings.groupby('property_id'):
        mask_prop = df_res['property_id'] == pid
        if not mask_prop.any():
            continue
        first = versions.iloc[0]
        for idx in df_res.index[mask_prop]:
            d = check_in[idx]
            valid = versions[(versions['valid_from'] <= d) & (versions['valid_to'].isna() | (versions['valid_to'] >= d))]
            row = valid.iloc[-1] if not valid.empty else first
            out.loc[idx, cols] = [row.get(c) for c in cols]
    return out


def apply_revenue_split(df_res: pd.DataFrame, settings: pd.DataFrame) -> pd.DataFrame:
    """
    Ritorna una copia di df_res con pm_net / owner_net ricalcolate dove split_mode = 'percent'
    (le quote originali del PMS restano in pm_net_pms / owner_net_pms) e la colonna unsplit_net
    (parte non ripartita, es. 72% + 25% → 3%).
    """
    df = df_res.copy()
    if df.empty:
        return df
    df['pm_net_pms'], df['owner_net_pms'] = df['pm_net'], df['owner_net']
    df['unsplit_net'] = 0.0

    cfg = settings_for_reservations(df, settings)
    pct_mode = cfg['split_mode'] == 'percent'
    if not pct_mode.any():
        return df

    c = cfg[pct_mode]
    r = df.loc[pct_mode]
    pm_pct    = pd.to_numeric(c['pm_pct']).fillna(0) / 100
    owner_pct = pd.to_numeric(c['owner_pct']).fillna(0) / 100
    cleaning  = pd.to_numeric(c['cleaning_fee']).fillna(0)
    base = r['gross_revenue'] - r['commission_amount'].where(c['split_basis'] == 'net_ota', 0)

    to = c['cleaning_fee_to']
    pm    = base * pm_pct    + cleaning.where(to == 'pm', 0)    + (cleaning * pm_pct).where(to == 'split', 0)
    owner = base * owner_pct + cleaning.where(to == 'owner', 0) + (cleaning * owner_pct).where(to == 'split', 0)

    df.loc[pct_mode, 'pm_net'] = pm.astype(float)
    df.loc[pct_mode, 'owner_net'] = owner.astype(float)
    # parte non ripartita del netto disponibile (soggiorno + pulizie − commissioni)
    df.loc[pct_mode, 'unsplit_net'] = (r['gross_revenue'] + cleaning - r['commission_amount'] - pm - owner).astype(float)
    return df
