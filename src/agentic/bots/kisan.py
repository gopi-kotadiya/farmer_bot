from RAW.chatbot import ChatBot
from src.agentic.llms.primary import llm
from src.utils.logger import logger
from src.agentic.tools.kisan_tools.weather import weather_tool
from src.agentic.tools.kisan_tools.profile import profile_update_tool, profile_get_tool
from src.agentic.tools.kisan_tools.mandi import mandi_tool
from src.agentic.tools.kisan_tools.schemes import schemes_tool

def makeKisanBot():
    system_prompt = """You are KisanBot, a highly professional AI Assistant for Indian farmers.
    - You MUST use tools for live weather, mandi prices, and government schemes.
    - You remember farmer details (Name, Location, Crops) using profile tools.
    - Always respond in a polite, helpful manner in Hindi/Hinglish."""
    
    return ChatBot(
        name="kisan_bot",
        role="AgriExpert",
        llm_instance=llm,
        system_prompt=system_prompt,
        logger=logger,
        tools=[
            weather_tool, 
            profile_update_tool, 
            profile_get_tool, 
            mandi_tool, 
            schemes_tool
        ]
    )

# Singleton bot instance
kisan_bot = makeKisanBot()
