# scripts/weekly_summary_email.py
"""
Invia un'email settimanale di riepilogo + alert agli owner di ogni tenant.
Eseguito da GitHub Actions (.github/workflows/weekly_summary_email.yml), non da Streamlit.
Usa la SUPABASE_SERVICE_ROLE_KEY (bypassa RLS) per leggere tutti i tenant/proprietà.
"""
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
from supabase import create_client

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import db  # noqa: E402

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL") or "onboarding@resend.dev"

OCC_ALERT_THRESHOLD = 40.0  # % — sotto questa soglia nei prossimi 7gg, la proprietà viene segnalata

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def load_owner_emails(tenant_id):
    members = supabase.table("tenant_members").select("user_id").eq("tenant_id", tenant_id).eq("role", "owner").execute().data
    if not members:
        return []
    profiles = supabase.table("profiles").select("email").in_("id", [m["user_id"] for m in members]).execute().data
    return [p["email"] for p in profiles if p.get("email")]


def compute_summary(df, total_units, today):
    """Stessa logica di calcola_kpi/Panoramica Anno in krossbooking_v1_1.py, ma standalone."""
    if df.empty or total_units <= 0:
        return None

    mask_canc = df["is_cancelled"].fillna(False).astype(bool)
    df_attive = df[~mask_canc].copy()
    df_canc = df[mask_canc].copy()

    year = today.year
    year_start = pd.Timestamp(year, 1, 1)
    days_ytd = (today - year_start).days + 1
    cap_ytd = total_units * days_ytd

    df_ytd = df_attive[(df_attive["check_in_date"].dt.year == year) & (df_attive["booking_date"] <= today)]
    rev_ytd = float(df_ytd["gross_revenue"].sum())
    notti_ytd = float(df_ytd["nights"].sum())
    comm_ytd = float(df_ytd["commission_amount"].sum()) if "commission_amount" in df_ytd.columns else 0.0

    adr_ytd = rev_ytd / notti_ytd if notti_ytd > 0 else 0.0
    net_adr_ytd = (rev_ytd - comm_ytd) / notti_ytd if notti_ytd > 0 else 0.0
    revpar_ytd = rev_ytd / cap_ytd if cap_ytd > 0 else 0.0
    occ_ytd = notti_ytd / cap_ytd * 100 if cap_ytd > 0 else 0.0

    # Pickup ultimi 7 giorni (prenotazioni acquisite, qualsiasi data di check-in)
    week_start = today - pd.Timedelta(days=7)
    df_pickup = df_attive[(df_attive["booking_date"] > week_start) & (df_attive["booking_date"] <= today)]
    pickup_n = int(len(df_pickup))
    pickup_rev = float(df_pickup["gross_revenue"].sum())

    # Cancellazioni ultimi 7 giorni
    df_canc_week = df_canc[(df_canc["booking_date"] > week_start) & (df_canc["booking_date"] <= today)]
    canc_n = int(len(df_canc_week))
    canc_rev_risk = float(df_canc_week["gross_revenue"].sum())

    # Occupancy prossimi 7 giorni (OTB ad oggi)
    week_end = today + pd.Timedelta(days=7)
    df_next7 = df_attive[
        (df_attive["check_in_date"] >= today)
        & (df_attive["check_in_date"] < week_end)
        & (df_attive["booking_date"] <= today)
    ]
    notti_next7 = float(df_next7["nights"].sum())
    cap_next7 = total_units * 7
    occ_next7 = notti_next7 / cap_next7 * 100 if cap_next7 > 0 else 0.0

    alerts = []
    if occ_next7 < OCC_ALERT_THRESHOLD:
        alerts.append(f"Occupancy prossimi 7 giorni al {occ_next7:.0f}% (sotto soglia {OCC_ALERT_THRESHOLD:.0f}%)")
    if canc_n >= 1:
        alerts.append(f"{canc_n} cancellazione/i nell'ultima settimana (€{canc_rev_risk:,.0f} a rischio)")

    return {
        "revenue_ytd": rev_ytd,
        "revpar_ytd": revpar_ytd,
        "occupancy_ytd": occ_ytd,
        "adr_ytd": adr_ytd,
        "net_adr_ytd": net_adr_ytd,
        "pickup_n": pickup_n,
        "pickup_rev": pickup_rev,
        "occ_next7": occ_next7,
        "canc_n": canc_n,
        "canc_rev_risk": canc_rev_risk,
        "alerts": alerts,
    }


def render_email(portfolio, per_property, today):
    all_alerts = list(portfolio["alerts"])
    for unit, s in per_property.items():
        for a in s["alerts"]:
            all_alerts.append(f"{unit}: {a}")

    alert_html = ""
    if all_alerts:
        items = "".join(f"<li>{a}</li>" for a in all_alerts)
        alert_html = f"""
        <div style="background:#fff4f2;border:1px solid #ffb4a8;border-radius:8px;padding:16px;margin-bottom:20px;">
          <p style="margin:0 0 8px;font-weight:600;color:#8c1d10;">⚠️ Punti di attenzione</p>
          <ul style="margin:0;padding-left:20px;color:#8c1d10;">{items}</ul>
        </div>
        """
    else:
        alert_html = """
        <div style="background:#f0f9f2;border:1px solid #a8dab5;border-radius:8px;padding:16px;margin-bottom:20px;">
          <p style="margin:0;font-weight:600;color:#1e7b34;">✅ Nessuna anomalia rilevata questa settimana</p>
        </div>
        """

    rows = ""
    for unit, s in sorted(per_property.items()):
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{unit}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{s['occupancy_ytd']:.1f}%</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">€{s['adr_ytd']:,.2f}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">€{s['revpar_ytd']:,.2f}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">{s['pickup_n']} (€{s['pickup_rev']:,.0f})</td>
        </tr>
        """

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#222;">
      <h2 style="margin-bottom:4px;">📊 Riepilogo settimanale</h2>
      <p style="color:#666;margin-top:0;">Portafoglio — {today.strftime('%d/%m/%Y')}</p>

      {alert_html}

      <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
        <tr>
          <td style="padding:8px;background:#f5f5f5;border-radius:6px;text-align:center;">
            <div style="font-size:12px;color:#666;">Revenue YTD</div>
            <div style="font-size:18px;font-weight:600;">€{portfolio['revenue_ytd']:,.0f}</div>
          </td>
          <td style="width:8px;"></td>
          <td style="padding:8px;background:#f5f5f5;border-radius:6px;text-align:center;">
            <div style="font-size:12px;color:#666;">RevPAR YTD</div>
            <div style="font-size:18px;font-weight:600;">€{portfolio['revpar_ytd']:,.2f}</div>
          </td>
          <td style="width:8px;"></td>
          <td style="padding:8px;background:#f5f5f5;border-radius:6px;text-align:center;">
            <div style="font-size:12px;color:#666;">Occupancy YTD</div>
            <div style="font-size:18px;font-weight:600;">{portfolio['occupancy_ytd']:.1f}%</div>
          </td>
        </tr>
      </table>

      <h3>Per appartamento</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr style="color:#666;text-align:right;">
          <th style="text-align:left;padding:8px;border-bottom:2px solid #ddd;">Appartamento</th>
          <th style="padding:8px;border-bottom:2px solid #ddd;">Occupancy YTD</th>
          <th style="padding:8px;border-bottom:2px solid #ddd;">ADR YTD</th>
          <th style="padding:8px;border-bottom:2px solid #ddd;">RevPAR YTD</th>
          <th style="padding:8px;border-bottom:2px solid #ddd;">Pickup 7gg</th>
        </tr>
        {rows}
      </table>

      <p style="color:#999;font-size:12px;margin-top:24px;">Rate Labs RMS — riepilogo automatico settimanale</p>
    </div>
    """


def send_email(to_email, subject, html):
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "html": html},
        timeout=30,
    )
    r.raise_for_status()


def main():
    today = pd.Timestamp(datetime.now(timezone.utc).date())

    tenants = supabase.table("tenants").select("id, name").execute().data or []

    sent, skipped = 0, 0
    for tenant in tenants:
        emails = load_owner_emails(tenant["id"])
        props = db.load_properties(supabase, tenant["id"])
        total_units = int(props["units"].sum()) if not props.empty else 0
        df = db.load_reservations(supabase, tenant["id"])
        if not emails or df.empty or total_units == 0:
            skipped += 1
            continue

        portfolio = compute_summary(df, total_units, today)
        if portfolio is None:
            skipped += 1
            continue

        per_property = {}
        units_by_name = dict(zip(props["name"], props["units"].astype(int)))
        for unit in sorted(df["unit_id"].dropna().unique()):
            df_unit = df[df["unit_id"] == unit]
            s = compute_summary(df_unit, units_by_name.get(unit, 1), today)
            if s:
                per_property[unit] = s

        has_alerts = bool(portfolio["alerts"]) or any(s["alerts"] for s in per_property.values())
        subject = "📊 Riepilogo settimanale" + (" — ⚠️ Attenzione richiesta" if has_alerts else "")
        html = render_email(portfolio, per_property, today)

        for email in emails:
            send_email(email, subject, html)
            print(f"Email inviata a {email} ({tenant['name']})")
            sent += 1

    print(f"Fatto. Inviate: {sent}, saltate (senza dati): {skipped}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(1)
