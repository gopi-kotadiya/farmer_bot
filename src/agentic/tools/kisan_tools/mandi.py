import requests
from RAW.models.tool import Tool, ToolParam
from src.utils.globals import globals
from datetime import datetime

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
