import inspect
from typing import List, Optional
from RAW.models.tool import Tool
from RAW.models.message import Message, Role
from src.utils.logger import logger as app_logger

class Agent:
    def __init__(self, llm, name: str = "", system_prompt: str = "", tools: List[Tool] = [], logger=None):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.messages: List[Message] = [Message(role=Role.SYSTEM, content=self.system_prompt)]
        self.tools: List[Tool] = tools
        self.logger = logger or app_logger

    async def execute(self, message: str, session_id: str = "") -> str:
        self.messages.append(Message(role=Role.USER, content=message))
        self.logger.info(f"User Message: {message}", session_id=session_id)
        
        # In a real tool-using agent, we would loop here.
        # For now, we use the LLM to get a response.
        
        # Preparing messages for GroqLLM (converting dict format)
        formatted_msgs = [{"role": m.role.value, "content": m.content} for m in self.messages]
        
        try:
            # Check if LLM should call tools (stub for now, as we're building structure)
            response_content = self.llm.chat(formatted_msgs)
            
            res_msg = Message(role=Role.ASSISTANT, content=response_content)
            self.messages.append(res_msg)
            self.logger.info(f"Assistant: {response_content[:100]}...", session_id=session_id)
            return response_content
        except Exception as e:
            self.logger.error(f"Agent Execution Error: {e}", session_id=session_id)
            return "Maaf kijiye, kuch error aaya hai."
