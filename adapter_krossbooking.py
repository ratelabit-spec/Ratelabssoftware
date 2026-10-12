import pandas as pd

STATI_CANCELLATI = ['Cancellata', 'Cancellata con penale']

def raggruppa_canale(canale):
    """
    Raggruppa i canali in macro-categorie.
    V1.3 - Mapeo Explícito basado en extracciones reales de KrossBooking.
    """
    if pd.isna(canale):
        return 'Altro'
        
    # Limpiamos espacios extra y usamos mayúsculas para unificar
    c_exact = str(canale).strip().upper()
    
    # 1. MAPEO EXACTO (Prioridad 1 - Basado en la lista auditada)
    if c_exact == 'BOOKING': 
        return 'Booking.com'
    elif c_exact == 'AIRBNB': 
        return 'Airbnb'
    elif c_exact in ['EXPEDIA', 'EXPEDIA AFFILIA', 'VRBO', 'HOMEAWAY_CAFR', 'HOMEAWAY_IT']: 
        return 'Expedia Group'
    elif c_exact in ['FRONTOFFICE', 'BOOKING ENGINE']: 
        return 'Diretto'
    elif c_exact == 'HTG': 
        return 'HTG'
        
    # 2. RED DE SEGURIDAD (Prioridad 2 - Por si KrossBooking añade nuevos canales en el futuro)
    c_lower = c_exact.lower()
    if 'booking' in c_lower and 'engine' not in c_lower: 
        return 'Booking.com'
    elif 'airbnb' in c_lower: 
        return 'Airbnb'
    elif any(k in c_lower for k in ['expedia', 'homeaway', 'vrbo']): 
        return 'Expedia Group'
    elif 'frontoffice' in c_lower or 'engine' in c_lower: 
        return 'Diretto'
        
    # 3. CANALES DESCONOCIDOS (Si llega aquí, es un canal 100% nuevo)
    return 'Altro'

def load_and_clean_krossbooking(file):
    """
    Carica, pulisce e arricchisce il file Excel di KrossBooking,
    restituendo un DataFrame aderente all'Internal Standard Data Model.
    """
    df = pd.read_excel(file)

    # 1. Parsing Date (a todo el dataset)
    for col in ['Check in', 'Data inserimento', 'Check-out', 'Data cancellazione']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')

    # 2. Pulizia dati corrotti
    # Eliminamos filas que no tengan fechas clave o ingresos brutos
    df = df.dropna(subset=['Check in', 'Data inserimento', 'Addebito soggiorno'])

    # 3. Metriche derivate (Aplicado a TODO el dataset, incluyendo futuras canceladas)
    df['Lead Time'] = (df['Check in'] - df['Data inserimento']).dt.days
    df['Netto PM'] = df['Quota PM'].fillna(0) if 'Quota PM' in df.columns else 0
    df['Canale_Gruppo'] = df['Canale'].apply(raggruppa_canale) if 'Canale' in df.columns else 'Altro'
    
    df['Commissioni'] = df['Commissioni'].fillna(0) if 'Commissioni' in df.columns else 0
    df['Netto_Real'] = df['Addebito soggiorno'] - df['Commissioni']

    if 'Quota proprietario' not in df.columns:
        df['Quota proprietario'] = 0
    if 'Stato' not in df.columns:
        df['Stato'] = 'Confermata'
    if 'ID' not in df.columns:
        df['ID'] = df.index

    # 4. Mappatura verso l'Internal Standard Data Model
    col_mapping = {
        'ID': 'id',
        'Camere': 'unit_id',
        'Check in': 'check_in_date',
        'Check-out': 'check_out_date',
        'Data inserimento': 'booking_date',
        'Addebito soggiorno': 'gross_revenue',
        'Commissioni': 'commission_amount',
        'Netto_Real': 'net_revenue',
        'Netto PM': 'pm_net',
        'Quota proprietario': 'owner_net',
        'Notti': 'nights',
        'Stato': 'status',
        'Canale': 'channel',
        'Canale_Gruppo': 'channel_group',
        'Lead Time': 'lead_time',
        'Data cancellazione': 'cancellation_date'
    }
    df = df.rename(columns=col_mapping)

    # 5. SPLIT FINALE (Separazione attive e cancellate con tutte le metriche calcolate)
    if 'cancellation_date' in df.columns:
        df_cancellate = df[df['cancellation_date'].notna()].copy()
        df_attive = df[df['cancellation_date'].isna()].copy()
    elif 'status' in df.columns: # 'Stato' ahora es 'status'
        df_cancellate = df[df['status'].isin(STATI_CANCELLATI)].copy()
        df_attive = df[~df['status'].isin(STATI_CANCELLATI)].copy()
    else:
        df_cancellate = pd.DataFrame()
        df_attive = df.copy()

    return df_attive, df_cancellate
