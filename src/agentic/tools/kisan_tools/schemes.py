import requests
import re
from datetime import datetime
from RAW.models.tool import Tool, ToolParam
from src.utils.globals import globals

def _extract_records(payload):
    """Extract list-of-dict records from variable API payload shapes."""
    if not isinstance(payload, dict):
        return []

    # Common key used by data.gov.in
    records = payload.get("records")
    if isinstance(records, list) and records and isinstance(records[0], dict):
        return records

    # Some datasets wrap in result/data keys
    for key in ("result", "data", "response"):
        node = payload.get(key)
        if isinstance(node, dict):
            rec = node.get("records")
            if isinstance(rec, list) and rec and isinstance(rec[0], dict):
                return rec

    # Generic fallback: pick largest list-of-dicts in payload
    candidate = []
    for value in payload.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            if len(value) > len(candidate):
                candidate = value
    return candidate

def _record_has_year(record, year: int) -> bool:
    token = str(year)
    blob = " ".join([str(v) for v in record.values()])
    return token in blob

def _extract_latest_year(records):
    years = set()
    for r in records:
        blob = " ".join([str(v) for v in r.values()])
        for y in re.findall(r"\b(20\d{2})\b", blob):
            years.add(int(y))
    return max(years) if years else None

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
        "limit": 50
    }
    
    try:
        print(f"[TOOL CALLED] session={session_id} tool=get_govt_schemes query={search_query}", flush=True)
        print(f"[API REQUEST] data.gov.in endpoint={url} query={search_query}", flush=True)
        res = requests.get(url, params=params, timeout=20)
        if res.status_code >= 500:
            # quick retry for transient gateway errors
            res = requests.get(url, params=params, timeout=20)
        print(f"[API RESPONSE] data.gov.in status={res.status_code} tool=get_govt_schemes", flush=True)
        if res.status_code == 200:
            data = res.json()
            records = _extract_records(data)
            if not records:
                api_hint = ""
                for key in ("message", "error", "status", "remarks"):
                    if key in data and str(data.get(key)).strip():
                        api_hint = str(data.get(key)).strip()
                        break
                if api_hint:
                    return (
                        "Maaf kijiye, live schemes API me records nahi mile. "
                        f"API message: {api_hint}"
                    )
                return (
                    "Maaf kijiye, live schemes API me records nahi mile. "
                    "Lagta hai selected resource_id par API data available nahi hai."
                )

            current_year = datetime.now().year
            current_year_records = [r for r in records if _record_has_year(r, current_year)]
            if not current_year_records:
                latest_year = _extract_latest_year(records)
                if latest_year:
                    return (
                        f"Maaf kijiye, {current_year} ki nayi schemes ka data abhi publish nahi hua. "
                        f"Live API me latest available year {latest_year} hai."
                    )
                return f"Maaf kijiye, {current_year} ki nayi schemes ka data abhi live API me available nahi hai."

            # Generic relevance scoring against whole record text
            query_terms = [t for t in re.split(r"\W+", str(search_query).lower()) if len(t) > 2]
            if query_terms:
                scored = []
                for r in current_year_records:
                    blob = " ".join([str(v) for v in r.values()]).lower()
                    score = sum(1 for t in query_terms if t in blob)
                    scored.append((score, r))
                scored.sort(key=lambda x: x[0], reverse=True)
                ranked_records = [r for _, r in scored]
            else:
                ranked_records = current_year_records

            def pick_field(record, keys, default=""):
                for k in keys:
                    val = record.get(k)
                    if val and str(val).strip():
                        return str(val).strip()
                return default

            output = f"Nayi Sarkari Yojnayein ({current_year}):\n"
            for r in ranked_records[:3]:
                title = pick_field(
                    r,
                    ["scheme_name", "title", "name", "scheme", "scheme_title"],
                    default="Scheme"
                )
                desc = pick_field(
                    r,
                    ["description", "details", "brief", "summary", "objective"],
                    default="Details portal par uplabdh hain."
                )
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
