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

    def get_recent_history(self, session_id: str, limit: int = 8) -> str:
        if not session_id:
            return ""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content
                FROM conversation_history
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit)
            )
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return ""

            # Keep chronological order for prompt clarity
            rows = list(reversed(rows))
            history_lines = []
            for row in rows:
                role = row["role"] if "role" in row.keys() else row[0]
                content = row["content"] if "content" in row.keys() else row[1]
                history_lines.append(f"{role}: {content}")
            return "\n".join(history_lines)
        except Exception:
            return ""

    async def chat(self, user_input: str, session_id: str = "") -> str:
        try:
            user_input = (user_input or "").strip()
            if not user_input:
                return "Kuch likho: mausam, mandi bhav ya scheme — Roman Hindi me (Devanagari mat)."

            self.save_to_db(session_id, "user", user_input)
            
            # --- CONTEXT ---
            get_tool = next((t for t in self.tools if t.name == "get_farmer_profile"), None)
            profile_context = get_tool.function(session_id=session_id) if get_tool else ""
            recent_history = self.get_recent_history(session_id=session_id, limit=8)

            # --- INTENT ---
            intent_prompt = (
                "Classify the request into exactly one label:\n"
                "1) WEATHER_QUERY\n"
                "2) MANDI_QUERY\n"
                "3) SCHEME_QUERY\n"
                "4) FASAL_QUERY (crop schedule: sowing, irrigation, fertilizer, harvesting)\n"
                "5) PEST_QUERY (keeda, bimari, spray, disease treatment)\n"
                "6) SOIL_QUERY (mitti type, pH, soil nutrients, soil health)\n"
                "7) FARMING_TIPS_QUERY (general kheti tips, seasonal guidance, water saving, crop planning)\n"
                "8) RECALL_QUERY (when user asks about previous messages/context like 'maine kya pucha tha', 'kis city ka', 'mera naam kya hai')\n"
                "9) GENERAL_CHAT\n\n"
                f"Recent Session History:\n{recent_history}\n\n"
                f"Request: '{user_input}'\n"
                "Reply ONLY one label."
            )
            intent = self.llm.chat([{"role": "user", "content": intent_prompt}]).strip().upper()

            # --- RECALL ---
            if "RECALL" in intent:
                recall_res = self.llm.chat([
                    {
                        "role": "system",
                        "content": (
                            "Tum KisanBot ho. Sirf diye gaye recent session history aur profile context se jawab do. "
                            "Hinglish me Roman script use karo (Devanagari bilkul nahi). "
                            "Short jawab do (max 2 lines), greeting aur paragraph mat do."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Profile Context:\n{profile_context}\n\n"
                            f"Recent Session History:\n{recent_history}\n\n"
                            f"Question:\n{user_input}"
                        )
                    }
                ])
                self.save_to_db(session_id, "assistant", recall_res)
                return recall_res

            # --- WEATHER ---
            if "WEATHER" in intent:
                extract_prompt = (
                    f"Extract only the city name for weather from: '{user_input}'. "
                    "Use standard English spelling for place names. "
                    "If no city is mentioned, reply exactly: NONE"
                )
                city = self.llm.chat([{"role": "user", "content": extract_prompt}]).strip().replace('"', "")
                city = (city or "").strip()
                if not city or city.upper() == "NONE":
                    need_city = "Kaun se shehar ka mausam chahiye? City ka naam likho (Roman me)."
                    self.save_to_db(session_id, "assistant", need_city)
                    return need_city
                weather_tool = next((t for t in self.tools if t.name == "get_live_weather"), None)
                if weather_tool:
                    tool_res = weather_tool.function(city=city, session_id=session_id)
                    if (
                        "Weather API Error" in tool_res
                        or "Connection" in tool_res
                        or "timed out" in tool_res.lower()
                    ):
                        err_short = (
                            f"Weather nahi mila — city ka naam sahi spelling me likho ya dobara try karo. "
                            f"({tool_res})"
                        )
                        self.save_to_db(session_id, "assistant", err_short)
                        return err_short
                    final_res = self.llm.chat([
                        {"role": "system", "content": "Hinglish me Roman script me short answer do (max 2 lines). Devanagari letters, greeting aur paragraph mat do."},
                        {"role": "user", "content": f"Weather Data: {tool_res}"}
                    ])
                    self.save_to_db(session_id, "assistant", final_res)
                    return final_res

            # --- MANDI ---
            if "MANDI" in intent:
                extract_prompt = f"Extract JSON: '{user_input}'. Format: {{\"commodity\": \"Cotton\", \"state\": \"Gujarat\", \"district\": \"Rajkot\"}}."
                res_raw = self.llm.chat([{"role": "user", "content": extract_prompt}])
                json_match = re.search(r'\{.*\}', res_raw, re.DOTALL)
                data = json.loads(json_match.group()) if json_match else {"commodity": "Cotton", "state": "Gujarat"}

                mandi_tool = next((t for t in self.tools if t.name == "get_mandi_prices"), None)
                if mandi_tool:
                    print(
                        f"[TOOL INPUT] session={session_id} tool=get_mandi_prices commodity={data.get('commodity')} state={data.get('state')} district={data.get('district')}",
                        flush=True
                    )
                    tool_res = mandi_tool.function(commodity=data.get("commodity"), state=data.get("state"), district=data.get("district"), session_id=session_id)
                    # Return tool output directly so 100kg and 20kg values are always preserved
                    self.save_to_db(session_id, "assistant", tool_res)
                    return tool_res

            # --- SCHEMES ---
            if "SCHEME" in intent:
                sc_tool = next((t for t in self.tools if t.name == "get_govt_schemes"), None)
                if sc_tool:
                    print(f"[TOOL INPUT] session={session_id} tool=get_govt_schemes query={user_input}", flush=True)
                    tool_res = sc_tool.function(search_query=user_input, session_id=session_id)
                    self.save_to_db(session_id, "assistant", tool_res)
                    return tool_res

            # --- FASAL RAG ---
            if "FASAL" in intent:
                fasal_tool = next((t for t in self.tools if t.name == "get_fasal_advice"), None)
                if fasal_tool:
                    print(f"[TOOL INPUT] session={session_id} tool=get_fasal_advice query={user_input}", flush=True)
                    tool_res = fasal_tool.function(query=user_input, top_k=3, session_id=session_id)
                    print(
                        f"[RAG RETRIEVED] session={session_id} query={user_input}\n{tool_res}",
                        flush=True
                    )
                    if "Fasal Adviser (RAG result):" in tool_res:
                        final_res = self.llm.chat([
                            {
                                "role": "system",
                                "content": (
                                    "Tum KisanBot ho. Neeche diye gaye retrieved crop notes ko base banakar "
                                    "short, practical Hinglish (Roman script only) answer do. "
                                    "Steps/bullets me do, extra fluff mat do."
                                )
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"User question: {user_input}\n\n"
                                    f"Retrieved notes:\n{tool_res}"
                                )
                            }
                        ])
                        print(
                            f"[RAG FINAL] session={session_id} query={user_input}\nresponse={final_res}",
                            flush=True
                        )
                        self.save_to_db(session_id, "assistant", final_res)
                        return final_res
                    print(
                        f"[RAG FINAL] session={session_id} query={user_input}\nresponse={tool_res}",
                        flush=True
                    )
                    self.save_to_db(session_id, "assistant", tool_res)
                    return tool_res

            # --- PEST RAG ---
            if "PEST" in intent:
                pest_tool = next((t for t in self.tools if t.name == "get_pest_advice"), None)
                if pest_tool:
                    print(f"[TOOL INPUT] session={session_id} tool=get_pest_advice query={user_input}", flush=True)
                    tool_res = pest_tool.function(query=user_input, top_k=3, session_id=session_id)
                    print(f"[RAG RETRIEVED] session={session_id} domain=pest query={user_input}\n{tool_res}", flush=True)
                    if "Pest & Disease Adviser (RAG result):" in tool_res:
                        final_res = self.llm.chat([
                            {
                                "role": "system",
                                "content": (
                                    "Tum KisanBot ho. Sirf diye gaye retrieved pest/disease notes par based "
                                    "short, practical Hinglish (Roman script only) answer do. "
                                    "Agar context me direct jawab na ho to clearly bolo: "
                                    "'Is topic ka exact detail abhi knowledge base me nahi mila.' "
                                    "3-5 bullet points me jawab do, extra facts mat jodo."
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"User question: {user_input}\n\n"
                                    f"Retrieved notes:\n{tool_res}"
                                ),
                            },
                        ])
                        print(f"[RAG FINAL] session={session_id} domain=pest query={user_input}\nresponse={final_res}", flush=True)
                        self.save_to_db(session_id, "assistant", final_res)
                        return final_res
                    print(f"[RAG FINAL] session={session_id} domain=pest query={user_input}\nresponse={tool_res}", flush=True)
                    self.save_to_db(session_id, "assistant", tool_res)
                    return tool_res

            # --- SOIL RAG ---
            if "SOIL" in intent:
                soil_tool = next((t for t in self.tools if t.name == "get_soil_health_advice"), None)
                if soil_tool:
                    print(f"[TOOL INPUT] session={session_id} tool=get_soil_health_advice query={user_input}", flush=True)
                    tool_res = soil_tool.function(query=user_input, top_k=3, session_id=session_id)
                    print(f"[RAG RETRIEVED] session={session_id} domain=soil query={user_input}\n{tool_res}", flush=True)
                    if "Soil Health Adviser (RAG result):" in tool_res:
                        final_res = self.llm.chat([
                            {
                                "role": "system",
                                "content": (
                                    "Tum KisanBot ho. Sirf diye gaye soil-health retrieved notes par based "
                                    "short aur practical Hinglish (Roman script only) answer do. "
                                    "Agar exact detail context me na mile to clearly bolo. "
                                    "3-5 bullet points me structured answer do, extra facts add mat karo."
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"User question: {user_input}\n\n"
                                    f"Retrieved notes:\n{tool_res}"
                                ),
                            },
                        ])
                        print(f"[RAG FINAL] session={session_id} domain=soil query={user_input}\nresponse={final_res}", flush=True)
                        self.save_to_db(session_id, "assistant", final_res)
                        return final_res
                    print(f"[RAG FINAL] session={session_id} domain=soil query={user_input}\nresponse={tool_res}", flush=True)
                    self.save_to_db(session_id, "assistant", tool_res)
                    return tool_res

            # --- FARMING TIPS RAG ---
            if "FARMING_TIPS" in intent or "FARMING" in intent:
                tips_tool = next((t for t in self.tools if t.name == "get_farming_tips_advice"), None)
                if tips_tool:
                    print(f"[TOOL INPUT] session={session_id} tool=get_farming_tips_advice query={user_input}", flush=True)
                    tool_res = tips_tool.function(query=user_input, top_k=3, session_id=session_id)
                    print(f"[RAG RETRIEVED] session={session_id} domain=farming query={user_input}\n{tool_res}", flush=True)
                    if "Farming Tips Adviser (RAG result):" in tool_res:
                        final_res = self.llm.chat([
                            {
                                "role": "system",
                                "content": (
                                    "Tum KisanBot ho. Sirf diye gaye farming tips retrieved notes par based "
                                    "short, actionable Hinglish (Roman script only) answer do. "
                                    "3-6 bullet points do, unnecessary text mat do."
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"User question: {user_input}\n\n"
                                    f"Retrieved notes:\n{tool_res}"
                                ),
                            },
                        ])
                        print(f"[RAG FINAL] session={session_id} domain=farming query={user_input}\nresponse={final_res}", flush=True)
                        self.save_to_db(session_id, "assistant", final_res)
                        return final_res
                    print(f"[RAG FINAL] session={session_id} domain=farming query={user_input}\nresponse={tool_res}", flush=True)
                    self.save_to_db(session_id, "assistant", tool_res)
                    return tool_res

            # --- GENERAL ---
            response = self.llm.chat([
                {
                    "role": "system",
                    "content": (
                        "You are KisanBot. Help farmer in short Hinglish (Roman script only, no Devanagari). "
                        "Use past session history when user asks follow-up questions."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Profile Context:\n{profile_context}\n\n"
                        f"Recent Session History:\n{recent_history}\n\n"
                        f"Current Question:\n{user_input}"
                    )
                }
            ])
            self.save_to_db(session_id, "assistant", response)
            return response

        except Exception as e:
            return f"Error: {str(e)}"
