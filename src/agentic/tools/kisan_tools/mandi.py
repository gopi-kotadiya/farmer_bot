import requests
from RAW.models.tool import Tool, ToolParam
from src.utils.globals import globals
from datetime import datetime
from pathlib import Path
import re

import pandas as pd
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

def _parse_arrival_date(date_str: str):
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

def get_mandi_prices(commodity: str = "Wheat", state: str = "Gujarat", district: str = None, session_id=""):
    """Fetch LATEST mandi prices (2025/2026) for the given filters."""
    api_key = globals.data_gov_key
    resource_id = "35985678-0d79-46b4-9ed6-6f13308a1d24"
    url = f"https://api.data.gov.in/resource/{resource_id}"
    
    # Get current year
    current_year = datetime.now().year
    
    params = {
        "api-key": api_key,
        "format": "json",
        "filters[Commodity]": commodity,
        "filters[State]": state,
        "sort[Arrival_Date]": "desc",
        "limit": 10
    }
    
    if district:
        params["filters[District]"] = district

    try:
        print(
            f"[TOOL CALLED] session={session_id} tool=get_mandi_prices commodity={commodity} state={state} district={district}",
            flush=True
        )
        print(
            f"[API REQUEST] data.gov.in endpoint={url} commodity={commodity} state={state} district={district}",
            flush=True
        )
        res = requests.get(url, params=params, timeout=15)
        print(
            f"[API RESPONSE] data.gov.in status={res.status_code} commodity={commodity} state={state} district={district}",
            flush=True
        )
        if res.status_code == 200:
            records = res.json().get('records', [])
            
            # Filter for recent data manually if sort failed
            recent_year = str(current_year)
            previous_year = str(current_year - 1)
            recent_records = [
                r for r in records
                if recent_year in str(r.get("Arrival_Date")) or previous_year in str(r.get("Arrival_Date"))
            ]
            display_records = recent_records if recent_records else records
            
            if not display_records:
                # Fallback: fetch available commodities for same location so user can pick valid names
                fallback_params = {
                    "api-key": api_key,
                    "format": "json",
                    "filters[State]": state,
                    "sort[Arrival_Date]": "desc",
                    "limit": 100
                }
                if district:
                    fallback_params["filters[District]"] = district

                try:
                    fb_res = requests.get(url, params=fallback_params, timeout=15)
                    if fb_res.status_code == 200:
                        fb_records = fb_res.json().get("records", [])
                        available = sorted({
                            str(r.get("Commodity", "")).strip()
                            for r in fb_records
                            if str(r.get("Commodity", "")).strip()
                        })
                        if available:
                            top_items = available[:12]
                            commodity_lines = "\n".join([f"- {item.title()}" for item in top_items])
                            return (
                                f"'{commodity}' ka latest rate {state} {district if district else ''} me nahi mila.\n"
                                f"Available commodities:\n{commodity_lines}\n"
                                f"Inme se kis commodity ka rate dekhna hai?"
                            )
                except Exception:
                    pass

                return f"{commodity} ka latest rate {state} {district if district else ''} me abhi available nahi hai."
            
            result_str = f"Live Mandi Rate Update ({commodity} - {district if district else state}):\n"
            latest_available_date = None

            # Keep only the latest entry per market
            latest_by_market = {}
            for r in display_records:
                mandi = str(r.get("Market", "Mandi")).strip() or "Mandi"
                date_str = str(r.get("Arrival_Date", "")).strip()
                parsed_date = _parse_arrival_date(date_str)

                existing = latest_by_market.get(mandi)
                if existing is None:
                    latest_by_market[mandi] = (parsed_date, r)
                else:
                    existing_date, _ = existing
                    if parsed_date and (existing_date is None or parsed_date > existing_date):
                        latest_by_market[mandi] = (parsed_date, r)

            # Sort markets by latest date descending (unknown dates last)
            market_records = sorted(
                latest_by_market.items(),
                key=lambda x: (x[1][0] is not None, x[1][0]),
                reverse=True
            )

            for mandi, (parsed_date, r) in market_records:
                price_raw = str(r.get('Modal_Price', '0')).replace(",", "").strip()
                date = str(r.get('Arrival_Date', '')).strip()

                if parsed_date and (latest_available_date is None or parsed_date > latest_available_date):
                    latest_available_date = parsed_date

                try:
                    modal_price = float(price_raw)
                except ValueError:
                    modal_price = 0.0

                # data.gov modal price is per quintal (100 kg)
                price_per_20kg = modal_price / 5
                result_str += (
                    f"- {mandi}: ₹{int(modal_price)}/100kg, ₹{price_per_20kg:.0f}/20kg (1 mann) "
                    f"[Latest Date: {date}]\n"
                )

            today = datetime.now().date()
            if latest_available_date and latest_available_date < today:
                result_str += (
                    f"\nNote: Aaj ka data ({today.strftime('%d-%m-%Y')}) abhi publish nahi hua. "
                    f"Latest available update {latest_available_date.strftime('%d-%m-%Y')} ka hai."
                )
            print(
                f"[API DATA] data.gov.in records_total={len(records)} markets_used={len(market_records)} latest_year_filter={recent_year}/{previous_year}",
                flush=True
            )
            return result_str
        return f"Mandi API error {res.status_code}."
    except Exception as e:
        return f"Error: {e}"

mandi_tool = Tool(
    name="get_mandi_prices",
    description="Live Mandi rates (LATEST). Required: commodity, state.",
    parameters=[
        ToolParam(name="commodity", type="string", description="Crop name (e.g. Cotton)", required=True),
        ToolParam(name="state", type="string", description="State (e.g. Gujarat)", required=True),
        ToolParam(name="district", type="string", description="District", required=False)
    ],
    function=get_mandi_prices
)


def get_mandi_price_trend(
    commodity: str = "Wheat",
    state: str = "Gujarat",
    district: str = None,
    days_ahead: int = 7,
    session_id: str = "",
):
    """
    Predict mandi modal price trend using linear regression.
    Returns text summary + graph file path.
    """
    api_key = globals.data_gov_key
    resource_id = "35985678-0d79-46b4-9ed6-6f13308a1d24"
    url = f"https://api.data.gov.in/resource/{resource_id}"
    days_ahead = max(1, min(int(days_ahead or 7), 14))

    params = {
        "api-key": api_key,
        "format": "json",
        "filters[Commodity]": commodity,
        "filters[State]": state,
        # Pull latest rows first; asc was returning old (2004-era) data on this dataset.
        "sort[Arrival_Date]": "desc",
        "limit": 300,
    }
    if district:
        params["filters[District]"] = district

    try:
        print(
            f"[TOOL CALLED] session={session_id} tool=get_mandi_price_trend commodity={commodity} state={state} district={district} days={days_ahead}",
            flush=True,
        )
        print(
            f"[API REQUEST] data.gov.in endpoint={url} commodity={commodity} state={state} district={district} limit=300",
            flush=True,
        )
        res = requests.get(url, params=params, timeout=20)
        print(
            f"[API RESPONSE] data.gov.in status={res.status_code} commodity={commodity} state={state} district={district}",
            flush=True,
        )
        if res.status_code != 200:
            return f"Mandi trend API error {res.status_code}."

        rows = res.json().get("records", [])
        if not rows:
            return f"{commodity} ka trend data {state} {district or ''} me available nahi hai."

        data = []
        for r in rows:
            dt = _parse_arrival_date(str(r.get("Arrival_Date", "")).strip())
            price_raw = str(r.get("Modal_Price", "0")).replace(",", "").strip()
            try:
                price = float(price_raw)
            except ValueError:
                continue
            if dt is None or price <= 0:
                continue
            data.append({"date": pd.to_datetime(dt), "price": price})

        if len(data) < 5:
            return "Trend banane ke liye kam se kam 5 valid mandi points chahiye."

        df = pd.DataFrame(data).dropna()
        # Multiple markets same date -> daily average modal price
        daily_all = (
            df.groupby("date", as_index=False)["price"]
            .mean()
            .sort_values("date")
            .tail(90)
            .reset_index(drop=True)
        )
        if len(daily_all) < 5:
            return "Trend banane ke liye enough daily data points nahi mile."

        # Prefer current/near-current years. If API only has very old data, avoid fake "current" prediction.
        today = pd.Timestamp(datetime.now().date())
        min_recent_date = today - pd.Timedelta(days=730)  # last ~2 years
        daily_recent = daily_all[daily_all["date"] >= min_recent_date].reset_index(drop=True)
        use_recent = len(daily_recent) >= 5
        if not use_recent:
            latest_hist = daily_all["date"].max().strftime("%d-%m-%Y")
            return (
                f"{commodity} ({district or state}) ke liye current/recent mandi data (last 2 years) nahi mila. "
                f"Latest available date: {latest_hist}. "
                "Accurate next 7 days prediction ke liye recent records chahiye; "
                "filter change karo (commodity/state/district)."
            )
        daily = daily_recent

        daily["t"] = (daily["date"] - daily["date"].min()).dt.days.astype(int)
        model = LinearRegression()
        model.fit(daily[["t"]], daily["price"])

        # Future should be next N days from *today*, not from last historical record date.
        t_today = int((today - daily["date"].min()).days)
        if t_today < 0:
            t_today = int(daily["t"].iloc[-1])
        future_t = [t_today + i for i in range(1, days_ahead + 1)]
        pred = model.predict(pd.DataFrame({"t": future_t}))
        future_dates = [today + pd.Timedelta(days=i) for i in range(1, days_ahead + 1)]

        chart_dir = Path("reports/mandi_trends")
        chart_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", f"{commodity}_{state}_{district or 'all'}").strip("_")
        chart_path = chart_dir / f"{safe}_{stamp}.png"

        plt.figure(figsize=(10, 5))
        plt.plot(daily["date"], daily["price"], marker="o", label="Historical Avg Modal Price")
        plt.plot(future_dates, pred, marker="x", linestyle="--", label=f"Predicted ({days_ahead} days)")
        plt.title(f"Mandi Trend: {commodity} ({district or state})")
        plt.xlabel("Date")
        plt.ylabel("Price (INR / 100kg)")
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(chart_path, dpi=140)
        plt.close()

        forecast_lines = []
        for dt, p in zip(future_dates, pred):
            p = max(0.0, float(p))
            forecast_lines.append(f"- {dt.strftime('%d-%m-%Y')}: ₹{p:.0f}/100kg (₹{(p/5):.0f}/20kg)")

        slope = float(model.coef_[0]) if hasattr(model, "coef_") else 0.0
        trend_word = "upar" if slope > 0 else ("neeche" if slope < 0 else "stable")
        summary = (
            f"Mandi Trend Prediction ({commodity} - {district or state})\n"
            f"Last {len(daily)} daily points par ML (Linear Regression) run kiya.\n"
            f"Trend: {trend_word} ({slope:+.2f} Rs/day approx)\n\n"
            f"Agle {days_ahead} din ka estimate:\n" + "\n".join(forecast_lines) + "\n\n"
            f"GRAPH_FILE={chart_path}"
        )
        return summary
    except Exception as e:
        return f"Trend prediction error: {e}"


mandi_trend_tool = Tool(
    name="get_mandi_price_trend",
    description=(
        "Mandi rate trend predict kare (ML). Inputs: commodity, state, optional district, days_ahead."
    ),
    parameters=[
        ToolParam(name="commodity", type="string", description="Crop name (e.g. Wheat)", required=True),
        ToolParam(name="state", type="string", description="State (e.g. Gujarat)", required=True),
        ToolParam(name="district", type="string", description="District (optional)", required=False),
        ToolParam(name="days_ahead", type="number", description="Future days (1-14)", required=False),
    ],
    function=get_mandi_price_trend,
)
