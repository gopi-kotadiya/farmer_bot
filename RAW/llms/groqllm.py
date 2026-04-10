import os
from groq import Groq

class GroqLLM:
    def __init__(self, api_key, model="llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model

    def chat(self, messages, temperature=0.1):
        """Standard chat interface for RAW LLMs."""
        response = self.client.chat.completions.create(
            messages=messages,
            model=self.model,
            temperature=temperature
        )
        return response.choices[0].message.content

    async def ainvoke(self, prompt):
        """LangChain-like async invoke if needed."""
        # For simplicity in this structure, we use the standard chat
        return self.chat([{"role": "user", "content": prompt}])
