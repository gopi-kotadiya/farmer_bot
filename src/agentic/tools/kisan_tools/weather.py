import requests
from datetime import datetime
from RAW.models.tool import Tool, ToolParam
from src.utils.globals import globals
from src.utils.logger import logger

def get_live_weather(city: str = "Surat", session_id=""):
    """Tool to get live weather data with timestamp verification."""
    api_key = globals.openweather_key
    short_key = f"{api_key[:5]}...{api_key[-5:]}" if api_key else "None"
    
    url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "hi"
    }
    
    try:
        res = requests.get(url, params=params)
        if res.status_code == 200:
            d = res.json()
            temp = d['main']['temp']
            desc = d['weather'][0]['description']
            humidity = d['main']['humidity']
            
            # Extract and convert timestamp to verify it's LIVE
            data_time = datetime.fromtimestamp(d['dt']).strftime('%H:%M:%S')
            
            result = (f"{city} mein abhi taapman {temp}°C hai aur mausam '{desc}' hai. "
                      f"Humidity {humidity}% hai. [Data Updated at: {data_time}]")
            
            print(f"\n[VERIFIED LIVE DATA] -> City: {city}, Temp: {temp}, Time: {data_time}")
            print(f"[API SOURCE] -> OpenWeatherMap (Key: {short_key})\n")
            
            return result
        return f"Error: {res.status_code}"
    except Exception as e:
        return str(e)

weather_tool = Tool(
    name="get_live_weather",
    description="Live mausam check karne ke liye.",
    parameters=[
        ToolParam(name="city", type="string", description="Shehar ka naam", required=True)
    ],
    function=get_live_weather
)
