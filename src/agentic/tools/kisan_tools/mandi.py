import requests
from RAW.models.tool import Tool, ToolParam
from src.utils.globals import globals
from datetime import datetime

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
        res = requests.get(url, params=params, timeout=15)
        if res.status_code == 200:
            records = res.json().get('records', [])
            
            # Filter for recent data manually if sort failed
            recent_records = [r for r in records if "2026" in str(r.get("Arrival_Date")) or "2025" in str(r.get("Arrival_Date"))]
            display_records = recent_records if recent_records else records
            
            if not display_records:
                return f"Maaf kijiye, {state} {district if district else ''} mein {commodity} ke taja bhav (2025-26) abhi update nahi huye hain."
            
            result_str = f"Live Mandi Rate Update ({commodity} - {district if district else state}):\n"
            for r in display_records[:3]:
                mandi = r.get('Market', 'Mandi')
                price = r.get('Modal_Price', '0')
                date = r.get('Arrival_Date', '')
                result_str += f"- {mandi}: ₹{price}/q [Taja Rate: {date}]\n"
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
