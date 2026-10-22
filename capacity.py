"""
Capacità vendibile (notti × unità) in base al calendario di apertura delle proprietà.

Regola: in un anno senza periodi registrati la proprietà è aperta tutto l'anno;
se nell'anno esiste almeno un periodo, sono vendibili solo i giorni dentro i periodi (estremi inclusi).
"""
import pandas as pd


def daily_open_units(props: pd.DataFrame, periods: pd.DataFrame, start, end) -> pd.DataFrame:
    """
    Matrice giorno × proprietà con le unità aperte (0 se chiusa).
    props:   colonne name, id, units (le proprietà da considerare)
    periods: colonne property_id, open_from, open_to (può essere vuoto)
    """
    days = pd.date_range(pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize(), freq='D')
    out = pd.DataFrame(index=days)
    if periods is None or periods.empty:
        periods = pd.DataFrame(columns=['property_id', 'open_from', 'open_to'])
    periods = periods.assign(open_from=pd.to_datetime(periods['open_from']),
                             open_to=pd.to_datetime(periods['open_to']))

    for _, p in props.iterrows():
        units = int(p.get('units') or 1)
        own = periods[periods['property_id'] == p['id']]
        is_open = pd.Series(True, index=days)
        for year in days.year.unique():
            in_year = days.year == year
            y_start, y_end = pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31)
            year_periods = own[(own['open_from'] <= y_end) & (own['open_to'] >= y_start)]
            if year_periods.empty:
                continue  # nessun calendario per quell'anno → aperta tutto l'anno
            open_mask = pd.Series(False, index=days)
            for _, per in year_periods.iterrows():
                open_mask |= (days >= per['open_from']) & (days <= per['open_to'])
            is_open[in_year] = open_mask[in_year]
        out[p['name']] = is_open.astype(int) * units
    return out


def capacity(props, periods, start, end) -> int:
    """Notti-unità vendibili tra start ed end (inclusi)."""
    if props is None or props.empty:
        return 0
    return int(daily_open_units(props, periods, start, end).to_numpy().sum())


def capacity_by_property(props, periods, start, end) -> dict:
    """{nome proprietà: notti-unità vendibili tra start ed end}."""
    if props is None or props.empty:
        return {}
    return daily_open_units(props, periods, start, end).sum().astype(int).to_dict()


def capacity_by_month(props, periods, year) -> pd.Series:
    """Capacità per mese (indice 1..12) di un anno."""
    if props is None or props.empty:
        return pd.Series(0, index=range(1, 13))
    daily = daily_open_units(props, periods, pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31)).sum(axis=1)
    return daily.groupby(daily.index.month).sum().reindex(range(1, 13), fill_value=0).astype(int)
