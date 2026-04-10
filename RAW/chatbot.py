import json
import re
from typing import List, Optional
from RAW.models.message import Message, Role
from RAW.models.tool import Tool
from src.utils.logger import logger as app_logger
from src.utils.database import get_connection

class ChatBot:
    def __init__(self, llm_instance, name: str = None, role: str = None, 
                 logger=None, system_prompt: str = "Assistant", tools: Optional[List[Tool]] = None):
        self.name = name
        self.role = role
        self.llm = llm_instance
        self.base_system_prompt = system_prompt
        self.messages: List[Message] = []
        self.tools: List[Tool] = tools if tools else []
        self.logger = logger or app_logger

    def save_to_db(self, session_id: str, role: str, content: str):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO conversation_history (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
            conn.commit()
            conn.close()
        except Exception: pass

    async def chat(self, user_input: str, session_id: str = "") -> str:
        try:
            self.save_to_db(session_id, "user", user_input)
            
            # --- CONTEXT ---
            get_tool = next((t for t in self.tools if t.name == "get_farmer_profile"), None)
            profile_context = get_tool.function(session_id=session_id) if get_tool else ""

            # --- INTENT ---
            intent_prompt = f"Identify: 'WEATHER_QUERY', 'MANDI_QUERY', 'SCHEME_QUERY', 'GENERAL_CHAT'. Request: '{user_input}'. Reply ONLY one word."
            intent = self.llm.chat([{"role": "user", "content": intent_prompt}]).strip().upper()

            # --- MANDI ---
            if "MANDI" in intent:
                extract_prompt = f"Extract JSON: '{user_input}'. Format: {{\"commodity\": \"Cotton\", \"state\": \"Gujarat\", \"district\": \"Rajkot\"}}."
                res_raw = self.llm.chat([{"role": "user", "content": extract_prompt}])
                json_match = re.search(r'\{.*\}', res_raw, re.DOTALL)
                data = json.loads(json_match.group()) if json_match else {"commodity": "Cotton", "state": "Gujarat"}

                mandi_tool = next((t for t in self.tools if t.name == "get_mandi_prices"), None)
                if mandi_tool:
                    print(f"[DEBUG] -> Searching {data.get('commodity')}...", flush=True)
                    tool_res = mandi_tool.function(commodity=data.get("commodity"), state=data.get("state"), district=data.get("district"), session_id=session_id)
                    
                    # FIXED PROMPT: Provide rates, not definitions!
                    final_res = self.llm.chat([
                        {"role": "system", "content": "Tell the mandi rates from the provided data in Hindi. Do not define words. Just give prices and markets."},
                        {"role": "user", "content": f"Mandi Data: {tool_res}"}
                    ])
                    self.save_to_db(session_id, "assistant", final_res)
                    return final_res

            # --- SCHEMES ---
            if "SCHEME" in intent:
                sc_tool = next((t for t in self.tools if t.name == "get_govt_schemes"), None)
                if sc_tool:
                    tool_res = sc_tool.function(session_id=session_id)
                    res = self.llm.chat([{"role": "system", "content": "List the schemes briefly in Hindi."}, {"role": "user", "content": tool_res}])
                    self.save_to_db(session_id, "assistant", res)
                    return res

            # --- GENERAL ---
            response = self.llm.chat([
                {"role": "system", "content": "You are KisanBot. Help farmer."},
                {"role": "user", "content": f"Context: {profile_context}\nQuestion: {user_input}"}
            ])
            self.save_to_db(session_id, "assistant", response)
            return response

        except Exception as e:
            return f"Error: {str(e)}"
