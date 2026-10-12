"""
Scraping pubblico del comp set (Apify) → market_snapshots.
Job standalone (da schedulare): legge i competitor attivi di TUTTI i tenant con la service_role key.

Variabili d'ambiente richieste: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, APIFY_API_TOKEN
"""
import os
import re
import urllib.parse
from datetime import date, timedelta

from apify_client import ApifyClient
from supabase import create_client

APIFY_ACTOR = "noraview/booking-price-scraper"
DAYS_AHEAD = 3  # versione light: solo i prossimi 3 giorni


def _clean_price(raw):
    if not raw:
        return 0.0
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(raw).replace(',', '.'))
    return float(nums[0]) if nums else 0.0


def main():
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    apify = ApifyClient(os.environ["APIFY_API_TOKEN"])

    competitors = supabase.table("competitors").select("id, tenant_id, property_id, url") \
        .eq("platform", "booking").eq("is_active", True).execute().data
    if not competitors:
        print("Nessun competitor attivo.")
        return

    today = date.today()
    stay_dates = [today + timedelta(days=i) for i in range(1, DAYS_AHEAD + 1)]

    hotel_urls, url_map = [], {}
    for comp in competitors:
        base_url = comp['url'].split('?')[0]
        hotel_path = urllib.parse.urlparse(base_url).path
        for d in stay_dates:
            checkin, checkout = d.isoformat(), (d + timedelta(days=1)).isoformat()
            hotel_urls.append({"url": f"{base_url}?checkin={checkin}&checkout={checkout}"
                                      f"&group_adults=2&no_rooms=1&selected_currency=EUR", "method": "GET"})
            url_map[f"{hotel_path}_{checkin}"] = (comp, checkin)

    print(f"Invio {len(hotel_urls)} URL ad Apify...")
    run = apify.actor(APIFY_ACTOR).call(
        run_input={"hotelUrls": hotel_urls, "includeSoldOut": True, "useApifyProxy": True}
    )

    records = []
    for item in apify.dataset(run["defaultDatasetId"]).iterate_items():
        parsed = urllib.parse.urlparse(item.get("url", ""))
        checkin = urllib.parse.parse_qs(parsed.query).get('checkin', [None])[0]
        match = url_map.get(f"{parsed.path}_{checkin}")
        if not match:
            continue
        comp, stay_date = match
        price = _clean_price(item.get("priceAmount") or item.get("price"))
        records.append({
            "tenant_id":     comp['tenant_id'],
            "property_id":   comp['property_id'],
            "competitor_id": comp['id'],
            "stay_date":     stay_date,
            "captured_on":   today.isoformat(),
            "price":         price,
            "is_available":  price > 0,  # prezzo 0 = sold out
        })

    if records:
        supabase.table("market_snapshots").upsert(
            records, on_conflict="property_id,competitor_id,stay_date,captured_on"
        ).execute()
        print(f"Salvati {len(records)} prezzi.")
    else:
        print("Nessun risultato mappato: Booking potrebbe aver cambiato struttura.")


if __name__ == "__main__":
    main()
