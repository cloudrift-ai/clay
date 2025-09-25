"""Generic LLM agent for task analysis and query answering."""

from typing import Optional

from ..llm import completion


class LLMAgent:
    """Generic LLM agent for various AI tasks."""

    def __init__(self):
        """Initialize the LLM agent."""
        pass

    async def think(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.5) -> str:
        """Think about and respond to a prompt."""
        messages = [
            {"role": "system", "content": system_prompt or "You are a helpful AI assistant."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(messages=messages, temperature=temperature)
        return response['choices'][0]['message']['content']