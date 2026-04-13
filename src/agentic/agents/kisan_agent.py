from langchain_groq import ChatGroq
from src.utils.globals import globals
from src.utils.logger import logger
from src.agentic.tools.weather import get_weather
import uuid

class KisanAgent:
    def __init__(self):
        self.llm = ChatGroq(
            groq_api_key=globals.groq_api_key,
            model_name=globals.llm_model
        )

    async def process_query(self, query: str, session_id=None):
        if not session_id:
            session_id = uuid.uuid4().hex[:8]
            
        logger.info(f"User Message: {query}", session_id=session_id)
        
        try:
            # Simple Weather Check Logic (We can use full LangChain agents later)
            if any(word in query.lower() for word in ["weather", "mausam", "temperature", "taapman"]):
                city_prompt = (
                    f"Extract only the city name from: '{query}'. "
                    "If no city is mentioned, reply exactly: NONE"
                )
                city = (await self.llm.ainvoke(city_prompt)).content.strip()
                if not city or city.upper() == "NONE":
                    response = "Kaun se shehar ka mausam chahiye? City ka naam likho."
                else:
                    response = get_weather(city, session_id=session_id)
            else:
                ai_res = await self.llm.ainvoke(query)
                response = ai_res.content
            
            logger.info(f"Assistant: {response[:50]}...", session_id=session_id)
            return response, session_id
            
        except Exception as e:
            logger.error(f"Agent Error: {e}", session_id=session_id)
            return "Maaf kijiye, main abhi iska jawab nahi de pa raha hoon.", session_id

# Global instance
kisan_agent = KisanAgent()
