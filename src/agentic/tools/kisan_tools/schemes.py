import requests
from RAW.models.tool import Tool, ToolParam
from src.utils.globals import globals

def get_govt_schemes(search_query: str = "Agriculture", session_id=""):
    """Tool to fetch government schemes from data.gov.in (Live API mode)."""
    api_key = globals.data_gov_key
    if not api_key:
        return "System error: Government Schemes API key missing."

    # Resource ID for Schemes (Example)
    # Note: In real setup, this would target a scheme-specific dataset
    resource_id = "507e174b-01ec-43c3-ae4c-0c1a8ce6d691" 
    
    url = f"https://api.data.gov.in/resource/{resource_id}"
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": 5
    }
    
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            data = res.json()
            records = data.get("records", [])
            if not records:
                return "Maaf kijiye, abhi koi nayi scheme nahi mil rahi jo is samay live ho."
            
            output = "Nayi Sarkari Yojnayein (Govt Schemes):\n"
            for r in records[:3]:
                title = r.get('scheme_name', 'Scheme')
                desc = r.get('description', 'Details available on portal.')
                output += f"- {title}: {desc}\n"
            return output
        return f"Schemes API Error: {res.status_code}"
    except Exception as e:
        return f"Connection error: {e}"

schemes_tool = Tool(
    name="get_govt_schemes",
    description="Nayi sarkari yojnaon (Government Schemes) ki jankari ke liye.",
    parameters=[
        ToolParam(name="search_query", type="string", description="Topic (e.g. Loan, Subsidy)", required=False)
    ],
    function=get_govt_schemes
)
