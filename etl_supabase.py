import os
import pandas as pd
import math
from supabase import create_client, Client

def _get_supabase_credentials():
    """Lee credenciales desde st.secrets (Streamlit) o variables de entorno (standalone)."""
    try:
        import streamlit as st
        return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    except Exception:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise EnvironmentError("Credenziali Supabase non trovate. Configura .streamlit/secrets.toml oppure le variabili d'ambiente SUPABASE_URL e SUPABASE_KEY.")
        return url, key

def upload_to_supabase(supabase_client: Client, df: pd.DataFrame, user_id: str):
    """
    Sube propiedades y reservas a Supabase de forma segura y dividida en lotes (chunks)
    para evitar caídas del servidor por Payload Too Large.
    """
    if df is None or df.empty:
        print("⚠️ No hay datos para subir.")
        return False, "Nessun dato valido da sincronizzare."

    print("🚀 Iniciando carga a Supabase...")
    
    try:
        # 1. CARGAR PROPIEDADES (Apartamentos)
        print("🏠 Sincronizando apartamentos...")
        unique_props = df['unit_id'].dropna().unique()
        prop_mapping = {}
        
        for prop_name in unique_props:
            data = {
                "user_id": user_id,
                "kross_unit_id": prop_name
            }
            res = supabase_client.table('properties').upsert(data, on_conflict='user_id, kross_unit_id').execute()
            prop_mapping[prop_name] = res.data[0]['id']

        # 2. PREPARAR RESERVAS CON DEFENSAS DE TIPO
        print("📅 Sincronizando reservas...")
        records = []
        
        for _, row in df.iterrows():
            record = {
                "user_id": user_id,
                "property_id": prop_mapping[row['unit_id']],
                "pms_reservation_id": str(row['id']),
                "check_in_date": row['check_in_date'].strftime('%Y-%m-%d'),
                "check_out_date": row['check_out_date'].strftime('%Y-%m-%d') if pd.notnull(row['check_out_date']) else None,
                "booking_date": row['booking_date'].strftime('%Y-%m-%d'),
                
                # Defensas usando .get y casting seguro por si el df trae datos sucios
                "gross_revenue": float(row.get('gross_revenue', 0) or 0),
                "commission_amount": float(row.get('commission_amount', 0) or 0),
                "net_revenue": float(row.get('net_revenue', 0) or 0),
                "pm_net": float(row.get('pm_net', 0) or 0),
                "owner_net": float(row.get('owner_net', 0) or 0),
                "nights": int(row.get('nights', 0) or 0),
                "lead_time": int(row.get('lead_time', 0) or 0),
                
                "status": str(row.get('status', 'Confermata')),
                "channel": str(row.get('channel', 'Altro')),
                "channel_group": str(row.get('channel_group', 'Altro'))
            }
            records.append(record)

        # 3. CHUNKING (Subir en lotes de 1000 para no saturar la API)
        chunk_size = 1000
        total_records = len(records)
        total_chunks = math.ceil(total_records / chunk_size)
        
        for i in range(total_chunks):
            start_idx = i * chunk_size
            end_idx = start_idx + chunk_size
            chunk = records[start_idx:end_idx]
            
            supabase_client.table('reservations').upsert(
                chunk, 
                on_conflict='user_id, pms_reservation_id'
            ).execute()
            
            print(f"📦 Lote {i+1}/{total_chunks} subido ({len(chunk)} reservas)")

        print(f"✅ ¡Éxito! Se han sincronizado {total_records} reservas en la nube.")
        return True, f"✅ Sincronizzazione completata! ({total_records} record aggiornati)."
        
    except Exception as e:
        error_msg = f"Errore durante l'aggiornamento: {str(e)}"
        print(f"❌ {error_msg}")
        return False, error_msg

if __name__ == "__main__":
    from adapter_krossbooking import load_and_clean_krossbooking

    USER_ID_TEST = os.getenv("USER_ID")
    ARCHIVO_EXCEL = os.getenv("EXCEL_FILE", "Prenotazioni2025.xlsx")

    if not USER_ID_TEST:
        print("❌ Imposta la variabile d'ambiente USER_ID prima di eseguire questo script.")
        exit(1)

    try:
        supabase_url, supabase_key = _get_supabase_credentials()
        supabase_client: Client = create_client(supabase_url, supabase_key)

        df_limpio, df_cancellate = load_and_clean_krossbooking(ARCHIVO_EXCEL)

        dfs_to_concat = []
        if df_limpio is not None and not df_limpio.empty: dfs_to_concat.append(df_limpio)
        if df_cancellate is not None and not df_cancellate.empty: dfs_to_concat.append(df_cancellate)

        if dfs_to_concat:
            df_total = pd.concat(dfs_to_concat, ignore_index=True)
            upload_to_supabase(supabase_client, df_total, USER_ID_TEST)
        else:
            print("⚠️ El Excel está vacío o no se pudo leer.")
    except Exception as e:
        print(f"❌ Error: {e}")