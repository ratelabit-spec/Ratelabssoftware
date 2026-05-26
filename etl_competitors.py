import streamlit as st
from supabase import create_client
from apify_client import ApifyClient
from datetime import datetime, timedelta
import urllib.parse
import re

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
print("🚀 Iniciando Cerebro de Competitive Set...")
supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
apify = ApifyClient(st.secrets["APIFY_API_TOKEN"])
USER_ID = st.secrets["USER_ID"]

def get_smart_sampling_dates():
    """Versión LIGHT: Solo los próximos 3 días"""
    today = datetime.now()
    return [today + timedelta(days=i) for i in range(1, 4)]

# --- 2. DESCARGAR CATÁLOGO DE COMPETIDORES ---
print("📥 Obteniendo competidores de Supabase...")
res_comp = supabase.table("competitors").select("id, name, booking_url").eq("user_id", USER_ID).execute()
competitors = res_comp.data

if not competitors:
    print("❌ No tienes competidores registrados.")
    exit()

print(f"✅ Se encontraron {len(competitors)} competidores.")

# --- 3. PREPARAR URLS PARA APIFY ---
target_dates = get_smart_sampling_dates()
hotel_urls = []
url_to_competitor_map = {} 

for comp in competitors:
    base_url = comp['booking_url'].split('?')[0] 
    # Extraemos solo la ruta del hotel (ej: /hotel/it/trullo-bello.html) para un mapeo a prueba de balas
    hotel_path = urllib.parse.urlparse(base_url).path
    
    for date_obj in target_dates:
        checkin_str = date_obj.strftime('%Y-%m-%d')
        checkout_str = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
        
        final_url = f"{base_url}?checkin={checkin_str}&checkout={checkout_str}&group_adults=2&no_rooms=1&selected_currency=EUR"
        
        hotel_urls.append({"url": final_url, "method": "GET"})
        
        # Guardamos la relación usando un ID compuesto: RutaHotel + Fecha
        mapping_key = f"{hotel_path}_{checkin_str}"
        url_to_competitor_map[mapping_key] = {
            "competitor_id": comp['id'],
            "stay_date": checkin_str
        }

print(f"🕸️ Enviando {len(hotel_urls)} URLs a Apify (Smart Sampling)...")

# --- 4. EJECUTAR EL SCRAPER EN APIFY ---
run_input = {
    "hotelUrls": hotel_urls,
    "includeSoldOut": True,
    "useApifyProxy": True
}

print("⏳ Scraping in corso (esto puede tomar 1-3 minutos)...")
run = apify.actor("noraview/booking-price-scraper").call(run_input=run_input)

# --- 5. PROCESAR RESULTADOS Y GUARDAR EN SUPABASE ---
print("✅ Scraping finalizado. Limpiando datos...")
dataset_items = apify.dataset(run["defaultDatasetId"]).iterate_items()

records_to_insert = []

for item in dataset_items:
    original_url = item.get("url", "")
    
    # 5.1 Reconstrucción de la clave de mapeo desde la URL devuelta
    parsed_url = urllib.parse.urlparse(original_url)
    returned_path = parsed_url.path
    # Buscamos el parámetro checkin en la URL devuelta
    query_params = urllib.parse.parse_qs(parsed_url.query)
    returned_checkin = query_params.get('checkin', [None])[0]
    
    if returned_path and returned_checkin:
        mapping_key = f"{returned_path}_{returned_checkin}"
        mapping_data = url_to_competitor_map.get(mapping_key)
        
        if mapping_data:
            # 5.2 Limpieza segura del precio
            raw_price = item.get("priceAmount") or item.get("price")
            clean_price = 0.0
            
            if raw_price:
                try:
                    # Extraer solo números y puntos decimales en caso de recibir "€ 150,00"
                    price_str = str(raw_price).replace(',', '.')
                    numbers_only = re.findall(r"[-+]?\d*\.\d+|\d+", price_str)
                    if numbers_only:
                        clean_price = float(numbers_only[0])
                except Exception as e:
                    print(f"⚠️ Error al parsear precio {raw_price}: {e}")
            
            records_to_insert.append({
                "competitor_id": mapping_data["competitor_id"],
                "stay_date": mapping_data["stay_date"],
                "price": clean_price,
                "is_available": clean_price > 0 # Si el precio es 0, asumimos sold out
            })

if records_to_insert:
    supabase.table("comp_set_prices").upsert(records_to_insert, on_conflict="competitor_id, stay_date").execute()
    print(f"🎉 ¡Éxito! Se han guardado {len(records_to_insert)} precios nuevos.")
else:
    print("⚠️ No se pudieron mapear resultados. Booking puede haber cambiado la estructura.")