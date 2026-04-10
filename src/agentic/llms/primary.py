from RAW.llms.groqllm import GroqLLM
from src.utils.globals import globals

# Primary LLM for the project
llm = GroqLLM(api_key=globals.groq_api_key)
