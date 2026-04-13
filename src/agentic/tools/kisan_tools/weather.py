import requests
from datetime import datetime
from RAW.models.tool import Tool, ToolParam
from src.utils.globals import globals


def get_live_weather(city: str = "", session_id=""):
    """Tool to get live weather data with timestamp verification."""
    api_key = globals.openweather_key
    short_key = f"{api_key[:5]}...{api_key[-5:]}" if api_key else "None"
    
    url = "http://api.openweathermap.org/data/2.5/weather"
    city = (city or "").strip()
    if not city:
        return "Weather API Error: city name missing"
    # Country hint only (no hardcoded city list)
    q = f"{city},IN"

    params = {
        "q": q,
        "appid": api_key,
        "units": "metric",
        "lang": "en",
    }

    try:
        print(f"[TOOL CALLED] session={session_id} tool=get_live_weather city={city} q={q}", flush=True)
        print(f"[API REQUEST] OpenWeatherMap endpoint={url} city={city} key={short_key}", flush=True)
        res = requests.get(url, params=params, timeout=15)
        print(f"[API RESPONSE] OpenWeatherMap status={res.status_code} city={city}", flush=True)
        if res.status_code == 200:
            d = res.json()
            temp = d['main']['temp']
            desc = d['weather'][0]['description']
            humidity = d['main']['humidity']
            
            # Extract and convert timestamp to verify it's LIVE
            data_time = datetime.fromtimestamp(d['dt']).strftime('%H:%M:%S')
            
            result = (
                f"{city} ka weather: {temp}C, {desc}, humidity {humidity}%. "
                f"Data update time: {data_time}."
            )
            
            print(f"[API DATA] source=OpenWeatherMap city={city} temp={temp} humidity={humidity} updated_at={data_time}", flush=True)
            
            return result
        return f"Weather API Error: {res.status_code} for city {city}"
    except Exception as e:
        print(f"[TOOL ERROR] session={session_id} tool=get_live_weather error={e}", flush=True)
        return str(e)

weather_tool = Tool(
    name="get_live_weather",
    description="Live mausam check karne ke liye.",
    parameters=[
        ToolParam(name="city", type="string", description="Shehar ka naam", required=True)
    ],
    function=get_live_weather
)
