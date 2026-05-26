# etl_metrics.py
import pandas as pd

def calculate_property_margins(df_res, df_fixed, df_vars, year):
    """Cruza reservas con costes para obtener el desglose financiero."""
    
    # Defensa 1: Si no hay reservas en absoluto, salimos rápido
    if df_res is None or df_res.empty:
        return 0, 0, 0, 0, 0

    # Defensa 2: Prevenir el SettingWithCopyWarning de Pandas usando .copy()
    df_res = df_res.copy()
    
    # 1. Filtro por año seguro
    df_res['check_in_date'] = pd.to_datetime(df_res['check_in_date'], errors='coerce')
    df_res_year = df_res[df_res['check_in_date'].dt.year == year]
    
    # Si tras filtrar por año no quedan reservas, los ingresos son 0
    if df_res_year.empty:
        return 0, 0, 0, 0, 0
        
    total_reservas = len(df_res_year)
    total_noches = df_res_year['nights'].sum()

    # 2. Ingresos y comisiones (Directo de las reservas)
    gross_revenue = float(df_res_year['gross_revenue'].sum())
    ota_commissions = float(df_res_year['commission_amount'].sum())

    # 3. Costes Variables Manuales (Vigentes)
    var_costs_total = 0.0
    
    # Defensa 3: Verificar que el DataFrame no esté vacío antes de buscar columnas
    if not df_vars.empty and 'valid_to' in df_vars.columns:
        df_vars_active = df_vars[df_vars['valid_to'].isnull()]
        for _, row in df_vars_active.iterrows():
            val = float(row['value'])
            if row['basis'] == 'per_booking':
                var_costs_total += (val * total_reservas)
            elif row['basis'] == 'per_night':
                var_costs_total += (val * total_noches)
            elif row['basis'] == 'per_guest':
                # Al no tener el dato exacto de huéspedes del PMS aún, estimamos 2 pax por reserva
                var_costs_total += (val * (total_reservas * 2))

    # 4. Costes Fijos (Vigentes)
    fixed_costs_total = 0.0
    if not df_fixed.empty and 'valid_to' in df_fixed.columns:
        df_fixed_active = df_fixed[df_fixed['valid_to'].isnull()]
        for _, row in df_fixed_active.iterrows():
            val = float(row['amount'])
            if row['frequency'] == 'monthly':
                fixed_costs_total += (val * 12)
            else: # yearly
                fixed_costs_total += val

    # 5. Margen Final
    netto_pm = gross_revenue - ota_commissions - var_costs_total - fixed_costs_total
    
    return gross_revenue, -ota_commissions, -var_costs_total, -fixed_costs_total, netto_pm