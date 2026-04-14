import os
from dotenv import load_dotenv
from .logger import logger

load_dotenv(override=True)

class Globals:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.openweather_key = os.getenv("OPENWEATHER_KEY")
        self.telegram_token = os.getenv("TELEGRAM_TOKEN")
        self.data_gov_key = os.getenv("DATA_GOV_KEY")
        self.gemini_key = os.getenv("GEMINI_KEY")
        self.gmail_user = os.getenv("GMAIL_USER")
        self.gmail_pass = os.getenv("GMAIL_PASS")
        self.admin_alert_key = (os.getenv("ADMIN_ALERT_KEY") or "").strip()
        self.daily_alert_time = (os.getenv("DAILY_ALERT_TIME") or "08:00").strip()
        self.alert_default_state = (os.getenv("ALERT_DEFAULT_STATE") or "Gujarat").strip()
        _eda = (os.getenv("ENABLE_DAILY_ALERTS") or "").lower()
        self.enable_daily_alerts = _eda in ("1", "true", "yes", "on")

        # Default Models
        self.llm_model = "llama-3.3-70b-versatile"
        self.vision_model = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
        
        # Verify critical keys
        if not self.groq_api_key:
            logger.error("Missing GROQ_API_KEY in .env")
        if not self.telegram_token:
            logger.error("Missing TELEGRAM_TOKEN in .env")

# Singleton instance
globals = Globals()
