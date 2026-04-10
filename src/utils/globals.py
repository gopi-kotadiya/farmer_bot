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
        
        # Default Models
        self.llm_model = "llama-3.3-70b-versatile"
        
        # Verify critical keys
        if not self.groq_api_key:
            logger.error("Missing GROQ_API_KEY in .env")
        if not self.telegram_token:
            logger.error("Missing TELEGRAM_TOKEN in .env")

# Singleton instance
globals = Globals()
